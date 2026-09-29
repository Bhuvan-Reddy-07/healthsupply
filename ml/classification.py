import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List

ADI_CUTOFF = 1.32
CV2_CUTOFF = 0.49

def compute_syntetos_boylan_metrics(demand: np.ndarray) -> Tuple[float, float, str, str]:
    """
    Computes Average Demand Interval (ADI) and Square Coefficient of Variation (CV^2).
    Classifies demand series into Syntetos-Boylan categories:
      - Smooth:       ADI < 1.32,  CV^2 < 0.49  --> Route: LightGBM
      - Erratic:      ADI < 1.32,  CV^2 >= 0.49 --> Route: LightGBM
      - Intermittent: ADI >= 1.32, CV^2 < 0.49  --> Route: Croston SBA
      - Lumpy:        ADI >= 1.32, CV^2 >= 0.49 --> Route: Croston SBA
    """
    arr = np.asarray(demand, dtype=float)
    non_zero_idx = np.where(arr > 0)[0]

    if len(non_zero_idx) < 2:
        # Extremely sparse: default to intermittent / Croston SBA
        adi = float(len(arr)) if len(non_zero_idx) == 0 else float(len(arr)) / max(1, len(non_zero_idx))
        cv2 = 0.0
        return round(adi, 2), round(cv2, 4), "Intermittent", "Croston SBA"

    intervals = np.diff(non_zero_idx)
    adi = float(np.mean(intervals))

    non_zero_vals = arr[non_zero_idx]
    mean_val = float(np.mean(non_zero_vals))
    std_val = float(np.std(non_zero_vals))
    cv2 = float((std_val / mean_val) ** 2) if mean_val > 0 else 0.0

    if adi < ADI_CUTOFF:
        if cv2 < CV2_CUTOFF:
            category = "Smooth"
            model = "LightGBM"
        else:
            category = "Erratic"
            model = "LightGBM"
    else:
        if cv2 < CV2_CUTOFF:
            category = "Intermittent"
            model = "Croston SBA"
        else:
            category = "Lumpy"
            model = "Croston SBA"

    return round(adi, 2), round(cv2, 4), category, model

def classify_demand_series(series_dict: Dict[str, np.ndarray]) -> pd.DataFrame:
    """
    Classifies a dictionary of item or facility-item demand series.
    Returns structured DataFrame with routing decisions.
    """
    records = []
    for item_key, series in series_dict.items():
        adi, cv2, category, model = compute_syntetos_boylan_metrics(series)
        non_zero_ratio = float(np.mean(np.asarray(series) > 0))
        records.append({
            "item_key": item_key,
            "adi": adi,
            "cv2": cv2,
            "non_zero_ratio": round(non_zero_ratio, 3),
            "category": category,
            "routed_model": model
        })

    df = pd.DataFrame(records)
    return df
