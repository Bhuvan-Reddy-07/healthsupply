import torch
import torch.nn as nn
from typing import List
import numpy as np

class DemandMLP(nn.Module):
    """
    Lightweight PyTorch Demand Forecasting Neural Network.
    Designed for resource-constrained edge devices (phones, tablets, low-power PCs).
    """
    def __init__(self, input_dim: int = 8, hidden_dim: int = 32):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
            nn.ReLU() # Strict non-negativity constraint for demand
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)

    def get_weights(self) -> List[np.ndarray]:
        """Extracts parameters as a list of NumPy arrays for Flower."""
        return [val.cpu().numpy().copy() for _, val in self.state_dict().items()]

    def set_weights(self, weights: List[np.ndarray]):
        """Sets model parameters from a list of NumPy arrays."""
        state_dict = {}
        for (key, _), val in zip(self.state_dict().items(), weights):
            state_dict[key] = torch.tensor(val, dtype=torch.float32)
        self.load_state_dict(state_dict)
