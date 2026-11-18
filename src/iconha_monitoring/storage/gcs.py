import json
import os
import logging
from pathlib import Path
from google.cloud import storage
from src.iconha_monitoring.renderer.json_builder import serialize_status_json


def read_previous_tier() -> str | None:
    """
    [HYDRO-06] Reads the previous risk_tier from local ./web/status.json or GCS status.json
    so stateless pipeline runs can apply de-escalation hysteresis without a database.
    """
    bucket_name = os.environ.get("GCS_PUBLIC_BUCKET")
    try:
        if bucket_name:
            client = storage.Client()
            bucket = client.bucket(bucket_name)
            blob = bucket.blob("status.json")
            if blob.exists():
                raw = blob.download_as_text(encoding="utf-8")
                return json.loads(raw).get("risk_tier")
        else:
            local_path = Path(__file__).resolve().parents[3] / "web" / "status.json"
            if local_path.is_file():
                raw = local_path.read_text(encoding="utf-8")
                return json.loads(raw).get("risk_tier")
    except Exception as exc:
        logging.debug("Could not read previous status.json for hysteresis: %s", exc)
    return None


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