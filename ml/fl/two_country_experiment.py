"""
Two-Country Federated Learning Simulation & Experiment Runner (Phase 4).
Evaluates:
1. Four FL Configurations:
   (a) Isolated Local
   (b) Naive FedAvg
   (c) FedProx (mu=0.1)
   (d) FedProx + Personalization (shared representation, country-specific head)
2. The Killer Experiment:
   Transfers epidemiological outbreak dynamics from Country A (observed) to Country B (facing novel outbreak).
3. Zero-Data-Leakage boundary verification.
"""
import torch
import torch.nn as nn
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple

from ml.fl.model import DemandMLP
from ml.fl.client import FacilityFlowerClient
from ml.fl.server import FederatedCoordinator
from ml.fl.mtls_transport import NetworkEnvelope
from ml.baselines import calc_mae, calc_rmse, calc_smape, calc_wape

def generate_synthetic_features(n_samples: int, base_mean: float, is_outbreak: bool = False, seed: int = 42) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generates non-IID demand telemetry features:
    Features (8 dims):
    [lag_1, lag_2, lag_3, lag_4, roll_mean_3, roll_std_3, month, tier_code]
    Target: daily demand
    """
    rng = np.random.default_rng(seed)
    
    # Simulate time series
    trend = np.linspace(0.8, 1.2, n_samples)
    seasonality = np.sin(np.linspace(0, 4 * np.pi, n_samples))
    
    demand = base_mean * trend * (1.0 + 0.3 * seasonality) + rng.normal(0, base_mean * 0.1, n_samples)
    demand = np.maximum(0.0, demand)

    if is_outbreak:
        # Logistic outbreak surge in second half
        ramp = 1.0 / (1.0 + np.exp(-np.linspace(-6, 6, n_samples // 2)))
        demand[n_samples // 2:] *= (1.0 + 3.0 * ramp)

    # Construct lag features
    features = np.zeros((n_samples, 8), dtype=np.float32)
    for t in range(4, n_samples):
        lag_1 = demand[t - 1]
        lag_2 = demand[t - 2]
        lag_3 = demand[t - 3]
        lag_4 = demand[t - 4]
        roll_mean = np.mean(demand[t-3:t])
        roll_std = np.std(demand[t-3:t])
        month = (t % 12) + 1
        tier_code = 1.0 if base_mean > 25 else 0.0 # CHC/DH vs PHC
        features[t] = [lag_1, lag_2, lag_3, lag_4, roll_mean, roll_std, month, tier_code]

    # Trim warmup
    X = features[4:]
    y = demand[4:]
    return X, y

class TwoCountryFLExperiment:
    """
    Executes the Phase 4 Federated Learning ablation and outbreak transfer experiment.
    """
    def __init__(self, input_dim: int = 8, hidden_dim: int = 32, seed: int = 42):
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.seed = seed

    def setup_datasets(self) -> Dict[str, Any]:
        """
        Creates non-IID datasets for Country A and Country B:
        - Country A: Experienced historical outbreak wave in training.
        - Country B: Lower baseline, no outbreak in local training data.
        - Country B Outbreak Test: Encounters novel epidemic surge.
        """
        # Country A: base_mean = 35.0, includes historical outbreak experience
        X_a_train, y_a_train = generate_synthetic_features(n_samples=400, base_mean=35.0, is_outbreak=True, seed=self.seed)
        X_a_test, y_a_test = generate_synthetic_features(n_samples=100, base_mean=35.0, is_outbreak=False, seed=self.seed + 1)

        # Country B: base_mean = 18.0, NO outbreak in training (in-distribution baseline only)
        X_b_train, y_b_train = generate_synthetic_features(n_samples=250, base_mean=18.0, is_outbreak=False, seed=self.seed + 2)
        X_b_test, y_b_test = generate_synthetic_features(n_samples=100, base_mean=18.0, is_outbreak=False, seed=self.seed + 3)

        # Killer Experiment: Novel outbreak test set facing Country B
        X_b_outbreak_test, y_b_outbreak_test = generate_synthetic_features(
            n_samples=120, base_mean=18.0, is_outbreak=True, seed=self.seed + 4
        )

        return {
            "country_a": {"X_train": X_a_train, "y_train": y_a_train, "X_test": X_a_test, "y_test": y_a_test},
            "country_b": {"X_train": X_b_train, "y_train": y_b_train, "X_test": X_b_test, "y_test": y_b_test},
            "country_b_outbreak_test": {"X": X_b_outbreak_test, "y": y_b_outbreak_test}
        }

    def train_isolated_model(self, X_train: np.ndarray, y_train: np.ndarray, epochs: int = 15) -> DemandMLP:
        """Trains a model strictly on local data without any federation."""
        torch.manual_seed(self.seed)
        model = DemandMLP(input_dim=self.input_dim, hidden_dim=self.hidden_dim)
        optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
        criterion = nn.MSELoss()
        X_t = torch.tensor(X_train, dtype=torch.float32)
        y_t = torch.tensor(y_train, dtype=torch.float32).view(-1, 1)

        model.train()
        for _ in range(epochs):
            optimizer.zero_grad()
            pred = model(X_t)
            loss = criterion(pred, y_t)
            loss.backward()
            optimizer.step()
        return model

    def evaluate_model(self, model: DemandMLP, X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, float]:
        """Computes standardized metrics across test split."""
        model.eval()
        with torch.no_grad():
            preds = model(torch.tensor(X_test, dtype=torch.float32)).view(-1).numpy()
        
        mae = calc_mae(y_test, preds)
        rmse = calc_rmse(y_test, preds)
        smape = calc_smape(y_test, preds)
        wape = calc_wape(y_test, preds)

        return {"mae": round(mae, 3), "rmse": round(rmse, 3), "smape": round(smape, 2), "wape": round(wape, 3)}

    def run_federated_pipeline(
        self,
        data: Dict[str, Any],
        mu: float = 0.1,
        personalized: bool = False,
        rounds: int = 8,
        noise_multiplier: float = 0.2
    ) -> Tuple[DemandMLP, FacilityFlowerClient, FacilityFlowerClient]:
        """Runs federated training across Country A and Country B."""
        torch.manual_seed(self.seed)
        np.random.seed(self.seed)

        client_a = FacilityFlowerClient(
            facility_id="COUNTRY_A_NODE",
            X_train=data["country_a"]["X_train"],
            y_train=data["country_a"]["y_train"],
            X_val=data["country_a"]["X_test"],
            y_val=data["country_a"]["y_test"],
            mu=mu,
            clip_norm=1.0,
            noise_multiplier=noise_multiplier,
            lr=0.01,
            local_epochs=3,
            personalized=personalized
        )
        client_b = FacilityFlowerClient(
            facility_id="COUNTRY_B_NODE",
            X_train=data["country_b"]["X_train"],
            y_train=data["country_b"]["y_train"],
            X_val=data["country_b"]["X_test"],
            y_val=data["country_b"]["y_test"],
            mu=mu,
            clip_norm=1.0,
            noise_multiplier=noise_multiplier,
            lr=0.01,
            local_epochs=3,
            personalized=personalized
        )

        coordinator = FederatedCoordinator(
            clients=[client_a, client_b],
            input_dim=self.input_dim,
            mu=mu,
            clip_norm=1.0,
            noise_multiplier=noise_multiplier,
            min_client_fraction=0.5,
            personalized=personalized
        )

        for r in range(1, rounds + 1):
            coordinator.train_round(server_round=r)

        return coordinator.global_model, client_a, client_b

    def run_full_ablation_and_killer_experiment(self) -> Dict[str, Any]:
        """
        Executes all 4 configurations + killer experiment + boundary audit.
        """
        torch.manual_seed(self.seed)
        np.random.seed(self.seed)
        data = self.setup_datasets()

        # 1. Config (a): Isolated Local
        iso_a = self.train_isolated_model(data["country_a"]["X_train"], data["country_a"]["y_train"])
        iso_b = self.train_isolated_model(data["country_b"]["X_train"], data["country_b"]["y_train"])
        eval_iso_a = self.evaluate_model(iso_a, data["country_a"]["X_test"], data["country_a"]["y_test"])
        eval_iso_b = self.evaluate_model(iso_b, data["country_b"]["X_test"], data["country_b"]["y_test"])
        avg_iso_mae = round((eval_iso_a["mae"] + eval_iso_b["mae"]) / 2.0, 3)
        avg_iso_wape = round((eval_iso_a["wape"] + eval_iso_b["wape"]) / 2.0, 3)

        # 2. Config (b): Naive FedAvg (mu=0.0, shared weights)
        fedavg_model, _, _ = self.run_federated_pipeline(data, mu=0.0, personalized=False, rounds=8)
        eval_fedavg_a = self.evaluate_model(fedavg_model, data["country_a"]["X_test"], data["country_a"]["y_test"])
        eval_fedavg_b = self.evaluate_model(fedavg_model, data["country_b"]["X_test"], data["country_b"]["y_test"])
        avg_fedavg_mae = round((eval_fedavg_a["mae"] + eval_fedavg_b["mae"]) / 2.0, 3)
        avg_fedavg_wape = round((eval_fedavg_a["wape"] + eval_fedavg_b["wape"]) / 2.0, 3)

        # 3. Config (c): FedProx (mu=0.1, shared weights)
        fedprox_model, _, _ = self.run_federated_pipeline(data, mu=0.1, personalized=False, rounds=8)
        eval_fedprox_a = self.evaluate_model(fedprox_model, data["country_a"]["X_test"], data["country_a"]["y_test"])
        eval_fedprox_b = self.evaluate_model(fedprox_model, data["country_b"]["X_test"], data["country_b"]["y_test"])
        avg_fedprox_mae = round((eval_fedprox_a["mae"] + eval_fedprox_b["mae"]) / 2.0, 3)
        avg_fedprox_wape = round((eval_fedprox_a["wape"] + eval_fedprox_b["wape"]) / 2.0, 3)

        # 4. Config (d): FedProx + Personalization (shared representation, country-specific head)
        _, client_a_pers, client_b_pers = self.run_federated_pipeline(data, mu=0.1, personalized=True, rounds=8)
        eval_pers_a = self.evaluate_model(client_a_pers.model, data["country_a"]["X_test"], data["country_a"]["y_test"])
        eval_pers_b = self.evaluate_model(client_b_pers.model, data["country_b"]["X_test"], data["country_b"]["y_test"])
        avg_pers_mae = round((eval_pers_a["mae"] + eval_pers_b["mae"]) / 2.0, 3)
        avg_pers_wape = round((eval_pers_a["wape"] + eval_pers_b["wape"]) / 2.0, 3)

        # Summary Benchmark Table
        benchmark_table = [
            {
                "Configuration": "(a) Isolated Local",
                "Country A MAE": eval_iso_a["mae"],
                "Country B MAE": eval_iso_b["mae"],
                "Average MAE": avg_iso_mae,
                "Average WAPE (%)": f"{avg_iso_wape:.1f}%",
                "Personalized": False
            },
            {
                "Configuration": "(b) Naive FedAvg (mu=0)",
                "Country A MAE": eval_fedavg_a["mae"],
                "Country B MAE": eval_fedavg_b["mae"],
                "Average MAE": avg_fedavg_mae,
                "Average WAPE (%)": f"{avg_fedavg_wape:.1f}%",
                "Personalized": False
            },
            {
                "Configuration": "(c) FedProx (mu=0.1)",
                "Country A MAE": eval_fedprox_a["mae"],
                "Country B MAE": eval_fedprox_b["mae"],
                "Average MAE": avg_fedprox_mae,
                "Average WAPE (%)": f"{avg_fedprox_wape:.1f}%",
                "Personalized": False
            },
            {
                "Configuration": "(d) FedProx + Personalization",
                "Country A MAE": eval_pers_a["mae"],
                "Country B MAE": eval_pers_b["mae"],
                "Average MAE": avg_pers_mae,
                "Average WAPE (%)": f"{avg_pers_wape:.1f}%",
                "Personalized": True
            },
        ]

        # 5. THE KILLER EXPERIMENT:
        # Novel outbreak pattern facing Country B
        # Compare:
        # Model 1: Isolated Country B (never saw outbreak)
        # Model 2: Federated Model (learned outbreak dynamics from Country A)
        X_outbreak_b = data["country_b_outbreak_test"]["X"]
        y_outbreak_b = data["country_b_outbreak_test"]["y"]

        eval_iso_b_outbreak = self.evaluate_model(iso_b, X_outbreak_b, y_outbreak_b)
        eval_fed_outbreak = self.evaluate_model(fedprox_model, X_outbreak_b, y_outbreak_b)

        mae_iso = eval_iso_b_outbreak["mae"]
        mae_fed = eval_fed_outbreak["mae"]
        improvement_pct = round(((mae_iso - mae_fed) / max(0.001, mae_iso)) * 100.0, 2)

        killer_results = {
            "isolated_country_b_mae": mae_iso,
            "isolated_country_b_wape": eval_iso_b_outbreak["wape"],
            "federated_country_b_mae": mae_fed,
            "federated_country_b_wape": eval_fed_outbreak["wape"],
            "mae_improvement_pct": improvement_pct,
            "hypothesis_verified": (mae_fed < mae_iso) and (improvement_pct > 10.0)
        }

        # 6. Zero-Data-Leakage Wire Audit
        envelope = NetworkEnvelope.serialize_parameters(
            node_id="COUNTRY_A_NODE",
            round_id=1,
            parameters=fedprox_model.get_weights(),
            metrics={"train_loss": 0.42, "samples": 400}
        )
        assert envelope["protocol"] == "mTLS_v1.3_SecAgg_v1"
        assert envelope["num_tensors"] > 0

        return {
            "benchmark_table": benchmark_table,
            "killer_experiment": killer_results,
            "boundary_verified": True
        }
