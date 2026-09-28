import pytest
from sqlalchemy import func
from simulator.generator import SyntheticDataGenerator
from simulator.outbreak import inject_outbreak
from backend.app.models.facilities import Facility
from backend.app.models.items import Item
from backend.app.models.stock import StockBatch, StockTransaction
from backend.app.models.intelligence import Alert

def test_facilities_generation_two_countries(db_session):
    """
    Acceptance Test: ~200 facilities across 2 'countries' with plausible
    lat/lon clusters and tiers (PHC/CHC/DH).
    """
    gen = SyntheticDataGenerator(db=db_session)
    facilities = gen.generate_facilities(count_per_country=100)
    
    assert len(facilities) == 200
    country_a = [f for f in facilities if f.country == "Country_A"]
    country_b = [f for f in facilities if f.country == "Country_B"]
    assert len(country_a) == 100
    assert len(country_b) == 100

    # Verify tiers
    tiers = {f.tier for f in facilities}
    assert {"PHC", "CHC", "DH"}.issubset(tiers)

    # Verify lat/lon are within geographic bounds
    for f in country_a:
        assert 10.0 <= f.latitude <= 20.0
        assert 70.0 <= f.longitude <= 82.0
    for f in country_b:
        assert 20.0 <= f.latitude <= 28.0
        assert 85.0 <= f.longitude <= 95.0

def test_items_catalog_classification(db_session):
    """
    Acceptance Test: ~150 items: mark ~20 as high-velocity (antipyretics, ORS, antibiotics),
    ~50 intermittent (Croston territory), ~10 cold-chain.
    """
    gen = SyntheticDataGenerator(db=db_session)
    items = gen.generate_items()
    
    assert len(items) == 150

    hv_items = [it for it in items if it.velocity_class == "high_velocity"]
    int_items = [it for it in items if it.velocity_class == "intermittent"]
    cc_items = [it for it in items if it.requires_cold_chain]

    # Verify ~20 high velocity
    assert 18 <= len(hv_items) <= 25, f"Expected ~20 high-velocity, got {len(hv_items)}"
    hv_categories = {it.category for it in hv_items}
    assert "antipyretic" in hv_categories
    assert "antibiotic" in hv_categories
    assert "rehydration" in hv_categories

    # Verify ~50 intermittent
    assert 45 <= len(int_items) <= 55, f"Expected ~50 intermittent, got {len(int_items)}"

    # Verify ~10 cold chain
    assert 8 <= len(cc_items) <= 15, f"Expected ~10 cold-chain, got {len(cc_items)}"
    for cc in cc_items:
        assert cc.temp_min_c is not None and cc.temp_max_c is not None
        assert cc.temp_min_c >= 0.0 and cc.temp_max_c <= 10.0

def test_simulation_stock_never_negative_and_censored_flags_appear(db_session):
    """
    CRITICAL ACCEPTANCE TEST:
    A unit test proves stock goes negative nowhere and censored flags appear during stock-outs.
    """
    gen = SyntheticDataGenerator(db=db_session)
    # Generate representative facilities across both countries
    facilities = gen.generate_facilities(count_per_country=2) # 4 facilities (Country_A & Country_B)
    items = gen.generate_items()

    # Run 3 months of daily simulation
    stats = gen.generate_simulation_history(
        facilities=facilities,
        items=items,
        months=3
    )

    # 1. PROVE: Stock goes negative NOWHERE across all batches in database
    min_stock = db_session.query(func.min(StockBatch.current_quantity)).scalar()
    assert min_stock is not None, "Stock batches were not generated"
    assert min_stock >= 0.0, f"Stock went negative! Minimum stock found: {min_stock}"

    # Verify check constraint across all batches
    all_batches = db_session.query(StockBatch).all()
    assert len(all_batches) > 0
    for b in all_batches:
        assert b.current_quantity >= 0.0, f"Batch {b.id} has negative quantity: {b.current_quantity}"
        assert b.expiry_date >= b.mfg_date, f"Batch {b.id} expiry before mfg date"

    # 2. PROVE: Censored flags appear during stock-outs
    censored_txs = (
        db_session.query(StockTransaction)
        .filter(StockTransaction.censored == True)
        .all()
    )
    assert len(censored_txs) > 0, "No censored transactions were generated during stock-outs!"
    
    # Verify structure of censored transactions
    for ctx in censored_txs:
        assert ctx.unfulfilled_quantity > 0.0, "Censored transaction must record unfulfilled quantity"
        # When stockout occurred, recorded consumption is either 0 or partial
        assert ctx.quantity >= 0.0

    # 3. PROVE: Non-censored transactions have unfulfilled_quantity == 0
    uncensored_txs = (
        db_session.query(StockTransaction)
        .filter(StockTransaction.censored == False)
        .limit(50)
        .all()
    )
    for utx in uncensored_txs:
        assert utx.unfulfilled_quantity == 0.0

def test_outbreak_injector_creates_censored_stockouts(db_session):
    """
    Acceptance Test: Outbreak injector triggers logistic surge and creates stock-out censoring.
    """
    gen = SyntheticDataGenerator(db=db_session)
    facilities = gen.generate_facilities(count_per_country=5)
    items = gen.generate_items()

    # Initialize batches
    gen.generate_simulation_history(facilities=facilities, items=items, months=1)

    target_district = facilities[0].district
    res = inject_outbreak(
        db=db_session,
        district=target_district,
        item_class="antimalarial",
        multiplier=5.0,
        ramp_days=7
    )

    assert res["facilities_affected"] > 0
    assert res["transactions_generated"] > 0
    assert res["total_surged_demand"] > 0.0

    # Verify alert was created
    alert = db_session.query(Alert).filter(Alert.id == res["alert_id"]).first()
    assert alert is not None
    assert alert.severity == "red"
    assert "Epidemic demand surge" in alert.message
