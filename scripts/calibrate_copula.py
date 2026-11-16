import sys
import json
from datetime import datetime
from pathlib import Path
import requests
from scipy import stats

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.iconha_monitoring.config import API_DECAY_K_DAILY, TZ_BR


def fetch_historical_era5(lat: float = -20.6400, lon: float = -40.8600) -> list[float]:
    """Fetches multi-year historical hourly precipitation from Open-Meteo ERA5 Archive."""
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": "2015-01-01",
        "end_date": "2025-12-31",
        "hourly": "precipitation",
        "timezone": "America/Sao_Paulo",
    }
    resp = requests.get(url, params=params, timeout=60)
    resp.raise_for_status()
    precip = resp.json()["hourly"]["precipitation"]
    return [float(x or 0.0) for x in precip]


def calibrate():
    print("Fetching ERA5 historical precipitation for Rio Iconha headwaters (includes Jan 2020 flood)...")
    hourly_p = fetch_historical_era5()

    k_hourly = API_DECAY_K_DAILY ** (1.0 / 24.0)
    api = 0.0
    p6h_blocks = []
    api_blocks = []

    # Step in non-overlapping 6-hour blocks (1460 events/year)
    for i in range(0, len(hourly_p) - 6, 6):
        chunk = hourly_p[i : i + 6]
        api_blocks.append(api)
        p6h_blocks.append(sum(chunk))
        for p_hr in chunk:
            api = (k_hourly * api) + p_hr

    exceedance_rate = 0.05
    q_thresh = 1.0 - exceedance_rate

    p6h_sorted = sorted(p6h_blocks)
    api_sorted = sorted(api_blocks)
    u_p6h = p6h_sorted[int(len(p6h_sorted) * q_thresh)]
    u_api = api_sorted[int(len(api_sorted) * q_thresh)]

    p6h_excess = [x - u_p6h for x in p6h_blocks if x > u_p6h]
    api_excess = [x - u_api for x in api_blocks if x > u_api]

    xi_p6h, _, sigma_p6h = stats.genpareto.fit(p6h_excess, floc=0)
    xi_api, _, sigma_api = stats.genpareto.fit(api_excess, floc=0)

    # Estimate Gumbel Copula theta from Kendall's tau on joint upper tail
    tau, _ = stats.kendalltau(p6h_blocks, api_blocks)
    gumbel_theta = max(1.05, round(1.0 / max(0.1, 1.0 - max(0.0, float(tau))), 3))

    params = {
        "calibrated_at": datetime.now(TZ_BR).isoformat(),
        "exceedance_rate": exceedance_rate,
        "events_per_year": 1460.0,
        "p6h_threshold_u": round(float(u_p6h), 2),
        "p6h_sigma": round(float(sigma_p6h), 2),
        "p6h_xi": round(float(xi_p6h), 3),
        "api_threshold_u": round(float(u_api), 2),
        "api_sigma": round(float(sigma_api), 2),
        "api_xi": round(float(xi_api), 3),
        "gumbel_theta": gumbel_theta,
    }

    out_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "iconha_monitor"
        / "hydrology"
        / "copula_params.json"
    )
    out_path.write_text(json.dumps(params, indent=2), encoding="utf-8")
    print(f"Saved calibrated parameters to {out_path}:\n{json.dumps(params, indent=2)}")


if __name__ == "__main__":
    calibrate()