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


def compute_rolling_tc_max(hourly_forecast_precip: list[float], window_hours: int = 6) -> float:
    """
    Computes State Variable 2: Maximum rolling N-hour accumulated precipitation
    matching the basin's Time of Concentration (Tc = 3h to 6h).
    """
    if not hourly_forecast_precip:
        return 0.0
    w = max(1, int(window_hours))
    clean = [max(0.0, float(x or 0.0)) for x in hourly_forecast_precip]
    if len(clean) <= w:
        return round(sum(clean), 2)

    max_accum = max(
        sum(clean[i : i + w])
        for i in range(len(clean) - w + 1)
    )
    return round(max_accum, 2)