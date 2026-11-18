import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from src.iconha_monitoring.config import (
    BASIN_POINTS,
    PAST_DAYS_FETCH,
    FORECAST_DAYS_FETCH,
)


def _build_resilient_session() -> requests.Session:
    """Builds an HTTP session with exponential backoff for transient NWP API hiccups."""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def sanitize_hourly_precip(
    raw_precip: list,
    raw_prob: list | None = None,
    zone: str = "lower",
) -> list[float]:
    """
    [HYDRO-07] Cleans hourly precipitation array:
    1. Linearly interpolates isolated single-hour None gaps between valid readings.
    2. Applies bounded orographic convective enhancement (up to +15%) on upper/middle
       escarpment nodes when heavy rain (>= 4 mm/h) coincides with high convective
       probability (>= 80%).
    """
    n = len(raw_precip)
    cleaned: list[float] = []

    for i in range(n):
        val = raw_precip[i]
        if val is None:
            prev_val = raw_precip[i - 1] if i > 0 and raw_precip[i - 1] is not None else None
            next_val = raw_precip[i + 1] if i + 1 < n and raw_precip[i + 1] is not None else None
            if prev_val is not None and next_val is not None:
                p = 0.5 * (float(prev_val) + float(next_val))
            elif prev_val is not None:
                p = float(prev_val)
            else:
                p = 0.0
        else:
            p = float(val)

        p = max(0.0, p)

        # Convective orographic adjustment for steep headwater escarpments
        if (
            zone in ("upper", "middle")
            and p >= 4.0
            and raw_prob is not None
            and i < len(raw_prob)
            and raw_prob[i] is not None
        ):
            prob = min(max(float(raw_prob[i]), 0.0), 100.0)
            if prob >= 80.0:
                boost = 1.0 + 0.15 * ((prob - 80.0) / 20.0)
                p *= boost

        cleaned.append(round(p, 2))

    return cleaned


def fetch_basin_weather() -> list[dict]:
    """
    Queries Open-Meteo for the 4-point Rio Iconha coordinate grid.
    Returns 14 days of past hourly precipitation + 2 days of forecast.
    """
    lats = ",".join(str(p["lat"]) for p in BASIN_POINTS)
    lons = ",".join(str(p["lon"]) for p in BASIN_POINTS)

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lats,
        "longitude": lons,
        "hourly": "precipitation,precipitation_probability",
        "past_days": PAST_DAYS_FETCH,
        "forecast_days": FORECAST_DAYS_FETCH,
        "timezone": "America/Sao_Paulo",
    }
    session = _build_resilient_session()
    resp = session.get(url, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else [data]