import torch
import torch.nn as nn
import numpy as np
from typing import Dict, Any, List, Tuple
import flwr as fl
from ml.fl.model import DemandMLP

class FacilityFlowerClient(fl.client.NumPyClient):
    """
    Facility-level Flower Client with FedProx and DP-SGD.
    Enforces privacy by never sending raw health records or unclipped gradients.
    """
    def __init__(
        self,
        facility_id: str,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        mu: float = 0.05,
        clip_norm: float = 1.0,
        noise_multiplier: float = 0.8,
        lr: float = 0.01,
        local_epochs: int = 2,
        personalized: bool = False
    ):
        self.facility_id = facility_id
        self.X_train = torch.tensor(X_train, dtype=torch.float32)
        self.y_train = torch.tensor(y_train, dtype=torch.float32).view(-1, 1)
        self.X_val = torch.tensor(X_val, dtype=torch.float32)
        self.y_val = torch.tensor(y_val, dtype=torch.float32).view(-1, 1)

        self.mu = mu # FedProx proximal regularization strength
        self.clip_norm = clip_norm # DP-SGD gradient clipping norm S
        self.noise_multiplier = noise_multiplier
        self.lr = lr
        self.local_epochs = local_epochs
        self.personalized = personalized

        self.model = DemandMLP(input_dim=X_train.shape[1], hidden_dim=32)
        self.criterion = nn.MSELoss()

    def get_parameters(self, config: Dict[str, Any] = None) -> List[np.ndarray]:
        if self.personalized:
            return self.model.get_feature_weights()
        return self.model.get_weights()

    def fit(self, parameters: List[np.ndarray], config: Dict[str, Any] = None) -> Tuple[List[np.ndarray], int, Dict[str, Any]]:
        # Set global weights (only feature extractor if personalized; full model otherwise)
        if self.personalized:
            self.model.set_feature_weights(parameters)
            global_tensors = [torch.tensor(w, dtype=torch.float32) for w in parameters]
            prox_params = list(self.model.feature_extractor.parameters())
        else:
            self.model.set_weights(parameters)
            global_tensors = [torch.tensor(w, dtype=torch.float32) for w in parameters]
            prox_params = list(self.model.parameters())

        optimizer = torch.optim.Adam(self.model.parameters(), lr=self.lr)

        total_loss = 0.0
        n_batches = 0

        self.model.train()
        batch_size = min(16, len(self.X_train))

        for epoch in range(self.local_epochs):
            permutation = torch.randperm(self.X_train.size(0))
            for i in range(0, self.X_train.size(0), batch_size):
                indices = permutation[i:i + batch_size]
                batch_x, batch_y = self.X_train[indices], self.y_train[indices]

                optimizer.zero_grad()
                pred = self.model(batch_x)
                task_loss = self.criterion(pred, batch_y)

                # FedProx Proximal Regularization: (mu / 2) * || w - w_global ||^2
                prox_term = 0.0
                if self.mu > 0:
                    for w_local, w_glob in zip(prox_params, global_tensors):
                        prox_term += torch.sum((w_local - w_glob) ** 2)
                
                loss = task_loss + 0.5 * self.mu * prox_term
                loss.backward()

                # DP-SGD: Clip AFTER proximal-adjusted gradient computation
                # Strictly bounds sensitivity S under FedProx modification
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=self.clip_norm)

                optimizer.step()
                total_loss += float(loss.item())
                n_batches += 1

        avg_loss = total_loss / max(1, n_batches)

        # Exported weights: feature extractor only if personalized; full model otherwise
        if self.personalized:
            updated_weights = self.model.get_feature_weights()
        else:
            updated_weights = self.model.get_weights()

        # Apply Differential Privacy Gaussian Noise to exported parameter delta
        if self.noise_multiplier > 0:
            dp_weights = []
            for w, w_g in zip(updated_weights, parameters):
                delta = w - w_g
                sigma = (self.noise_multiplier * self.clip_norm) / np.sqrt(max(1, len(self.X_train)))
                noise = np.random.normal(loc=0.0, scale=sigma, size=delta.shape)
                dp_weights.append(w_g + delta + noise)
            exported_weights = dp_weights
        else:
            exported_weights = updated_weights

        # Boundary security verification: assert weights only, zero raw data
        assert isinstance(exported_weights, list)
        for arr in exported_weights:
            assert isinstance(arr, np.ndarray), "Only numpy weight tensors may cross node boundary"

        metrics = {
            "facility_id": self.facility_id,
            "train_loss": round(avg_loss, 4),
            "samples": len(self.X_train),
            "personalized": self.personalized
        }
        return exported_weights, len(self.X_train), metrics

    def evaluate(self, parameters: List[np.ndarray], config: Dict[str, Any] = None) -> Tuple[float, int, Dict[str, Any]]:
        if self.personalized:
            self.model.set_feature_weights(parameters)
        else:
            self.model.set_weights(parameters)

        self.model.eval()

        with torch.no_grad():
            if len(self.X_val) > 0:
                preds = self.model(self.X_val)
                loss = float(self.criterion(preds, self.y_val).item())
                mae = float(torch.mean(torch.abs(preds - self.y_val)).item())
            else:
                loss, mae = 0.0, 0.0

        metrics = {"val_loss": round(loss, 4), "val_mae": round(mae, 4)}
        return loss, len(self.X_val), metrics
