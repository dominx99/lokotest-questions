"""Simple HTTP server for the verification viewer with apply API."""

from __future__ import annotations

import json
import sys
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

# Resolve project root (parent of scripts/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from apply_verification import apply_all, apply_by_type, apply_uuid, dismiss_uuid


class ViewerHandler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/api/apply":
            self._handle_apply_one()
        elif self.path == "/api/apply-all":
            self._handle_apply_all()
        elif self.path == "/api/apply-type":
            self._handle_apply_type()
        elif self.path == "/api/dismiss":
            self._handle_dismiss()
        else:
            self.send_error(404)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length))

    def _json_response(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_apply_one(self):
        try:
            body = self._read_body()
            name = body["name"]
            uuid = body["uuid"]
            result = apply_uuid(name, uuid)
            if "error" in result:
                self._json_response(result, 400)
            else:
                self._json_response(result)
        except Exception as e:
            self._json_response({"error": str(e)}, 500)

    def _handle_dismiss(self):
        try:
            body = self._read_body()
            name = body["name"]
            uuid = body["uuid"]
            result = dismiss_uuid(name, uuid)
            if "error" in result:
                self._json_response(result, 400)
            else:
                self._json_response(result)
        except Exception as e:
            self._json_response({"error": str(e)}, 500)

    def _handle_apply_type(self):
        try:
            body = self._read_body()
            name = body["name"]
            status_type = body["type"]
            result = apply_by_type(name, status_type)
            if "error" in result:
                self._json_response(result, 400)
            else:
                self._json_response(result)
        except Exception as e:
            self._json_response({"error": str(e)}, 500)

    def _handle_apply_all(self):
        try:
            body = self._read_body()
            name = body["name"]
            result = apply_all(name)
            self._json_response(result)
        except Exception as e:
            self._json_response({"error": str(e)}, 500)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    handler = partial(ViewerHandler, directory=str(PROJECT_ROOT))
    server = HTTPServer(("", port), handler)
    print(f"Serving on http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
