from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from lung_ai.config import Config
from lung_ai.worker import TaskManager


class CallbackHandler(BaseHTTPRequestHandler):
    payloads: list[dict[str, object]] = []

    def do_POST(self) -> None:
        length = int(self.headers["Content-Length"])
        type(self).payloads.append(json.loads(self.rfile.read(length)))
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


class WorkerTest(unittest.TestCase):
    def test_end_to_end_generation_and_callback(self) -> None:
        CallbackHandler.payloads = []
        callback_server = ThreadingHTTPServer(("127.0.0.1", 0), CallbackHandler)
        callback_thread = threading.Thread(
            target=callback_server.serve_forever, daemon=True
        )
        callback_thread.start()
        try:
            with tempfile.TemporaryDirectory() as temporary_directory:
                root = Path(temporary_directory)
                dataset = root / "dataset"
                for number in (1, 2):
                    image = (
                        dataset
                        / f"patient-{number}"
                        / f"study-{number}"
                        / f"series-{number}"
                        / "image.nii.gz"
                    )
                    image.parent.mkdir(parents=True, exist_ok=True)
                    image.write_bytes(b"synthetic nifti placeholder")

                answer_base = root / "answer"
                config = Config(
                    host="127.0.0.1",
                    port=8000,
                    answer_base=answer_base,
                    callback_url=(
                        f"http://127.0.0.1:{callback_server.server_port}/callback"
                    ),
                    callback_pred_path_mode="evaluation",
                    callback_attempts=1,
                    callback_timeout_seconds=2.0,
                )
                manager = TaskManager(config)
                manager.submit("request-1", "evaluation-1", str(dataset))
                state = manager.wait("evaluation-1", timeout=5.0)

                self.assertEqual(state["status"], "succeeded")
                predicate = answer_base / "evaluation-1" / "predicate"
                self.assertTrue((predicate / "duplicate_pairs.jsonl").is_file())
                self.assertTrue(
                    (
                        predicate
                        / "patient-1"
                        / "study-1"
                        / "prediction.json"
                    ).is_file()
                )
                self.assertEqual(len(CallbackHandler.payloads), 1)
                callback_payload = CallbackHandler.payloads[0]
                self.assertEqual(callback_payload["request_id"], "request-1")
                self.assertEqual(callback_payload["evaluationId"], "evaluation-1")
                self.assertEqual(
                    callback_payload["predPath"], str(answer_base / "evaluation-1")
                )
        finally:
            callback_server.shutdown()
            callback_server.server_close()


if __name__ == "__main__":
    unittest.main()
