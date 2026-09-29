import math
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Tuple, Optional
from ortools.linear_solver import pywraplp
from sqlalchemy.orm import Session

from backend.app.models.facilities import Facility
from backend.app.models.items import Item
from backend.app.models.stock import StockBatch
from backend.app.models.intelligence import TransferProposal
from backend.app.models.audit import record_audit
from backend.app.core.logging import logger

def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes great-circle distance between two GPS coordinates in kilometers."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2.0) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

class RedistributionOptimizer:
    """
    Mixed-Integer Linear Programming (MILP) Redistribution Engine powered by Google OR-Tools.
    Matches surplus facilities (at risk of medicine expiry/wastage) with deficit facilities
    (at imminent risk of stockouts) subject to FEFO shelf-life, cold-chain transport limits,
    and road transit distance constraints.
    """
    def __init__(
        self,
        planning_horizon_days: int = 30,
        max_transit_km: float = 250.0,
        max_cold_chain_km: float = 100.0,
        min_shelf_life_margin_days: int = 14
    ):
        self.horizon_days = planning_horizon_days
        self.max_transit_km = max_transit_km
        self.max_cold_chain_km = max_cold_chain_km
        self.min_shelf_life_days = min_shelf_life_margin_days

    def solve_redistribution(
        self,
        db: Session,
        demand_forecasts: Dict[Tuple[str, str], float],
        actor: str = "redistribution_engine"
    ) -> List[TransferProposal]:
        """
        Computes optimal proactive stock transfers and persists TransferProposal records to DB.
        demand_forecasts: Dict[(facility_id, item_id)] -> forecast_demand_over_horizon
        """
        facilities = {f.id: f for f in db.query(Facility).all()}
        items = {it.id: it for it in db.query(Item).all()}
        batches = db.query(StockBatch).filter(StockBatch.current_quantity > 0, StockBatch.status == "active").all()

        now = datetime.now(timezone.utc)
        today = now.date()

        # Aggregate on-hand inventory per (facility, item) and compute expiring surplus
        on_hand: Dict[Tuple[str, str], float] = {}
        batch_lookup: Dict[Tuple[str, str], List[StockBatch]] = {}

        for b in batches:
            key = (b.facility_id, b.item_id)
            on_hand[key] = on_hand.get(key, 0.0) + float(b.current_quantity)
            if key not in batch_lookup:
                batch_lookup[key] = []
            batch_lookup[key].append(b)

        # Identify Donors (Surplus) and Recipients (Deficit)
        donors: Dict[Tuple[str, str], float] = {}
        recipients: Dict[Tuple[str, str], float] = {}

        for (fac_id, itm_id), f_demand in demand_forecasts.items():
            if fac_id not in facilities or itm_id not in items:
                continue

            current_stock = on_hand.get((fac_id, itm_id), 0.0)
            safety_stock = max(5.0, 0.20 * f_demand)

            if current_stock > (f_demand + safety_stock):
                surplus = current_stock - (f_demand + safety_stock)
                if surplus >= 1.0:
                    donors[(fac_id, itm_id)] = surplus
            elif current_stock < (f_demand + safety_stock):
                deficit = (f_demand + safety_stock) - current_stock
                if deficit >= 1.0:
                    recipients[(fac_id, itm_id)] = deficit

        logger.info(f"Redistribution Candidates: {len(donors)} donor pairs, {len(recipients)} recipient pairs")

        if not donors or not recipients:
            return []

        # Formulate OR-Tools Solver
        solver = pywraplp.Solver.CreateSolver("GLOP")
        if not solver:
            solver = pywraplp.Solver.CreateSolver("CBC")
        assert solver is not None, "Failed to initialize OR-Tools linear solver"

        x_vars = {}
        objective = solver.Objective()
        objective.SetMaximization()

        candidate_routes = []

        for (donor_id, itm_id), surplus_qty in donors.items():
            donor_fac = facilities[donor_id]
            item = items[itm_id]

            for (rec_id, rec_item_id), deficit_qty in recipients.items():
                if itm_id != rec_item_id or donor_id == rec_id:
                    continue

                rec_fac = facilities[rec_id]
                dist_km = haversine_distance_km(
                    donor_fac.latitude, donor_fac.longitude,
                    rec_fac.latitude, rec_fac.longitude
                )

                # Distance feasibility constraint
                if dist_km > self.max_transit_km:
                    continue

                # Cold-chain constraint: max distance / transit time in solar/ice packs
                if item.requires_cold_chain and dist_km > self.max_cold_chain_km:
                    continue

                # Shelf-life feasibility: donor must have batch that will not expire in transit
                valid_batches = [
                    b for b in batch_lookup.get((donor_id, itm_id), [])
                    if b.expiry_date >= (today + timedelta(days=self.min_shelf_life_days + int(dist_km / 100.0)))
                ]
                if not valid_batches:
                    continue

                # Variable: units of item transferred from donor to recipient
                var_name = f"x_{donor_id}_{rec_id}_{itm_id}"
                max_transfer = min(surplus_qty, deficit_qty)
                x = solver.NumVar(0.0, max_transfer, var_name)
                x_vars[(donor_id, rec_id, itm_id)] = x

                # Weighting: Priority for high-criticality items, penalized by transport distance
                crit_factor = 200.0 if item.criticality_tier == "A" else 100.0
                dist_penalty = 0.3 * dist_km
                profit_coeff = crit_factor - dist_penalty

                objective.SetCoefficient(x, profit_coeff)
                candidate_routes.append((donor_id, rec_id, itm_id, dist_km))

        if not x_vars:
            logger.info("No viable routes satisfied cold-chain or distance constraints")
            return []

        # Constraint 1: Donor Outflow <= Donor Surplus
        for (donor_id, itm_id), surplus_qty in donors.items():
            donor_vars = [x_vars[k] for k in x_vars if k[0] == donor_id and k[2] == itm_id]
            if donor_vars:
                constraint = solver.Constraint(0.0, surplus_qty)
                for v in donor_vars:
                    constraint.SetCoefficient(v, 1.0)

        # Constraint 2: Recipient Inflow <= Recipient Deficit
        for (rec_id, itm_id), deficit_qty in recipients.items():
            rec_vars = [x_vars[k] for k in x_vars if k[1] == rec_id and k[2] == itm_id]
            if rec_vars:
                constraint = solver.Constraint(0.0, deficit_qty)
                for v in rec_vars:
                    constraint.SetCoefficient(v, 1.0)

        # Solve
        status = solver.Solve()
        if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
            logger.warning(f"Redistribution solver finished with non-optimal status: {status}")
            return []

        proposals = []
        for (donor_id, rec_id, itm_id, dist_km) in candidate_routes:
            v = x_vars.get((donor_id, rec_id, itm_id))
            if v and v.solution_value() >= 1.0:
                transfer_qty = round(v.solution_value(), 1)
                item = items[itm_id]
                donor_fac = facilities[donor_id]
                rec_fac = facilities[rec_id]

                priority = "high" if item.criticality_tier == "A" or item.requires_cold_chain else "medium"
                proposal_id = f"PROP-{uuid.uuid4().hex[:8].upper()}"

                rationale = (
                    f"Proactive transfer of {transfer_qty} {item.unit_of_measure} of {item.name}: "
                    f"Relieves deficit at {rec_fac.name} while salvaging surplus at {donor_fac.name}. "
                    f"Transit distance: {dist_km:.1f} km."
                )

                # FEFO selection of batch
                donor_batches = [
                    b for b in batch_lookup.get((donor_id, itm_id), [])
                    if b.expiry_date >= (today + timedelta(days=self.min_shelf_life_days + int(dist_km / 100.0)))
                ]
                donor_batches.sort(key=lambda b: b.expiry_date)
                batch_id = donor_batches[0].id if donor_batches else "BATCH-UNKNOWN"

                # Cover days calculation
                d_demand = demand_forecasts.get((donor_id, itm_id), 1.0)
                d_daily = max(0.1, d_demand / self.horizon_days)
                d_stock = on_hand.get((donor_id, itm_id), 0.0)
                donor_cover_before = round(d_stock / d_daily, 1)
                donor_cover_after = round(max(0.0, d_stock - transfer_qty) / d_daily, 1)

                r_demand = demand_forecasts.get((rec_id, itm_id), 1.0)
                r_daily = max(0.1, r_demand / self.horizon_days)
                r_stock = on_hand.get((rec_id, itm_id), 0.0)
                rec_cover_before = round(r_stock / r_daily, 1)
                rec_cover_after = round((r_stock + transfer_qty) / r_daily, 1)

                eta_days = max(0.5, round(dist_km / 250.0, 1))

                prop = TransferProposal(
                    id=proposal_id,
                    donor_facility_id=donor_id,
                    recipient_facility_id=rec_id,
                    item_id=itm_id,
                    batch_id=batch_id,
                    quantity=transfer_qty,
                    donor_cover_days_before=donor_cover_before,
                    donor_cover_days_after=donor_cover_after,
                    recipient_cover_days_before=rec_cover_before,
                    recipient_cover_days_after=rec_cover_after,
                    eta_days=eta_days,
                    cold_chain_required=bool(item.requires_cold_chain),
                    priority=priority,
                    explanation=rationale,
                    status="proposed",
                    created_at=now
                )
                db.add(prop)
                proposals.append(prop)

                record_audit(
                    db=db,
                    table_name="transfer_proposals",
                    record_id=prop.id,
                    action="GENERATE_REDISTRIBUTION",
                    actor=actor,
                    new_state={
                        "source": donor_id,
                        "destination": rec_id,
                        "item": itm_id,
                        "quantity": transfer_qty,
                        "distance_km": round(dist_km, 1)
                    }
                )

        db.commit()
        logger.info(f"Redistribution Solver created {len(proposals)} transfer proposals")
        return proposals
