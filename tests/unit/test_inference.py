from __future__ import annotations

from types import SimpleNamespace

import pytest
import torch

from app.services.inference import (
    InferenceError,
    _load_model_resource,
    infer_candidate_labels,
    load_local_model,
)


class FakeTokenizer:
    def __init__(self, maximum: int = 128) -> None:
        self.model_max_length = maximum
        self.calls: list[dict[str, object]] = []
        self.full_lengths: list[int] = []

    def __call__(
        self,
        premises: list[str],
        hypotheses: list[str],
        **options: object,
    ) -> dict[str, torch.Tensor]:
        self.calls.append(options)
        self.full_lengths = [
            len(premise.split()) + len(hypothesis.split()) + 3
            for premise, hypothesis in zip(premises, hypotheses, strict=True)
        ]
        width = max(self.full_lengths)
        return {
            "input_ids": torch.ones((len(premises), width), dtype=torch.long),
            "attention_mask": torch.ones((len(premises), width), dtype=torch.long),
        }


class FakeModel:
    def __init__(self, logits: object, maximum: int = 128) -> None:
        self.logits = logits
        self.config = SimpleNamespace(
            max_position_embeddings=maximum,
            label2id={"contradiction": 0, "neutral": 1, "entailment": 2},
        )
        self.calls = 0

    def __call__(self, **_inputs: torch.Tensor) -> SimpleNamespace:
        self.calls += 1
        return SimpleNamespace(logits=self.logits)


def test_competing_labels_are_scored_and_ranked_with_full_pairs() -> None:
    tokenizer = FakeTokenizer()
    model = FakeModel(
        torch.tensor(
            [
                [0.0, 0.1, 2.0],
                [0.2, 0.1, 0.0],
                [0.0, 0.2, 1.0],
            ]
        )
    )

    ranked = infer_candidate_labels(
        "A short document",
        ("sports", "technology", "news"),
        tokenizer=tokenizer,
        model=model,
    )

    assert [label for label, _score in ranked] == ["sports", "news", "technology"]
    assert sum(score for _label, score in ranked) == pytest.approx(1.0)
    assert all(torch.isfinite(torch.tensor(score)) for _label, score in ranked)
    assert tokenizer.calls[0]["truncation"] is False
    assert tokenizer.calls[0]["add_special_tokens"] is True
    assert max(tokenizer.full_lengths) <= 128


def test_tied_scores_keep_candidate_order() -> None:
    tokenizer = FakeTokenizer()
    model = FakeModel(torch.tensor([[0.0, 0.0, 1.0], [0.0, 0.0, 1.0]]))

    ranked = infer_candidate_labels(
        "Short text",
        ("first", "second"),
        tokenizer=tokenizer,
        model=model,
    )

    assert [label for label, _score in ranked] == ["first", "second"]
    assert ranked[0][1] == pytest.approx(ranked[1][1])


def test_rejects_pair_over_limit_without_calling_model() -> None:
    tokenizer = FakeTokenizer(maximum=8)
    model = FakeModel(torch.tensor([[0.0, 0.0, 1.0]]), maximum=8)

    with pytest.raises(InferenceError, match="(?i)shorten"):
        infer_candidate_labels(
            "a document with several words",
            ("a long candidate label", "other"),
            tokenizer=tokenizer,
            model=model,
        )

    assert model.calls == 0
    assert max(tokenizer.full_lengths) > 8


@pytest.mark.parametrize(
    "text,labels",
    [
        ("  \n", ("one", "two")),
        ("text", ("same", "same")),
        ("text", ("only-one",)),
    ],
)
def test_rejects_invalid_input_and_candidates(
    text: str, labels: tuple[str, ...]
) -> None:
    tokenizer = FakeTokenizer()
    model = FakeModel(torch.zeros((len(labels), 3)))

    with pytest.raises(InferenceError):
        infer_candidate_labels(text, labels, tokenizer=tokenizer, model=model)

    assert model.calls == 0


def test_rejects_unknown_model_input_bound() -> None:
    tokenizer = FakeTokenizer(maximum=10**30)
    model = FakeModel(torch.zeros((2, 3)), maximum=10**30)
    model.config.max_position_embeddings = None

    with pytest.raises(InferenceError, match="limit"):
        infer_candidate_labels("text", ("one", "two"), tokenizer=tokenizer, model=model)

    assert model.calls == 0


@pytest.mark.parametrize(
    "logits",
    [
        torch.zeros((1, 3)),
        torch.tensor([[0.0, 0.0, float("nan")], [0.0, 0.0, 1.0]]),
        [["not", "numeric", "scores"], ["not", "numeric", "scores"]],
    ],
)
def test_rejects_malformed_model_output(logits: object) -> None:
    tokenizer = FakeTokenizer()
    model = FakeModel(logits)

    with pytest.raises(InferenceError):
        infer_candidate_labels("text", ("one", "two"), tokenizer=tokenizer, model=model)


def test_resource_cache_is_keyed_by_model_identity_and_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.inference as inference

    inference.load_local_model.clear()
    loaded: list[tuple[str, str, str, str]] = []

    def fake_loader(
        model_path: str,
        model_id: str,
        revision: str,
        device: str,
    ) -> object:
        loaded.append((model_path, model_id, revision, device))
        return object()

    monkeypatch.setattr(inference, "_load_model_resource", fake_loader)
    first = load_local_model("models/a", "org/model", "a" * 40, "cpu")
    repeated = load_local_model("models/a", "org/model", "a" * 40, "cpu")
    changed_revision = load_local_model("models/a", "org/model", "b" * 40, "cpu")
    changed_runtime = load_local_model("models/a", "org/model", "a" * 40, "cuda")

    assert first is repeated
    assert changed_revision is not first
    assert changed_runtime is not first
    assert len(loaded) == 3
    inference.load_local_model.clear()


def test_model_loading_is_local_only_pytorch_without_remote_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.inference as inference

    calls: list[tuple[str, dict[str, object]]] = []

    class LoadableFakeModel(FakeModel):
        def to(self, device: str) -> LoadableFakeModel:
            calls.append(("device", {"device": device}))
            return self

        def eval(self) -> LoadableFakeModel:
            calls.append(("eval", {}))
            return self

    model = LoadableFakeModel(torch.zeros((2, 3)))

    def fake_tokenizer_loader(path, **options):
        calls.append(("tokenizer", {"path": path, **options}))
        return FakeTokenizer()

    def fake_model_loader(path, **options):
        calls.append(("model", {"path": path, **options}))
        return model

    monkeypatch.setattr(
        inference.AutoTokenizer, "from_pretrained", fake_tokenizer_loader
    )
    monkeypatch.setattr(
        inference.AutoModelForSequenceClassification,
        "from_pretrained",
        fake_model_loader,
    )

    resource = _load_model_resource("models/local", "org/model", "a" * 40, "cpu")

    assert resource.model is model
    for kind in ("tokenizer", "model"):
        options = next(options for entry, options in calls if entry == kind)
        assert options["local_files_only"] is True
        assert options["trust_remote_code"] is False
    assert ("device", {"device": "cpu"}) in calls
