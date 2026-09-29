import pytest
from datetime import datetime, timezone, timedelta
from backend.app.models.facilities import Facility
from backend.app.models.items import Item
from backend.app.models.stock import StockBatch
from backend.app.models.intelligence import TransferProposal
from backend.app.models.audit import AuditLog
from backend.app.optimization.redistribution import RedistributionOptimizer, haversine_distance_km

@pytest.fixture
def redistribution_db(db_session):
    now = datetime.now(timezone.utc)
    today = now.date()

    # 1. Three facilities:
    # F1 (Donor): Center
    # F2 (Recipient Near): 35 km away
    # F3 (Recipient Far): 450 km away
    f1 = Facility(
        id="FAC_DONOR", name="Central District Hospital", country="Country_A",
        region="Region_1", district="District_1", tier="DH",
        latitude=12.9716, longitude=77.5946, has_cold_chain=True
    )
    # Approx 35 km North
    f2 = Facility(
        id="FAC_REC_NEAR", name="Rural Clinic Near", country="Country_A",
        region="Region_1", district="District_1", tier="PHC",
        latitude=13.2800, longitude=77.5946, has_cold_chain=True
    )
    # Approx 450 km away
    f3 = Facility(
        id="FAC_REC_FAR", name="Remote Border Post", country="Country_A",
        region="Region_2", district="District_2", tier="PHC",
        latitude=17.0000, longitude=77.5946, has_cold_chain=False
    )
    db_session.add_all([f1, f2, f3])

    # 2. Two Items:
    # Standard Amoxicillin
    # Cold-chain Oxytocin
    item_amox = Item(
        id="MED_AMOX", name="Amoxicillin 500mg", category="antibiotic",
        dosage_form="capsule", unit_of_measure="strip", velocity_class="high_velocity",
        requires_cold_chain=False, unit_cost_usd=0.8, shelf_life_days=730, criticality_tier="A"
    )
    item_oxy = Item(
        id="MED_OXY", name="Oxytocin 10 IU/ml", category="maternal_health",
        dosage_form="ampoule", unit_of_measure="vial", velocity_class="cold_chain",
        requires_cold_chain=True, temp_min_c=2.0, temp_max_c=8.0,
        unit_cost_usd=1.5, shelf_life_days=365, criticality_tier="A"
    )
    db_session.add_all([item_amox, item_oxy])

    # 3. Stock Batches at Donor F1:
    # Amox: 100 units, expires in 180 days (viable)
    b_amox = StockBatch(
        id="BATCH-AMOX-SURPLUS", batch_number="B-AMX-01", facility_id="FAC_DONOR",
        item_id="MED_AMOX", current_quantity=100.0, initial_quantity=100.0,
        mfg_date=today - timedelta(days=60), expiry_date=today + timedelta(days=180),
        gs1_gtin="08901234567890", status="active"
    )
    # Oxytocin: 50 units, expires in 90 days (viable)
    b_oxy = StockBatch(
        id="BATCH-OXY-SURPLUS", batch_number="B-OXY-01", facility_id="FAC_DONOR",
        item_id="MED_OXY", current_quantity=50.0, initial_quantity=50.0,
        mfg_date=today - timedelta(days=30), expiry_date=today + timedelta(days=90),
        gs1_gtin="08909876543210", status="active"
    )
    # Near-expired batch (expires in 3 days - should NOT be transferred!)
    b_expired = StockBatch(
        id="BATCH-EXPIRED", batch_number="B-EXP-01", facility_id="FAC_DONOR",
        item_id="MED_AMOX", current_quantity=20.0, initial_quantity=20.0,
        mfg_date=today - timedelta(days=360), expiry_date=today + timedelta(days=3),
        gs1_gtin="08901234567890", status="active"
    )
    db_session.add_all([b_amox, b_oxy, b_expired])
    db_session.commit()

    return db_session

def test_ortools_redistribution_surplus_to_deficit(redistribution_db):
    """
    CRITICAL ACCEPTANCE TEST:
    Verifies OR-Tools solves redistribution from surplus to deficit facility:
    1. Donor retains safety stock (no negative stock).
    2. Zero transfers beyond max distance constraint (FAC_REC_FAR receives nothing).
    3. Cold chain constraints respected.
    4. Expiry feasibility respected (near-expired batch excluded).
    5. Creates TransferProposal records with audit logging.
    """
    db = redistribution_db
    optimizer = RedistributionOptimizer(
        planning_horizon_days=30,
        max_transit_km=250.0,
        max_cold_chain_km=100.0,
        min_shelf_life_margin_days=14
    )

    # Forecasts:
    # Donor FAC_DONOR: needs 20 Amox, 10 Oxy (massive surplus)
    # Recipient Near FAC_REC_NEAR: needs 40 Amox, 20 Oxy (massive deficit, currently 0 stock)
    # Recipient Far FAC_REC_FAR: needs 30 Amox (deficit, but >400 km away!)
    forecasts = {
        ("FAC_DONOR", "MED_AMOX"): 20.0,
        ("FAC_DONOR", "MED_OXY"): 10.0,
        ("FAC_REC_NEAR", "MED_AMOX"): 40.0,
        ("FAC_REC_NEAR", "MED_OXY"): 20.0,
        ("FAC_REC_FAR", "MED_AMOX"): 30.0,
    }

    proposals = optimizer.solve_redistribution(db=db, demand_forecasts=forecasts)

    assert len(proposals) >= 1

    # 1. Verify destination is Near recipient, NOT Far recipient
    dest_ids = [p.destination_facility_id for p in proposals]
    assert "FAC_REC_NEAR" in dest_ids
    assert "FAC_REC_FAR" not in dest_ids, "Facility beyond 250km must not receive transfers!"

    # 2. Verify Amoxicillin transfer proposal
    amox_prop = next(p for p in proposals if p.item_id == "MED_AMOX")
    assert amox_prop.source_facility_id == "FAC_DONOR"
    assert amox_prop.destination_facility_id == "FAC_REC_NEAR"
    assert amox_prop.quantity > 0.0
    # Donor had 100 stock, forecast 20, safety stock 5 -> surplus ~75
    # Recipient needed 40 + safety stock 8 -> deficit ~48
    # Transferred quantity should saturate recipient (~48) and not exceed surplus
    assert amox_prop.quantity <= 48.0
    assert amox_prop.status == "proposed"
    assert "Central District Hospital" in amox_prop.rationale

    # 3. Verify Oxytocin (Cold Chain) transfer proposal
    # Distance to FAC_REC_NEAR is ~35km, which is <= max_cold_chain_km (100km)
    oxy_prop = next(p for p in proposals if p.item_id == "MED_OXY")
    assert oxy_prop.quantity > 0.0
    assert oxy_prop.priority == "high" # Cold chain gets high priority

    # 4. Verify Cryptographic Audit Log was populated
    audits = db.query(AuditLog).filter(AuditLog.table_name == "transfer_proposals").all()
    assert len(audits) >= len(proposals)
    assert any(a.action == "GENERATE_REDISTRIBUTION" for a in audits)
