import random
from typing import List, Dict, Any

# Catalog definition ensuring:
# ~20 high-velocity (antipyretics, ORS, antibiotics)
# ~50 intermittent (rare, antivenom, emergency, specialized)
# ~10 cold-chain (vaccines, oxytocin, insulin)
# ~70 standard maintenance drugs (cardiovascular, diabetes, maternal, antiseptics)

HIGH_VELOCITY_ITEMS = [
    {"name": "Paracetamol 500mg Tablet", "category": "antipyretic", "dosage_form": "tablet", "unit": "strip", "cost": 0.40, "shelf": 730},
    {"name": "Paracetamol 120mg/5ml Syrup", "category": "antipyretic", "dosage_form": "suspension", "unit": "bottle", "cost": 0.85, "shelf": 730},
    {"name": "Ibuprofen 400mg Tablet", "category": "antipyretic", "dosage_form": "tablet", "unit": "strip", "cost": 0.55, "shelf": 730},
    {"name": "Oral Rehydration Salts (ORS) 20.5g", "category": "rehydration", "dosage_form": "sachet", "unit": "sachet", "cost": 0.20, "shelf": 1095},
    {"name": "Zinc Sulfate 20mg Dispersible Tablet", "category": "rehydration", "dosage_form": "tablet", "unit": "strip", "cost": 0.30, "shelf": 730},
    {"name": "Amoxicillin 500mg Capsule", "category": "antibiotic", "dosage_form": "capsule", "unit": "strip", "cost": 0.90, "shelf": 730},
    {"name": "Amoxicillin 250mg Dispersible Tablet", "category": "antibiotic", "dosage_form": "tablet", "unit": "strip", "cost": 0.70, "shelf": 730},
    {"name": "Amoxicillin-Clavulanic Acid 625mg", "category": "antibiotic", "dosage_form": "tablet", "unit": "strip", "cost": 1.80, "shelf": 730},
    {"name": "Azithromycin 500mg Tablet", "category": "antibiotic", "dosage_form": "tablet", "unit": "strip", "cost": 1.20, "shelf": 730},
    {"name": "Ciprofloxacin 500mg Tablet", "category": "antibiotic", "dosage_form": "tablet", "unit": "strip", "cost": 0.80, "shelf": 730},
    {"name": "Metronidazole 400mg Tablet", "category": "antibiotic", "dosage_form": "tablet", "unit": "strip", "cost": 0.45, "shelf": 730},
    {"name": "Ceftriaxone 1g Injection Vial", "category": "antibiotic", "dosage_form": "vial", "unit": "vial", "cost": 2.10, "shelf": 730},
    {"name": "Cotrimoxazole 480mg Tablet", "category": "antibiotic", "dosage_form": "tablet", "unit": "strip", "cost": 0.50, "shelf": 730},
    {"name": "Artemether-Lumefantrine 20/120mg (Adult)", "category": "antimalarial", "dosage_form": "tablet", "unit": "box", "cost": 2.50, "shelf": 730},
    {"name": "Artemether-Lumefantrine 20/120mg (Pediatric)", "category": "antimalarial", "dosage_form": "tablet", "unit": "box", "cost": 1.80, "shelf": 730},
    {"name": "Injectable Artesunate 60mg", "category": "antimalarial", "dosage_form": "vial", "unit": "vial", "cost": 3.80, "shelf": 730},
    {"name": "Chloroquine Phosphate 250mg", "category": "antimalarial", "dosage_form": "tablet", "unit": "strip", "cost": 0.60, "shelf": 1095},
    {"name": "Albendazole 400mg Chewable Tablet", "category": "antiparasitic", "dosage_form": "tablet", "unit": "strip", "cost": 0.35, "shelf": 1095},
    {"name": "Cetirizine 10mg Tablet", "category": "antihistamine", "dosage_form": "tablet", "unit": "strip", "cost": 0.25, "shelf": 1095},
    {"name": "Dextromethorphan Cough Syrup 100ml", "category": "respiratory", "dosage_form": "suspension", "unit": "bottle", "cost": 1.10, "shelf": 730},
]

