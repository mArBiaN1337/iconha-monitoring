def compute_continuous_api(hourly_past_precip: list[float], k_daily: float = 0.88) -> float:
    """
    Computes State Variable 1: Antecedent Precipitation Index (API_t)
    over a rolling 14-day (336-hour) window using hourly decay derived from k_daily.
    """
    k_clamped = min(max(float(k_daily), 1e-6), 1.0)
    k_hourly = k_clamped ** (1.0 / 24.0)
    api = 0.0
    for p_t in hourly_past_precip:
        val = max(0.0, float(p_t or 0.0))
        api = (k_hourly * api) + val
    return round(api, 2)


def compute_rolling_tc_window(
    hourly_precip: list[float],
    hourly_times: list[str] | None = None,
    window_hours: int = 6,
) -> dict:
    """
    Computes State Variable 2: Maximum rolling N-hour accumulated precipitation
    matching the basin's Time of Concentration (Tc = 3h to 6h) along with the
    clock window (e.g. '19:00 às 01:00') where the peak occurs.
    """
    if not hourly_precip:
        return {"max_mm": 0.0, "peak_window": "--:-- às --:--", "peak_start_idx": 0}

    w = max(1, int(window_hours))
    clean = [max(0.0, float(x or 0.0)) for x in hourly_precip]

    if len(clean) <= w:
        start_label = hourly_times[0][-5:] if hourly_times else "00:00"
        end_label = hourly_times[-1][-5:] if hourly_times else "06:00"
        return {
            "max_mm": round(sum(clean), 2),
            "peak_window": f"{start_label} às {end_label}",
            "peak_start_idx": 0,
        }

    best_idx = 0
    best_sum = -1.0
    for i in range(len(clean) - w + 1):
        window_sum = sum(clean[i : i + w])
        if window_sum > best_sum:
            best_sum = window_sum
            best_idx = i

    if hourly_times and len(hourly_times) >= best_idx + w:
        start_hr = hourly_times[best_idx][-5:]
        end_idx = min(len(hourly_times) - 1, best_idx + w)
        end_hr = hourly_times[end_idx][-5:]
        peak_window = f"{start_hr} às {end_hr}"
    else:
        peak_window = "--:-- às --:--"

    return {
        "max_mm": round(best_sum, 2),
        "peak_window": peak_window,
        "peak_start_idx": best_idx,
    }


def compute_rolling_tc_max(hourly_forecast_precip: list[float], window_hours: int = 6) -> float:
    """
    Computes State Variable 2: Maximum rolling N-hour accumulated precipitation
    matching the basin's Time of Concentration (Tc = 3h to 6h).
    """
    return compute_rolling_tc_window(
        hourly_precip=hourly_forecast_precip,
        hourly_times=None,
        window_hours=window_hours,
    )["max_mm"]