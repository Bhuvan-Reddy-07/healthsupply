import math
import random
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import List, Dict, Any, Tuple
import numpy as np
from sqlalchemy.orm import Session

from backend.app.models.facilities import Facility
from backend.app.models.items import Item
from backend.app.models.stock import StockBatch, StockTransaction
from backend.app.models.bed_staff import BedState, StaffAttendance
from backend.app.models.intelligence import Forecast, Alert
from backend.app.models.audit import record_audit
from simulator.data_items import generate_150_items

# Districts & geographic clusters for Country A & Country B
COUNTRY_A_DISTRICTS = [
    {"name": "Kolar", "lat": 13.1367, "lon": 78.1291},
    {"name": "Hospet", "lat": 15.2689, "lon": 76.3909},
    {"name": "Bellary", "lat": 15.1394, "lon": 76.9214},
    {"name": "Shimoga", "lat": 13.9299, "lon": 75.5681},
    {"name": "Tumkur", "lat": 13.3409, "lon": 77.1010},
]

COUNTRY_B_DISTRICTS = [
    {"name": "Sylhet", "lat": 24.8949, "lon": 91.8687},
    {"name": "Chittagong", "lat": 22.3569, "lon": 91.7832},
    {"name": "Khulna", "lat": 22.8456, "lon": 89.5403},
    {"name": "Rajshahi", "lat": 24.3636, "lon": 88.6241},
    {"name": "Barisal", "lat": 22.7010, "lon": 90.3535},
]

