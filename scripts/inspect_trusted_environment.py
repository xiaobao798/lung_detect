#!/usr/bin/env python3
"""Create a privacy-conscious inventory inside the competition environment.

The script is read-only with respect to competition data. It never opens image,
annotation, or label files and never records patient/study/series directory names.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_PUBLIC_MODELS = Path("/2026aicompetition/public_models")
DEFAULT_TRAINING = Path("/2026aicompetition/datasets/training")
DEFAULT_OUTPUT = Path(
    "/2026aicompetition/workspace/common/lung-ai/trusted_environment_report.json"
)

PACKAGE_NAMES = (
    "torch",
    "torchvision",
    "monai",
    "nibabel",
    "numpy",
    "scipy",
    "scikit-image",
    "SimpleITK",
    "fastapi",
    "uvicorn",
)

SAFE_MODEL_SUFFIXES = {
    ".pt", ".pth", ".ckpt", ".onnx", ".engine", ".safetensors",
    ".json", ".yaml", ".yml", ".toml", ".py", ".txt", ".md",
}


def file_kind(path: Path) -> str:
    lower = path.name.lower()
    if lower.endswith(".nii.gz"):
        return ".nii.gz"
    if lower.endswith(".tar.gz"):
        return ".tar.gz"
    return path.suffix.lower() or "<no-extension>"


def count_tree(root: Path) -> dict[str, Any]:
    if not root.is_dir():
        return {"exists": False}
    file_types: Counter[str] = Counter()
    file_depths: Counter[int] = Counter()
    directory_depths: Counter[int] = Counter()
    total_files = total_directories = total_bytes = 0
    for current, directories, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        relative = current_path.relative_to(root)
        depth = 0 if str(relative) == "." else len(relative.parts)
        directory_depths[depth] += len(directories)
        total_directories += len(directories)
        for filename in files:
            path = current_path / filename
            total_files += 1
            file_types[file_kind(path)] += 1
            file_depths[depth + 1] += 1
            try:
                total_bytes += path.stat().st_size
            except OSError:
                pass
    return {
        "exists": True,
        "total_files": total_files,
        "total_directories": total_directories,
        "total_bytes": total_bytes,
        "file_types": dict(sorted(file_types.items())),
        "file_depth_histogram": {
            str(key): value for key, value in sorted(file_depths.items())
        },
        "directory_depth_histogram": {
            str(key): value for key, value in sorted(directory_depths.items())
        },
    }


def training_summary(root: Path) -> dict[str, Any]:
    summary = count_tree(root)
    if not summary.get("exists"):
        return summary
    annotation_root = root / "annotation"
    summary.update(
        {
            "annotation_directory_exists": annotation_root.is_dir(),
            "known_special_directories": {
                name: count_tree(annotation_root / name)
                for name in ("Composition", "fake", "duplicate")
            },
            "privacy_note": (
                "Directory and file names are omitted to avoid exporting patient, "
                "study, or series identifiers."
            ),
        }
    )
    return summary


def public_model_inventory(root: Path, limit: int) -> dict[str, Any]:
    if not root.is_dir():
        return {"exists": False, "files": []}
    files: list[dict[str, Any]] = []
    truncated = False
    for current, _, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        for filename in sorted(filenames):
            path = current_path / filename
            if path.suffix.lower() not in SAFE_MODEL_SUFFIXES:
                continue
            if len(files) >= limit:
                truncated = True
                break
            try:
                size = path.stat().st_size
            except OSError:
                size = None
            files.append(
                {
                    "relative_path": path.relative_to(root).as_posix(),
                    "size_bytes": size,
                }
            )
        if truncated:
            break
    return {
        "exists": True,
        "matching_file_count": len(files),
        "truncated": truncated,
        "files": files,
        "privacy_note": "Only the official public_models tree is named here.",
    }


def package_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for name in PACKAGE_NAMES:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def torch_summary() -> dict[str, Any]:
    try:
        import torch
    except Exception as error:
        return {"available": False, "error_type": type(error).__name__}
    cuda_available = bool(torch.cuda.is_available())
    devices = []
    if cuda_available:
        for index in range(torch.cuda.device_count()):
            properties = torch.cuda.get_device_properties(index)
            devices.append(
                {
                    "index": index,
                    "name": properties.name,
                    "total_memory_bytes": properties.total_memory,
                }
            )
    return {
        "available": True,
        "version": torch.__version__,
        "cuda_available": cuda_available,
        "torch_cuda_version": torch.version.cuda,
        "cudnn_version": torch.backends.cudnn.version(),
        "device_count": len(devices),
        "devices": devices,
    }


def nvidia_smi_summary() -> dict[str, Any]:
    executable = shutil.which("nvidia-smi")
    if executable is None:
        return {"available": False}
    command = [
        executable,
        "--query-gpu=name,driver_version,memory.total",
        "--format=csv,noheader,nounits",
    ]
    try:
        completed = subprocess.run(
            command, check=True, capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError) as error:
        return {"available": True, "error_type": type(error).__name__}
    devices = []
    for index, line in enumerate(completed.stdout.splitlines()):
        parts = [part.strip() for part in line.split(",")]
        if len(parts) == 3:
            devices.append(
                {
                    "index": index,
                    "name": parts[0],
                    "driver_version": parts[1],
                    "memory_total_mib": parts[2],
                }
            )
    return {"available": True, "devices": devices}


def build_report(public_models: Path, training: Path, limit: int) -> dict[str, Any]:
    return {
        "report_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "privacy": {
            "reads_file_contents": False,
            "includes_patient_or_study_names": False,
            "includes_environment_variables": False,
            "warning": (
                "Keep this report inside the trusted environment unless event rules "
                "allow selected sections to be shared."
            ),
        },
        "system": {
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "cpu_count": os.cpu_count(),
        },
        "packages": package_versions(),
        "torch": torch_summary(),
        "nvidia_smi": nvidia_smi_summary(),
        "public_models": public_model_inventory(public_models, limit),
        "training_data": training_summary(training),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a privacy-conscious trusted-environment report"
    )
    parser.add_argument("--public-models", type=Path, default=DEFAULT_PUBLIC_MODELS)
    parser.add_argument("--training", type=Path, default=DEFAULT_TRAINING)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-model-files", type=int, default=2000)
    args = parser.parse_args()
    if args.max_model_files <= 0:
        raise SystemExit("--max-model-files must be greater than zero")
    report = build_report(args.public_models, args.training, args.max_model_files)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    print(f"Report written to: {args.output}")
    print("Review event data-export rules before sharing any section.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
