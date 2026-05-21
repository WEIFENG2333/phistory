"""Local fake LLM API used to capture prompts without calling real services.

phistory's job is to observe the real CLI request shape. The upstream response
only needs to be valid enough for that CLI to finish cleanly; otherwise clients
like Codex retry failed requests and produce noisy traces.
"""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterator


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self._reply(_response_for_path(self.path))

    def do_POST(self) -> None:
        self._reply(_response_for_path(self.path))

    def _reply(self, payload: dict) -> None:
        length = int(self.headers.get("content-length") or 0)
        if length:
            self.rfile.read(length)
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        return


def _response_for_path(path: str) -> dict:
    if path.startswith("/v1/messages"):
        return {
            "id": "msg_phistory_dummy",
            "type": "message",
            "role": "assistant",
            "model": "phistory-dummy",
            "content": [{"type": "text", "text": "ok"}],
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }
    if path.startswith(("/v1/responses", "/responses")):
        return {
            "id": "resp_phistory_dummy",
            "object": "response",
            "created_at": 0,
            "status": "completed",
            "model": "phistory-dummy",
            "output": [
                {
                    "id": "msg_phistory_dummy",
                    "type": "message",
                    "status": "completed",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "ok", "annotations": []}],
                }
            ],
            "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
        }
    if path.startswith("/v1/models"):
        return {"object": "list", "data": [{"id": "gpt-5.4", "object": "model"}]}
    return {"ok": True, "path": path}


@contextmanager
def dummy_upstream() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
