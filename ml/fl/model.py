import torch
import torch.nn as nn
from typing import List
import numpy as np

class DemandMLP(nn.Module):
    """
    Lightweight PyTorch Demand Forecasting Neural Network.
    Designed for resource-constrained edge devices (phones, tablets, low-power PCs).
    Structured into a shared feature extractor and a customizable prediction head
    to support federated personalization (shared representation, local head).
    """
    def __init__(self, input_dim: int = 8, hidden_dim: int = 32):
        super().__init__()
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim

        # Shared feature extractor: maps raw demand features to latent clinical state
        self.feature_extractor = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 16),
            nn.ReLU()
        )
        # Prediction head: maps latent state to non-negative demand estimate
        self.head = nn.Sequential(
            nn.Linear(16, 1),
            nn.ReLU() # Strict non-negativity constraint for demand
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        features = self.feature_extractor(x)
        return self.head(features)

    def get_weights(self) -> List[np.ndarray]:
        """Extracts all model parameters as a list of NumPy arrays."""
        return [val.cpu().numpy().copy() for _, val in self.state_dict().items()]

    def set_weights(self, weights: List[np.ndarray]):
        """Sets all model parameters from a list of NumPy arrays."""
        state_dict = {}
        for (key, _), val in zip(self.state_dict().items(), weights):
            state_dict[key] = torch.tensor(val, dtype=torch.float32)
        self.load_state_dict(state_dict)

    def get_feature_weights(self) -> List[np.ndarray]:
        """Extracts only feature extractor parameters (for personalized federation)."""
        return [val.cpu().numpy().copy() for _, val in self.feature_extractor.state_dict().items()]

    def set_feature_weights(self, weights: List[np.ndarray]):
        """Sets only feature extractor parameters from incoming global weights."""
        state_dict = {}
        for (key, _), val in zip(self.feature_extractor.state_dict().items(), weights):
            state_dict[key] = torch.tensor(val, dtype=torch.float32)
        self.feature_extractor.load_state_dict(state_dict)

    def get_head_weights(self) -> List[np.ndarray]:
        """Extracts only prediction head parameters."""
        return [val.cpu().numpy().copy() for _, val in self.head.state_dict().items()]

    def set_head_weights(self, weights: List[np.ndarray]):
        """Sets prediction head parameters."""
        state_dict = {}
        for (key, _), val in zip(self.head.state_dict().items(), weights):
            state_dict[key] = torch.tensor(val, dtype=torch.float32)
        self.head.load_state_dict(state_dict)
