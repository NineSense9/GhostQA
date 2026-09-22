"""BuggyDesk local server: static files + a seeded webhook 500.

Fully offline, deterministic. Usage:
    python server.py [port]        (default 3941)
Endpoints:
    GET  /*              static files from ./static
    POST /api/webhook    always HTTP 500 (seeded integration failure)
    POST /api/echo       200 JSON echo
"""
import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def log_message(self, *args):  # quiet
        pass

    def _json(self, code: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path == "/api/webhook":
            self._json(500, {"error": "webhook dispatch failed: NullPointerException"})
        elif self.path == "/api/echo":
            length = int(self.headers.get("Content-Length", 0))
            self._json(200, {"echo": self.rfile.read(length).decode("utf-8", "ignore")})
        else:
            self._json(404, {"error": "not found"})


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 3941
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"BuggyDesk listening on http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
