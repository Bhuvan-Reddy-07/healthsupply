import pytest
import numpy as np
from ml.reconciliation import HierarchicalReconciler

def test_cross_item_aggregate_coherence_across_hierarchy():
    """
    CRITICAL PHASE 3 / FINDING B ACCEPTANCE TEST:
    Demonstrates cross-item aggregate coherence:
    1. National total across ALL items equals sum of facility-level reconciled forecasts across ALL items.
    2. District totals across ALL items equal sum of child facility reconciled forecasts across ALL items.
    3. Reconciled outputs are strictly non-negative.
    """
    # 2 Districts, 5 Facilities
    facilities = ["FAC_A1", "FAC_A2", "FAC_B1", "FAC_B2", "FAC_B3"]
    districts = ["DIST_A", "DIST_B"]
    fac_to_dist = {
        "FAC_A1": "DIST_A",
        "FAC_A2": "DIST_A",
        "FAC_B1": "DIST_B",
        "FAC_B2": "DIST_B",
        "FAC_B3": "DIST_B"
    }
    hierarchy = {
        "national": "NATIONAL_HEALTH",
        "districts": districts,
        "facilities": facilities,
        "facility_to_district": fac_to_dist
    }
    reconciler = HierarchicalReconciler(hierarchy)

    items = ["ITEM_AMOXICILLIN", "ITEM_ORS", "ITEM_PARACETAMOL", "ITEM_ANTIVENOM"]
    
    # Store reconciled vectors for each item
    item_reconciled_all = {}
    item_bottom_reconciled = {}

    np.random.seed(42)

    for item in items:
        # Generate base forecasts with random discrepancies and potential negative artifacts
        fac_base = np.random.uniform(5.0, 50.0, size=len(facilities))
        if item == "ITEM_ANTIVENOM":
            fac_base[1] = -5.0 # Negative base artifact
        
        dist_base = [
            sum(fac_base[i] for i, f in enumerate(facilities) if fac_to_dist[f] == d) * np.random.uniform(0.9, 1.1)
            for d in districts
        ]
        nat_base = sum(dist_base) * np.random.uniform(0.95, 1.05)

        base_vec = np.array([nat_base] + dist_base + list(fac_base), dtype=float)

        reconciled_all, bottom_reconciled, _ = reconciler.reconcile(base_vec)
        
        # Verify non-negativity
        assert np.all(bottom_reconciled >= 0.0)
        assert np.all(reconciled_all >= 0.0)

        item_reconciled_all[item] = reconciled_all
        item_bottom_reconciled[item] = bottom_reconciled

    # 1. Total-of-totals: National sum across all items vs. bottom facility sum across all items
    grand_national_total = sum(item_reconciled_all[it][0] for it in items)
    grand_bottom_facility_total = sum(np.sum(item_bottom_reconciled[it]) for it in items)

    assert grand_national_total == pytest.approx(grand_bottom_facility_total, abs=1e-3), (
        f"Cross-item national total ({grand_national_total:.3f}) must exactly match "
        f"grand bottom facility total ({grand_bottom_facility_total:.3f})"
    )

    # 2. District level cross-item sums
    for d_idx, dist in enumerate(districts):
        dist_row_idx = 1 + d_idx
        district_cross_item_total = sum(item_reconciled_all[it][dist_row_idx] for it in items)
        
        # Sum of child facilities in this district across all items
        child_indices = [i for i, f in enumerate(facilities) if fac_to_dist[f] == dist]
        child_facilities_cross_item_total = sum(
            sum(item_bottom_reconciled[it][c_idx] for c_idx in child_indices)
            for it in items
        )

        assert district_cross_item_total == pytest.approx(child_facilities_cross_item_total, abs=1e-3), (
            f"District '{dist}' cross-item total ({district_cross_item_total:.3f}) must match "
            f"sum of its child facilities ({child_facilities_cross_item_total:.3f})"
        )
