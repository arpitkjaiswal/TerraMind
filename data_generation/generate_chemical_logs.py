"""
TerraMind — Chemical Application Log Generator
=================================================
Generates structured CSV chemical application records per plot per season.
Includes intentional problematic combinations for causal chain discovery.
"""

import os
import csv
import json
import random
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "data_generation", "generated")
os.makedirs(OUTPUT_DIR, exist_ok=True)

random.seed(42)

CHEMICALS = {
    "fertilizers": [
        {"name": "Urea (46-0-0)", "category": "nitrogen", "unit": "kg/ha", "typical_rate": (80, 150)},
        {"name": "DAP (18-46-0)", "category": "phosphorus", "unit": "kg/ha", "typical_rate": (50, 100)},
        {"name": "MOP (0-0-60)", "category": "potassium", "unit": "kg/ha", "typical_rate": (30, 80)},
        {"name": "NPK 20:20:0", "category": "complex", "unit": "kg/ha", "typical_rate": (60, 120)},
        {"name": "Ammonium Sulphate", "category": "nitrogen", "unit": "kg/ha", "typical_rate": (50, 120)},
        {"name": "SSP (Single Super Phosphate)", "category": "phosphorus", "unit": "kg/ha", "typical_rate": (100, 200)},
        {"name": "Zinc Sulphate", "category": "micronutrient", "unit": "kg/ha", "typical_rate": (10, 25)},
        {"name": "Borax", "category": "micronutrient", "unit": "kg/ha", "typical_rate": (5, 15)},
    ],
    "pesticides": [
        {"name": "Chlorpyrifos 20EC", "category": "insecticide", "unit": "ml/ha", "typical_rate": (1000, 2500)},
        {"name": "Imidacloprid 17.8SL", "category": "insecticide", "unit": "ml/ha", "typical_rate": (80, 200)},
        {"name": "Lambda Cyhalothrin 5EC", "category": "insecticide", "unit": "ml/ha", "typical_rate": (300, 600)},
        {"name": "Mancozeb 75WP", "category": "fungicide", "unit": "g/ha", "typical_rate": (1500, 3000)},
        {"name": "Carbendazim 50WP", "category": "fungicide", "unit": "g/ha", "typical_rate": (250, 500)},
        {"name": "Propiconazole 25EC", "category": "fungicide", "unit": "ml/ha", "typical_rate": (400, 800)},
        {"name": "Glyphosate 41SL", "category": "herbicide", "unit": "ml/ha", "typical_rate": (1500, 3000)},
        {"name": "2,4-D Sodium Salt 80WP", "category": "herbicide", "unit": "g/ha", "typical_rate": (500, 1000)},
        {"name": "Pretilachlor 50EC", "category": "herbicide", "unit": "ml/ha", "typical_rate": (600, 1000)},
    ]
}

PLOTS = [
    {"id": "plot-001a", "farm_id": "farm-001", "crop": "Rice", "state": "Punjab"},
    {"id": "plot-001b", "farm_id": "farm-001", "crop": "Wheat", "state": "Punjab"},
    {"id": "plot-001c", "farm_id": "farm-001", "crop": "Rice", "state": "Punjab"},
    {"id": "plot-002a", "farm_id": "farm-002", "crop": "Rice", "state": "Karnataka"},
    {"id": "plot-002b", "farm_id": "farm-002", "crop": "Maize", "state": "Karnataka"},
    {"id": "plot-002c", "farm_id": "farm-002", "crop": "Sugarcane", "state": "Karnataka"},
    {"id": "plot-003a", "farm_id": "farm-003", "crop": "Rice", "state": "Assam"},
    {"id": "plot-003b", "farm_id": "farm-003", "crop": "Arecanut", "state": "Assam"},
    {"id": "plot-003c", "farm_id": "farm-003", "crop": "Potato", "state": "Assam"},
    {"id": "plot-004a", "farm_id": "farm-004", "crop": "Cotton(lint)", "state": "Maharashtra"},
    {"id": "plot-004b", "farm_id": "farm-004", "crop": "Arhar/Tur", "state": "Maharashtra"},
    {"id": "plot-004c", "farm_id": "farm-004", "crop": "Onion", "state": "Maharashtra"},
    {"id": "plot-005a", "farm_id": "farm-005", "crop": "Wheat", "state": "Uttar Pradesh"},
    {"id": "plot-005b", "farm_id": "farm-005", "crop": "Sugarcane", "state": "Uttar Pradesh"},
    {"id": "plot-005c", "farm_id": "farm-005", "crop": "Rapeseed &Mustard", "state": "Uttar Pradesh"},
]


