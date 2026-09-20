from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any


DENSITY_KEYS = ("Solid", "PartSolid", "GroundGlass", "Calcified")
SIZE_KEYS = ("MicroNodule", "SmallNodule", "Nodule", "Mass")
PATHOLOGY_KEYS = (
    "Adenocarcinoma",
    "Squamous",
    "SmallCell",
    "LargeCell",
    "Other",
)
T_STAGING_KEYS = ("1", "2", "3", "4")
SIGN_KEYS = (
    "Lobulation",
    "Spiculation",
    "SpineSign",
    "PleuralTag",
    "VesselConvergence",
    "BronchialCutoff",
    "VacuoleSign",
    "Cavity",
    "LiquefactionNecrosis",
    "AirBronchogram",
    "HaloSign",
    "None",
)
LOCATION_KEYS = (
    "RightUpperLobe/Apical",
    "RightUpperLobe/Posterior",
    "RightUpperLobe/Anterior",
    "RightMiddleLobe/Lateral",
    "RightMiddleLobe/Medial",
    "RightLowerLobe/Superior",
    "RightLowerLobe/MedialBasal",
    "RightLowerLobe/AnteriorBasal",
    "RightLowerLobe/LateralBasal",
    "RightLowerLobe/PosteriorBasal",
    "LeftUpperLobe/Apicoposterior",
    "LeftUpperLobe/Anterior",
    "LeftUpperLobe/SuperiorLingular",
    "LeftUpperLobe/InferiorLingular",
    "LeftLowerLobe/Superior",
    "LeftLowerLobe/AnteromedialBasal",
    "LeftLowerLobe/LateralBasal",
    "LeftLowerLobe/PosteriorBasal",
    "Pleura",
)


class SchemaError(ValueError):
    pass


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SchemaError(f"{path} must be an object")
    return value