class SyntheticDataGenerator:
    def __init__(self, db: Session, random_seed: int = 42):
        self.db = db
        self.rng = np.random.default_rng(random_seed)
        random.seed(random_seed)

    def generate_facilities(self, count_per_country: int = 100) -> List[Facility]:
        """
        Generates ~200 facilities across Country A and Country B with realistic tiers (PHC/CHC/DH)
        and lat/lon clustering around districts.
        """
        facilities = []
        
        # Country A
        for i in range(count_per_country):
            dist = COUNTRY_A_DISTRICTS[i % len(COUNTRY_A_DISTRICTS)]
            tier = "DH" if i % 10 == 0 else ("CHC" if i % 5 == 0 else "PHC")
            has_cold = True if tier in ["DH", "CHC"] else (random.random() < 0.45)
            cap = 600.0 if tier == "DH" else (200.0 if tier == "CHC" else (50.0 if has_cold else 0.0))
            
            # Lat/Lon with small jitter (+- 0.15 deg)
            lat = dist["lat"] + float(self.rng.normal(0, 0.08))
            lon = dist["lon"] + float(self.rng.normal(0, 0.08))
            pop = 80000 if tier == "DH" else (30000 if tier == "CHC" else 8000)

            fac = Facility(
                id=f"FAC-A-{i+1:03d}",
                name=f"{dist['name']} {tier} #{i+1}",
                country="Country_A",
                region="Region_South",
                district=dist["name"],
                tier=tier,
                latitude=round(lat, 5),
                longitude=round(lon, 5),
                has_cold_chain=has_cold,
                cold_chain_capacity_liters=cap,
                population_served=pop,
                contact_phone=f"+91-9845{i+1:04d}"
            )
            facilities.append(fac)

        # Country B
        for i in range(count_per_country):
            dist = COUNTRY_B_DISTRICTS[i % len(COUNTRY_B_DISTRICTS)]
            tier = "DH" if i % 10 == 0 else ("CHC" if i % 5 == 0 else "PHC")
            has_cold = True if tier in ["DH", "CHC"] else (random.random() < 0.35)
            cap = 500.0 if tier == "DH" else (180.0 if tier == "CHC" else (40.0 if has_cold else 0.0))
            
            lat = dist["lat"] + float(self.rng.normal(0, 0.08))
            lon = dist["lon"] + float(self.rng.normal(0, 0.08))
            pop = 95000 if tier == "DH" else (35000 if tier == "CHC" else 9000)

            fac = Facility(
                id=f"FAC-B-{i+1:03d}",
                name=f"{dist['name']} {tier} #{i+1}",
                country="Country_B",
                region="Region_Delta",
                district=dist["name"],
                tier=tier,
                latitude=round(lat, 5),
                longitude=round(lon, 5),
                has_cold_chain=has_cold,
                cold_chain_capacity_liters=cap,
                population_served=pop,
                contact_phone=f"+880-171{i+1:04d}"
            )
            facilities.append(fac)

        self.db.add_all(facilities)
        self.db.commit()
        return facilities

    def generate_items(self) -> List[Item]:
        """Populates the database with exactly 150 items catalogued by clinical class."""
        catalog = generate_150_items()
        items = []
        for it in catalog:
            item_obj = Item(
                id=it["id"],
                name=it["name"],
                category=it["category"],
                dosage_form=it["dosage_form"],
                unit_of_measure=it["unit_of_measure"],
                velocity_class=it["velocity_class"],
                requires_cold_chain=it.get("requires_cold_chain", False),
                temp_min_c=it.get("temp_min_c"),
                temp_max_c=it.get("temp_max_c"),
                unit_cost_usd=it.get("unit_cost_usd", 1.0),
                shelf_life_days=it.get("shelf_life_days", 730),
                criticality_tier=it.get("criticality_tier", "B")
            )
            items.append(item_obj)
            
        self.db.add_all(items)
        self.db.commit()
        return items

    def _calc_daily_seasonality(self, day_of_year: int, country: str, item_category: str) -> float:
        """
        Sinusoid seasonality models:
        - Country A: Monsoon spike in antimalarials (June-Sept / day 160-260).
          Summer dengue wave in antipyretics (March-May / day 70-150).
        - Country B: Non-IID seasonal mix! Late monsoon spike (July-Oct / day 190-290).
          Winter respiratory / antibiotic surge (Nov-Jan / day 310-365 and 1-30).
        """
        # Base sinusoidal wave
        angle = 2.0 * math.pi * (day_of_year / 365.25)
        seasonal_mult = 1.0

        if country == "Country_A":
            if item_category == "antimalarial":
                # Monsoon spike centered at day 210 (August)
                seasonal_mult += 2.2 * max(0.0, math.sin(math.pi * max(0.0, (day_of_year - 150)) / 120.0))
            elif item_category in ["antipyretic", "rehydration"]:
                # Summer dengue & diarrheal wave centered at day 110 (April)
                seasonal_mult += 1.8 * max(0.0, math.sin(math.pi * max(0.0, (day_of_year - 60)) / 100.0))
        else: # Country_B (Non-IID shifted parameters)
            if item_category == "antimalarial":
                # Late monsoon centered at day 240
                seasonal_mult += 1.9 * max(0.0, math.sin(math.pi * max(0.0, (day_of_year - 180)) / 110.0))
            elif item_category in ["antibiotic", "respiratory"]:
                # Winter respiratory spike centered around Dec/Jan
                winter_val = math.cos(angle) # peaks at day 0/365
                seasonal_mult += 1.6 * max(0.0, winter_val)

        return max(0.2, seasonal_mult)

    def _clinic_day_multiplier(self, day_of_week: int) -> float:
        """
        Weekly clinic-day cycles:
        Monday (0) and Wednesday (2) are heavy immunization and clinic days.
        """
        if day_of_week == 0:    # Monday
            return 1.6
        elif day_of_week == 2:  # Wednesday
            return 1.5
        elif day_of_week in [1, 3]: # Tuesday, Thursday
            return 1.0
        elif day_of_week == 4:  # Friday
            return 1.1
        elif day_of_week == 5:  # Saturday
            return 0.5
        else:                   # Sunday (Emergency only)
            return 0.25

    def generate_simulation_history(
        self,
        facilities: List[Facility],
        items: List[Item],
        months: int = 24,
        sample_facilities_count: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Simulates 24 months of daily consumption, monthly batch shipments,
        and stock-out censoring.
        """
        start_date = date.today() - timedelta(days=months * 30)
        total_days = months * 30
        
        # If sampling requested (e.g. for rapid execution during testing)
        target_facilities = facilities[:sample_facilities_count] if sample_facilities_count else facilities
        
        total_batches = 0
        total_transactions = 0
        censored_stockouts = 0

        # Fast tracking of on-hand inventory per (facility_id, item_id)
        # Value is list of active batches: [{"id": id, "qty": qty, "exp": exp_date}]
        on_hand_inventory: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}

        # 1. Initial supply shipments for each facility & item
        for fac in target_facilities:
            for itm in items:
                key = (fac.id, itm.id)
                on_hand_inventory[key] = []
                
                # Base initial quantity scaled by tier and velocity class
                base_qty = 150.0 if itm.velocity_class == "high_velocity" else (20.0 if itm.velocity_class == "intermittent" else 60.0)
                if fac.tier == "DH":
                    base_qty *= 3.0
                elif fac.tier == "CHC":
                    base_qty *= 1.8
                
                # Create initial batch
                batch_id = f"BATCH-{fac.id}-{itm.id}-INIT"
                mfg = start_date - timedelta(days=60)
                exp = start_date + timedelta(days=itm.shelf_life_days - 60)
                gtin = f"0890{random.randint(100000000, 999999999)}"

                b = StockBatch(
                    id=batch_id,
                    batch_number=f"B-{random.randint(1000, 9999)}",
                    facility_id=fac.id,
                    item_id=itm.id,
                    current_quantity=base_qty,
                    initial_quantity=base_qty,
                    mfg_date=mfg,
                    expiry_date=exp,
                    gs1_gtin=gtin,
                    status="active",
                    received_at=datetime(mfg.year, mfg.month, mfg.day, 8, 0, tzinfo=timezone.utc)
                )
                self.db.add(b)
                total_batches += 1
                on_hand_inventory[key].append({"id": batch_id, "qty": base_qty, "exp": exp, "db_obj": b})

        self.db.commit()

        # Batch insert buffer for transactions
        tx_buffer = []

        # 2. Daily simulation loop over total_days
        for day_idx in range(total_days):
            current_day = start_date + timedelta(days=day_idx)
            day_of_year = current_day.timetuple().tm_yday
            day_of_week = current_day.weekday()
            clinic_mult = self._clinic_day_multiplier(day_of_week)

            # Monthly shipment arrival every 30 days
            is_shipment_day = (day_idx > 0 and day_idx % 30 == 0)

            for fac in target_facilities:
                for itm in items:
                    key = (fac.id, itm.id)
                    batches = on_hand_inventory[key]

                    # Monthly Replenishment
                    if is_shipment_day:
                        # Periodic replenishment
                        replenish_qty = 100.0 if itm.velocity_class == "high_velocity" else (15.0 if itm.velocity_class == "intermittent" else 45.0)
                        if fac.tier == "DH":
                            replenish_qty *= 2.5
                        
                        mfg = current_day - timedelta(days=15)
                        exp = current_day + timedelta(days=itm.shelf_life_days)
                        b_id = f"BATCH-{fac.id}-{itm.id}-M{day_idx // 30}"
                        new_batch = StockBatch(
                            id=b_id,
                            batch_number=f"B-{random.randint(1000, 9999)}",
                            facility_id=fac.id,
                            item_id=itm.id,
                            current_quantity=replenish_qty,
                            initial_quantity=replenish_qty,
                            mfg_date=mfg,
                            expiry_date=exp,
                            gs1_gtin=f"0890{random.randint(100000000, 999999999)}",
                            status="active",
                            received_at=datetime(current_day.year, current_day.month, current_day.day, 9, 0, tzinfo=timezone.utc)
                        )
                        self.db.add(new_batch)
                        total_batches += 1
                        batches.append({"id": b_id, "qty": replenish_qty, "exp": exp, "db_obj": new_batch})

                    # Calculate Daily Demand
                    if itm.velocity_class == "intermittent":
                        # Croston territory: demand occurs probabilistically
                        p_demand = 0.08 if fac.tier == "PHC" else (0.15 if fac.tier == "CHC" else 0.25)
                        if random.random() < p_demand:
                            true_demand = float(self.rng.poisson(lam=2.0) + 1)
                        else:
                            true_demand = 0.0
                    else:
                        base_rate = 6.0 if itm.velocity_class == "high_velocity" else 2.0
                        if fac.tier == "DH":
                            base_rate *= 3.0
                        elif fac.tier == "CHC":
                            base_rate *= 1.8

                        season_mult = self._calc_daily_seasonality(day_of_year, fac.country, itm.category)
                        # Add Gamma distributed facility noise
                        noise = float(self.rng.gamma(shape=4.0, scale=0.25)) # mean = 1.0
                        mean_daily = base_rate * season_mult * clinic_mult * noise
                        true_demand = round(max(0.0, float(self.rng.poisson(lam=max(0.5, mean_daily)))), 1)

                    if true_demand <= 0:
                        continue

                    # Check available stock across batches
                    available_batches = [b for b in batches if b["qty"] > 0 and b["exp"] >= current_day]
                    total_stock = sum(b["qty"] for b in available_batches)

                    tx_timestamp = datetime(current_day.year, current_day.month, current_day.day, 14, 0, tzinfo=timezone.utc)
                    crdt_id = f"CRDT-{fac.id}-{itm.id}-{day_idx}"

                    if total_stock <= 0:
                        # STOCK-OUT CENSORED DEMAND TRAP
                        # Recorded consumption = 0, censored=True, unfulfilled=true_demand
                        tx_buffer.append(
                            StockTransaction(
                                id=f"TX-{uuid.uuid4().hex[:12]}",
                                crdt_tx_id=crdt_id,
                                facility_id=fac.id,
                                item_id=itm.id,
                                batch_id=None,
                                tx_type="dispense",
                                quantity=0.0,
                                censored=True,
                                unfulfilled_quantity=true_demand,
                                tx_timestamp=tx_timestamp,
                                source="simulator",
                                source_reliability_score=1.0,
                                data_quality_score=1.0
                            )
                        )
                        censored_stockouts += 1
                        total_transactions += 1
                    else:
                        # FEFO Allocation
                        available_batches.sort(key=lambda x: x["exp"])
                        if total_stock < true_demand:
                            # Partial stockout
                            unfulfilled = true_demand - total_stock
                            dispensed = total_stock
                            is_censored = True
                            censored_stockouts += 1
                        else:
                            unfulfilled = 0.0
                            dispensed = true_demand
                            is_censored = False

                        remaining = dispensed
                        assigned_b_id = None
                        for b_dict in available_batches:
                            if remaining <= 0:
                                break
                            deduct = min(b_dict["qty"], remaining)
                            b_dict["qty"] -= deduct
                            remaining -= deduct
                            assigned_b_id = b_dict["id"]
                            b_dict["db_obj"].current_quantity = b_dict["qty"]
                            if b_dict["qty"] == 0:
                                b_dict["db_obj"].status = "depleted"

                        tx_buffer.append(
                            StockTransaction(
                                id=f"TX-{uuid.uuid4().hex[:12]}",
                                crdt_tx_id=crdt_id,
                                facility_id=fac.id,
                                item_id=itm.id,
                                batch_id=assigned_b_id,
                                tx_type="dispense",
                                quantity=dispensed,
                                censored=is_censored,
                                unfulfilled_quantity=unfulfilled,
                                tx_timestamp=tx_timestamp,
                                source="simulator",
                                source_reliability_score=1.0,
                                data_quality_score=1.0
                            )
                        )
                        total_transactions += 1

            # Flush buffer periodically to maintain low memory profile
            if len(tx_buffer) >= 2000:
                self.db.add_all(tx_buffer)
                self.db.commit()
                tx_buffer.clear()

        # Flush any remaining transactions
        if tx_buffer:
            self.db.add_all(tx_buffer)
            self.db.commit()
            tx_buffer.clear()

        # Audit the completed simulation run
        record_audit(
            db=self.db,
            table_name="stock_transactions",
            record_id=f"SIM-{months}M",
            action="SIMULATION_RUN",
            actor="simulator_engine",
            new_state={
                "facilities": len(target_facilities),
                "items": len(items),
                "months": months,
                "total_batches": total_batches,
                "total_transactions": total_transactions,
                "censored_stockouts": censored_stockouts
            }
        )

        return {
            "facilities": len(target_facilities),
            "items": len(items),
            "months": months,
            "total_batches": total_batches,
            "total_transactions": total_transactions,
            "censored_stockouts": censored_stockouts
        }
