import numpy as np
import pandas as pd
import lightgbm as lgb
from typing import Dict, Any, List, Tuple, Optional
from ml.baselines import seasonal_naive, croston_sba, calc_smape, calc_mase
from ml.classification import compute_syntetos_boylan_metrics

class DemandForecaster:
    """
    LightGBM Demand Forecaster with Censored Demand Correction.
    Handles P10/P50/P90 quantile predictions and incorporates stockout censoring indicators.
    """
    def __init__(self, quantiles: List[float] = [0.1, 0.5, 0.9]):
        self.quantiles = quantiles
        self.models: Dict[float, lgb.LGBMRegressor] = {}
        self.feature_cols: List[str] = []

    def create_features(
        self,
        df: pd.DataFrame,
        is_censored_aware: bool = True,
        history_df: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Engineers temporal lags, rolling statistics, calendar signals, and censoring features.
        Optionally uses history_df to populate initial lags for test windows.
        """
        if history_df is not None and len(history_df) > 0:
            combined = pd.concat([history_df, df], ignore_index=True).drop_duplicates(subset=["item_id", "facility_id", "period"])
            data = combined.sort_values(by=["item_id", "facility_id", "period"]).copy()
            is_subset = True
        else:
            data = df.copy().sort_values(by=["item_id", "facility_id", "period"])
            is_subset = False

        # Construct true latent demand target vs raw observed consumption
        data["consumed"] = data["quantity"].astype(float)
        data["unfulfilled"] = data["unfulfilled_quantity"].fillna(0.0).astype(float)
        data["censored_flag"] = data["censored"].fillna(False).astype(int)

        if is_censored_aware:
            data["target"] = data["consumed"] + data["unfulfilled"]
        else:
            data["target"] = data["consumed"]

        # Lag features
        grouped = data.groupby(["item_id", "facility_id"])
        data["lag_1"] = grouped["target"].shift(1)
        data["lag_2"] = grouped["target"].shift(2)
        data["lag_3"] = grouped["target"].shift(3)
        data["lag_4"] = grouped["target"].shift(4)

        # Rolling statistics
        data["roll_mean_3"] = grouped["target"].shift(1).rolling(3, min_periods=1).mean()
        data["roll_std_3"] = grouped["target"].shift(1).rolling(3, min_periods=1).std().fillna(0.0)

        # Censoring signals
        data["censored_lag_1"] = grouped["censored_flag"].shift(1).fillna(0)
        data["unfulfilled_lag_1"] = grouped["unfulfilled"].shift(1).fillna(0.0)

        # Temporal signals
        if "month" in data.columns:
            data["month"] = data["month"].astype(int)
        else:
            data["month"] = (data["period"] % 12) + 1

        feature_cols = ["lag_1", "lag_2", "lag_3", "lag_4", "roll_mean_3", "roll_std_3", "month"]
        if is_censored_aware:
            feature_cols.extend(["censored_lag_1", "unfulfilled_lag_1"])

        if "facility_tier_code" in data.columns:
            feature_cols.append("facility_tier_code")

        self.feature_cols = feature_cols

        if is_subset:
            # Filter back to only target df periods
            target_periods = set(df["period"].unique())
            data = data[data["period"].isin(target_periods)].copy()

        return data

    def fit(self, train_df: pd.DataFrame, is_censored_aware: bool = True):
        """Trains LightGBM models for each quantile target."""
        feat_df = self.create_features(train_df, is_censored_aware=is_censored_aware)
        clean_df = feat_df.dropna(subset=self.feature_cols + ["target"])

        X = clean_df[self.feature_cols]
        y = clean_df["target"]

        for q in self.quantiles:
            model = lgb.LGBMRegressor(
                objective="quantile",
                alpha=q,
                n_estimators=60,
                learning_rate=0.08,
                num_leaves=15,
                min_child_samples=5,
                verbose=-1,
                random_state=42
            )
            model.fit(X, y)
            self.models[q] = model

    def predict(
        self,
        test_df: pd.DataFrame,
        is_censored_aware: bool = True,
        history_df: Optional[pd.DataFrame] = None
    ) -> Dict[str, np.ndarray]:
        """Generates P10, P50, P90 predictions for test feature dataframe."""
        feat_df = self.create_features(test_df, is_censored_aware=is_censored_aware, history_df=history_df)
        clean_df = feat_df.dropna(subset=self.feature_cols)

        preds = {}
        for q, model in self.models.items():
            col_name = f"p{int(q*100)}"
            if len(clean_df) > 0:
                raw_pred = model.predict(clean_df[self.feature_cols])
                preds[col_name] = np.maximum(0.0, raw_pred)
            else:
                preds[col_name] = np.zeros(len(test_df))

        return preds


def run_demand_ablation_experiment(
    history_df: pd.DataFrame,
    test_periods: int = 4
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Executes the required Phase 2 Ablation Experiment:
    Compares:
      1. Seasonal Naive
      2. Croston SBA
      3. LightGBM (Naive - trained on raw consumed quantity without unfulfilled)
      4. LightGBM (Censored-Aware - trained on latent demand = consumed + unfulfilled with censor features)
    Evaluates sMAPE and MASE on:
      - Censored SKUs (high stockout periods)
      - Uncensored SKUs (adequate stock)
      - Overall Catalog
    """
    periods = sorted(history_df["period"].unique())
    split_period = periods[-test_periods]

    train_raw = history_df[history_df["period"] < split_period].copy()
    test_raw = history_df[history_df["period"] >= split_period].copy()

    # Determine which items are heavily censored in the test period
    censored_items = set(test_raw[test_raw["censored"] == True]["item_id"].unique())

    # 1. Fit LightGBM Models
    model_naive = DemandForecaster(quantiles=[0.5])
    model_naive.fit(train_raw, is_censored_aware=False)

    model_censored = DemandForecaster(quantiles=[0.5])
    model_censored.fit(train_raw, is_censored_aware=True)

    results_records = []

    # Iterate over item-facility pairs
    pairs = history_df[["item_id", "facility_id"]].drop_duplicates().values

    for item_id, fac_id in pairs:
        pair_hist = history_df[(history_df["item_id"] == item_id) & (history_df["facility_id"] == fac_id)].sort_values("period")
        pair_train = pair_hist[pair_hist["period"] < split_period]
        pair_test = pair_hist[pair_hist["period"] >= split_period]

        if len(pair_test) == 0 or len(pair_train) < 6:
            continue

        # Ground truth true demand: consumed + unfulfilled
        y_true = (pair_test["quantity"] + pair_test["unfulfilled_quantity"].fillna(0.0)).values
        train_series = (pair_train["quantity"] + pair_train["unfulfilled_quantity"].fillna(0.0)).values
        raw_train_series = pair_train["quantity"].values

        is_censored_item = item_id in censored_items

        # Model 1: Seasonal Naive
        pred_naive = seasonal_naive(raw_train_series, horizon=len(y_true), season_length=4)

        # Model 2: Croston SBA
        pred_croston = croston_sba(train_series, horizon=len(y_true), alpha=0.1)

        # Model 3: LightGBM Uncensored-Blind
        test_feat_naive = model_naive.create_features(pair_hist, is_censored_aware=False)
        test_window_naive = test_feat_naive[test_feat_naive["period"] >= split_period]
        if len(test_window_naive) == len(y_true) and not test_window_naive[model_naive.feature_cols].isna().any().any():
            pred_lgb_naive = np.maximum(0.0, model_naive.models[0.5].predict(test_window_naive[model_naive.feature_cols]))
        else:
            pred_lgb_naive = pred_naive

        # Model 4: LightGBM Censored-Aware
        test_feat_cens = model_censored.create_features(pair_hist, is_censored_aware=True)
        test_window_cens = test_feat_cens[test_feat_cens["period"] >= split_period]
        if len(test_window_cens) == len(y_true) and not test_window_cens[model_censored.feature_cols].isna().any().any():
            pred_lgb_cens = np.maximum(0.0, model_censored.models[0.5].predict(test_window_cens[model_censored.feature_cols]))
        else:
            pred_lgb_cens = pred_croston

        for model_name, preds in [
            ("Seasonal Naive", pred_naive),
            ("Croston SBA", pred_croston),
            ("LightGBM (Raw Blind)", pred_lgb_naive),
            ("LightGBM (Censored-Aware)", pred_lgb_cens)
        ]:
            smape = calc_smape(y_true, preds)
            mase = calc_mase(y_true, preds, train_series)
            results_records.append({
                "item_id": item_id,
                "facility_id": fac_id,
                "is_censored_item": is_censored_item,
                "model": model_name,
                "smape": smape,
                "mase": mase,
                "preds": preds,
                "y_true": y_true,
                "train_series": train_series
            })

    # Hierarchical Reconciliation (MinT-OSQP) step
    from ml.reconciliation import HierarchicalReconciler
    if "district" in history_df.columns:
        facilities_all = sorted(history_df["facility_id"].unique())
        districts_all = sorted(history_df["district"].unique())
        fac_to_dist = history_df.drop_duplicates("facility_id").set_index("facility_id")["district"].to_dict()

        hierarchy = {
            "national": "NATIONAL",
            "districts": districts_all,
            "facilities": facilities_all,
            "facility_to_district": fac_to_dist
        }
        reconciler = HierarchicalReconciler(hierarchy)

        for item_id in history_df["item_id"].unique():
            item_records = [r for r in results_records if r["item_id"] == item_id and r["model"] == "LightGBM (Censored-Aware)"]
            if len(item_records) == len(facilities_all):
                is_censored_item = item_id in censored_items
                h_len = len(item_records[0]["y_true"])

                # Reconcile period by period
                for t in range(h_len):
                    bottom_base = [next(r for r in item_records if r["facility_id"] == fac)["preds"][t] for fac in facilities_all]
                    dist_base = [sum(bottom_base[i] for i, fac in enumerate(facilities_all) if fac_to_dist.get(fac) == d) for d in districts_all]
                    nat_base = sum(bottom_base)

                    base_vec = np.array([nat_base] + dist_base + bottom_base, dtype=float)
                    reconciled_all, reconciled_bottom, _ = reconciler.reconcile(base_vec)

                    for idx, fac in enumerate(facilities_all):
                        matching_rec = next(r for r in item_records if r["facility_id"] == fac)
                        if "reconciled_preds" not in matching_rec:
                            matching_rec["reconciled_preds"] = []
                        matching_rec["reconciled_preds"].append(reconciled_bottom[idx])

                for fac in facilities_all:
                    rec = next(r for r in item_records if r["facility_id"] == fac)
                    reconciled_p = np.array(rec["reconciled_preds"])
                    smape = calc_smape(rec["y_true"], reconciled_p)
                    mase = calc_mase(rec["y_true"], reconciled_p, rec["train_series"])
                    results_records.append({
                        "item_id": item_id,
                        "facility_id": fac,
                        "is_censored_item": is_censored_item,
                        "model": "Reconciled (MinT-OSQP)",
                        "smape": smape,
                        "mase": mase
                    })

    res_df = pd.DataFrame(results_records)

    # Compute Aggregate Summary Table
    summary = []
    models_to_report = ["Seasonal Naive", "Croston SBA", "LightGBM (Raw Blind)", "LightGBM (Censored-Aware)", "Reconciled (MinT-OSQP)"]
    for model_name in models_to_report:
        m_df = res_df[res_df["model"] == model_name]
        if len(m_df) == 0:
            continue
        cens_sub = m_df[m_df["is_censored_item"] == True]
        uncens_sub = m_df[m_df["is_censored_item"] == False]

        summary.append({
            "Model": model_name,
            "Censored sMAPE (%)": round(cens_sub["smape"].mean(), 2) if len(cens_sub) > 0 else 0.0,
            "Censored MASE": round(cens_sub["mase"].mean(), 3) if len(cens_sub) > 0 else 0.0,
            "Uncensored sMAPE (%)": round(uncens_sub["smape"].mean(), 2) if len(uncens_sub) > 0 else 0.0,
            "Uncensored MASE": round(uncens_sub["mase"].mean(), 3) if len(uncens_sub) > 0 else 0.0,
            "Overall sMAPE (%)": round(m_df["smape"].mean(), 2),
            "Overall MASE": round(m_df["mase"].mean(), 3),
        })

    summary_df = pd.DataFrame(summary)
    return summary_df, {"raw_results": res_df, "censored_items_count": len(censored_items)}
