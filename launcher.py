from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
HOST = "127.0.0.1"
PORT = int(os.environ.get("AI_LAB_UI_PORT", "8765"))
BACKEND = os.environ.get("AI_LAB_BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        print("[UI]", fmt % args)

    def _json(self, status: int, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _proxy(self, method: str, target_path: str) -> None:
        body = None
        if method == "POST":
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length else b"{}"

        request = urllib.request.Request(
            f"{BACKEND}{target_path}",
            data=body,
            method=method,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=3600) as response:
                data = response.read()
                self.send_response(response.status)
                self.send_header("Content-Type", response.headers.get("Content-Type", "application/json"))
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as exc:
            data = exc.read() or json.dumps({"detail": str(exc)}).encode("utf-8")
            self.send_response(exc.code)
            self.send_header("Content-Type", exc.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as exc:
            self._json(502, {
                "ok": False,
                "error": "AI Lab Brain backend is unreachable",
                "detail": str(exc),
                "backend": BACKEND,
            })

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/bridge/status":
            self._json(200, {"ok": True, "bridge": "online", "backend": BACKEND})
            return
        if path == "/api/health":
            self._proxy("GET", "/health")
            return
        if path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/agent/cline":
            self._proxy("POST", "/agent/cline")
            return
        self._json(404, {"detail": "Unknown API route"})


def open_browser() -> None:
    webbrowser.open(f"http://{HOST}:{PORT}/")


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print("=" * 60)
    print("AI LAB OS VISUAL CONTROL SURFACE")
    print(f"UI      : http://{HOST}:{PORT}/")
    print(f"BACKEND : {BACKEND}")
    print("Proxy   : /api/agent/cline -> /agent/cline")
    print("=" * 60)
    threading.Timer(0.8, open_browser).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
