from __future__ import annotations

import time
from typing import Any, Protocol

from .dataset import Study


class Predictor(Protocol):
    def predict(self, study: Study) -> dict[str, Any]: ...


class ConstantBaselinePredictor:
    """Format-only baseline. It is not intended as a ranked submission model."""

    def predict(self, study: Study) -> dict[str, Any]:
        started = time.perf_counter()

        # Model inference will replace this block. Keep elapsed time real and positive.
        is_not_human_probability = 0.01
        is_stitched_probability = 0.01
        malignancy_score = 0.0

        elapsed_ms = max(1, round((time.perf_counter() - started) * 1000))
        return {
            "StudyUID": study.study_uid,
            "ProcessingTime_ms": elapsed_ms,
            "IsNotHumanBodyProb": is_not_human_probability,
            "IsStitchedProb": is_stitched_probability,
            "Prediction": {
                "HasMalignantLesion": False,
                "MalignancyScore": malignancy_score,
                "LesionCount": 0,
                "Lesions": [],
                "Interpretation": {
                    "Conclusion": "未检出恶性肺结节",
                    "ReportText": "格式基线结果，仅用于推理链路验证。",
                    "AttentionMap": [],
                },
            },
        }
