"""
Adaptive Drift Detection for Health Supply Demand Telemetry.
Specifically engineered to prevent spurious alert storms in low-volume rural health clinics
(5-10 transactions/week) by enforcing minimum sample thresholds and volume-adaptive Wasserstein distance bounds.
"""
import numpy as np
from scipy import stats
from typing import Dict, Any, List, Optional, Tuple

class AdaptiveDriftDetector:
    """
    Evaluates distribution drift between baseline (reference) demand distributions
    and recent production ingestion windows.
    Protects against false positives in low-volume facilities through:
    1. Hard minimum sample size gating (default N_min = 25).
    2. Adaptive Wasserstein distance thresholding scaled by sample size variance.
    3. Dual-mode statistical confirmation (Wasserstein + Kolmogorov-Smirnov test).
    """
    def __init__(
        self,
        min_sample_size: int = 25,
        base_wasserstein_threshold: float = 2.5,
        p_value_alpha: float = 0.01
    ):
        self.min_sample_size = min_sample_size
        self.base_threshold = base_wasserstein_threshold
        self.alpha = p_value_alpha

    def calculate_adaptive_threshold(self, n_ref: int, n_curr: int, ref_std: float) -> float:
        """
        Dynamically adjusts acceptable Wasserstein distance based on empirical CDF variance:
        tau = tau_base * max(1.0, ref_std * 0.2) * (1.0 + 1.5 / sqrt(n_curr))
        """
        sample_penalty = 1.0 + (1.5 / np.sqrt(max(1, n_curr)))
        scale_factor = max(1.0, float(ref_std) * 0.2)
        return float(self.base_threshold * scale_factor * sample_penalty)

    def detect_drift(
        self,
        reference_data: np.ndarray,
        current_data: np.ndarray,
        facility_id: str = "UNKNOWN",
        item_id: str = "UNKNOWN"
    ) -> Dict[str, Any]:
        """
        Evaluates drift between reference period and current period for a specific (facility, item).
        """
        n_ref = len(reference_data)
        n_curr = len(current_data)

        # 1. Low-volume gate: if current sample size < min_sample_size, refuse to raise false alarm
        if n_curr < self.min_sample_size:
            return {
                "status": "INSUFFICIENT_DATA",
                "drift_detected": False,
                "facility_id": facility_id,
                "item_id": item_id,
                "current_samples": n_curr,
                "min_required_samples": self.min_sample_size,
                "wasserstein_distance": 0.0,
                "adaptive_threshold": 0.0,
                "p_value": 1.0,
                "message": f"Sample size {n_curr} < {self.min_sample_size}: warming up, drift check deferred."
            }

        ref_clean = reference_data[~np.isnan(reference_data)]
        curr_clean = current_data[~np.isnan(current_data)]

        if len(ref_clean) < 10 or len(curr_clean) < 10:
            return {
                "status": "INSUFFICIENT_DATA",
                "drift_detected": False,
                "facility_id": facility_id,
                "item_id": item_id,
                "current_samples": len(curr_clean),
                "min_required_samples": self.min_sample_size,
                "wasserstein_distance": 0.0,
                "adaptive_threshold": 0.0,
                "p_value": 1.0,
                "message": "Too few non-NaN observations in reference or current data."
            }

        # 2. Compute 1-Wasserstein Earth Mover's Distance
        w_dist = float(stats.wasserstein_distance(ref_clean, curr_clean))

        # 3. Two-sample Kolmogorov-Smirnov test
        ks_stat, p_val = stats.ks_2samp(ref_clean, curr_clean)

        # 4. Adaptive threshold computation
        ref_std = float(np.std(ref_clean))
        adaptive_threshold = self.calculate_adaptive_threshold(n_ref, n_curr, ref_std)

        # 5. Dual criteria for drift detection:
        # Distance must exceed adaptive threshold AND p-value must reject null hypothesis (p < alpha)
        drift_detected = (w_dist > adaptive_threshold) and (float(p_val) < self.alpha)

        status = "DRIFT_DETECTED" if drift_detected else "IN_CONTROL"

        return {
            "status": status,
            "drift_detected": drift_detected,
            "facility_id": facility_id,
            "item_id": item_id,
            "current_samples": n_curr,
            "reference_samples": n_ref,
            "wasserstein_distance": round(w_dist, 4),
            "adaptive_threshold": round(adaptive_threshold, 4),
            "ks_statistic": round(float(ks_stat), 4),
            "p_value": round(float(p_val), 6),
            "message": (
                f"Drift confirmed: W1={w_dist:.2f} > threshold={adaptive_threshold:.2f} (p={p_val:.4e})"
                if drift_detected else
                f"In control: W1={w_dist:.2f} <= threshold={adaptive_threshold:.2f}"
            )
        }
