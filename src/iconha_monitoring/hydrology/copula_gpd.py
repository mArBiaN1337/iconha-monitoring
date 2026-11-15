# src/iconha_monitoring/hydrology/copula_gpd.py
import json
import math
from pathlib import Path


def load_copula_params() -> dict:
    """Loads pre-calibrated GPD and Gumbel Copula parameters from copula_params.json."""
    param_path = Path(__file__).resolve().parent / "copula_params.json"
    with open(param_path, "r", encoding="utf-8") as f:
        return json.load(f)


def gpd_cdf(
    x: float,
    threshold_u: float,
    scale_sigma: float,
    shape_xi: float,
    exceedance_rate: float = 0.05,
) -> float:
    """Evaluates the cumulative non-exceedance probability F(x) using a POT GPD."""
    if x <= threshold_u:
        return max(0.001, (1.0 - exceedance_rate) * (x / max(threshold_u, 1.0)))

    z = (x - threshold_u) / scale_sigma
    if abs(shape_xi) < 1e-6:
        tail_prob = math.exp(-z)
    else:
        tail_prob = max(1e-9, 1.0 + shape_xi * z) ** (-1.0 / shape_xi)

    prob = 1.0 - exceedance_rate * tail_prob
    return min(max(prob, 0.0001), 0.999999)


def gumbel_copula_joint_return_period(
    p_6h_mm: float,
    api_mm: float,
    params: dict | None = None,
    events_per_year: float = 1460.0,
) -> dict:
    """
    Couples 6-hour precipitation intensity and API_t via an upper-tail-dependent
    Gumbel Copula and returns the Joint Return Period (in years).
    """
    active_params = params if params is not None else load_copula_params()

    exc_rate = float(active_params.get("exceedance_rate", 0.05))
    ev_per_yr = float(active_params.get("events_per_year", events_per_year))

    u = gpd_cdf(
        p_6h_mm,
        float(active_params["p6h_threshold_u"]),
        float(active_params["p6h_sigma"]),
        float(active_params["p6h_xi"]),
        exc_rate,
    )
    v = gpd_cdf(
        api_mm,
        float(active_params["api_threshold_u"]),
        float(active_params["api_sigma"]),
        float(active_params["api_xi"]),
        exc_rate,
    )

    theta = max(1.0, float(active_params["gumbel_theta"]))
    term_u = (-math.log(u)) ** theta
    term_v = (-math.log(v)) ** theta
    c_uv = math.exp(-((term_u + term_v) ** (1.0 / theta)))

    joint_exceedance = max(1e-7, 1.0 - u - v + c_uv)
    return_period_years = 1.0 / (ev_per_yr * joint_exceedance)

    return {
        "joint_return_period_years": round(return_period_years, 1),
        "marginal_u_p6h": round(u, 4),
        "marginal_v_api": round(v, 4),
    }