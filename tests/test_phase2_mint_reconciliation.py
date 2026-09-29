import pytest
import numpy as np
from ml.reconciliation import HierarchicalReconciler

@pytest.fixture
def sample_hierarchy():
    facilities = ["FAC_A1", "FAC_A2", "FAC_B1", "FAC_B2", "FAC_B3"]
    districts = ["DIST_A", "DIST_B"]
    fac_to_dist = {
        "FAC_A1": "DIST_A",
        "FAC_A2": "DIST_A",
        "FAC_B1": "DIST_B",
        "FAC_B2": "DIST_B",
        "FAC_B3": "DIST_B"
    }
    return {
        "national": "COUNTRY_1",
        "districts": districts,
        "facilities": facilities,
        "facility_to_district": fac_to_dist
    }

def test_mint_reconciliation_coherence_and_non_negativity(sample_hierarchy):
    """
    Verifies that:
    1. Reconciled forecasts strictly obey the hierarchy (Coherence: Nat == Sum(Dist) == Sum(Fac)).
    2. Even when base forecasts are wildly contradictory or negative, reconciled forecasts are >= 0.
    """
    reconciler = HierarchicalReconciler(sample_hierarchy)
    assert reconciler.S.shape == (8, 5) # 1 Nat + 2 Dist + 5 Fac, 5 bottom

    # Base forecasts (deliberately incoherent with a negative shock)
    # [Nat, Dist_A, Dist_B, Fac_A1, Fac_A2, Fac_B1, Fac_B2, Fac_B3]
    base_forecasts = np.array([
        150.0, # Nat forecast
        60.0,  # Dist_A forecast
        90.0,  # Dist_B forecast
        35.0,  # Fac_A1
        -15.0, # Fac_A2 (negative artifact from unconstrained model!)
        40.0,  # Fac_B1
        30.0,  # Fac_B2
        10.0   # Fac_B3
    ])

    reconciled_all, bottom_reconciled, solver = reconciler.reconcile(base_forecasts)

    # 1. Non-negativity check
    assert np.all(bottom_reconciled >= 0.0), "Bottom facility forecasts must be non-negative!"
    assert np.all(reconciled_all >= 0.0), "All reconciled hierarchy levels must be non-negative!"

    # 2. Mathematical Coherence check
    nat_reconciled = reconciled_all[0]
    dist_reconciled = reconciled_all[1:3]
    fac_reconciled = reconciled_all[3:]

    # National must equal sum of bottom facilities
    assert nat_reconciled == pytest.approx(np.sum(fac_reconciled), abs=1e-4)

    # National must equal sum of districts
    assert nat_reconciled == pytest.approx(np.sum(dist_reconciled), abs=1e-4)

    # Dist_A must equal sum of Fac_A1 + Fac_A2
    assert dist_reconciled[0] == pytest.approx(fac_reconciled[0] + fac_reconciled[1], abs=1e-4)

    # Dist_B must equal sum of Fac_B1 + Fac_B2 + Fac_B3
    assert dist_reconciled[1] == pytest.approx(fac_reconciled[2] + fac_reconciled[3] + fac_reconciled[4], abs=1e-4)