def _finite_number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SchemaError(f"{path} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise SchemaError(f"{path} must be finite")
    return number


def _probability(value: Any, path: str) -> float:
    number = _finite_number(value, path)
    if not 0.0 <= number <= 1.0:
        raise SchemaError(f"{path} must be in [0, 1]")
    return number


def _score_100(value: Any, path: str) -> float:
    number = _finite_number(value, path)
    if not 0.0 <= number <= 100.0:
        raise SchemaError(f"{path} must be in [0, 100]")
    return number


def _text(value: Any, path: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise SchemaError(f"{path} must be a non-empty string")
    return value


def _probability_distribution(
    value: Any, keys: Sequence[str], path: str
) -> Mapping[str, Any]:
    probabilities = _mapping(value, path)
    if set(probabilities) != set(keys):
        raise SchemaError(f"{path} must contain exactly: {', '.join(keys)}")
    total = sum(
        _probability(probabilities[key], f"{path}.{key}") for key in keys
    )
    if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-6):
        raise SchemaError(f"{path} probabilities must sum to 1, got {total}")
    return probabilities


def _classification(value: Any, keys: Sequence[str], path: str) -> None:
    obj = _mapping(value, path)
    predicted = _text(obj.get("predicted"), f"{path}.predicted")
    if predicted not in keys:
        raise SchemaError(f"{path}.predicted has an unknown value: {predicted}")
    _probability_distribution(obj.get("probabilities"), keys, f"{path}.probabilities")


def _validate_lesion(value: Any, index: int) -> None:
    path = f"Prediction.Lesions[{index}]"
    lesion = _mapping(value, path)
    _text(lesion.get("LesionID"), f"{path}.LesionID")
    _text(lesion.get("SeriesInstanceUID"), f"{path}.SeriesInstanceUID")
    _score_100(lesion.get("MalignancyScore"), f"{path}.MalignancyScore")

    if "BoundingBox" in lesion:
        box = lesion["BoundingBox"]
        if (
            not isinstance(box, list)
            or len(box) != 6
            or any(isinstance(item, bool) or not isinstance(item, int) for item in box)
        ):
            raise SchemaError(f"{path}.BoundingBox must contain six integers")

    _classification(lesion.get("NoduleDensity"), DENSITY_KEYS, f"{path}.NoduleDensity")
    _classification(
        lesion.get("NoduleLocation"), LOCATION_KEYS, f"{path}.NoduleLocation"
    )
    _classification(lesion.get("NoduleSize"), SIZE_KEYS, f"{path}.NoduleSize")
    size = _mapping(lesion["NoduleSize"], f"{path}.NoduleSize")
    if _finite_number(
        size.get("meanDiameter_mm"), f"{path}.NoduleSize.meanDiameter_mm"
    ) <= 0:
        raise SchemaError(f"{path}.NoduleSize.meanDiameter_mm must be greater than 0")

    signs = _mapping(lesion.get("AssociatedSigns"), f"{path}.AssociatedSigns")
    if set(signs) != set(SIGN_KEYS):
        raise SchemaError(f"{path}.AssociatedSigns must contain all 12 keys")
    for key in SIGN_KEYS:
        _probability(signs[key], f"{path}.AssociatedSigns.{key}")

    has_pathology = "PathologyType" in lesion
    has_staging = "T_Staging" in lesion
    if has_pathology != has_staging:
        raise SchemaError(f"{path} must provide PathologyType and T_Staging together")
    if has_pathology:
        _classification(
            lesion["PathologyType"], PATHOLOGY_KEYS, f"{path}.PathologyType"
        )
        staging = _mapping(lesion["T_Staging"], f"{path}.T_Staging")
        staging_value = _text(staging.get("value"), f"{path}.T_Staging.value")
        if staging_value not in T_STAGING_KEYS:
            raise SchemaError(f"{path}.T_Staging.value must be 1, 2, 3 or 4")
        _probability_distribution(
            staging.get("confidence"), T_STAGING_KEYS, f"{path}.T_Staging.confidence"
        )

    key_points = lesion.get("KeyPoints")
    if not isinstance(key_points, list) or not key_points:
        raise SchemaError(f"{path}.KeyPoints must be a non-empty list")
    for point_index, point_value in enumerate(key_points):
        point_path = f"{path}.KeyPoints[{point_index}]"
        point = _mapping(point_value, point_path)
        if point.get("type") != "NoduleCenter":
            raise SchemaError(f"{point_path}.type must be NoduleCenter")
        coord = point.get("coord")
        if not isinstance(coord, list) or len(coord) != 3:
            raise SchemaError(f"{point_path}.coord must contain three mm coordinates")
        for axis, number in enumerate(coord):
            _finite_number(number, f"{point_path}.coord[{axis}]")
        _probability(point.get("confidence"), f"{point_path}.confidence")


def validate_prediction_document(
    document: Any, expected_study_uid: str | None = None
) -> None:
    root = _mapping(document, "root")
    study_uid = _text(root.get("StudyUID"), "StudyUID")
    if expected_study_uid is not None and study_uid != expected_study_uid:
        raise SchemaError(
            f"StudyUID {study_uid!r} does not match expected {expected_study_uid!r}"
        )
    processing_time = root.get("ProcessingTime_ms")
    if (
        isinstance(processing_time, bool)
        or not isinstance(processing_time, int)
        or processing_time <= 0
    ):
        raise SchemaError("ProcessingTime_ms must be a positive integer")
    _probability(root.get("IsNotHumanBodyProb"), "IsNotHumanBodyProb")
    _probability(root.get("IsStitchedProb"), "IsStitchedProb")

    prediction = _mapping(root.get("Prediction"), "Prediction")
    if not isinstance(prediction.get("HasMalignantLesion"), bool):
        raise SchemaError("Prediction.HasMalignantLesion must be a boolean")
    _score_100(prediction.get("MalignancyScore"), "Prediction.MalignancyScore")
    lesion_count = prediction.get("LesionCount")
    if isinstance(lesion_count, bool) or not isinstance(lesion_count, int) or lesion_count < 0:
        raise SchemaError("Prediction.LesionCount must be a non-negative integer")
    lesions = prediction.get("Lesions")
    if not isinstance(lesions, list):
        raise SchemaError("Prediction.Lesions must be a list")
    if lesion_count != len(lesions):
        raise SchemaError("Prediction.LesionCount must equal len(Prediction.Lesions)")
    for index, lesion in enumerate(lesions):
        _validate_lesion(lesion, index)

    interpretation = _mapping(prediction.get("Interpretation"), "Prediction.Interpretation")
    _text(interpretation.get("Conclusion"), "Prediction.Interpretation.Conclusion")
    _text(
        interpretation.get("ReportText"),
        "Prediction.Interpretation.ReportText",
        allow_empty=True,
    )
    attention_map = interpretation.get("AttentionMap")
    if not isinstance(attention_map, list) or any(
        not isinstance(item, str) for item in attention_map
    ):
        raise SchemaError("Prediction.Interpretation.AttentionMap must be a list of paths")


def validate_duplicate_record(
    record: Any, allowed_study_uids: set[str]
) -> None:
    obj = _mapping(record, "duplicate record")
    if set(obj) != {"StudyUID", "StudyUID_dup", "PairProb"}:
        raise SchemaError("duplicate record has unexpected fields")
    first = _text(obj["StudyUID"], "StudyUID")
    second = _text(obj["StudyUID_dup"], "StudyUID_dup")
    if first not in allowed_study_uids or second not in allowed_study_uids:
        raise SchemaError("duplicate record UID does not belong to this test set")
    if first == second:
        raise SchemaError("duplicate record must contain two different studies")
    _probability(obj["PairProb"], "PairProb")
