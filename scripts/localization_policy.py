"""Shared review-state policy for localized product content."""


EDITORIALLY_REVIEWED = "editorially-reviewed"
MACHINE_GENERATED_UNREVIEWED = "machine-generated-unreviewed"


def is_product_editorially_reviewed(entry):
    """Only an explicit editorial marker counts as human review evidence."""
    if not isinstance(entry, dict):
        return False
    return (
        entry.get("_review_status") == EDITORIALLY_REVIEWED
        or entry.get("_reviewed") is True
    )


def should_regenerate_product(entry, source_hash):
    """Regenerate changed machine output, but never overwrite reviewed copy."""
    if not isinstance(entry, dict):
        return True
    if entry.get("_source_hash") == source_hash:
        return False
    return not is_product_editorially_reviewed(entry)


def product_review_status(entry):
    if is_product_editorially_reviewed(entry):
        return EDITORIALLY_REVIEWED
    if isinstance(entry, dict) and entry:
        return MACHINE_GENERATED_UNREVIEWED
    return "missing"
