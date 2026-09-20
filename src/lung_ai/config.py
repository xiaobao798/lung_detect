from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _positive_int(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _positive_float(name: str, default: float) -> float:
    value = float(os.getenv(name, str(default)))
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


@dataclass(frozen=True)
class Config:
    host: str
    port: int
    answer_base: Path
    callback_url: str | None
    callback_pred_path_mode: str
    callback_attempts: int
    callback_timeout_seconds: float

    @classmethod
    def from_env(cls) -> "Config":
        mode = os.getenv("LUNG_AI_CALLBACK_PRED_PATH_MODE", "evaluation")
        if mode not in {"evaluation", "predicate"}:
            raise ValueError(
                "LUNG_AI_CALLBACK_PRED_PATH_MODE must be evaluation or predicate"
            )
        callback_url = os.getenv("LUNG_AI_CALLBACK_URL") or None
        return cls(
            host=os.getenv("LUNG_AI_HOST", "0.0.0.0"),
            port=_positive_int("LUNG_AI_PORT", 8000),
            answer_base=Path(
                os.getenv(
                    "LUNG_AI_ANSWER_BASE",
                    "/2026aicompetition/workspace/answer",
                )
            ),
            callback_url=callback_url,
            callback_pred_path_mode=mode,
            callback_attempts=_positive_int("LUNG_AI_CALLBACK_ATTEMPTS", 3),
            callback_timeout_seconds=_positive_float(
                "LUNG_AI_CALLBACK_TIMEOUT_SECONDS", 30.0
            ),
        )
