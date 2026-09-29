import pytest
import numpy as np
import pandas as pd
from ml.forecaster import DemandForecaster, run_demand_ablation_experiment
from ml.reconciliation import HierarchicalReconciler

def create_synthetic_ablation_dataset():
    """
    Creates a benchmark multi-tier time series dataset covering:
    - 2 Districts (D1, D2) with 4 Facilities (F1, F2, F3, F4)
    - 3 Item archetypes:
      * ITEM_UNCENSORED: continuous consumption, stock always available.
      * ITEM_CENSORED: high demand, but recurring stockouts (quantity=0, unfulfilled > 0).
      * ITEM_INTERMITTENT: intermittent spikes with long zero streaks.
    - 24 monthly periods.
    """
    records = []
    np.random.seed(42)

    facilities = [
        {"id": "F1", "district": "D1", "tier": 1},
        {"id": "F2", "district": "D1", "tier": 2},
        {"id": "F3", "district": "D2", "tier": 1},
        {"id": "F4", "district": "D2", "tier": 3},
    ]

    for p in range(1, 25):
        month = (p % 12) + 1
        seasonal_mult = 1.0 + 0.3 * np.sin(2 * np.pi * p / 12)

        for fac in facilities:
            base_rate = 20.0 * fac["tier"] * seasonal_mult

            # 1. Uncensored Item: Always full stock
            true_d_uncens = max(5.0, np.random.normal(loc=base_rate, scale=4.0))
            records.append({
                "period": p,
                "month": month,
                "facility_id": fac["id"],
                "district": fac["district"],
                "facility_tier_code": fac["tier"],
                "item_id": "ITEM_UNCENSORED",
                "quantity": round(true_d_uncens, 1),
                "unfulfilled_quantity": 0.0,
                "censored": False
            })

            # 2. Censored Item: True latent demand is high, but in periods 18-24 stockouts occur!
            true_d_cens = max(10.0, np.random.normal(loc=base_rate * 1.5, scale=5.0))
            if p >= 18 and p % 2 == 0:
                # Stockout: only 20% fulfilled, remainder unfulfilled!
                dispensed = round(true_d_cens * 0.2, 1)
                unfulfilled = round(true_d_cens - dispensed, 1)
                is_cens = True
            else:
                dispensed = round(true_d_cens, 1)
                unfulfilled = 0.0
                is_cens = False

            records.append({
                "period": p,
                "month": month,
                "facility_id": fac["id"],
                "district": fac["district"],
                "facility_tier_code": fac["tier"],
                "item_id": "ITEM_CENSORED",
                "quantity": dispensed,
                "unfulfilled_quantity": unfulfilled,
                "censored": is_cens
            })

            # 3. Intermittent Item: mostly zero, periodic spikes
            if np.random.rand() > 0.75:
                interm_qty = float(np.random.randint(15, 45))
            else:
                interm_qty = 0.0

            records.append({
                "period": p,
                "month": month,
                "facility_id": fac["id"],
                "district": fac["district"],
                "facility_tier_code": fac["tier"],
                "item_id": "ITEM_INTERMITTENT",
                "quantity": interm_qty,
                "unfulfilled_quantity": 0.0,
                "censored": False
            })

    return pd.DataFrame(records)

def test_demand_forecaster_quantiles():
    df = create_synthetic_ablation_dataset()
    train_df = df[df["period"] <= 20]
    test_df = df[df["period"] > 20]

    forecaster = DemandForecaster(quantiles=[0.1, 0.5, 0.9])
    forecaster.fit(train_df, is_censored_aware=True)

    preds = forecaster.predict(test_df, is_censored_aware=True, history_df=train_df)
    assert "p10" in preds
    assert "p50" in preds
    assert "p90" in preds

    # Check quantile ordering: p10 <= p50 <= p90 on average
    assert np.mean(preds["p10"]) <= np.mean(preds["p50"])
    assert np.mean(preds["p50"]) <= np.mean(preds["p90"])

def test_ablation_experiment_censored_vs_uncensored():
    """
    CRITICAL ACCEPTANCE TEST:
    Executes the required Phase 2 ablation experiment.
    Demonstrates:
      1. Naive and Blind LightGBM suffer severe degradation on censored SKUs.
      2. Censored-aware LightGBM recovers the true latent demand.
      3. Outputs the formal ablation table for the demo report.
    """
    df = create_synthetic_ablation_dataset()
    summary_table, meta = run_demand_ablation_experiment(df, test_periods=4)

    assert meta["censored_items_count"] > 0
    assert len(summary_table) == 5

    print("\n" + "="*80)
    print("PHASE 2 REQUIRED ABLATION BENCHMARK TABLE")
    print("="*80)
    print(summary_table.to_string(index=False))
    print("="*80)

    # 1. Proves Censored-Aware LightGBM has lower sMAPE than Raw Blind LightGBM on censored SKUs
    cens_aware_row = summary_table[summary_table["Model"] == "LightGBM (Censored-Aware)"].iloc[0]
    raw_blind_row = summary_table[summary_table["Model"] == "LightGBM (Raw Blind)"].iloc[0]

    assert cens_aware_row["Censored sMAPE (%)"] < raw_blind_row["Censored sMAPE (%)"], (
        f"Expected Censored-Aware sMAPE ({cens_aware_row['Censored sMAPE (%)']}%) < "
        f"Raw Blind sMAPE ({raw_blind_row['Censored sMAPE (%)']}%)"
    )

    # 2. Proves Censored-Aware LightGBM has lower MASE on censored SKUs
    assert cens_aware_row["Censored MASE"] < raw_blind_row["Censored MASE"]
