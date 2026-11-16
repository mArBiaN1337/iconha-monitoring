# tests/test_scs_cn.py
from src.iconha_monitoring.hydrology.scs_cn import compute_scs_effective_runoff
from src.iconha_monitoring.hydrology.state_vars import (
    compute_continuous_api,
    compute_rolling_tc_max,
)


def test_zero_runoff_below_initial_abstraction():
    res = compute_scs_effective_runoff(precip_mm=5.0, api_mm=10.0, cn_ii_base=78.0)
    assert res["effective_runoff_q_mm"] == 0.0
    assert "AMC I" in res["amc_class"]


def test_high_runoff_under_saturated_amc_iii():
    dry = compute_scs_effective_runoff(precip_mm=80.0, api_mm=10.0, cn_ii_base=78.0)
    wet = compute_scs_effective_runoff(precip_mm=80.0, api_mm=85.0, cn_ii_base=78.0)
    assert wet["effective_runoff_q_mm"] > dry["effective_runoff_q_mm"]
    assert "AMC III" in wet["amc_class"]


def test_continuous_api_daily_decay_consistency():
    # 100 mm pulse followed by 24 hours of dry weather should decay by k_daily = 0.88
    series = [100.0] + [0.0] * 24
    assert compute_continuous_api(series, k_daily=0.88) == 88.0


def test_rolling_tc_max_and_edge_cases():
    assert compute_rolling_tc_max([], window_hours=6) == 0.0
    assert compute_rolling_tc_max([2.0, 3.0], window_hours=6) == 5.0
    assert compute_rolling_tc_max([1.0, 5.0, 10.0, 10.0, 5.0, 1.0, 0.0, 0.0], window_hours=3) == 25.0
    # Negative or extreme CN values should be safely clamped without division by zero
    extreme = compute_scs_effective_runoff(precip_mm=-5.0, api_mm=-10.0, cn_ii_base=105.0)
    assert extreme["effective_runoff_q_mm"] == 0.0