COLD_CHAIN_ITEMS = [
    {"name": "Oxytocin Injection 10 IU/ml", "category": "maternal_health", "dosage_form": "ampoule", "unit": "ampoule", "cost": 1.50, "shelf": 730, "min_temp": 2.0, "max_temp": 8.0},
    {"name": "Insulin Human Regular 100 IU/ml", "category": "endocrine", "dosage_form": "vial", "unit": "vial", "cost": 6.50, "shelf": 540, "min_temp": 2.0, "max_temp": 8.0},
    {"name": "Insulin NPH Intermediate 100 IU/ml", "category": "endocrine", "dosage_form": "vial", "unit": "vial", "cost": 6.80, "shelf": 540, "min_temp": 2.0, "max_temp": 8.0},
    {"name": "BCG Vaccine (Tuberculosis) 20 doses", "category": "vaccine", "dosage_form": "vial", "unit": "vial", "cost": 4.20, "shelf": 730, "min_temp": 2.0, "max_temp": 8.0},
    {"name": "Pentavalent DTP-HepB-Hib Vaccine", "category": "vaccine", "dosage_form": "vial", "unit": "vial", "cost": 5.50, "shelf": 730, "min_temp": 2.0, "max_temp": 8.0},
    {"name": "Rotavirus Oral Vaccine", "category": "vaccine", "dosage_form": "vial", "unit": "vial", "cost": 4.80, "shelf": 540, "min_temp": 2.0, "max_temp": 8.0},
    {"name": "Inactivated Polio Vaccine (IPV)", "category": "vaccine", "dosage_form": "vial", "unit": "vial", "cost": 3.90, "shelf": 730, "min_temp": 2.0, "max_temp": 8.0},
    {"name": "Measles-Rubella (MR) Vaccine", "category": "vaccine", "dosage_form": "vial", "unit": "vial", "cost": 3.50, "shelf": 730, "min_temp": 2.0, "max_temp": 8.0},
    {"name": "Hepatitis B Pediatric Vaccine", "category": "vaccine", "dosage_form": "vial", "unit": "vial", "cost": 3.20, "shelf": 730, "min_temp": 2.0, "max_temp": 8.0},
    {"name": "Rabies Purified Vero Cell Vaccine", "category": "vaccine", "dosage_form": "vial", "unit": "vial", "cost": 12.00, "shelf": 730, "min_temp": 2.0, "max_temp": 8.0},
]

