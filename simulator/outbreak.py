import math
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from backend.app.models.facilities import Facility
from backend.app.models.items import Item
from backend.app.models.stock import StockBatch, StockTransaction
from backend.app.models.intelligence import Alert
from backend.app.models.audit import record_audit

def logistic_ramp(t: float, ramp_days: float, multiplier: float) -> float:
    """
    Computes a smooth logistic surge multiplier from 1.0 up to `multiplier`.
    Midpoint of the ramp is at ramp_days / 2.
    """
    if ramp_days <= 0:
        return multiplier
    k = 6.0 / ramp_days
    t_mid = ramp_days / 2.0
    # Logistic function bounded between 0 and 1
    sigmoid = 1.0 / (1.0 + math.exp(-k * (t - t_mid)))
    return 1.0 + (multiplier - 1.0) * sigmoid

def inject_outbreak(
    db: Session,
    district: str,
    item_class: str,
    multiplier: float = 3.5,
    ramp_days: int = 7,
    start_date: Optional[date] = None,
    duration_days: int = 21,
    actor: str = "outbreak_injector"
) -> Dict[str, Any]:
    """
    Injects a realistic disease outbreak into a specified district:
    - Spikes demand for matching items via a logistic ramp
    - Depletes stock batches rapidly under surge load
    - Tags censored=True when stock runs out, creating the training signal and stock-out trap
    - Raises early warning alert for CUSUM / detection engines
    """
    if not start_date:
        start_date = date.today() - timedelta(days=duration_days)

    # 1. Locate affected facilities in district
    facilities = db.query(Facility).filter(Facility.district == district).all()
    if not facilities:
        raise ValueError(f"No facilities found in district '{district}'")

    # 2. Locate affected items matching category
    items = db.query(Item).filter(Item.category == item_class).all()
    if not items:
        # Fallback to category substring match
        items = db.query(Item).filter(Item.category.ilike(f"%{item_class}%")).all()
    if not items:
        raise ValueError(f"No items found for category/class '{item_class}'")

    affected_tx_count = 0
    stockout_events = 0
    total_spiked_demand = 0.0

    facility_ids = [f.id for f in facilities]
    item_ids = [it.id for it in items]

    for day_offset in range(duration_days):
        current_dt = start_date + timedelta(days=day_offset)
        surge_factor = logistic_ramp(float(day_offset), float(ramp_days), multiplier)

        for fac in facilities:
            for itm in items:
                # Baseline normal daily demand for item in this facility
                base_demand = 8.0 if itm.velocity_class == "high_velocity" else 2.0
                if fac.tier == "DH":
                    base_demand *= 3.0
                elif fac.tier == "CHC":
                    base_demand *= 1.8

                surged_demand = round(base_demand * surge_factor, 1)
                total_spiked_demand += surged_demand

                # Fetch active batches under FEFO
                batches = (
                    db.query(StockBatch)
                    .filter(
                        StockBatch.facility_id == fac.id,
                        StockBatch.item_id == itm.id,
                        StockBatch.status == "active",
                        StockBatch.current_quantity > 0
                    )
                    .order_by(StockBatch.expiry_date.asc())
                    .all()
                )

                total_stock = sum(b.current_quantity for b in batches)

                crdt_id = f"CRDT-OUTBREAK-{fac.id}-{itm.id}-{current_dt.isoformat()}"
                tx_timestamp = datetime(current_dt.year, current_dt.month, current_dt.day, 11, 30, tzinfo=timezone.utc)

                if total_stock <= 0:
                    # Stock-out censoring: stock is 0, recorded consumption is 0, censored=True
                    tx = StockTransaction(
                        id=f"TX-{uuid.uuid4().hex[:12]}",
                        crdt_tx_id=crdt_id,
                        facility_id=fac.id,
                        item_id=itm.id,
                        batch_id=None,
                        tx_type="dispense",
                        quantity=0.0,
                        censored=True,
                        unfulfilled_quantity=surged_demand,
                        tx_timestamp=tx_timestamp,
                        source="simulator",
                        source_reliability_score=1.0,
                        data_quality_score=1.0
                    )
                    db.add(tx)
                    stockout_events += 1
                    affected_tx_count += 1
                else:
                    needed = surged_demand
                    dispensed = 0.0
                    assigned_batch = None

                    if total_stock < needed:
                        # Partial stockout
                        unfulfilled = needed - total_stock
                        dispensed = total_stock
                        is_censored = True
                        stockout_events += 1
                    else:
                        unfulfilled = 0.0
                        dispensed = needed
                        is_censored = False

                    remaining = dispensed
                    for b in batches:
                        if remaining <= 0:
                            break
                        deduct = min(b.current_quantity, remaining)
                        b.current_quantity -= deduct
                        remaining -= deduct
                        assigned_batch = b.id
                        if b.current_quantity == 0:
                            b.status = "depleted"

                    tx = StockTransaction(
                        id=f"TX-{uuid.uuid4().hex[:12]}",
                        crdt_tx_id=crdt_id,
                        facility_id=fac.id,
                        item_id=itm.id,
                        batch_id=assigned_batch,
                        tx_type="dispense",
                        quantity=dispensed,
                        censored=is_censored,
                        unfulfilled_quantity=unfulfilled,
                        tx_timestamp=tx_timestamp,
                        source="simulator",
                        source_reliability_score=1.0,
                        data_quality_score=1.0
                    )
                    db.add(tx)
                    affected_tx_count += 1

    # Create system alert for outbreak detection
    alert = Alert(
        id=f"ALT-OUTBREAK-{uuid.uuid4().hex[:8]}",
        facility_id=facilities[0].id,
        item_id=items[0].id,
        alert_type="outbreak_detected",
        severity="red",
        days_remaining=2.5,
        p_stockout_before_lead=0.95,
        message=f"Epidemic demand surge: {multiplier}x ramp in district '{district}' across {len(facilities)} facilities for {item_class}."
    )
    db.add(alert)
    db.commit()

    record_audit(
        db=db,
        table_name="alerts",
        record_id=alert.id,
        action="INJECT_OUTBREAK",
        actor=actor,
        new_state={"district": district, "item_class": item_class, "multiplier": multiplier, "ramp_days": ramp_days}
    )

    return {
        "district": district,
        "item_class": item_class,
        "facilities_affected": len(facilities),
        "items_affected": len(items),
        "duration_days": duration_days,
        "peak_multiplier": multiplier,
        "transactions_generated": affected_tx_count,
        "stockout_censored_events": stockout_events,
        "total_surged_demand": round(total_spiked_demand, 1),
        "alert_id": alert.id
    }
