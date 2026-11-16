import os
import http.server
import socketserver
from pathlib import Path
from src.iconha_monitoring.pipeline import execute_pipeline


def main():
    # Ensure local execution writes to ./web/ instead of GCS
    os.environ.pop("GCS_PUBLIC_BUCKET", None)
    print("1. Running hydrological pipeline and generating ./web/status.json + card_whatsapp.png...")
    execute_pipeline()

    web_dir = Path(__file__).resolve().parents[1] / "src" / "web"
    os.chdir(web_dir)

    port = 8000
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"2. Serving Zero-Typing PWA Dashboard at http://localhost:{port}")
        print("   Press Ctrl+C to stop.")
        httpd.serve_forever()


if __name__ == "__main__":
    main()