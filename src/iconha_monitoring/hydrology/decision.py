from datetime import datetime
from src.iconha_monitoring.config import (
    BASIN_POINTS,
    API_DECAY_K_DAILY,
    TC_WINDOW_HOURS,
    HYSTERESIS_DEESCALATION_FACTOR,
    TZ_BR,
)
from src.iconha_monitoring.hydrology.state_vars import (
    compute_continuous_api,
    compute_rolling_tc_window,
)
from src.iconha_monitoring.hydrology.scs_cn import compute_scs_effective_runoff
from src.iconha_monitoring.hydrology.copula_gpd import (
    load_copula_params,
    gumbel_copula_joint_return_period,
)
from src.iconha_monitoring.ingestion.open_meteo import sanitize_hourly_precip

TIER_RANK = {"VERDE": 0, "AMARELO": 1, "LARANJA": 2, "VERMELHO": 3}


def _resolve_current_hour_index(times: list[str], now_str: str) -> int:
    """
    [HYDRO-07] Resolves the index corresponding to `now_str` in the hourly time array.
    Falls back to the latest timestamp <= now_str rather than midnight (len - 48).
    """
    if not times:
        return 0
    try:
        return times.index(now_str)
    except ValueError:
        pass

    candidate_idx = -1
    for i, t_str in enumerate(times):
        if t_str <= now_str:
            candidate_idx = i
        else:
            break

    if candidate_idx >= 0:
        return candidate_idx
    return min(336, max(0, len(times) - 48))


def _classify_tier_with_hysteresis(
    q_eff_24h: float,
    q_eff_6h: float,
    t_joint_years: float,
    weighted_api_t: float,
    previous_tier: str | None = None,
) -> str:
    """
    [HYDRO-03] & [HYDRO-06] Dual Decision Engine Tier Classifier with fixed 6h fast-trigger
    threshold (24.0 mm for VERMELHO) and 10% deadband hysteresis on de-escalation.
    """
    if (
        q_eff_24h >= 34.0
        or q_eff_6h >= 24.0
        or t_joint_years >= 9.0
    ):
        raw_tier = "VERMELHO"
    elif (
        q_eff_24h >= 23.0
        or q_eff_6h >= 15.0
        or t_joint_years >= 2.0
    ):
        raw_tier = "LARANJA"
    elif (
        q_eff_24h >= 8.0
        or q_eff_6h >= 5.0
        or weighted_api_t >= 60.0
        or t_joint_years >= 1.2
    ):
        raw_tier = "AMARELO"
    else:
        raw_tier = "VERDE"

    prev = (previous_tier or "").upper()
    if prev not in TIER_RANK or TIER_RANK[raw_tier] >= TIER_RANK[prev]:
        return raw_tier

    h = HYSTERESIS_DEESCALATION_FACTOR  # 0.90 deadband factor
    if prev == "VERMELHO" and (
        q_eff_24h >= 34.0 * h
        or q_eff_6h >= 24.0 * h
        or t_joint_years >= 9.0 * h
    ):
        return "VERMELHO"

    if prev in ("VERMELHO", "LARANJA") and TIER_RANK[raw_tier] < TIER_RANK["LARANJA"] and (
        q_eff_24h >= 23.0 * h
        or q_eff_6h >= 15.0 * h
        or t_joint_years >= 2.0 * h
    ):
        return "LARANJA"

    if prev in ("VERMELHO", "LARANJA", "AMARELO") and raw_tier == "VERDE" and (
        q_eff_24h >= 8.0 * h
        or q_eff_6h >= 5.0 * h
        or weighted_api_t >= 60.0 * h
        or t_joint_years >= 1.2 * h
    ):
        return "AMARELO"

    return raw_tier


def _compute_hydro_trend(
    past_6h_up: float,
    next_6h_up: float,
    after_6h_up: float,
    q_eff_24h: float,
) -> tuple[str, str]:
    """
    [UI-01] Determines whether basin hydrological risk is RISING, PEAKING, RECEDING, or STABLE.
    """
    if next_6h_up >= 10.0 and next_6h_up >= past_6h_up and next_6h_up >= after_6h_up:
        return "PEAKING", "⚠ Pico previsto nas próx. 6h"
    if (
        next_6h_up > past_6h_up + 2.0
        or after_6h_up > next_6h_up + 2.5
        or (q_eff_24h >= 10.0 and next_6h_up >= 4.0)
    ):
        return "RISING", "↗ Subindo nas próx. 6h"
    if past_6h_up >= 4.0 and past_6h_up > next_6h_up + 2.0 and after_6h_up <= next_6h_up + 1.0:
        return "RECEDING", "↘ Recuando nas cabeceiras"
    return "STABLE", "→ Tendência Estável"


