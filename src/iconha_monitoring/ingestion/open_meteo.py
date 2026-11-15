import requests
from src.iconha_monitoring.config import (
    BASIN_POINTS,
    PAST_DAYS_FETCH,
    FORECAST_DAYS_FETCH,
)


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
    resp = requests.get(url, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else [data]