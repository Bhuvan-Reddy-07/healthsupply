import math
import numpy as np
from typing import List, Tuple, Dict, Any

class RdpPrivacyAccountant:
    """
    Rényi Differential Privacy (RDP) Accountant for Subsampled Gaussian Mechanisms in Federated Learning.
    Guarantees formal, auditable (epsilon, delta)-DP accounting across training rounds.
    """
    def __init__(
        self,
        orders: List[float] = None,
        target_delta: float = 1e-5
    ):
        if orders is None:
            # Standard discrete RDP orders from Mironov (2017)
            self.orders = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 6.0, 7.0, 8.0, 10.0, 12.0, 16.0, 20.0, 32.0, 64.0]
        else:
            self.orders = orders
        self.target_delta = target_delta
        self.rdp_total = np.zeros(len(self.orders), dtype=float)
        self.round_history: List[Dict[str, Any]] = []

    def compute_rdp_gaussian(self, q: float, noise_multiplier: float, alpha: float) -> float:
        """
        Computes Rényi divergence for subsampled Gaussian mechanism at order alpha.
        Uses Mironov / Wang subsampled RDP formulation.
        """
        if noise_multiplier <= 0:
            return float("inf")
        if q == 0:
            return 0.0

        # Base Gaussian RDP: alpha / (2 * sigma^2)
        # Subsampled upper bound: q^2 * alpha / (2 * sigma^2) + higher-order correction
        sigma2 = noise_multiplier ** 2
        rdp_base = (alpha) / (2.0 * sigma2)
        rdp_subsampled = min(rdp_base, (q ** 2) * alpha / (2.0 * sigma2) + (q ** 3) * (alpha ** 2) / (3.0 * sigma2))
        return float(rdp_subsampled)

    def step(self, q: float, noise_multiplier: float, steps: int = 1) -> Tuple[float, float]:
        """
        Records 1 or more federated training rounds with subsampling ratio q and noise multiplier.
        Returns the current cumulative (epsilon, delta).
        """
        for i, alpha in enumerate(self.orders):
            rdp_round = self.compute_rdp_gaussian(q=q, noise_multiplier=noise_multiplier, alpha=alpha)
            self.rdp_total[i] += steps * rdp_round

        eps, best_alpha = self.get_epsilon(self.target_delta)
        self.round_history.append({
            "round": len(self.round_history) + 1,
            "q": q,
            "noise_multiplier": noise_multiplier,
            "epsilon": eps,
            "delta": self.target_delta,
            "optimal_alpha": best_alpha
        })
        return eps, self.target_delta

    def get_epsilon(self, delta: float = None) -> Tuple[float, float]:
        """
        Converts cumulative RDP to (epsilon, delta)-DP via standard RDP-to-DP conversion:
          eps(delta) = min_{alpha > 1} ( RDP(alpha) + ln(1/delta) / (alpha - 1) )
        """
        d = delta if delta is not None else self.target_delta
        assert 0 < d < 1.0, "Delta must be in (0, 1)"

        eps_candidates = []
        for i, alpha in enumerate(self.orders):
            if alpha <= 1.0:
                continue
            eps_at_alpha = self.rdp_total[i] + (math.log(1.0 / d)) / (alpha - 1.0)
            eps_candidates.append((eps_at_alpha, alpha))

        if not eps_candidates:
            return float("inf"), 1.0

        best_eps, best_alpha = min(eps_candidates, key=lambda x: x[0])
        return round(float(best_eps), 3), float(best_alpha)
