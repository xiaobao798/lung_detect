from __future__ import annotations

from typing import Any

from .dataset import Study


def baseline_duplicate_pairs(studies: list[Study]) -> list[dict[str, Any]]:
    """Return valid sparse pairs for format testing, not for competitive scoring."""

    ordered = sorted(studies, key=lambda item: item.study_uid)
    if len(ordered) < 2:
        raise ValueError(
            "duplicate_pairs.jsonl requires at least two different studies; "
            "the official single-study behavior must be clarified"
        )
    return [
        {
            "StudyUID": first.study_uid,
            "StudyUID_dup": second.study_uid,
            "PairProb": 0.0,
        }
        for first, second in zip(ordered, ordered[1:])
    ]
