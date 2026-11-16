"""Мок-сервіс Telegram Bot API для локального наскрізного запуску (лише стандартна бібліотека).

POST /bot<token>/sendMessage → {"ok": true}; GET /health → 200. Отримані повідомлення пише в stdout.
"""

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: dict) -> None:
        data = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        self._send(200, {"status": "ok"}) if self.path == "/health" else self._send(404, {"ok": False})

    def do_POST(self) -> None:  # noqa: N802
        if not self.path.endswith("/sendMessage"):
            self._send(404, {"ok": False})
            return
        payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        print(f"[telegram-mock] → {payload.get('chat_id')}: {payload.get('text')}", flush=True)
        self._send(200, {"ok": True, "result": {"message_id": 1}})

    def log_message(self, *_args) -> None:
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8081"))
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
