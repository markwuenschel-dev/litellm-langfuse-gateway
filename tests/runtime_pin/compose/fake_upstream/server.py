"""Minimal OpenAI-compatible chat completions server for pin-spike tests.

Deterministic: always returns the same assistant text and token counts.
No external network. Not used in production.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        # Keep compose logs quiet unless debugging.
        return

    def _json(self, code: int, body: dict[str, object]) -> None:
        raw = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/health", "/"):
            self._json(200, {"ok": True, "service": "pin-spike-fake-upstream"})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0") or "0")
        _ = self.rfile.read(length) if length else b""
        # Accept /v1/chat/completions and /chat/completions
        if self.path.rstrip("/").endswith("chat/completions"):
            self._json(
                200,
                {
                    "id": "chatcmpl-pin-spike",
                    "object": "chat.completion",
                    "created": 1,
                    "model": "gpt-4o-mini",
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": "pin-spike-pong",
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 8,
                        "completion_tokens": 4,
                        "total_tokens": 12,
                    },
                },
            )
            return
        self._json(404, {"error": f"unsupported path {self.path}"})


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", 8080), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
