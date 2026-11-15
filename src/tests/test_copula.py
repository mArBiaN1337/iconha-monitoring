# tests/test_copula.py
from src.iconha_monitoring.hydrology.copula_gpd import gumbel_copula_joint_return_period

SAMPLE_PARAMS = {
    "exceedance_rate": 0.05,
    "events_per_year": 1460.0,
    "p6h_threshold_u": 14.5,
    "p6h_sigma": 11.2,
    "p6h_xi": 0.18,
    "api_threshold_u": 48.0,
    "api_sigma": 19.5,
    "api_xi": 0.08,
    "gumbel_theta": 1.45,
}


def test_return_period_increases_with_compound_extremes():
    normal = gumbel_copula_joint_return_period(
        p_6h_mm=5.0, api_mm=15.0, params=SAMPLE_PARAMS
    )
    extreme = gumbel_copula_joint_return_period(
        p_6h_mm=95.0, api_mm=90.0, params=SAMPLE_PARAMS
    )
    assert extreme["joint_return_period_years"] > normal["joint_return_period_years"]
    assert extreme["joint_return_period_years"] >= 10.0


def test_default_copula_params_file_loader():
    res = gumbel_copula_joint_return_period(p_6h_mm=10.0, api_mm=20.0)
    assert "joint_return_period_years" in res