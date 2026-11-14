import streamlit as st

from app.config.label_settings import LabelSettingsError
from app.services.label_manager import LabelManager, LabelManagerError


def _save_draft() -> None:
    st.session_state["label_draft_name"] = st.session_state["label_name"]
    if not st.session_state["label_individual_mode"]:
        st.session_state["label_draft_values"] = st.session_state["label_values"]


def _clear_label_widgets() -> None:
    for key in list(st.session_state):
        if isinstance(key, str) and key.startswith("label_item_"):
            del st.session_state[key]


def _clear_removal_confirmations() -> None:
    for key in list(st.session_state):
        if isinstance(key, str) and key.startswith("label_confirm_"):
            del st.session_state[key]


def _save_label(index: int) -> None:
    labels = list(st.session_state["label_draft_labels"])
    labels[index] = st.session_state[f"label_item_{index}"]
    st.session_state["label_draft_labels"] = labels


def _add_label() -> None:
    st.session_state["label_draft_labels"] = [
        *st.session_state["label_draft_labels"],
        "",
    ]


def _remove_label(index: int) -> None:
    labels = list(st.session_state["label_draft_labels"])
    labels.pop(index)
    st.session_state["label_draft_labels"] = labels
    _clear_label_widgets()


def _render_labels(*, allow_structure_changes: bool) -> list[str]:
    state = st.session_state
    if not state["label_individual_mode"]:
        values = st.text_area(
            "Labels (one per line)",
            key="label_values",
            help="Enter at least two labels.",
            on_change=_save_draft,
        )
        return values.split("\n")

    for index, value in enumerate(state["label_draft_labels"]):
        key = f"label_item_{index}"
        state.setdefault(key, value)
        st.text_area(
            f"Label {index + 1}", key=key, on_change=_save_label, args=(index,)
        )
        if allow_structure_changes:
            st.button(
                f"Remove label {index + 1}",
                key=f"label_remove_item_{index}",
                on_click=_remove_label,
                args=(index,),
            )
    if allow_structure_changes:
        st.button("Add label", on_click=_add_label)
    return list(state["label_draft_labels"])