INTERMITTENT_BASE = [
    ("Polyvalent Snake Antivenom 10ml", "antidote", "vial", 45.0, 730),
    ("Rabies Human Immunoglobulin (RIG)", "antidote", "vial", 65.0, 540),
    ("Naloxone 0.4mg/ml Injection", "emergency", "ampoule", 5.50, 730),
    ("Magnesium Sulfate 50% Injection (Eclampsia)", "maternal_health", "ampoule", 2.20, 1095),
    ("Tranexamic Acid 500mg Injection (PPH)", "maternal_health", "ampoule", 3.10, 730),
    ("Dantrolene Sodium 20mg IV", "emergency", "vial", 85.0, 730),
    ("Glucagon 1mg HypoKit", "endocrine", "kit", 38.0, 540),
    ("Epinephrine (Adrenaline) 1:1000 Ampoule", "emergency", "ampoule", 1.80, 540),
    ("Atropine Sulfate 0.6mg Injection", "emergency", "ampoule", 1.20, 1095),
    ("Pralidoxime (2-PAM) 1g Injection", "antidote", "vial", 22.0, 730),
    ("Sodium Nitrite 3% Injection", "antidote", "ampoule", 14.0, 730),
    ("Sodium Thiosulfate 25% Injection", "antidote", "ampoule", 12.0, 730),
    ("Methylene Blue 1% Injection", "antidote", "ampoule", 16.0, 730),
    ("Deferoxamine Mesylate 500mg", "antidote", "vial", 18.0, 730),
    ("Dimercaprol (BAL) 100mg/2ml", "antidote", "ampoule", 25.0, 730),
    ("Calcium Disodium EDTA 200mg/ml", "antidote", "ampoule", 28.0, 730),
    ("Phytomenadione (Vitamin K1) 10mg", "hematology", "ampoule", 2.00, 730),
    ("Protamine Sulfate 10mg/ml", "hematology", "ampoule", 4.50, 730),
    ("Succinylcholine Chloride 50mg/ml", "anesthesia", "vial", 6.20, 540),
    ("Pancuronium Bromide 2mg/ml", "anesthesia", "ampoule", 5.80, 540),
    ("Neostigmine Methylsulfate 0.5mg/ml", "anesthesia", "ampoule", 2.40, 1095),
    ("Thiopental Sodium 500mg Powder", "anesthesia", "vial", 7.50, 730),
    ("Ketamine Hydrochloride 50mg/ml", "anesthesia", "vial", 4.50, 730),
    ("Diazepam 5mg/ml Injection", "neuro", "ampoule", 1.50, 1095),
    ("Phenytoin Sodium 50mg/ml Injection", "neuro", "vial", 3.40, 730),
    ("Phenobarbital 100mg/ml Injection", "neuro", "ampoule", 2.10, 1095),
    ("Digoxin 0.25mg/ml Injection", "cardio", "ampoule", 3.00, 730),
    ("Amiodarone 50mg/ml Injection", "cardio", "ampoule", 4.20, 730),
    ("Adenosine 3mg/ml Injection", "cardio", "vial", 8.50, 730),
    ("Dopamine Hydrochloride 40mg/ml", "cardio", "ampoule", 2.80, 730),
    ("Norepinephrine Bitartrate 2mg/ml", "cardio", "ampoule", 7.20, 730),
    ("Sodium Nitroprusside 50mg IV", "cardio", "vial", 18.0, 730),
    ("Labetalol 5mg/ml Injection", "cardio", "vial", 5.50, 730),
    ("Hydralazine 20mg/ml Injection", "cardio", "ampoule", 4.80, 730),
    ("Mannitol 20% IV Infusion 500ml", "neuro", "bottle", 3.60, 1095),
    ("Potassium Chloride 15% Concentrate", "electrolyte", "ampoule", 1.10, 1095),
    ("Sodium Bicarbonate 8.4% Injection", "electrolyte", "ampoule", 1.90, 1095),
    ("Calcium Gluconate 10% Injection", "electrolyte", "ampoule", 1.70, 1095),
    ("Dextrose 50% Injection 50ml", "emergency", "vial", 2.00, 1095),
    ("Mifepristone 200mg + Misoprostol", "maternal_health", "pack", 9.50, 730),
    ("Carboprost Tromethamine 250mcg", "maternal_health", "ampoule", 11.0, 730),
    ("Methotrexate 50mg Injection", "oncology", "vial", 15.0, 730),
    ("Bleomycin 15 units Injection", "oncology", "vial", 32.0, 540),
    ("Cisplatin 50mg Injection", "oncology", "vial", 26.0, 730),
    ("Cyclophosphamide 500mg Injection", "oncology", "vial", 14.0, 730),
    ("Fluorouracil 250mg Injection", "oncology", "vial", 8.00, 730),
    ("Furosemide 10mg/ml Injection", "renal", "ampoule", 0.90, 1095),
    ("Heparin Sodium 5000 IU/ml", "cardio", "vial", 6.00, 730),
    ("Enoxaparin 40mg/0.4ml Syringe", "cardio", "syringe", 8.20, 730),
    ("Hydrocortisone Sodium Succinate 100mg", "emergency", "vial", 2.80, 730),
]

