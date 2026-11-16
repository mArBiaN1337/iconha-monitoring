from datetime import datetime
from src.iconha_monitoring.config import (
    BASIN_POINTS,
    API_DECAY_K_DAILY,
    TC_WINDOW_HOURS,
    TZ_BR,
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


def evaluate_basin_hydrology(raw_locations: list[dict]) -> dict:
    """
    Runs the Dual Decision Engine (SCS-CN + GPD/Gumbel Copula) across all 4 basin points.
    """
    now_str = datetime.now(TZ_BR).strftime("%Y-%m-%dT%H:00")
    copula_params = load_copula_params()

    point_metrics = []
    weighted_api_t = 0.0
    weighted_f24h = 0.0
    weighted_cn_base = 0.0
    upstream_tc_6h_max = 0.0
    upstream_hourly_12h = [0.0] * 12

    for idx, point in enumerate(BASIN_POINTS):
        loc_data = raw_locations[idx]["hourly"]
        times = loc_data["time"]
        precip = [float(x or 0.0) for x in loc_data["precipitation"]]

        try:
            curr_idx = times.index(now_str)
        except ValueError:
            curr_idx = len(times) - 48  # Fallback to start of 48h forecast window

        past_slice = precip[max(0, curr_idx - 336) : curr_idx]  # Past 14 days (336h)
        past_72h_sum = sum(precip[max(0, curr_idx - 72) : curr_idx])
        next_12h_slice = precip[curr_idx : curr_idx + 12]
        next_24h_slice = precip[curr_idx : curr_idx + 24]

        # 1. Slow Memory (API_t) & Fast Trigger (Rolling 6h Tc max)
        api_t = compute_continuous_api(past_slice, k_daily=API_DECAY_K_DAILY)
        rolling_6h_max = compute_rolling_tc_max(next_24h_slice, window_hours=TC_WINDOW_HOURS)
        total_24h = round(sum(next_24h_slice), 1)

        # Point-level SCS-CN Effective Runoff
        scs_point = compute_scs_effective_runoff(
            precip_mm=total_24h,
            api_mm=api_t,
            cn_ii_base=point["cn_ii"],
        )

        w = point["weight"]
        weighted_api_t += w * api_t
        weighted_f24h += w * total_24h
        weighted_cn_base += w * point["cn_ii"]

        if point["zone"] in ("upper", "middle"):
            if rolling_6h_max > upstream_tc_6h_max:
                upstream_tc_6h_max = rolling_6h_max
            for h in range(min(12, len(next_12h_slice))):
                upstream_hourly_12h[h] += (w / 0.90) * next_12h_slice[h]

        point_metrics.append({
            "id": point["id"],
            "name": point["name"],
            "zone": point["zone"],
            "weight": w,
            "api_t_mm": api_t,
            "rain_past_72h_mm": round(past_72h_sum, 1),
            "forecast_24h_mm": total_24h,
            "rolling_6h_tc_mm": rolling_6h_max,
            "effective_runoff_24h_mm": scs_point["effective_runoff_q_mm"],
            "next_12h_times": [t[-5:] for t in times[curr_idx : curr_idx + 12]],
        })

    # Basin-wide Deterministic Path (SCS-CN for 24h and 6h windows)
    scs_basin_24h = compute_scs_effective_runoff(
        precip_mm=weighted_f24h,
        api_mm=weighted_api_t,
        cn_ii_base=weighted_cn_base,
    )
    scs_basin_6h = compute_scs_effective_runoff(
        precip_mm=upstream_tc_6h_max,
        api_mm=weighted_api_t,
        cn_ii_base=weighted_cn_base,
    )

    q_eff_24h = scs_basin_24h["effective_runoff_q_mm"]
    q_eff_6h = scs_basin_6h["effective_runoff_q_mm"]

    # Basin-wide Probabilistic Path (GPD + Gumbel Copula Joint Return Period)
    copula_res = gumbel_copula_joint_return_period(
        p_6h_mm=upstream_tc_6h_max,
        api_mm=weighted_api_t,
        params=copula_params,
    )
    t_joint_years = copula_res["joint_return_period_years"]

    # Dual Decision Engine Tier Classification
    if (
        q_eff_24h >= 34.0
        or q_eff_6h >= 38.0
        or t_joint_years >= 9.0
    ):
        tier = "VERMELHO"
    elif (
        q_eff_24h >= 23.0
        or q_eff_6h >= 15.0
        or t_joint_years >= 2.0
    ):
        tier = "LARANJA"
    elif (
        q_eff_24h >= 8.0
        or weighted_api_t >= 60.0
        or t_joint_years >= 1.2
    ):
        tier = "AMARELO"
    else:
        tier = "VERDE"

    return {
        "risk_tier": tier,
        "weighted_api_t_mm": round(weighted_api_t, 1),
        "weighted_f24h_mm": round(weighted_f24h, 1),
        "upstream_tc_6h_mm": round(upstream_tc_6h_max, 1),
        "scs_24h": scs_basin_24h,
        "scs_6h": scs_basin_6h,
        "copula": copula_res,
        "upstream_hourly_12h": [round(val, 1) for val in upstream_hourly_12h],
        "points": point_metrics,
    }