def generate_chemical_logs():
    """Generate chemical application logs with intentional causal patterns."""
    logs = []
    record_id = 0

    for plot in PLOTS:
        for year in range(2020, 2027):
            season = "Kharif" if plot["crop"] in ["Rice", "Maize", "Cotton(lint)"] else "Rabi"

            # Fertilizer applications (2-4 per season)
            num_fert = random.randint(2, 4)
            for i in range(num_fert):
                fert = random.choice(CHEMICALS["fertilizers"])
                rate = random.uniform(*fert["typical_rate"])

                # CAUSAL PATTERN 1: plot-001b gets excessive ammonium sulphate → pH decline
                if plot["id"] == "plot-001b" and fert["category"] == "nitrogen":
                    fert = {"name": "Ammonium Sulphate", "category": "nitrogen",
                            "unit": "kg/ha", "typical_rate": (100, 180)}
                    rate = random.uniform(120, 180)  # Overuse

                # CAUSAL PATTERN 2: plot-004a reduces fertilizer in 2025 → yield crash 2026
                if plot["id"] == "plot-004a" and year == 2025:
                    rate *= 0.4  # 60% reduction

                month = random.randint(5, 8) if season == "Kharif" else random.randint(11, 12)
                day = random.randint(1, 28)

                record_id += 1
                logs.append({
                    "record_id": f"CHEM-{record_id:04d}",
                    "plot_id": plot["id"],
                    "farm_id": plot["farm_id"],
                    "crop": plot["crop"],
                    "state": plot["state"],
                    "year": year,
                    "season": season,
                    "date": f"{year}-{month:02d}-{day:02d}",
                    "chemical_name": fert["name"],
                    "chemical_type": "fertilizer",
                    "chemical_category": fert["category"],
                    "application_rate": round(rate, 1),
                    "unit": fert["unit"],
                    "application_method": random.choice(["broadcast", "band", "foliar", "drip"]),
                    "weather_at_application": random.choice(["clear", "cloudy", "light rain", "overcast"]),
                    "temperature_c": round(random.uniform(20, 40), 1),
                    "notes": "",
                })

            # Pesticide applications (1-3 per season)
            num_pest = random.randint(1, 3)
            for i in range(num_pest):
                pest = random.choice(CHEMICALS["pesticides"])
                rate = random.uniform(*pest["typical_rate"])

                # CAUSAL PATTERN 3: plot-001b gets Chlorpyrifos in 2024 — combined with drought → crash
                if plot["id"] == "plot-001b" and year == 2024:
                    pest = CHEMICALS["pesticides"][0]  # Chlorpyrifos
                    rate = random.uniform(2000, 3000)  # High dose
                    notes = "Heavy dose due to severe stem borer infestation"
                # CAUSAL PATTERN 4: plot-004a excessive pesticide in 2025
                elif plot["id"] == "plot-004a" and year == 2025:
                    rate *= 2.5  # Overuse
                    notes = "Applied double dose - couldn't control bollworm"
                else:
                    notes = ""

                month = random.randint(6, 9) if season == "Kharif" else random.randint(1, 3)
                day = random.randint(1, 28)

                record_id += 1
                logs.append({
                    "record_id": f"CHEM-{record_id:04d}",
                    "plot_id": plot["id"],
                    "farm_id": plot["farm_id"],
                    "crop": plot["crop"],
                    "state": plot["state"],
                    "year": year,
                    "season": season,
                    "date": f"{year}-{month:02d}-{day:02d}",
                    "chemical_name": pest["name"],
                    "chemical_type": "pesticide",
                    "chemical_category": pest["category"],
                    "application_rate": round(rate, 1),
                    "unit": pest["unit"],
                    "application_method": random.choice(["foliar spray", "knapsack", "power sprayer", "drone"]),
                    "weather_at_application": random.choice(["clear morning", "cloudy", "evening calm"]),
                    "temperature_c": round(random.uniform(22, 38), 1),
                    "notes": notes,
                })

    return logs


def main():
    print("=" * 60)
    print("TerraMind — Chemical Application Log Generator")
    print("=" * 60)

    logs = generate_chemical_logs()
    print(f"  ✓ Generated {len(logs)} chemical application records")

    # Save as CSV
    csv_path = os.path.join(OUTPUT_DIR, "chemical_logs.csv")
    fieldnames = list(logs[0].keys())
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(logs)
    print(f"  ✓ CSV: {csv_path}")

    # Save as JSON
    json_path = os.path.join(OUTPUT_DIR, "chemical_logs.json")
    with open(json_path, "w") as f:
        json.dump(logs, f, indent=2)
    print(f"  ✓ JSON: {json_path}")

    # Summary stats
    fert_count = sum(1 for l in logs if l["chemical_type"] == "fertilizer")
    pest_count = sum(1 for l in logs if l["chemical_type"] == "pesticide")
    print(f"\n  Fertilizer records: {fert_count}")
    print(f"  Pesticide records:  {pest_count}")
    print(f"  Total plots: {len(PLOTS)}")
    print(f"  Year range: 2020-2026")

    print(f"\n✅ Chemical logs generated!")


if __name__ == "__main__":
    main()
