def compute_continuous_api(hourly_past_precip: list[float], k_daily: float = 0.88) -> float:
    """
    Computes State Variable 1: Antecedent Precipitation Index (API_t)
    over a rolling 14-day (336-hour) window using hourly decay derived from k_daily.
    """
    k_hourly = k_daily ** (1.0 / 24.0)
    api = 0.0
    for p_t in hourly_past_precip:
        api = (k_hourly * api) + p_t
    return round(api, 2)


def compute_rolling_tc_max(hourly_forecast_precip: list[float], window_hours: int = 6) -> float:
    """
    Computes State Variable 2: Maximum rolling N-hour accumulated precipitation
    matching the basin's Time of Concentration (Tc = 3h to 6h).
    """
    if not hourly_forecast_precip:
        return 0.0
    if len(hourly_forecast_precip) <= window_hours:
        return round(sum(hourly_forecast_precip), 2)

    max_accum = max(
        sum(hourly_forecast_precip[i : i + window_hours])
        for i in range(len(hourly_forecast_precip) - window_hours + 1)
    )
    return round(max_accum, 2)