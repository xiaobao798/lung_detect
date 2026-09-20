from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path


class CallbackError(RuntimeError):
    pass


def notify_completion(
    callback_url: str,
    request_id: str,
    evaluation_id: str,
    pred_path: Path,
    *,
    attempts: int,
    timeout_seconds: float,
) -> None:
    payload = {
        "request_id": request_id,
        "evaluationId": evaluation_id,
        "predPath": str(pred_path),
    }
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(
            callback_url,
            data=encoded,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                if not 200 <= response.status < 300:
                    raise CallbackError(f"callback returned HTTP {response.status}")
                return
        except (OSError, urllib.error.URLError, CallbackError) as error:
            last_error = error
            if attempt < attempts:
                time.sleep(min(2 ** (attempt - 1), 8))
    raise CallbackError(f"callback failed after {attempts} attempts: {last_error}")