def render_label_management() -> None:
    st.title("Candidate-Label Management")
    st.warning(
        "Manage labels only in local or otherwise trusted environments. "
        "Hiding this page is not authentication or access control."
    )
    state = st.session_state
    state.setdefault("label_draft_name", "")
    state.setdefault("label_draft_values", "")
    state.setdefault("label_draft_labels", [])
    state.setdefault("label_individual_mode", False)
    state.setdefault("label_name", state["label_draft_name"])
    state.setdefault("label_values", state["label_draft_values"])
    state.setdefault("label_id", None)
    state.setdefault("label_revision", None)
    state.setdefault("label_opened_name", "")
    state.setdefault("label_inspection_required", False)
    try:
        manager = LabelManager()
        snapshot = manager.list_sets()
    except (LabelManagerError, LabelSettingsError) as error:
        st.error(str(error))
        if (
            state["label_draft_name"]
            or state["label_draft_values"]
            or any(state["label_draft_labels"])
        ):
            st.info("Your draft is retained. Repair the configuration before saving.")
            st.text_input("Set name", key="label_name", on_change=_save_draft)
            _render_labels(allow_structure_changes=False)
        return
    if "label_notice" in state:
        st.success(state.pop("label_notice"))
    if snapshot.warning:
        st.warning(snapshot.warning)
    selected = None
    if not snapshot.sets:
        st.info(
            "No label sets are available. Enter a name and two labels to create one."
        )
    else:
        st.subheader("Saved sets")
        for item in snapshot.sets:
            st.text(f"Set: {item.name}")
            for index, label in enumerate(item.labels, 1):
                st.text(f"Label {index}: {label}")
        by_id = {item.id: item for item in snapshot.sets}
        selected = st.selectbox(
            "Choose a saved set",
            list(by_id),
            format_func=lambda key: by_id[key].name,
            on_change=_clear_removal_confirmations,
        )
        if st.button("Open selected set"):
            item = by_id[selected]
            state["label_id"] = item.id
            state["label_revision"] = item.revision
            state["label_opened_name"] = item.name
            state["label_name"] = item.name
            state["label_values"] = "\n".join(item.labels)
            state["label_draft_values"] = state["label_values"]
            state["label_draft_labels"] = list(item.labels)
            state["label_individual_mode"] = any(
                "\n" in label or "\r" in label for label in item.labels
            )
            _clear_label_widgets()
            _save_draft()
        if st.button("Refresh selected revision while keeping draft"):
            item = by_id[selected]
            if state["label_id"] == item.id:
                state["label_revision"] = item.revision
                st.info("Latest revision selected; your draft is unchanged.")
            else:
                st.info("Open this set before refreshing its revision.")

    if st.button("Start a new set"):
        state["label_id"] = None
        state["label_revision"] = None
        state["label_opened_name"] = ""
        state["label_name"] = ""
        state["label_values"] = ""
        state["label_draft_labels"] = []
        state["label_individual_mode"] = False
        _clear_label_widgets()
        _save_draft()

    if state["label_inspection_required"]:
        st.warning(
            "The previous outcome is uncertain. Inspect the saved sets above "
            "before allowing another change."
        )
        if st.button("I inspected the saved sets"):
            state["label_inspection_required"] = False

    opened_set_missing = state["label_id"] is not None and all(
        item.id != state["label_id"] for item in snapshot.sets
    )
    if opened_set_missing:
        st.warning(
            "The opened set was removed. Saved sets have been refreshed and your "
            "draft is retained. Use it as a new set or copy it before opening "
            "another set."
        )
        if st.button("Use draft as a new set"):
            state["label_id"] = None
            state["label_revision"] = None
            state["label_opened_name"] = ""
            st.rerun()

    selection_conflicts = (
        state["label_id"] is not None
        and selected is not None
        and selected != state["label_id"]
    )
    if state["label_id"] is not None:
        st.text(f"Opened saved set: {state['label_opened_name']}")
        if selection_conflicts and not opened_set_missing:
            st.info(
                "Open the selected set or reselect the opened set before saving "
                "or removing."
            )

    st.subheader("Edit draft" if state["label_id"] else "New set")
    name = st.text_input("Set name", key="label_name", on_change=_save_draft)
    if not state["label_individual_mode"] and st.button("Edit labels individually"):
        state["label_draft_labels"] = state["label_draft_values"].split("\n")
        state["label_individual_mode"] = True
        _clear_label_widgets()
    labels = _render_labels(allow_structure_changes=True)
    disabled = bool(state["label_inspection_required"])
    save_disabled = disabled or selection_conflicts
    if (
        st.button("Save set", key="label_save", disabled=save_disabled)
        and not save_disabled
    ):
        try:
            if state["label_id"] is None:
                saved = manager.create(name, labels)
            else:
                saved = manager.update(
                    state["label_id"], state["label_revision"], name, labels
                )
            state["label_id"] = saved.id
            state["label_revision"] = saved.revision
            state["label_opened_name"] = saved.name
            state["label_notice"] = "Set saved."
            st.rerun()
        except LabelManagerError as error:
            if error.kind == "indeterminate":
                state["label_inspection_required"] = True
            st.error(str(error))

    if state["label_id"] is not None:
        confirm = st.checkbox(
            "Confirm removal of the opened set",
            key=f"label_confirm_{state['label_id']}_{state['label_revision']}",
            disabled=selection_conflicts,
        )
        if (
            st.button(
                "Remove opened set",
                disabled=not confirm or disabled or selection_conflicts,
            )
            and confirm
            and not disabled
            and not selection_conflicts
        ):
            try:
                manager.remove(
                    state["label_id"], state["label_revision"], confirmed=True
                )
                state["label_id"] = None
                state["label_revision"] = None
                state["label_opened_name"] = ""
                state["label_notice"] = "Set removed."
                st.rerun()
            except LabelManagerError as error:
                if error.kind == "indeterminate":
                    state["label_inspection_required"] = True
                st.error(str(error))


render_label_management()
