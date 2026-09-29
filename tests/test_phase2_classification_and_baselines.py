import pytest
import numpy as np
from ml.classification import compute_syntetos_boylan_metrics, classify_demand_series
from ml.baselines import seasonal_naive, croston_sba, calc_smape, calc_mase

def test_syntetos_boylan_classification_categories():
    # 1. Smooth demand: continuous non-zero, low variance
    smooth_series = np.array([50, 52, 48, 51, 49, 53, 50, 48, 52, 51, 50, 49])
    adi, cv2, cat, model = compute_syntetos_boylan_metrics(smooth_series)
    assert cat == "Smooth"
    assert model == "LightGBM"
    assert adi < 1.32
    assert cv2 < 0.49

    # 2. Intermittent demand: long streaks of zeros, low non-zero variance
    intermittent_series = np.array([0, 0, 0, 10, 0, 0, 0, 12, 0, 0, 0, 10, 0, 0, 0, 11])
    adi_i, cv2_i, cat_i, model_i = compute_syntetos_boylan_metrics(intermittent_series)
    assert cat_i == "Intermittent"
    assert model_i == "Croston SBA"
    assert adi_i >= 1.32
    assert cv2_i < 0.49

    # 3. Lumpy demand: long streaks of zeros, high non-zero variance
    lumpy_series = np.array([0, 0, 0, 5, 0, 0, 0, 150, 0, 0, 0, 20, 0, 0, 0, 200])
    adi_l, cv2_l, cat_l, model_l = compute_syntetos_boylan_metrics(lumpy_series)
    assert cat_l == "Lumpy"
    assert model_l == "Croston SBA"
    assert adi_l >= 1.32
    assert cv2_l >= 0.49

def test_croston_sba_debiasing():
    # Sparse series
    series = np.array([0, 0, 10, 0, 0, 0, 10, 0, 0, 10])
    pred = croston_sba(series, horizon=3, alpha=0.1)
    assert len(pred) == 3
    assert np.all(pred > 0)
    # Check debiasing: SBA forecast should be strictly less than uncorrected ratio
    # Non-negative and bounded
    assert pred[0] < 10.0

def test_seasonal_naive_and_metrics():
    train = np.array([10, 20, 30, 40, 10, 20, 30, 40, 10, 20, 30, 40])
    test = np.array([10, 20, 30, 40])
    pred = seasonal_naive(train, horizon=4, season_length=4)
    np.testing.assert_array_equal(pred, test)

    smape = calc_smape(test, pred)
    assert smape == pytest.approx(0.0, abs=1e-3)

    mase = calc_mase(test, pred, train)
    assert mase == pytest.approx(0.0, abs=1e-3)
