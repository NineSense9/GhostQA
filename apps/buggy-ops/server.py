"""BuggyOps local server: static files + a seeded 500.

Fully offline, deterministic. Usage:
    python server.py [port]        (default 3944)
"""
import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
FAIL_PATH = "/api/page"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def log_message(self, *args):
        pass

    def _json(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path == FAIL_PATH:
            self._json(500, {"error": "pager dispatch failed: NullPointerException"})
        elif self.path == "/api/echo":
            length = int(self.headers.get("Content-Length", 0))
            self._json(200, {"echo": self.rfile.read(length).decode("utf-8", "ignore")})
        else:
            self._json(404, {"error": "not found"})


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 3944
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("BuggyOps listening on http://127.0.0.1:" + str(port))
    server.serve_forever()


if __name__ == "__main__":
    main()
