from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from .config import Config
from .worker import TaskManager


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def make_server(
    host: str,
    port: int,
    manager: TaskManager,
) -> ThreadingHTTPServer:
    class InferenceHandler(BaseHTTPRequestHandler):
        def _reply(self, status: int, value: Any) -> None:
            body = _json_bytes(value)
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self._reply(HTTPStatus.OK, {"status": "active"})
                return
            if parsed.path == "/status":
                evaluation_id = parse_qs(parsed.query).get("evaluation_id", [""])[0]
                state = manager.get_state(evaluation_id)
                if state is None:
                    self._reply(HTTPStatus.NOT_FOUND, {"error": "task not found"})
                else:
                    self._reply(HTTPStatus.OK, state)
                return
            self._reply(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_POST(self) -> None:
            if urlparse(self.path).path != "/call":
                self._reply(HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 1024 * 1024:
                    raise ValueError("invalid Content-Length")
                payload = json.loads(self.rfile.read(length))
                request_id = payload["request_id"]
                input_data = payload["input"]
                evaluation_id = input_data.get("evaluation_id") or input_data["evaluationId"]
                dataset_path = input_data["dataset_path"]
                if not all(
                    isinstance(value, str)
                    for value in (request_id, str(evaluation_id), dataset_path)
                ):
                    raise ValueError("request fields have invalid types")
                state = manager.submit(request_id, str(evaluation_id), dataset_path)
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                self._reply(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            self._reply(HTTPStatus.OK, {"status": "received", "task": state})

        def log_message(self, format: str, *args: object) -> None:
            return

    return ThreadingHTTPServer((host, port), InferenceHandler)


def main() -> None:
    config = Config.from_env()
    manager = TaskManager(config)
    server = make_server(config.host, config.port, manager)
    print(
        json.dumps(
            {"event": "server_started", "host": config.host, "port": config.port},
            ensure_ascii=False,
        ),
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
