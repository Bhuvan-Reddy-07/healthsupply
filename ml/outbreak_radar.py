import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple

class CusumOutbreakRadar:
    """
    CUSUM (Cumulative Sum) Outbreak Radar.
    Consumes demand forecast residuals to detect anomalous epidemiologic demand surges
    before physical stockouts occur.
    """
    def __init__(self, k: float = 0.5, h: float = 4.0):
        """
        k: Reference parameter (slack/allowance). Typically 0.5 standard deviations.
        h: Decision interval threshold. Typically 4.0 to 5.0 (approx 3-sigma cumulative shift).
        """
        self.k = k
        self.h = h

    def monitor_stream(
        self,
        actuals: np.ndarray,
        forecasts: np.ndarray,
        baseline_window: int = 12
    ) -> Dict[str, Any]:
        """
        Runs one-sided upper CUSUM on forecast residuals e_t = y_t - y_hat_t.
        """
        y = np.asarray(actuals, dtype=float)
        y_hat = np.asarray(forecasts, dtype=float)
        assert len(y) == len(y_hat), "Actuals and forecasts must have identical lengths"

        n = len(y)
        residuals = y - y_hat

        # In-control baseline statistics
        base_len = min(baseline_window, max(3, n // 2))
        base_residuals = residuals[:base_len]
        mu = float(np.mean(base_residuals))
        sigma = float(np.std(base_residuals))
        sigma = max(1.0, sigma) # Prevent division by near-zero variance

        cusum_stat = np.zeros(n)
        alarm_idx = None
        severity = "none"

        for t in range(n):
            z_t = (residuals[t] - mu) / sigma
            prev = cusum_stat[t-1] if t > 0 else 0.0
            stat = max(0.0, prev + z_t - self.k)
            cusum_stat[t] = stat

            if stat >= self.h:
                if alarm_idx is None:
                    alarm_idx = t

                if stat >= (1.8 * self.h):
                    severity = "red"
                elif severity != "red":
                    severity = "yellow"

        return {
            "alarm_fired": alarm_idx is not None,
            "first_alarm_period": alarm_idx,
            "alarm_severity": severity,
            "max_cusum_stat": round(float(np.max(cusum_stat)), 2),
            "threshold_h": self.h,
            "residuals": [round(float(r), 2) for r in residuals],
            "cusum_values": [round(float(c), 2) for c in cusum_stat]
        }

def evaluate_outbreak_on_held_out_district(
    pre_outbreak_history: np.ndarray,
    outbreak_ramp: np.ndarray,
    control_normal: np.ndarray,
    ramp_duration_periods: int = 4
) -> Dict[str, Any]:
    """
    Validates CUSUM radar against a held-out district outbreak:
    1. Trains/calibrates baseline on pre-outbreak normal history.
    2. Proves alarm fires within the ramp window on the held-out surge series.
    3. Proves alarm does NOT fire on the normal control district (zero false positives).
    """
    radar = CusumOutbreakRadar(k=0.5, h=4.0)

    # Combine pre-outbreak + surge
    surge_series = np.concatenate([pre_outbreak_history, outbreak_ramp])
    # Expected normal forecast is the continuation of baseline mean
    baseline_level = np.mean(pre_outbreak_history)
    forecast_surge = np.full(len(surge_series), baseline_level)

    # Monitor surge series
    res_surge = radar.monitor_stream(
        actuals=surge_series,
        forecasts=forecast_surge,
        baseline_window=len(pre_outbreak_history)
    )

    # Monitor control series
    normal_series = np.concatenate([pre_outbreak_history, control_normal])
    forecast_normal = np.full(len(normal_series), baseline_level)
    res_control = radar.monitor_stream(
        actuals=normal_series,
        forecasts=forecast_normal,
        baseline_window=len(pre_outbreak_history)
    )

    start_outbreak_idx = len(pre_outbreak_history)
    first_alarm = res_surge["first_alarm_period"]

    fired_in_ramp = False
    if first_alarm is not None:
        fired_in_ramp = start_outbreak_idx <= first_alarm <= (start_outbreak_idx + ramp_duration_periods)

    return {
        "surge_detected": res_surge["alarm_fired"],
        "fired_within_ramp_window": fired_in_ramp,
        "first_alarm_offset_from_outbreak_start": (first_alarm - start_outbreak_idx) if first_alarm else None,
        "surge_severity": res_surge["alarm_severity"],
        "control_false_alarm": res_control["alarm_fired"],
        "res_surge": res_surge,
        "res_control": res_control
    }