def evaluate_basin_hydrology(
    raw_locations: list[dict],
    previous_tier: str | None = None,
) -> dict:
    """
    Runs the Dual Decision Engine (SCS-CN + GPD/Gumbel Copula) across all 4 basin points
    with kinematic wave lag routing, distributed runoff integration, cross-boundary Tc windows,
    and de-escalation hysteresis.
    """
    now_str = datetime.now(TZ_BR).strftime("%Y-%m-%dT%H:00")
    copula_params = load_copula_params()

    point_metrics = []
    weighted_api_t = 0.0
    weighted_f24h = 0.0
    weighted_cn_base = 0.0
    distributed_q_eff_24h = 0.0
    distributed_q_eff_6h = 0.0

    upstream_past_6h = 0.0
    upstream_past_72h = 0.0
    upstream_next_6h = 0.0
    upstream_after_6h = 0.0

    max_node_upstream_6h = 0.0
    best_peak_window = "--:-- às --:--"
    upstream_hourly_12h = [0.0] * 12

    # Kinematic wave routed upstream series straddling [-5h .. +23h] around curr_idx (29 hours)
    STRADDLE_PAST = TC_WINDOW_HOURS - 1  # 5 hours prior to curr_idx
    ROUTED_LEN = STRADDLE_PAST + 24
    routed_upstream_series = [0.0] * ROUTED_LEN
    routed_upstream_times: list[str] = []

    # Observed (-3h..-1h) + Forecast (0h..+8h) 12-bar split timeline for UI-02
    OBS_BARS = 3
    FUT_BARS = 9
    timeline_12h_mm = [0.0] * (OBS_BARS + FUT_BARS)
    timeline_12h_hours: list[str] = []

    for idx, point in enumerate(BASIN_POINTS):
        loc_data = raw_locations[idx]["hourly"]
        times = loc_data["time"]
        raw_precip = loc_data.get("precipitation", [])
        raw_prob = loc_data.get("precipitation_probability")
        precip = sanitize_hourly_precip(raw_precip, raw_prob, zone=point["zone"])

        curr_idx = _resolve_current_hour_index(times, now_str)

        past_slice = precip[max(0, curr_idx - 336) : curr_idx]  # Past 14 days (336h)
        past_72h_sum = sum(precip[max(0, curr_idx - 72) : curr_idx])
        past_24h_sum = sum(precip[max(0, curr_idx - 24) : curr_idx])
        past_6h_sum = sum(precip[max(0, curr_idx - 6) : curr_idx])

        next_12h_slice = precip[curr_idx : curr_idx + 12]
        next_24h_slice = precip[curr_idx : curr_idx + 24]

        # [HYDRO-04] Straddling 6h Tc slice [curr_idx - 5 : curr_idx + 24] so active storms aren't cut in half
        tc_start = max(0, curr_idx - STRADDLE_PAST)
        tc_end = min(len(precip), curr_idx + 24)
        tc_slice = precip[tc_start:tc_end]
        tc_times = times[tc_start:tc_end]

        # 1. Slow Memory (API_t) & Fast Trigger (Rolling 6h Tc max + peak clock window)
        api_t = compute_continuous_api(past_slice, k_daily=API_DECAY_K_DAILY)
        tc_info = compute_rolling_tc_window(tc_slice, tc_times, window_hours=TC_WINDOW_HOURS)
        rolling_6h_max = tc_info["max_mm"]
        total_24h = round(sum(next_24h_slice), 1)

        # Point-level SCS-CN Effective Runoff (24h and 6h)
        scs_point_24h = compute_scs_effective_runoff(
            precip_mm=total_24h,
            api_mm=api_t,
            cn_ii_base=point["cn_ii"],
        )
        scs_point_6h = compute_scs_effective_runoff(
            precip_mm=rolling_6h_max,
            api_mm=api_t,
            cn_ii_base=point["cn_ii"],
        )

        w = point["weight"]
        lag = int(point.get("lag_hours", 0))

        weighted_api_t += w * api_t
        weighted_f24h += w * total_24h
        weighted_cn_base += w * point["cn_ii"]
        distributed_q_eff_24h += w * scs_point_24h["effective_runoff_q_mm"]
        distributed_q_eff_6h += w * scs_point_6h["effective_runoff_q_mm"]

        if idx == 0:
            routed_upstream_times = [
                times[max(0, min(len(times) - 1, curr_idx - STRADDLE_PAST + k))]
                for k in range(ROUTED_LEN)
            ]
            timeline_12h_hours = [
                times[max(0, min(len(times) - 1, curr_idx - OBS_BARS + k))][-5:]
                for k in range(OBS_BARS + FUT_BARS)
            ]

        if point["zone"] in ("upper", "middle"):
            up_w = w / 0.90
            upstream_past_6h += up_w * past_6h_sum
            upstream_past_72h += up_w * past_72h_sum
            upstream_next_6h += up_w * sum(next_12h_slice[:6])
            upstream_after_6h += up_w * sum(next_12h_slice[6:12])

            if rolling_6h_max > max_node_upstream_6h:
                max_node_upstream_6h = rolling_6h_max
                best_peak_window = tc_info["peak_window"]

            for h in range(min(12, len(next_12h_slice))):
                upstream_hourly_12h[h] += up_w * next_12h_slice[h]

            # [HYDRO-03] Kinematic wave lag routing P_routed(t) = sum_i (w_i / 0.90) * P_i(t - tau_i)
            for k in range(ROUTED_LEN):
                target_hr = curr_idx - STRADDLE_PAST + k - lag
                if 0 <= target_hr < len(precip):
                    routed_upstream_series[k] += up_w * precip[target_hr]

            # [UI-02] Split timeline: 3 observed past hours + 9 forecast hours
            for k in range(OBS_BARS + FUT_BARS):
                src_hr = curr_idx - OBS_BARS + k
                if 0 <= src_hr < len(precip):
                    timeline_12h_mm[k] += up_w * precip[src_hr]

        point_metrics.append({
            "id": point["id"],
            "name": point["name"],
            "zone": point["zone"],
            "weight": w,
            "lag_hours": lag,
            "api_t_mm": api_t,
            "rain_past_6h_mm": round(past_6h_sum, 1),
            "rain_past_24h_mm": round(past_24h_sum, 1),
            "rain_past_72h_mm": round(past_72h_sum, 1),
            "forecast_24h_mm": total_24h,
            "rolling_6h_tc_mm": rolling_6h_max,
            "peak_6h_window": tc_info["peak_window"],
            "effective_runoff_24h_mm": scs_point_24h["effective_runoff_q_mm"],
            "effective_runoff_6h_mm": scs_point_6h["effective_runoff_q_mm"],
            "next_12h_times": [t[-5:] for t in times[curr_idx : curr_idx + 12]],
        })

    # Evaluate routed kinematic wave 6-hour peak arriving at lower valley
    routed_tc_info = compute_rolling_tc_window(
        routed_upstream_series,
        routed_upstream_times,
        window_hours=TC_WINDOW_HOURS,
    )
    if routed_tc_info["max_mm"] >= max_node_upstream_6h:
        upstream_tc_6h_max = routed_tc_info["max_mm"]
        if routed_tc_info["peak_window"] != "--:-- às --:--":
            best_peak_window = routed_tc_info["peak_window"]
    else:
        upstream_tc_6h_max = max_node_upstream_6h

    # Basin-wide Deterministic Path (SCS-CN for 24h and 6h windows + distributed point integration)
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

    # [HYDRO-03] Eliminate Jensen's Inequality spatial dilution by taking max of distributed vs lumped runoff
    q_eff_24h = round(max(distributed_q_eff_24h, scs_basin_24h["effective_runoff_q_mm"]), 1)
    q_eff_6h = round(max(distributed_q_eff_6h, scs_basin_6h["effective_runoff_q_mm"]), 1)
    scs_basin_24h["effective_runoff_q_mm"] = q_eff_24h
    scs_basin_6h["effective_runoff_q_mm"] = q_eff_6h

    # Basin-wide Probabilistic Path (GPD + Gumbel Copula Joint Return Period)
    copula_res = gumbel_copula_joint_return_period(
        p_6h_mm=upstream_tc_6h_max,
        api_mm=weighted_api_t,
        params=copula_params,
    )
    t_joint_years = copula_res["joint_return_period_years"]

    # Dual Decision Engine Tier Classification with De-escalation Hysteresis
    tier = _classify_tier_with_hysteresis(
        q_eff_24h=q_eff_24h,
        q_eff_6h=q_eff_6h,
        t_joint_years=t_joint_years,
        weighted_api_t=weighted_api_t,
        previous_tier=previous_tier,
    )

    trend_state, trend_label = _compute_hydro_trend(
        past_6h_up=upstream_past_6h,
        next_6h_up=upstream_next_6h,
        after_6h_up=upstream_after_6h,
        q_eff_24h=q_eff_24h,
    )

    chart_timeline_12h = [
        {
            "hour": timeline_12h_hours[k] if k < len(timeline_12h_hours) else "--:--",
            "mm": round(timeline_12h_mm[k], 1),
            "kind": "observed" if k < OBS_BARS else "forecast",
            "is_now": k == OBS_BARS,
        }
        for k in range(OBS_BARS + FUT_BARS)
    ]

    return {
        "risk_tier": tier,
        "trend_state": trend_state,
        "trend_label": trend_label,
        "peak_6h_window": best_peak_window,
        "weighted_api_t_mm": round(weighted_api_t, 1),
        "weighted_f24h_mm": round(weighted_f24h, 1),
        "upstream_tc_6h_mm": round(upstream_tc_6h_max, 1),
        "routed_tc_6h_mm": round(routed_tc_info["max_mm"], 1),
        "upstream_past_6h_mm": round(upstream_past_6h, 1),
        "upstream_past_72h_mm": round(upstream_past_72h, 1),
        "scs_24h": scs_basin_24h,
        "scs_6h": scs_basin_6h,
        "copula": copula_res,
        "upstream_hourly_12h": [round(val, 1) for val in upstream_hourly_12h],
        "chart_timeline_12h": chart_timeline_12h,
        "points": point_metrics,
    }