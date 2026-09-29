import numpy as np
import scipy.sparse as sp
from scipy.optimize import lsq_linear
from typing import Dict, Any, List, Tuple, Optional
import osqp

class HierarchicalReconciler:
    """
    OSQP-Constrained Minimum Trace (MinT) Hierarchical Forecaster.
    Reconciles multi-level demand forecasts (National -> District -> Facility)
    ensuring mathematical coherence (aggregate == sum of children) and
    strict non-negativity (reconciled demand >= 0).
    """
    def __init__(self, hierarchy: Dict[str, Any]):
        """
        hierarchy dict specifies:
          - 'national': name of national node
          - 'districts': list of district names
          - 'facilities': list of facility IDs
          - 'facility_to_district': dict mapping fac_id -> district_name
        """
        self.national = hierarchy["national"]
        self.districts = hierarchy["districts"]
        self.facilities = hierarchy["facilities"]
        self.fac_to_dist = hierarchy["facility_to_district"]

        self.n_bottom = len(self.facilities)
        self.n_districts = len(self.districts)
        self.n_total = 1 + self.n_districts + self.n_bottom

        self.S = self._build_summing_matrix()

    def _build_summing_matrix(self) -> np.ndarray:
        """
        Constructs summing matrix S such that y_total = S @ y_bottom.
        Shape: (1 + n_districts + n_bottom, n_bottom)
        """
        S = np.zeros((self.n_total, self.n_bottom), dtype=float)

        # Row 0: National (sums all bottom facilities)
        S[0, :] = 1.0

        # Rows 1 .. n_districts: District sums
        for d_idx, dist in enumerate(self.districts):
            row_idx = 1 + d_idx
            for f_idx, fac in enumerate(self.facilities):
                if self.fac_to_dist.get(fac) == dist:
                    S[row_idx, f_idx] = 1.0

        # Rows (1 + n_districts) .. end: Identity for bottom facilities
        offset = 1 + self.n_districts
        for f_idx in range(self.n_bottom):
            S[offset + f_idx, f_idx] = 1.0

        return S

    def reconcile(
        self,
        base_forecasts: np.ndarray,
        error_variances: Optional[np.ndarray] = None
    ) -> Tuple[np.ndarray, np.ndarray, str]:
        """
        Solves the Non-Negative MinT Quadratic Program:
          min_b (y_hat - S b)^T W^-1 (y_hat - S b)
          subject to: b >= 0

        Returns:
          (reconciled_all_levels, reconciled_bottom_facilities, solver_used)
        """
        y_hat = np.asarray(base_forecasts, dtype=float)
        assert len(y_hat) == self.n_total, f"Expected {self.n_total} forecasts, got {len(y_hat)}"

        # Default W to diagonal variance or identity (OLS/MinT-diag)
        if error_variances is not None and len(error_variances) == self.n_total:
            # Avoid division by zero
            safe_var = np.maximum(1e-4, error_variances)
            w_inv = 1.0 / safe_var
        else:
            w_inv = np.ones(self.n_total, dtype=float)

        W_inv = np.diag(w_inv)

        # Formulate QP:
        # 1/2 b^T P b + q^T b
        # where P = 2 S^T W^-1 S, q = -2 S^T W^-1 y_hat
        St_Winv = self.S.T @ W_inv
        P = 2.0 * (St_Winv @ self.S)
        q = -2.0 * (St_Winv @ y_hat)

        # Guarantee P is symmetric positive semi-definite
        P = (P + P.T) / 2.0
        P_reg = P + 1e-6 * np.eye(self.n_bottom)

        solver_used = "OSQP"
        try:
            P_sparse = sp.csc_matrix(P_reg)
            A_sparse = sp.csc_matrix(sp.eye(self.n_bottom))
            l = np.zeros(self.n_bottom)
            u = np.full(self.n_bottom, np.inf)

            prob = osqp.OSQP()
            prob.setup(P_sparse, q, A_sparse, l, u, verbose=False, eps_abs=1e-5, eps_rel=1e-5)
            res = prob.solve()

            if res.info.status_val in (1, 2): # Solved or Solved Inaccurate
                b_opt = np.maximum(0.0, res.x)
            else:
                raise RuntimeError(f"OSQP status: {res.info.status}")
        except Exception:
            # Robust mathematical fallback via bounded least squares (lsq_linear)
            # min || W^-1/2 (S b - y_hat) ||_2^2 s.t. b >= 0
            solver_used = "SciPy_lsq_linear"
            W_inv_half = np.diag(np.sqrt(w_inv))
            A_lsq = W_inv_half @ self.S
            b_lsq = W_inv_half @ y_hat
            res_lsq = lsq_linear(A_lsq, b_lsq, bounds=(0, np.inf))
            b_opt = np.maximum(0.0, res_lsq.x)

        # Calculate reconciled vector for all hierarchy levels
        y_reconciled = self.S @ b_opt

        return y_reconciled, b_opt, solver_used
