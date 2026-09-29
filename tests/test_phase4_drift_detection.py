"""
Phase 4 Verification Suite: Adaptive Drift Detection for Low-Volume Facilities.
Tests:
1. Low-volume rural facilities (5-10 transactions/week) do NOT trigger false alarms.
2. In-control high-volume facilities remain IN_CONTROL.
3. Authentic structural demand shifts (outbreaks / regime changes) reliably trigger DRIFT_DETECTED.
4. Adaptive threshold variance scaling behavior.
"""
import pytest
import numpy as np
from ml.drift_detector import AdaptiveDriftDetector

def test_low_volume_clinic_suppresses_false_alarms():
    """
    CRITICAL ACCEPTANCE TEST:
    A remote PHC clinic with only 6 transactions in the current window
    must NOT trigger spurious data drift alerts.
    """
    detector = AdaptiveDriftDetector(min_sample_size=25)
    rng = np.random.default_rng(42)

    reference_data = rng.poisson(lam=12, size=100) # Baseline distribution
    low_volume_current = rng.poisson(lam=12, size=6) # 6 transactions this week

    result = detector.detect_drift(
        reference_data=reference_data,
        current_data=low_volume_current,
        facility_id="PHC_REMOTE_01",
        item_id="MED_AMOX"
    )

    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["drift_detected"] is False
    assert result["current_samples"] == 6
    assert result["min_required_samples"] == 25
    assert "warming up" in result["message"]

def test_in_control_demand_distribution_passes():
    """
    Verifies that normal stochastic variations from the same distribution
    do not trigger drift when sample sizes are adequate.
    """
    detector = AdaptiveDriftDetector(min_sample_size=25, base_wasserstein_threshold=2.5)
    rng = np.random.default_rng(101)

    reference_data = rng.normal(loc=25.0, scale=4.0, size=200)
    current_data = rng.normal(loc=25.3, scale=4.1, size=40)

    result = detector.detect_drift(
        reference_data=reference_data,
        current_data=current_data,
        facility_id="CHC_VALLEY",
        item_id="MED_PARACETAMOL"
    )

    assert result["status"] == "IN_CONTROL"
    assert result["drift_detected"] is False
    assert result["wasserstein_distance"] <= result["adaptive_threshold"]

def test_authentic_outbreak_triggers_drift_detection():
    """
    Verifies that a genuine demand regime shift (e.g. malaria epidemic surge)
    is detected as DRIFT_DETECTED once sample threshold is satisfied.
    """
    detector = AdaptiveDriftDetector(min_sample_size=25, base_wasserstein_threshold=2.5)
    rng = np.random.default_rng(202)

    # Reference: baseline seasonal malaria cases (mean = 15)
    reference_data = rng.poisson(lam=15, size=200).astype(float)
    # Current: epidemic surge (mean = 65, >4x surge)
    outbreak_current = rng.poisson(lam=65, size=45).astype(float)

    result = detector.detect_drift(
        reference_data=reference_data,
        current_data=outbreak_current,
        facility_id="DH_KOLAR",
        item_id="MED_ARTEMETHER"
    )

    assert result["status"] == "DRIFT_DETECTED"
    assert result["drift_detected"] is True
    assert result["wasserstein_distance"] > result["adaptive_threshold"]
    assert result["p_value"] < 0.01

def test_adaptive_threshold_scales_with_sample_size():
    """
    Verifies that the threshold is higher for smaller sample sizes
    to absorb the greater variance of small empirical sample sizes.
    """
    detector = AdaptiveDriftDetector()
    t_small = detector.calculate_adaptive_threshold(n_ref=100, n_curr=30, ref_std=5.0)
    t_large = detector.calculate_adaptive_threshold(n_ref=100, n_curr=300, ref_std=5.0)

    assert t_small > t_large, "Smaller sample sizes must receive higher adaptive tolerance."
