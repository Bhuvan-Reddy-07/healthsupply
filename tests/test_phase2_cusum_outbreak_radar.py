import pytest
import numpy as np
from ml.outbreak_radar import CusumOutbreakRadar, evaluate_outbreak_on_held_out_district

def test_cusum_radar_basic_in_control_vs_shift():
    radar = CusumOutbreakRadar(k=0.5, h=4.0)

    # 1. In-control white noise: should never trigger alarm
    np.random.seed(42)
    in_control_actual = np.random.normal(loc=100.0, scale=5.0, size=24)
    in_control_forecast = np.full(24, 100.0)

    res_normal = radar.monitor_stream(in_control_actual, in_control_forecast, baseline_window=12)
    assert res_normal["alarm_fired"] is False
    assert res_normal["alarm_severity"] == "none"

    # 2. Outbreak surge: 12 baseline periods, then sudden 3x demand surge
    surge_actual = np.concatenate([
        np.full(12, 100.0),
        np.array([120.0, 160.0, 220.0, 300.0]) # Ramp
    ])
    surge_forecast = np.full(16, 100.0)

    res_surge = radar.monitor_stream(surge_actual, surge_forecast, baseline_window=12)
    assert res_surge["alarm_fired"] is True
    assert res_surge["first_alarm_period"] in [12, 13, 14] # Fired promptly inside surge ramp
    assert res_surge["alarm_severity"] == "red"

def test_outbreak_detection_proven_on_held_out_district():
    """
    CRITICAL PHASE 2 ACCEPTANCE TEST:
    Outbreak detection proven on injected ramp: radar must fire within the ramp window
    on a district it was not hand-tuned against. Hold out at least one injected outbreak from tuning.
    """
    # Baseline 16 weeks of normal clinic consumption (approx 50 units/week with minor noise)
    np.random.seed(101)
    pre_outbreak = np.array([48, 52, 49, 51, 50, 53, 47, 52, 50, 49, 51, 48, 50, 52, 49, 51], dtype=float)

    # Injected Outbreak: 4-week logistic surge ramp (held-out district: District_Omega)
    # Ramp multipliers: 1.4x, 2.1x, 3.2x, 4.0x
    outbreak_ramp = np.array([70.0, 105.0, 160.0, 200.0], dtype=float)

    # Control district (District_Alpha): continues normal consumption
    control_normal = np.array([49, 51, 50, 52], dtype=float)

    eval_result = evaluate_outbreak_on_held_out_district(
        pre_outbreak_history=pre_outbreak,
        outbreak_ramp=outbreak_ramp,
        control_normal=control_normal,
        ramp_duration_periods=4
    )

    # 1. Proves radar fires on held-out district
    assert eval_result["surge_detected"] is True, "Outbreak was not detected on held-out district!"

    # 2. Proves radar fires within the ramp window (not delayed until stockout)
    assert eval_result["fired_within_ramp_window"] is True, "Radar did not fire within ramp window!"
    assert eval_result["first_alarm_offset_from_outbreak_start"] <= 2, "Alarm must fire by week 2 of ramp!"

    # 3. Proves severity is red
    assert eval_result["surge_severity"] == "red"

    # 4. Proves zero false alarms on control district
    assert eval_result["control_false_alarm"] is False, "Control district produced false alarm!"
