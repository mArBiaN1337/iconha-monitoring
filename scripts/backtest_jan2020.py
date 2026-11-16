# scripts/backtest_jan2020.py
import argparse
import sys
from datetime import datetime
from pathlib import Path
import requests
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.iconha_monitoring.config import (
    BASIN_POINTS,
    API_DECAY_K_DAILY,
    TC_WINDOW_HOURS,
)
from src.iconha_monitoring.hydrology.state_vars import (
    compute_continuous_api,
    compute_rolling_tc_max,
)
from src.iconha_monitoring.hydrology.scs_cn import compute_scs_effective_runoff
from src.iconha_monitoring.hydrology.copula_gpd import (
    load_copula_params,
    gumbel_copula_joint_return_period,
)


def fetch_jan2020_archive() -> list[dict]:
    """Fetches hourly historical precipitation from 2020-01-01 to 2020-01-19 across all 4 nodes."""
    lats = ",".join(str(p["lat"]) for p in BASIN_POINTS)
    lons = ",".join(str(p["lon"]) for p in BASIN_POINTS)

    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lats,
        "longitude": lons,
        "start_date": "2020-01-01",
        "end_date": "2020-01-19",
        "hourly": "precipitation",
        "timezone": "America/Sao_Paulo",
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else [data]


def simulate_hour(raw_locations: list[dict], curr_idx: int, copula_params: dict, scale: float = 1.0) -> dict:
    weighted_api_t = 0.0
    weighted_f24h = 0.0
    weighted_cn_base = 0.0
    upstream_tc_6h_max = 0.0

    for idx, point in enumerate(BASIN_POINTS):
        precip_raw = [float(x or 0.0) for x in raw_locations[idx]["hourly"]["precipitation"]]
        node_scale = scale if point["zone"] in ("upper", "middle") else 1.0
        precip = [p * node_scale for p in precip_raw]

        past_slice = precip[max(0, curr_idx - 336) : curr_idx]
        next_24h_slice = precip[curr_idx : curr_idx + 24]

        api_t = compute_continuous_api(past_slice, k_daily=API_DECAY_K_DAILY)
        rolling_6h_max = compute_rolling_tc_max(next_24h_slice, window_hours=TC_WINDOW_HOURS)
        total_24h = sum(next_24h_slice)

        w = point["weight"]
        weighted_api_t += w * api_t
        weighted_f24h += w * total_24h
        weighted_cn_base += w * point["cn_ii"]

        if point["zone"] in ("upper", "middle") and rolling_6h_max > upstream_tc_6h_max:
            upstream_tc_6h_max = rolling_6h_max

    scs_24h = compute_scs_effective_runoff(weighted_f24h, weighted_api_t, weighted_cn_base)
    scs_6h = compute_scs_effective_runoff(upstream_tc_6h_max, weighted_api_t, weighted_cn_base)

    q_24h = scs_24h["effective_runoff_q_mm"]
    q_6h = scs_6h["effective_runoff_q_mm"]
    copula_res = gumbel_copula_joint_return_period(upstream_tc_6h_max, weighted_api_t, copula_params)
    t_joint = copula_res["joint_return_period_years"]

    if q_24h >= 34.0 or q_6h >= 38.0 or t_joint >= 9.0:
        tier = "VERMELHO"
    elif q_24h >= 23.0 or q_6h >= 15.0 or t_joint >= 2.0:
        tier = "LARANJA"
    elif q_24h >= 8.0 or weighted_api_t >= 60.0 or t_joint >= 1.2:
        tier = "AMARELO"
    else:
        tier = "VERDE"

    return {
        "time": raw_locations[0]["hourly"]["time"][curr_idx],
        "api_t": round(weighted_api_t, 1),
        "f24h": round(weighted_f24h, 1),
        "tc_6h": round(upstream_tc_6h_max, 1),
        "q_eff_24h": q_24h,
        "t_joint_yr": t_joint,
        "tier": tier,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scale", type=float, default=2.0, help="Cloudburst convective scaling factor")
    args = parser.parse_args()

    print("Fetching Jan 2020 ERA5 archive for Rio Iconha backtest...")
    raw_locations = fetch_jan2020_archive()
    copula_params = load_copula_params()
    times = raw_locations[0]["hourly"]["time"]

    # Replay Jan 15 to Jan 18, 2020
    start_idx = times.index("2020-01-15T00:00")
    end_idx = times.index("2020-01-18T12:00")

    timestamps = []
    runoff_vals = []

    print("\n" + "=" * 85)
    print(f"{'TIMESTAMP':<18} | {'API_t':>7} | {'Q_eff24h':>9} | {'T_joint':>9} | {'TIER'}")
    print("-" * 85)

    for idx in range(start_idx, end_idx + 1, 1):
        res = simulate_hour(raw_locations, idx, copula_params, scale=args.scale)
        # Parse ISO string into a native datetime object for proper time-series plotting
        timestamps.append(datetime.fromisoformat(res["time"]))
        runoff_vals.append(res["q_eff_24h"])

        if res["tier"] in ("LARANJA", "VERMELHO") or idx % 6 == 0:
            print(f"{res['time']:<18} | {res['api_t']:>5.1f}mm | {res['q_eff_24h']:>7.1f}mm | {res['t_joint_yr']:>6.1f}yr | {res['tier']}")

    print("=" * 85)

    # Generate Graphical Evidence Chart via Matplotlib
    plt.style.use("default")
    fig, ax = plt.subplots(figsize=(12, 6), facecolor="white")
    ax.set_facecolor("white")

    ax.plot(
        timestamps,
        runoff_vals,
        label="Effective Surface Runoff Q_eff (mm)",
        color="#0284c7",
        linewidth=2,
    )

    # Convert datetime to a float matplotlib date number for axvline typing
    flood_peak_dt = datetime.fromisoformat("2020-01-17T21:30")
    flood_peak_x = float(mdates.date2num(flood_peak_dt))
    ax.axvline(
        x=flood_peak_x,
        color="#ef4444",
        linestyle="--",
        label="Actual Flood Peak (Jan 17, 21:30)",
    )

    ax.set_title(
        "Iconha Flood Model Backtest — January 17, 2020 Event Replay",
        fontsize=14,
        fontweight="bold",
        pad=15,
        color="#0f172a",
    )
    ax.set_xlabel("Timeline (January 2020)", fontsize=11, color="#1e293b")
    ax.set_ylabel("Effective Runoff Q_eff (mm)", fontsize=11, color="#1e293b")

    # Configure and display explicit x and y scales
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=6))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m %H:%M"))
    ax.tick_params(
        axis="both",
        which="major",
        labelsize=10,
        colors="#1e293b",
        labelbottom=True,
        labelleft=True,
    )
    fig.autofmt_xdate()

    ax.grid(True, alpha=0.35, linestyle="--", color="#94a3b8")
    ax.legend(loc="upper left", frameon=True, facecolor="white", edgecolor="#cbd5e1")
    fig.tight_layout()

    chart_path = REPO_ROOT / "imgs" / "backtest_jan2020_result.png"
    chart_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(chart_path, dpi=300, facecolor="white", bbox_inches="tight")
    print(f"\nGraphical evidence chart successfully saved to: {chart_path}")
    plt.show()


if __name__ == "__main__":
    main()