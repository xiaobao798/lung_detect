from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, order=True)
class Study:
    patient_id: str
    study_uid: str
    series_uids: tuple[str, ...]
    image_paths: tuple[Path, ...]


def _is_nifti(path: Path) -> bool:
    name = path.name.lower()
    return name.endswith(".nii") or name.endswith(".nii.gz")


def _is_source_image(path: Path) -> bool:
    if not _is_nifti(path):
        return False
    name = path.name.lower()
    return not (
        name.startswith("ai-肺结节检测;")
        or name.startswith("heatmap_")
    )


def discover_studies(dataset_path: Path) -> list[Study]:
    root = dataset_path.resolve()
    if not root.is_dir():
        raise ValueError(f"dataset_path is not a directory: {root}")

    grouped: dict[tuple[str, str], dict[str, list[Path]]] = {}
    for image_path in sorted(root.rglob("*")):
        if not image_path.is_file() or not _is_source_image(image_path):
            continue
        relative = image_path.relative_to(root)
        if len(relative.parts) < 4:
            raise ValueError(
                "expected dataset layout "
                "<patientid>/<studyid>/<seriesuid>/<image>.nii[.gz], got "
                f"{relative}"
            )
        patient_id, study_uid, series_uid = relative.parts[:3]
        grouped.setdefault((patient_id, study_uid), {}).setdefault(
            series_uid, []
        ).append(image_path)

    if not grouped:
        raise ValueError(f"no source NIfTI images found under {root}")

    studies: list[Study] = []
    seen_study_uids: set[str] = set()
    for (patient_id, study_uid), series in sorted(grouped.items()):
        if study_uid in seen_study_uids:
            raise ValueError(f"duplicate StudyUID across patients: {study_uid}")
        seen_study_uids.add(study_uid)
        studies.append(
            Study(
                patient_id=patient_id,
                study_uid=study_uid,
                series_uids=tuple(sorted(series)),
                image_paths=tuple(
                    path
                    for series_uid in sorted(series)
                    for path in sorted(series[series_uid])
                ),
            )
        )
    return studies
