# tests/test_scs_cn.py
from src.iconha_monitoring.hydrology.scs_cn import compute_scs_effective_runoff
from src.iconha_monitoring.hydrology.state_vars import (
    compute_continuous_api,
    compute_rolling_tc_max,
    compute_rolling_tc_window,
)
from src.iconha_monitoring.hydrology.decision import _classify_tier_with_hysteresis
from src.iconha_monitoring.ingestion.open_meteo import sanitize_hourly_precip


def test_zero_runoff_below_initial_abstraction():
    res = compute_scs_effective_runoff(precip_mm=5.0, api_mm=10.0, cn_ii_base=78.0)
    assert res["effective_runoff_q_mm"] == 0.0
    assert "AMC I" in res["amc_class"]


def test_high_runoff_under_saturated_amc_iii():
    dry = compute_scs_effective_runoff(precip_mm=80.0, api_mm=10.0, cn_ii_base=78.0)
    wet = compute_scs_effective_runoff(precip_mm=80.0, api_mm=85.0, cn_ii_base=78.0)
    deep_sat = compute_scs_effective_runoff(precip_mm=80.0, api_mm=130.0, cn_ii_base=78.0)
    assert wet["effective_runoff_q_mm"] > dry["effective_runoff_q_mm"]
    assert deep_sat["cn_effective"] > wet["cn_effective"]
    assert "AMC III" in wet["amc_class"]


def test_tropical_initial_abstraction_ratio_sensitivity():
    # Moderate 18mm burst on moist soil (API=55mm) triggers runoff with Ia=0.05S vs 0.20S
    trop = compute_scs_effective_runoff(precip_mm=18.0, api_mm=55.0, cn_ii_base=79.0, ia_ratio=0.05)
    classic = compute_scs_effective_runoff(precip_mm=18.0, api_mm=55.0, cn_ii_base=79.0, ia_ratio=0.20)
    assert trop["effective_runoff_q_mm"] > classic["effective_runoff_q_mm"]


def test_continuous_api_daily_decay_consistency():
    # 100 mm pulse followed by 24 hours of dry weather should decay by k_daily = 0.88
    series = [100.0] + [0.0] * 24
    assert compute_continuous_api(series, k_daily=0.88) == 88.0


def test_rolling_tc_max_and_edge_cases():
    assert compute_rolling_tc_max([], window_hours=6) == 0.0
    assert compute_rolling_tc_max([2.0, 3.0], window_hours=6) == 5.0
    assert compute_rolling_tc_max([1.0, 5.0, 10.0, 10.0, 5.0, 1.0, 0.0, 0.0], window_hours=3) == 25.0
    win = compute_rolling_tc_window(
        [1.0, 10.0, 15.0, 2.0],
        ["2026-11-18T18:00", "2026-11-18T19:00", "2026-11-18T20:00", "2026-11-18T21:00"],
        window_hours=2,
    )
    assert win["max_mm"] == 25.0
    assert win["peak_window"] == "19:00 às 21:00"
    # Negative or extreme CN values should be safely clamped without division by zero
    extreme = compute_scs_effective_runoff(precip_mm=-5.0, api_mm=-10.0, cn_ii_base=105.0)
    assert extreme["effective_runoff_q_mm"] == 0.0


def test_deescalation_hysteresis_and_missing_slot_interpolation():
    # Once in VERMELHO, a minor dip to Q_eff_24h = 32.0 (>= 30.6 deadband) stays VERMELHO
    held = _classify_tier_with_hysteresis(
        q_eff_24h=32.0, q_eff_6h=10.0, t_joint_years=1.5, weighted_api_t=50.0, previous_tier="VERMELHO"
    )
    assert held == "VERMELHO"
    # Dropping below 30.6 de-escalates cleanly to LARANJA
    dropped = _classify_tier_with_hysteresis(
        q_eff_24h=28.0, q_eff_6h=10.0, t_joint_years=1.5, weighted_api_t=50.0, previous_tier="VERMELHO"
    )
    assert dropped == "LARANJA"

    # Isolated None gap between 4.0 and 8.0 interpolates to 6.0
    cleaned = sanitize_hourly_precip([4.0, None, 8.0], raw_prob=[50, 50, 50], zone="lower")
    assert cleaned == [4.0, 6.0, 8.0]