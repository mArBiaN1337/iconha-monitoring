import os
import logging
from pathlib import Path
from google.cloud import storage
from src.iconha_monitoring.renderer.json_builder import serialize_status_json


def publish_artifacts(status_payload: dict, png_bytes: bytes) -> None:
    """Uploads status.json and card_whatsapp.png to GCS or ./web/ locally."""
    bucket_name = os.environ.get("GCS_PUBLIC_BUCKET")
    json_str = serialize_status_json(status_payload)

    if bucket_name:
        client = storage.Client()
        bucket = client.bucket(bucket_name)

        blob_json = bucket.blob("status.json")
        blob_json.cache_control = "public, max-age=300"
        blob_json.upload_from_string(
            json_str.encode("utf-8"),
            content_type="application/json; charset=utf-8",
        )

        blob_png = bucket.blob("card_whatsapp.png")
        blob_png.cache_control = "public, max-age=300"
        blob_png.upload_from_string(png_bytes, content_type="image/png")
        logging.info("Published artifacts to gs://%s", bucket_name)
    else:
        web_dir = Path(__file__).resolve().parents[3] / "web"
        web_dir.mkdir(parents=True, exist_ok=True)
        (web_dir / "status.json").write_text(json_str, encoding="utf-8")
        (web_dir / "card_whatsapp.png").write_bytes(png_bytes)
        logging.info("Saved status.json and card_whatsapp.png locally to %s", web_dir)