import os
import sys
import http.server
import socketserver
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.iconha_monitoring.pipeline import execute_pipeline


class Utf8HTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Serves static PWA files with explicit UTF-8 charset headers."""

    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".mjs": "application/javascript; charset=utf-8",
        ".json": "application/json; charset=utf-8",
    }


def main():
    # Ensure local execution writes to ./web/ instead of GCS
    os.environ.pop("GCS_PUBLIC_BUCKET", None)
    print("1. Running hydrological pipeline and generating ./web/status.json + card_whatsapp.png...")
    execute_pipeline()

    web_dir = REPO_ROOT / "web"
    os.chdir(web_dir)

    port = int(os.environ.get("PORT", "8000"))
    with socketserver.TCPServer(("", port), Utf8HTTPRequestHandler) as httpd:
        print(f"2. Serving Zero-Typing PWA Dashboard at http://localhost:{port}")
        print("   Press Ctrl+C to stop.")
        httpd.serve_forever()


if __name__ == "__main__":
    main()