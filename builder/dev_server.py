"""Dev HTTP server with no-cache headers.

Stdlib `python -m http.server` responds with `Cache-Control: max-age=...`,
so `location.reload()` serves stale `res/*` files from browser cache after
a rebuild. We force `no-store` on every response so edits to resources like
`res/maps/level1.json` appear on the next reload without a hard-refresh.

Invoked as: `python dev_server.py <port>`, cwd set to the web output dir.
"""
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class NoCacheHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, format: str, *args) -> None:
        # Silence per-request lines; watch mode owns the stdout.
        pass


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5500
    with ThreadingHTTPServer(("0.0.0.0", port), NoCacheHandler) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    main()
