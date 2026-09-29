import numpy as np
from typing import Dict, Any, Tuple

def seasonal_naive(series: np.ndarray, horizon: int = 4, season_length: int = 12) -> np.ndarray:
    """
    Seasonal Naive baseline forecaster:
    Repeats the value observed at the same point in the previous seasonal cycle.
    """
    arr = np.asarray(series, dtype=float)
    n = len(arr)
    if n == 0:
        return np.zeros(horizon)

    if n >= season_length:
        forecasts = []
        for h in range(horizon):
            idx = n - season_length + (h % season_length)
            forecasts.append(arr[idx])
        return np.array(forecasts)
    else:
        # Fallback to last observed value
        return np.full(horizon, arr[-1])

def croston_sba(series: np.ndarray, horizon: int = 4, alpha: float = 0.1) -> np.ndarray:
    """
    Croston's Method with Syntetos-Boylan Approximation (SBA).
    Specifically tailored for intermittent and lumpy demand profiles.
    Corrects the inherent positive bias of standard Croston by multiplying by (1 - alpha/2).
    """
    arr = np.asarray(series, dtype=float)
    non_zero_indices = np.where(arr > 0)[0]

    if len(non_zero_indices) == 0:
        return np.zeros(horizon)

    # Initialize at first non-zero demand
    first_idx = non_zero_indices[0]
    z = arr[first_idx] # smoothed demand magnitude
    p = max(1.0, float(first_idx + 1)) # smoothed inter-demand interval
    q = 1.0 # counter of periods since last non-zero demand

    for t in range(first_idx + 1, len(arr)):
        y_t = arr[t]
        if y_t > 0:
            z = alpha * y_t + (1.0 - alpha) * z
            p = alpha * q + (1.0 - alpha) * p
            q = 1.0
        else:
            q += 1.0

    # Point forecast using Syntetos-Boylan debiasing factor
    sba_factor = 1.0 - (alpha / 2.0)
    point_forecast = max(0.0, sba_factor * (z / max(1e-4, p)))

    return np.full(horizon, point_forecast)

def calc_smape(actual: np.ndarray, predicted: np.ndarray, eps: float = 1e-4) -> float:
    """
    Symmetric Mean Absolute Percentage Error (sMAPE) in percentage [0, 200%].
    sMAPE = (200 / n) * sum(|actual - predicted| / (|actual| + |predicted| + eps))
    """
    act = np.asarray(actual, dtype=float)
    pred = np.asarray(predicted, dtype=float)
    denom = np.abs(act) + np.abs(pred) + eps
    return float(np.mean(200.0 * np.abs(act - pred) / denom))

def calc_mase(actual: np.ndarray, predicted: np.ndarray, train_history: np.ndarray) -> float:
    """
    Mean Absolute Scaled Error (MASE).
    Scales MAE by the in-sample mean absolute difference of a 1-step naive forecast.
    """
    act = np.asarray(actual, dtype=float)
    pred = np.asarray(predicted, dtype=float)
    mae = np.mean(np.abs(act - pred))

    train = np.asarray(train_history, dtype=float)
    if len(train) < 2:
        return float(mae)

    naive_errors = np.mean(np.abs(np.diff(train)))
    if naive_errors < 1e-4:
        return float(mae)

    return float(mae / naive_errors)