def generate_150_items() -> List[Dict[str, Any]]:
    """Generates the full 150-item catalog with all required classes."""
    items = []
    
    # 1. ~20 High Velocity
    for i, meta in enumerate(HIGH_VELOCITY_ITEMS):
        items.append({
            "id": f"MED-HV-{i+1:03d}",
            "name": meta["name"],
            "category": meta["category"],
            "dosage_form": meta["dosage_form"],
            "unit_of_measure": meta["unit"],
            "velocity_class": "high_velocity",
            "requires_cold_chain": False,
            "unit_cost_usd": meta["cost"],
            "shelf_life_days": meta["shelf"],
            "criticality_tier": "A"
        })

    # 2. ~10 Cold Chain
    for i, meta in enumerate(COLD_CHAIN_ITEMS):
        items.append({
            "id": f"MED-CC-{i+1:03d}",
            "name": meta["name"],
            "category": meta["category"],
            "dosage_form": meta["dosage_form"],
            "unit_of_measure": meta["unit"],
            "velocity_class": "high_velocity" if "Oxytocin" in meta["name"] else "standard",
            "requires_cold_chain": True,
            "temp_min_c": meta["min_temp"],
            "temp_max_c": meta["max_temp"],
            "unit_cost_usd": meta["cost"],
            "shelf_life_days": meta["shelf"],
            "criticality_tier": "A"
        })

    # 3. ~50 Intermittent
    for i, meta in enumerate(INTERMITTENT_BASE[:50]):
        items.append({
            "id": f"MED-INT-{i+1:03d}",
            "name": meta[0],
            "category": meta[1],
            "dosage_form": meta[2],
            "unit_of_measure": meta[2],
            "velocity_class": "intermittent",
            "requires_cold_chain": False,
            "unit_cost_usd": meta[3],
            "shelf_life_days": meta[4],
            "criticality_tier": "A" if meta[3] > 20 else "B"
        })

    # 4. Fill remainder to 150 (~70 standard items)
    std_categories = [
        ("Amlodipine 5mg Tablet", "cardio", "tablet", "strip", 0.35, 1095),
        ("Enalapril 5mg Tablet", "cardio", "tablet", "strip", 0.40, 1095),
        ("Atenolol 50mg Tablet", "cardio", "tablet", "strip", 0.30, 1095),
        ("Metformin 500mg Tablet", "endocrine", "tablet", "strip", 0.45, 1095),
        ("Glibenclamide 5mg Tablet", "endocrine", "tablet", "strip", 0.25, 1095),
        ("Salbutamol 100mcg Inhaler", "respiratory", "inhaler", "canister", 3.20, 730),
        ("Beclomethasone 100mcg Inhaler", "respiratory", "inhaler", "canister", 4.50, 730),
        ("Omeprazole 20mg Capsule", "gastro", "capsule", "strip", 0.60, 730),
        ("Ranitidine 150mg Tablet", "gastro", "tablet", "strip", 0.30, 1095),
        ("Iron + Folic Acid Tablet", "maternal_health", "tablet", "strip", 0.15, 1095),
        ("Calcium + Vitamin D3 Tablet", "supplement", "tablet", "strip", 0.25, 1095),
        ("Vitamin A 200,000 IU Capsule", "supplement", "capsule", "bottle", 0.10, 1095),
        ("Povidone Iodine 10% Solution 500ml", "antiseptic", "solution", "bottle", 2.20, 1095),
        ("Chlorhexidine Gluconate 4% 500ml", "antiseptic", "solution", "bottle", 2.60, 1095),
        ("Surgical Gauze Roll 100m", "consumable", "roll", "roll", 4.50, 1825),
        ("Absorbent Cotton 500g", "consumable", "pack", "pack", 3.00, 1825),
        ("Adhesive Plaster 7.5cm x 5m", "consumable", "tape", "roll", 1.80, 1825),
        ("Sterile Surgical Gloves 7.5", "consumable", "pair", "pair", 0.85, 1095),
        ("Disposable Syringes 5ml with needle", "consumable", "unit", "box", 0.15, 1825),
        ("IV Cannula 20G Pink", "consumable", "unit", "box", 0.70, 1825),
        ("Normal Saline 0.9% 500ml IV", "infusion", "infusion", "bottle", 1.10, 1095),
        ("Ringer Lactate 500ml IV", "infusion", "infusion", "bottle", 1.25, 1095),
        ("Dextrose 5% 500ml IV", "infusion", "infusion", "bottle", 1.15, 1095),
    ]

    current_count = len(items)
    target_count = 150
    needed = target_count - current_count
    
    for i in range(needed):
        base = std_categories[i % len(std_categories)]
        item_num = i + 1
        items.append({
            "id": f"MED-STD-{item_num:03d}",
            "name": f"{base[0]} (Type {item_num})",
            "category": base[1],
            "dosage_form": base[2],
            "unit_of_measure": base[3],
            "velocity_class": "standard",
            "requires_cold_chain": False,
            "unit_cost_usd": base[4],
            "shelf_life_days": base[5],
            "criticality_tier": "B"
        })

    return items
