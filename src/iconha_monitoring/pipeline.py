import json
import logging
from src.iconha_monitoring.ingestion.open_meteo import fetch_basin_weather
from src.iconha_monitoring.ingestion.telemetry import fetch_official_brazilian_telemetry
from src.iconha_monitoring.hydrology.decision import evaluate_basin_hydrology
from src.iconha_monitoring.renderer.json_builder import build_status_payload
from src.iconha_monitoring.renderer.whatsapp_card import generate_whatsapp_card
from src.iconha_monitoring.storage.gcs import publish_artifacts

logging.basicConfig(level=logging.INFO)


def execute_pipeline():
    """End-to-end execution of the Iconha Flood Monitoring Pipeline."""
    raw_weather = fetch_basin_weather()
    telemetry = fetch_official_brazilian_telemetry()
    hydro_result = evaluate_basin_hydrology(raw_weather)
    status_payload = build_status_payload(hydro_result, telemetry)
    png_bytes = generate_whatsapp_card(status_payload)
    publish_artifacts(status_payload, png_bytes)

    return (
        json.dumps({
            "status": "ok",
            "version": status_payload["version"],
            "risk_tier": status_payload["risk_tier"],
            "effective_runoff_24h_mm": status_payload["summary"]["effective_runoff_24h_mm"],
            "joint_return_period_years": status_payload["summary"]["joint_return_period_years"],
        }),
        200,
        {"Content-Type": "application/json"},
    )