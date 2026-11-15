from __future__ import annotations

import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol, cast

import streamlit as st
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

_HYPOTHESIS_TEMPLATE = "This example is {}."
_UNRELIABLE_LIMIT = 1_000_000


class InferenceError(RuntimeError):
    pass


class Tokenizer(Protocol):
    model_max_length: int

    def __call__(
        self,
        text: Sequence[str],
        text_pair: Sequence[str],
        *,
        add_special_tokens: bool,
        truncation: Literal[False],
        padding: Literal[True],
        return_tensors: Literal["pt"],
    ) -> Mapping[str, torch.Tensor]: ...


class ModelConfig(Protocol):
    label2id: Mapping[str, int]


class SequenceClassifier(Protocol):
    config: ModelConfig

    def __call__(self, **inputs: torch.Tensor) -> object: ...


class LoadableSequenceClassifier(SequenceClassifier, Protocol):
    def to(self, device: str) -> LoadableSequenceClassifier: ...

    def eval(self) -> LoadableSequenceClassifier: ...


@dataclass
class LocalModelResource:
    tokenizer: Tokenizer
    model: SequenceClassifier
    use_lock: threading.RLock = field(default_factory=threading.RLock)


def _load_model_resource(
    model_path: str,
    _model_id: str,
    _resolved_revision: str,
    device: str,
) -> LocalModelResource:
    path = Path(model_path)
    try:
        tokenizer_loader = cast(Callable[..., Tokenizer], AutoTokenizer.from_pretrained)
        model_loader = cast(
            Callable[..., LoadableSequenceClassifier],
            AutoModelForSequenceClassification.from_pretrained,
        )
        tokenizer = tokenizer_loader(
            path,
            local_files_only=True,
            trust_remote_code=False,
        )
        model = model_loader(
            path,
            local_files_only=True,
            trust_remote_code=False,
        )
        model.to(device)
        model.eval()
    except Exception:
        raise InferenceError(
            "The selected local model could not be loaded. Check its managed files."
        ) from None
    return LocalModelResource(
        tokenizer=tokenizer,
        model=cast(SequenceClassifier, model),
    )


@st.cache_resource(show_spinner=False)
def load_local_model(
    model_path: str,
    model_id: str,
    resolved_revision: str,
    device: str = "cpu",
) -> LocalModelResource:
    return _load_model_resource(model_path, model_id, resolved_revision, device)


def _input_limit(tokenizer: Tokenizer, model: SequenceClassifier) -> int:
    values: list[int] = []
    tokenizer_limit = getattr(tokenizer, "model_max_length", None)
    if isinstance(tokenizer_limit, int) and 0 < tokenizer_limit < _UNRELIABLE_LIMIT:
        values.append(tokenizer_limit)

    for name in ("max_position_embeddings", "n_positions", "max_sequence_length"):
        model_limit = getattr(model.config, name, None)
        if isinstance(model_limit, int) and 0 < model_limit < _UNRELIABLE_LIMIT:
            values.append(model_limit)

    if not values:
        raise InferenceError(
            "The selected model's single-request input limit cannot be determined. "
            "Choose a model with a reliable tokenizer and model limit."
        )
    return min(values)


def _entailment_index(model: SequenceClassifier) -> int:
    label_mapping = getattr(model.config, "label2id", None)
    if not isinstance(label_mapping, Mapping):
        raise InferenceError(
            "The selected model does not expose a supported entailment label."
        )
    matches = [
        index
        for label, index in label_mapping.items()
        if isinstance(label, str)
        and label.strip().casefold() == "entailment"
        and isinstance(index, int)
        and index >= 0
    ]
    if len(matches) != 1:
        raise InferenceError(
            "The selected model does not expose a supported entailment label."
        )
    return matches[0]


def infer_candidate_labels(
    text: str,
    candidate_labels: Sequence[str],
    *,
    tokenizer: Tokenizer,
    model: SequenceClassifier,
) -> tuple[tuple[str, float], ...]:
    if not isinstance(text, str) or not text.strip():
        raise InferenceError("Enter non-blank text before classifying.")
    if len(candidate_labels) < 2 or any(
        not isinstance(label, str) or not label.strip() for label in candidate_labels
    ):
        raise InferenceError("Select a valid label set with at least two labels.")
    if len(set(candidate_labels)) != len(candidate_labels):
        raise InferenceError("Candidate labels must be unique.")

    limit = _input_limit(tokenizer, model)
    premises = [text] * len(candidate_labels)
    hypotheses = [_HYPOTHESIS_TEMPLATE.format(label) for label in candidate_labels]
    try:
        encoded = tokenizer(
            premises,
            hypotheses,
            add_special_tokens=True,
            truncation=False,
            padding=True,
            return_tensors="pt",
        )
    except Exception:
        raise InferenceError(
            "The selected model could not tokenize this request. Check the text and "
            "model, then try again."
        ) from None

    input_ids = encoded.get("input_ids")
    if (
        not isinstance(input_ids, torch.Tensor)
        or input_ids.ndim != 2
        or input_ids.shape[0] != len(candidate_labels)
    ):
        raise InferenceError("The selected model returned malformed tokenized input.")
    if input_ids.shape[1] > limit:
        raise InferenceError(
            f"This text and its candidate-label prompts exceed the model's "
            f"{limit}-token single-request limit. Shorten the text and try again."
        )

    entailment_index = _entailment_index(model)
    try:
        with torch.inference_mode():
            output = model(**encoded)
        logits = getattr(output, "logits", None)
        if (
            not isinstance(logits, torch.Tensor)
            or logits.ndim != 2
            or logits.shape[0] != len(candidate_labels)
            or logits.shape[1] <= entailment_index
        ):
            raise InferenceError("The selected model returned malformed scores.")
        scores = torch.softmax(logits[:, entailment_index].float(), dim=0)
        if not bool(torch.isfinite(scores).all()):
            raise InferenceError("The selected model returned non-finite scores.")
        values = [float(value) for value in scores.detach().cpu().tolist()]
    except InferenceError:
        raise
    except Exception:
        raise InferenceError(
            "The selected model could not score this request. Check the model files "
            "and try again."
        ) from None

    if len(values) != len(candidate_labels) or any(
        not torch.isfinite(torch.tensor(value)).item() for value in values
    ):
        raise InferenceError("The selected model returned malformed scores.")

    ranked = sorted(
        zip(candidate_labels, values, strict=True),
        key=lambda item: -item[1],
    )
    return tuple((label, score) for label, score in ranked)


def infer_local_model(
    text: str,
    candidate_labels: tuple[str, ...],
    model_path: str,
    model_id: str,
    resolved_revision: str,
) -> tuple[tuple[str, float], ...]:
    resource = load_local_model(model_path, model_id, resolved_revision, "cpu")
    with resource.use_lock:
        return infer_candidate_labels(
            text,
            candidate_labels,
            tokenizer=resource.tokenizer,
            model=resource.model,
        )
