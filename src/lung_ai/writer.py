from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from .dataset import Study
from .schemas import (
    SchemaError,
    validate_duplicate_record,
    validate_prediction_document,
)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    if not records:
        raise SchemaError("duplicate_pairs.jsonl must contain at least one record")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(
                json.dumps(record, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            )
            handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def validate_result_set(predicate_path: Path, studies: list[Study]) -> None:
    allowed_uids = {study.study_uid for study in studies}
    expected_prediction_paths: set[Path] = set()
    for study in studies:
        path = predicate_path / study.patient_id / study.study_uid / "prediction.json"
        expected_prediction_paths.add(path)
        if not path.is_file():
            raise SchemaError(f"missing prediction file: {path}")
        with path.open("r", encoding="utf-8") as handle:
            validate_prediction_document(json.load(handle), study.study_uid)

    actual_prediction_paths = set(predicate_path.rglob("prediction.json"))
    if actual_prediction_paths != expected_prediction_paths:
        raise SchemaError("prediction file set does not exactly match input studies")

    duplicate_path = predicate_path / "duplicate_pairs.jsonl"
    if not duplicate_path.is_file():
        raise SchemaError("missing duplicate_pairs.jsonl")
    seen_count: dict[str, int] = {uid: 0 for uid in allowed_uids}
    line_count = 0
    with duplicate_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                raise SchemaError(f"blank JSONL line at {line_number}")
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise SchemaError(f"invalid JSONL at line {line_number}: {error}") from error
            validate_duplicate_record(record, allowed_uids)
            seen_count[record["StudyUID"]] += 1
            seen_count[record["StudyUID_dup"]] += 1
            line_count += 1
    if line_count == 0:
        raise SchemaError("duplicate_pairs.jsonl must contain at least one record")
    if any(count > 200 for count in seen_count.values()):
        raise SchemaError("a study appears in more than 200 duplicate candidate pairs")


def write_result_set(
    answer_base: Path,
    evaluation_id: str,
    studies: list[Study],
    predictions: list[dict[str, Any]],
    duplicate_pairs: list[dict[str, Any]],
) -> Path:
    if not evaluation_id or any(char in evaluation_id for char in ("/", "\\", "..")):
        raise ValueError("evaluation_id contains unsafe path characters")
    if len(predictions) != len(studies):
        raise ValueError("prediction count must match study count")

    evaluation_path = answer_base / evaluation_id
    predicate_path = evaluation_path / "predicate"
    if predicate_path.exists():
        validate_result_set(predicate_path, studies)
        return predicate_path

    evaluation_path.mkdir(parents=True, exist_ok=True)
    staging_path = evaluation_path / f".predicate-{uuid.uuid4().hex}.tmp"
    staging_path.mkdir()
    try:
        study_by_uid = {study.study_uid: study for study in studies}
        for prediction in predictions:
            study_uid = prediction.get("StudyUID")
            study = study_by_uid.get(study_uid)
            if study is None:
                raise SchemaError(f"prediction has unknown StudyUID: {study_uid!r}")
            validate_prediction_document(prediction, study_uid)
            _write_json(
                staging_path / study.patient_id / study.study_uid / "prediction.json",
                prediction,
            )

        for record in duplicate_pairs:
            validate_duplicate_record(record, set(study_by_uid))
        _write_jsonl(staging_path / "duplicate_pairs.jsonl", duplicate_pairs)
        validate_result_set(staging_path, studies)
        os.replace(staging_path, predicate_path)
    except Exception:
        # Staging cleanup is deliberately left to the deployment housekeeping step.
        # Keeping it here aids diagnosis and never contaminates the final predicate path.
        raise
    return predicate_path
