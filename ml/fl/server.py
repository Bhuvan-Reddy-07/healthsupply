import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from ml.fl.model import DemandMLP
from ml.fl.privacy_accountant import RdpPrivacyAccountant
from ml.fl.client import FacilityFlowerClient

class FederatedCoordinator:
    """
    Federated Learning Coordinator with FedProx aggregation, straggler tolerance,
    and formal RDP Privacy Accounting.
    """
    def __init__(
        self,
        clients: List[FacilityFlowerClient],
        input_dim: int = 8,
        mu: float = 0.05,
        clip_norm: float = 1.0,
        noise_multiplier: float = 0.8,
        min_client_fraction: float = 0.2, # Minimum quorum to tolerate stragglers/dropouts
        target_delta: float = 1e-5
    ):
        self.clients = clients
        self.n_total_clients = len(clients)
        self.global_model = DemandMLP(input_dim=input_dim, hidden_dim=32)
        self.global_weights = self.global_model.get_weights()

        self.mu = mu
        self.clip_norm = clip_norm
        self.noise_multiplier = noise_multiplier
        self.min_client_fraction = min_client_fraction

        self.accountant = RdpPrivacyAccountant(target_delta=target_delta)
        self.round_metrics: List[Dict[str, Any]] = []

    def train_round(
        self,
        server_round: int,
        client_dropout_rate: float = 0.0
    ) -> Dict[str, Any]:
        """
        Executes one federated round:
        1. Selects participating clients (simulating low-bandwidth dropouts).
        2. Dispatches global parameters.
        3. Clients train locally using FedProx + post-proximal DP clipping.
        4. Aggregates updates via sample-weighted FedAvg.
        5. Steps the RDP privacy accountant.
        """
        # Determine available clients after simulated dropout/stragglers
        participating = []
        for c in self.clients:
            if np.random.rand() >= client_dropout_rate:
                participating.append(c)

        min_required = max(1, int(self.n_total_clients * self.min_client_fraction))
        if len(participating) < min_required:
            # Enforce minimum quorum
            participating = self.clients[:min_required]

        q = len(participating) / float(self.n_total_clients) # Subsampling ratio

        client_weights = []
        client_samples = []
        client_losses = []

        for client in participating:
            weights, num_samples, metrics = client.fit(
                parameters=self.global_weights,
                config={"server_round": server_round, "mu": self.mu}
            )
            client_weights.append(weights)
            client_samples.append(num_samples)
            client_losses.append(metrics["train_loss"])

        # Weighted Federated Averaging (FedAvg on FedProx updates)
        total_samples = sum(client_samples)
        new_global_weights = []
        for param_idx in range(len(self.global_weights)):
            weighted_param = np.zeros_like(self.global_weights[param_idx])
            for c_idx in range(len(participating)):
                weight_factor = client_samples[c_idx] / total_samples
                weighted_param += weight_factor * client_weights[c_idx][param_idx]
            new_global_weights.append(weighted_param)

        self.global_weights = new_global_weights
        self.global_model.set_weights(self.global_weights)

        # Step RDP Privacy Accountant
        eps, delta = self.accountant.step(q=q, noise_multiplier=self.noise_multiplier, steps=1)

        # Evaluate on all participating clients
        eval_losses = []
        eval_maes = []
        for client in participating:
            loss, n_val, metrics = client.evaluate(self.global_weights)
            eval_losses.append(metrics["val_loss"])
            eval_maes.append(metrics["val_mae"])

        round_info = {
            "round": server_round,
            "participating_clients": len(participating),
            "total_clients": self.n_total_clients,
            "sampling_ratio_q": round(q, 3),
            "mean_train_loss": round(float(np.mean(client_losses)), 4),
            "mean_val_loss": round(float(np.mean(eval_losses)), 4),
            "mean_val_mae": round(float(np.mean(eval_maes)), 4),
            "cumulative_epsilon": eps,
            "delta": delta
        }
        self.round_metrics.append(round_info)
        return round_info

    def run_federation(
        self,
        num_rounds: int = 5,
        client_dropout_rate: float = 0.1
    ) -> List[Dict[str, Any]]:
        """Executes full multi-round federated training run."""
        for r in range(1, num_rounds + 1):
            self.train_round(server_round=r, client_dropout_rate=client_dropout_rate)
        return self.round_metrics

    def evaluate_global(self, X_eval: np.ndarray, y_eval: np.ndarray) -> Dict[str, float]:
        """Evaluates current global model on a holdout evaluation dataset."""
        import torch
        import torch.nn as nn
        self.global_model.eval()
        criterion = nn.MSELoss()
        with torch.no_grad():
            t_x = torch.tensor(X_eval, dtype=torch.float32)
            t_y = torch.tensor(y_eval, dtype=torch.float32).view(-1, 1)
            preds = self.global_model(t_x)
            loss = float(criterion(preds, t_y).item())
            mae = float(torch.mean(torch.abs(preds - t_y)).item())
        return {"eval_loss": round(loss, 4), "eval_mae": round(mae, 4)}
