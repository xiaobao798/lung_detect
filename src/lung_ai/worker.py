from __future__ import annotations

import queue
import threading
import time
import traceback
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .callback import notify_completion
from .config import Config
from .dataset import discover_studies
from .duplicate import baseline_duplicate_pairs
from .predictor import ConstantBaselinePredictor, Predictor
from .writer import write_result_set


@dataclass(frozen=True)
class InferenceTask:
    request_id: str
    evaluation_id: str
    dataset_path: Path


@dataclass
class JobState:
    request_id: str
    evaluation_id: str
    status: str
    detail: str = ""


class TaskManager:
    def __init__(self, config: Config, predictor: Predictor | None = None) -> None:
        self._config = config
        self._predictor = predictor or ConstantBaselinePredictor()
        self._queue: queue.Queue[InferenceTask] = queue.Queue()
        self._states: dict[str, JobState] = {}
        self._lock = threading.Lock()
        self._changed = threading.Condition(self._lock)
        self._thread = threading.Thread(target=self._run, daemon=True, name="inference-worker")
        self._thread.start()

    def submit(
        self, request_id: str, evaluation_id: str, dataset_path: str
    ) -> dict[str, Any]:
        if not request_id.strip() or not evaluation_id.strip():
            raise ValueError("request_id and evaluation_id must be non-empty strings")
        path = Path(dataset_path).resolve()
        if not path.is_dir():
            raise ValueError(f"dataset_path is not a directory: {path}")
        with self._changed:
            existing = self._states.get(evaluation_id)
            if existing is not None:
                if existing.request_id != request_id:
                    raise ValueError("evaluation_id was already used by another request_id")
                return asdict(existing)
            state = JobState(request_id, evaluation_id, "accepted")
            self._states[evaluation_id] = state
            self._queue.put(InferenceTask(request_id, evaluation_id, path))
            self._changed.notify_all()
            return asdict(state)

    def get_state(self, evaluation_id: str) -> dict[str, Any] | None:
        with self._lock:
            state = self._states.get(evaluation_id)
            return None if state is None else asdict(state)

    def wait(self, evaluation_id: str, timeout: float = 10.0) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        with self._changed:
            while True:
                state = self._states.get(evaluation_id)
                if state is not None and state.status in {
                    "succeeded",
                    "succeeded_without_callback",
                    "failed",
                }:
                    return asdict(state)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"task {evaluation_id} did not finish in time")
                self._changed.wait(remaining)

    def _set_state(self, evaluation_id: str, status: str, detail: str = "") -> None:
        with self._changed:
            state = self._states[evaluation_id]
            state.status = status
            state.detail = detail
            self._changed.notify_all()

    def _run(self) -> None:
        while True:
            task = self._queue.get()
            try:
                self._execute(task)
            except Exception as error:  # keep the worker alive for later requests
                detail = "".join(
                    traceback.format_exception_only(type(error), error)
                ).strip()
                self._set_state(task.evaluation_id, "failed", detail)
            finally:
                self._queue.task_done()

    def _execute(self, task: InferenceTask) -> None:
        self._set_state(task.evaluation_id, "running")
        studies = discover_studies(task.dataset_path)
        predictions = [self._predictor.predict(study) for study in studies]
        pairs = baseline_duplicate_pairs(studies)
        predicate_path = write_result_set(
            self._config.answer_base,
            task.evaluation_id,
            studies,
            predictions,
            pairs,
        )
        if self._config.callback_url is None:
            self._set_state(
                task.evaluation_id,
                "succeeded_without_callback",
                "LUNG_AI_CALLBACK_URL is not configured",
            )
            return
        pred_path = (
            predicate_path.parent
            if self._config.callback_pred_path_mode == "evaluation"
            else predicate_path
        )
        notify_completion(
            self._config.callback_url,
            task.request_id,
            task.evaluation_id,
            pred_path,
            attempts=self._config.callback_attempts,
            timeout_seconds=self._config.callback_timeout_seconds,
        )
        self._set_state(task.evaluation_id, "succeeded")
