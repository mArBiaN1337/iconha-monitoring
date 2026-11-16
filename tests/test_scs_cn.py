# tests/test_scs_cn.py
from src.iconha_monitoring.hydrology.scs_cn import compute_scs_effective_runoff


def test_zero_runoff_below_initial_abstraction():
    res = compute_scs_effective_runoff(precip_mm=5.0, api_mm=10.0, cn_ii_base=78.0)
    assert res["effective_runoff_q_mm"] == 0.0
    assert "AMC I" in res["amc_class"]


def test_high_runoff_under_saturated_amc_iii():
    dry = compute_scs_effective_runoff(precip_mm=80.0, api_mm=10.0, cn_ii_base=78.0)
    wet = compute_scs_effective_runoff(precip_mm=80.0, api_mm=85.0, cn_ii_base=78.0)
    assert wet["effective_runoff_q_mm"] > dry["effective_runoff_q_mm"]
    assert "AMC III" in wet["amc_class"]