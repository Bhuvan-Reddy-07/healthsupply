import argparse
import sys
import time
from backend.app.core.database import SessionLocal, Base, engine
from backend.app.core.logging import logger
from simulator.generator import SyntheticDataGenerator
from simulator.outbreak import inject_outbreak
from backend.app.models.audit import verify_audit_log_integrity

def main():
    parser = argparse.ArgumentParser(description="HealthSupply Synthetic 2-Country Data Generator")
    parser.add_argument("--generate", action="store_true", help="Generate full synthetic dataset")
    parser.add_argument("--facilities", type=int, default=200, help="Total facilities across both countries (default: 200)")
    parser.add_argument("--items", type=int, default=150, help="Total items to generate (default: 150)")
    parser.add_argument("--months", type=int, default=24, help="Months of daily consumption history (default: 24)")
    parser.add_argument("--sample-facilities", type=int, default=None, help="Sample count of facilities to simulate history for (default: all)")
    parser.add_argument("--outbreak-district", type=str, default="Kolar", help="Inject demo outbreak in district")
    parser.add_argument("--outbreak-class", type=str, default="antimalarial", help="Outbreak target item class")
    parser.add_argument("--outbreak-multiplier", type=float, default=4.0, help="Outbreak surge multiplier")
    parser.add_argument("--outbreak-ramp", type=int, default=7, help="Outbreak ramp days")
    parser.add_argument("--inject-outbreak-only", action="store_true", help="Only inject outbreak on existing DB")

    args = parser.parse_args()

    # Ensure tables exist
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        if args.inject_outbreak_only:
            logger.info(f"Injecting outbreak into {args.outbreak_district} for {args.outbreak_class}...")
            res = inject_outbreak(
                db=db,
                district=args.outbreak_district,
                item_class=args.outbreak_class,
                multiplier=args.outbreak_multiplier,
                ramp_days=args.outbreak_ramp
            )
            logger.info(f"Outbreak injection successful: {res}")
            return

        if args.generate:
            start_t = time.time()
            logger.info("Starting HealthSupply Phase 0 Synthetic Data Generation...")
            gen = SyntheticDataGenerator(db=db)

            # 1. Facilities
            count_per_country = args.facilities // 2
            logger.info(f"Generating {args.facilities} facilities ({count_per_country} per country)...")
            facilities = gen.generate_facilities(count_per_country=count_per_country)
            logger.info(f"Generated {len(facilities)} facilities across Country_A and Country_B.")

            # 2. Items
            logger.info("Generating 150 item clinical catalog (~20 high-velocity, ~50 intermittent, ~10 cold-chain)...")
            items = gen.generate_items()
            logger.info(f"Generated {len(items)} items.")

            # 3. 24 Months Simulation
            logger.info(f"Simulating {args.months} months of daily consumption, monthly batches, and stockout censoring...")
            stats = gen.generate_simulation_history(
                facilities=facilities,
                items=items,
                months=args.months,
                sample_facilities_count=args.sample_facilities
            )
            logger.info(f"Simulation history generated: {stats}")

            # 4. Outbreak Injection Demo Run
            logger.info(f"Injecting demonstration outbreak into district '{args.outbreak_district}'...")
            outbreak_res = inject_outbreak(
                db=db,
                district=args.outbreak_district,
                item_class=args.outbreak_class,
                multiplier=args.outbreak_multiplier,
                ramp_days=args.outbreak_ramp
            )
            logger.info(f"Outbreak successfully injected: {outbreak_res}")

            # 5. Verify Tamper-evident Audit Integrity
            is_valid = verify_audit_log_integrity(db)
            logger.info(f"Audit log cryptographic chain verification: {'VALID (Zero Tampering)' if is_valid else 'FAILED'}")

            elapsed = round(time.time() - start_t, 2)
            logger.info(f"Phase 0 Generation completed in {elapsed}s.")
            print("\n=======================================================")
            print("  PHASE 0 SYNTHETIC DATA GENERATION SUCCESSFUL")
            print("=======================================================")
            print(f"Facilities:       {len(facilities)} (Country_A & Country_B)")
            print(f"Items:            {len(items)} (High-velocity, Intermittent, Cold-chain)")
            print(f"Total Batches:    {stats['total_batches']}")
            print(f"Transactions:     {stats['total_transactions']}")
            print(f"Censored Traps:   {stats['censored_stockouts']}")
            print(f"Outbreak Events:  {outbreak_res['stockout_censored_events']}")
            print(f"Audit Log Status: {'PASSED (Cryptographic Chain Verified)' if is_valid else 'FAILED'}")
            print("=======================================================\n")
    finally:
        db.close()

if __name__ == "__main__":
    main()
