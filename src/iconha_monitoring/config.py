import os
from pathlib import Path
from zoneinfo import ZoneInfo


def _load_dotenv() -> None:
    """Lightweight standard-library .env loader (no external dependency required)."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key:
            os.environ.setdefault(key, value)


_load_dotenv()

TZ_BR = ZoneInfo("America/Sao_Paulo")

# Multi-point coordinate grid for the Rio Iconha watershed
# Headwaters in Alfredo Chaves / Duas Barras carry 90% of the basin weight
BASIN_POINTS = [
    {
        "id": "P1_CRUBIXA",
        "name": "Cabeceira Norte (Crubixá - Alfredo Chaves)",
        "zone": "upper",
        "lat": -20.6400,
        "lon": -40.8600,
        "weight": 0.35,
        "cn_ii": 79.0,  # Steep mountain scarp with mixed pasture/forest
        "lag_hours": 3,  # Kinematic wave travel time to lower floodplain (~22 km)
    },
    {
        "id": "P2_MONTE_ALEGRE",
        "name": "Cabeceira Oeste (Alto Rib. Monte Alegre)",
        "zone": "upper",
        "lat": -20.6850,
        "lon": -40.9100,
        "weight": 0.30,
        "cn_ii": 80.0,  # High-gradient crystalline escarpment
        "lag_hours": 3,  # Kinematic wave travel time to lower floodplain (~18 km)
    },
    {
        "id": "P3_DUAS_BARRAS",
        "name": "Médio Curso (Duas Barras - Iconha)",
        "zone": "middle",
        "lat": -20.7291,
        "lon": -40.8822,
        "weight": 0.25,
        "cn_ii": 78.0,  # Confluence bottleneck valley
        "lag_hours": 1,  # Kinematic wave travel time from Duas Barras to Iconha Sede (~10 km)
    },
    {
        "id": "P4_ICONHA_SEDE",
        "name": "Baixo Curso (Iconha Sede)",
        "zone": "lower",
        "lat": -20.7928,
        "lon": -40.8108,
        "weight": 0.10,
        "cn_ii": 85.0,  # Urbanized floodplain
        "lag_hours": 0,  # Reference basin outlet
    },
]

# Hydrological constants
API_DECAY_K_DAILY = 0.88               # Daily soil drainage recession factor (0.85 - 0.92)
TC_WINDOW_HOURS = 6                    # Time of concentration fast-trigger window (3h - 6h)
SCS_IA_RATIO = 0.05                    # Tropical steep-escarpment initial abstraction ratio (Ia = 0.05 * S)
HYSTERESIS_DEESCALATION_FACTOR = 0.90  # 10% deadband buffer on tier de-escalation to prevent flickering
PAST_DAYS_FETCH = 14                   # 14-day rolling memory window for API_t
FORECAST_DAYS_FETCH = 2                # 48-hour lookahead

TIER_CONFIG = {
    "VERDE": {
        "color_hex": "#2E7D32",
        "color_rgb": (46, 125, 50),
        "title": "NÍVEL VERDE: NORMALIDADE",
        "headline": "Bacia do Rio Iconha em condições normais.",
        "advice": "Infiltração segura no solo. Sem previsão de escoamento superficial crítico.",
    },
    "AMARELO": {
        "color_hex": "#F9A825",
        "color_rgb": (249, 168, 37),
        "title": "NÍVEL AMARELO: OBSERVAÇÃO",
        "headline": "Solo úmido na bacia ou chuva moderada nas cabeceiras.",
        "advice": "Acompanhe as atualizações. Atenção moradores próximos ao rio e encostas.",
    },
    "LARANJA": {
        "color_hex": "#EF6C00",
        "color_rgb": (239, 108, 0),
        "title": "NÍVEL LARANJA: ATENÇÃO SEVERA",
        "headline": "Escoamento superficial elevado previsto nas cabeceiras.",
        "advice": "Risco de elevação rápida do Rio Iconha. Prepare documentos e itens essenciais.",
    },
    "VERMELHO": {
        "color_hex": "#C62828",
        "color_rgb": (198, 40, 40),
        "title": "NÍVEL VERMELHO: ALERTA MÁXIMO",
        "headline": "RISCO EXTREMO DE ENXURRADA / CHEIA NA BACIA.",
        "advice": "Saturação crítica e chuva intensa nas cabeceiras. Procure áreas elevadas e seguras imediatamente.",
    },
}