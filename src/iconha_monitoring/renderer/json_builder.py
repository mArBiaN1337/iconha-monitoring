import json
from datetime import datetime
from src.iconha_monitoring import __version__
from src.iconha_monitoring.config import TIER_CONFIG, TZ_BR


def serialize_status_json(payload: dict) -> str:
    """Serializes the status payload to UTF-8 JSON preserving Portuguese accents."""
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_status_payload(hydro_result: dict, telemetry: dict) -> dict:
    """Formats the hydrological decision output into the static status.json schema."""
    now_dt = datetime.now(TZ_BR)
    tier = hydro_result["risk_tier"]
    points = hydro_result["points"]

    upstream_24h = sum(
        p["forecast_24h_mm"] * (p["weight"] / 0.90)
        for p in points
        if p["zone"] in ("upper", "middle")
    )
    local_iconha = next(p for p in points if p["zone"] == "lower")
    hours_labels = points[0]["next_12h_times"]

    return {
        "version": __version__,
        "updated_at_iso": now_dt.isoformat(),
        "updated_at_br": now_dt.strftime("%d/%m/%Y às %H:%M"),
        "risk_tier": tier,
        "banner": TIER_CONFIG[tier],
        "summary": {
            "api_t_mm": hydro_result["weighted_api_t_mm"],
            "soil_status": hydro_result["scs_24h"]["amc_class"],
            "cn_effective": hydro_result["scs_24h"]["cn_effective"],
            "effective_runoff_24h_mm": hydro_result["scs_24h"]["effective_runoff_q_mm"],
            "effective_runoff_6h_mm": hydro_result["scs_6h"]["effective_runoff_q_mm"],
            "joint_return_period_years": hydro_result["copula"]["joint_return_period_years"],
            "upstream_forecast_24h_mm": round(upstream_24h, 1),
            "upstream_tc_6h_mm": hydro_result["upstream_tc_6h_mm"],
            "local_iconha_24h_mm": local_iconha["forecast_24h_mm"],
            "local_iconha_tc_6h_mm": local_iconha["rolling_6h_tc_mm"],
        },
        "chart_12h_upstream": [
            {"hour": hours_labels[i], "mm": hydro_result["upstream_hourly_12h"][i]}
            for i in range(len(hours_labels))
        ],
        "points": points,
        "telemetry": telemetry,
        "disclaimer": (
            "Monitoramento Hidrológico Independente - Rio Iconha (modelos científicos SCS-CN + Cópula de Gumbel). "
            "Iniciativa técnica e científica independente de acompanhamento preventivo da bacia."
        ),
    }