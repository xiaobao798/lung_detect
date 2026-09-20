from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from lung_ai.server import make_server


class FakeManager:
    def __init__(self) -> None:
        self.submissions: list[tuple[str, str, str]] = []

    def submit(self, request_id: str, evaluation_id: str, dataset_path: str):
        self.submissions.append((request_id, evaluation_id, dataset_path))
        return {
            "request_id": request_id,
            "evaluation_id": evaluation_id,
            "status": "accepted",
            "detail": "",
        }

    def get_state(self, evaluation_id: str):
        return None


class ServerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = FakeManager()
        self.server = make_server("127.0.0.1", 0, self.manager)  # type: ignore[arg-type]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def test_health(self) -> None:
        with urllib.request.urlopen(f"{self.base_url}/health") as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(json.load(response), {"status": "active"})

    def test_call_returns_immediately(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            payload = {
                "request_id": "request-1",
                "input": {
                    "evaluation_id": "evaluation-1",
                    "dataset_path": str(Path(temporary_directory)),
                },
            }
            request = urllib.request.Request(
                f"{self.base_url}/call",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request) as response:
                body = json.load(response)
            self.assertEqual(response.status, 200)
            self.assertEqual(body["status"], "received")
            self.assertEqual(len(self.manager.submissions), 1)


if __name__ == "__main__":
    unittest.main()
