# src/iconha_monitoring/hydrology/copula_gpd.py
from functools import lru_cache
import json
import math
from pathlib import Path


@lru_cache(maxsize=1)
def _load_copula_params_cached() -> dict:
    param_path = Path(__file__).resolve().parent / "copula_params.json"
    with open(param_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_copula_params() -> dict:
    """Loads pre-calibrated GPD and Gumbel Copula parameters from copula_params.json."""
    return dict(_load_copula_params_cached())


def gpd_survival(
    x: float,
    threshold_u: float,
    scale_sigma: float,
    shape_xi: float,
    exceedance_rate: float = 0.05,
) -> float:
    """
    Evaluates the upper-tail exceedance (survival) probability S(x) = 1 - F(x)
    using a Peaks-Over-Threshold Generalized Pareto Distribution without
    premature 1 - 1e-6 clamping that causes catastrophic cancellation.
    """
    x_val = max(0.0, float(x or 0.0))
    sigma_safe = max(float(scale_sigma), 1e-6)
    exc_safe = min(max(float(exceedance_rate), 1e-6), 0.999)

    if x_val <= threshold_u:
        f_sub = max(0.001, (1.0 - exc_safe) * (x_val / max(threshold_u, 1.0)))
        return min(max(1.0 - f_sub, exc_safe), 0.999)

    z = (x_val - threshold_u) / sigma_safe
    if abs(shape_xi) < 1e-6:
        tail_prob = math.exp(-z)
    else:
        tail_prob = max(1e-12, 1.0 + shape_xi * z) ** (-1.0 / shape_xi)

    return min(max(exc_safe * tail_prob, 1e-12), 0.999)


def gpd_cdf(
    x: float,
    threshold_u: float,
    scale_sigma: float,
    shape_xi: float,
    exceedance_rate: float = 0.05,
) -> float:
    """Evaluates the cumulative non-exceedance probability F(x) using a POT GPD."""
    s_val = gpd_survival(x, threshold_u, scale_sigma, shape_xi, exceedance_rate)
    return min(max(1.0 - s_val, 0.0001), 0.999999999)


def gumbel_copula_joint_return_period(
    p_6h_mm: float,
    api_mm: float,
    params: dict | None = None,
    events_per_year: float = 120.0,
) -> dict:
    """
    Couples 6-hour precipitation intensity and API_t via an upper-tail-dependent
    Gumbel-Hougaard Copula evaluated in log-survival space (log1p / expm1) to prevent
    floating-point cancellation, returning the Joint Return Period (in years).
    """
    active_params = params if params is not None else load_copula_params()

    exc_rate = float(active_params.get("exceedance_rate", 0.05))
    ev_per_yr = max(1e-6, float(active_params.get("events_per_year", events_per_year)))

    u_bar = gpd_survival(
        p_6h_mm,
        float(active_params["p6h_threshold_u"]),
        float(active_params["p6h_sigma"]),
        float(active_params["p6h_xi"]),
        exc_rate,
    )
    v_bar = gpd_survival(
        api_mm,
        float(active_params["api_threshold_u"]),
        float(active_params["api_sigma"]),
        float(active_params["api_xi"]),
        exc_rate,
    )

    u = 1.0 - u_bar
    v = 1.0 - v_bar

    theta = max(1.0, float(active_params["gumbel_theta"]))
    # -ln(u) = -ln(1 - u_bar) = -log1p(-u_bar), preserving precision when u_bar -> 0
    neg_log_u = max(1e-15, -math.log1p(-u_bar))
    neg_log_v = max(1e-15, -math.log1p(-v_bar))

    a_val = ((neg_log_u ** theta) + (neg_log_v ** theta)) ** (1.0 / theta)
    # 1 - u - v + C(u,v) = u_bar + v_bar + (exp(-a_val) - 1) = u_bar + v_bar + expm1(-a_val)
    joint_exceedance = max(1e-12, u_bar + v_bar + math.expm1(-a_val), u_bar * v_bar)
    return_period_years = 1.0 / (ev_per_yr * joint_exceedance)

    return {
        "joint_return_period_years": round(max(0.1, return_period_years), 1),
        "marginal_u_p6h": round(u, 4),
        "marginal_v_api": round(v, 4),
    }