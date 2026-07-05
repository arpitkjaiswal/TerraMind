"""
TerraMind — Synthetic Field Notes Generator
=============================================
Generates realistic farmer-style field notes for Cognee ingestion demo.

Produces 50+ synthetic field notes across 5 farms, 15 plots, 2020–2026.
Written in natural, informal farmer language with abbreviations.
"""

import os
import json
import random
from datetime import datetime, timedelta

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "data_generation", "generated")
os.makedirs(OUTPUT_DIR, exist_ok=True)

random.seed(42)

# ── Seed Data ─────────────────────────────────────────────────────────────────
FARMS = [
    {"id": "farm-001", "name": "Greenfield Agro", "state": "Punjab", "owner": "Rajinder Singh"},
    {"id": "farm-002", "name": "Deccan Harvest", "state": "Karnataka", "owner": "Venkatesh Rao"},
    {"id": "farm-003", "name": "Brahmaputra Fields", "state": "Assam", "owner": "Ranjit Das"},
    {"id": "farm-004", "name": "Vidarbha Crops", "state": "Maharashtra", "owner": "Suresh Patil"},
    {"id": "farm-005", "name": "Indo-Gangetic Farms", "state": "Uttar Pradesh", "owner": "Arun Kumar"},
]

PLOTS = [
    # Farm 1 — Punjab
    {"id": "plot-001a", "farm_id": "farm-001", "name": "Field A (North)", "crop": "Rice", "size_ha": 12.5},
    {"id": "plot-001b", "farm_id": "farm-001", "name": "Field B (South)", "crop": "Wheat", "size_ha": 8.0},
    {"id": "plot-001c", "farm_id": "farm-001", "name": "Field C (East)", "crop": "Rice", "size_ha": 15.0},
    # Farm 2 — Karnataka
    {"id": "plot-002a", "farm_id": "farm-002", "name": "Block 1", "crop": "Rice", "size_ha": 10.0},
    {"id": "plot-002b", "farm_id": "farm-002", "name": "Block 2", "crop": "Maize", "size_ha": 7.5},
    {"id": "plot-002c", "farm_id": "farm-002", "name": "Block 3", "crop": "Sugarcane", "size_ha": 5.0},
    # Farm 3 — Assam
    {"id": "plot-003a", "farm_id": "farm-003", "name": "Paddy Field 1", "crop": "Rice", "size_ha": 20.0},
    {"id": "plot-003b", "farm_id": "farm-003", "name": "Tea Garden A", "crop": "Arecanut", "size_ha": 6.0},
    {"id": "plot-003c", "farm_id": "farm-003", "name": "Vegetable Patch", "crop": "Potato", "size_ha": 3.5},
    # Farm 4 — Maharashtra
    {"id": "plot-004a", "farm_id": "farm-004", "name": "Cotton Field 1", "crop": "Cotton(lint)", "size_ha": 18.0},
    {"id": "plot-004b", "farm_id": "farm-004", "name": "Soybean Plot", "crop": "Arhar/Tur", "size_ha": 12.0},
    {"id": "plot-004c", "farm_id": "farm-004", "name": "Onion Beds", "crop": "Onion", "size_ha": 4.0},
    # Farm 5 — UP
    {"id": "plot-005a", "farm_id": "farm-005", "name": "Wheat Field Alpha", "crop": "Wheat", "size_ha": 25.0},
    {"id": "plot-005b", "farm_id": "farm-005", "name": "Sugarcane Block", "crop": "Sugarcane", "size_ha": 15.0},
    {"id": "plot-005c", "farm_id": "farm-005", "name": "Mustard Plot", "crop": "Rapeseed &Mustard", "size_ha": 8.0},
]


def _random_date(year, month_range=(1, 12)):
    month = random.randint(month_range[0], month_range[1])
    day = random.randint(1, 28)
    return f"{year}-{month:02d}-{day:02d}"


def generate_planting_notes():
    """Generate planting/sowing records."""
    notes = []
    templates = [
        "Sowed {crop} in {plot_name} today. Used {seed_var} variety. Soil was {soil_cond}. Applied {fert} at {rate} kg/ha before sowing. Weather clear, temp around {temp}°C.",
        "Started planting {crop} ({seed_var}) in {plot_name}. Prepared with {fert} basal dose ({rate} kg/ha). Soil felt {soil_cond}. Hoping for good monsoon this yr.",
        "Planted {seed_var} {crop} in {plot_name} - {size} hectares total. Pre-treated seeds w/ {treatment}. Applied {fert} @ {rate}kg/ha. {soil_cond} soil conditions.",
        "{plot_name}: sowing done. {crop} - {seed_var}. Fert: {fert} ({rate} kg/ha). Notes: {soil_cond} texture, need irrigation in 3 days. Temp was {temp}C today.",
    ]
    seed_vars = ["Pusa-44", "PR-126", "HKR-47", "Basmati-1509", "HD-2967", "PBW-343",
                 "DWR-162", "IR-64", "Swarna", "MTU-1010", "Co-0238", "UP-262"]
    fertilizers = ["DAP", "Urea", "NPK 20:20:0", "SSP", "MOP", "Ammonium Sulphate"]
    soil_conditions = ["moist", "dry", "slightly wet", "waterlogged", "cracked", "well-drained"]
    treatments = ["Thiram", "Carbendazim", "Trichoderma", "bio-agent treatment", "no treatment"]

    for plot in PLOTS:
        farm = next(f for f in FARMS if f["id"] == plot["farm_id"])
        for year in range(2020, 2027):
            date = _random_date(year, (4, 7) if plot["crop"] in ["Rice", "Maize", "Cotton(lint)"] else (10, 12))
            template = random.choice(templates)
            note_text = template.format(
                crop=plot["crop"], plot_name=plot["name"], seed_var=random.choice(seed_vars),
                soil_cond=random.choice(soil_conditions), fert=random.choice(fertilizers),
                rate=random.randint(40, 150), temp=random.randint(22, 38),
                size=plot["size_ha"], treatment=random.choice(treatments),
            )
            notes.append({
                "id": f"note-{plot['id']}-plant-{year}",
                "farm_id": plot["farm_id"],
                "plot_id": plot["id"],
                "category": "planting_record",
                "date": date,
                "farmer": farm["owner"],
                "text": note_text,
            })
    return notes


def generate_weather_observations():
    """Generate weather observation notes."""
    notes = []
    templates = [
        "{plot_name}: No rain for {days} days straight. Soil cracking badly. Temp hitting {temp}°C. Crops showing stress - leaves curling. Need to arrange irrigation ASAP.",
        "Heavy rainfall last {days} days in {plot_name} area. Measured approx {rain}mm. Some waterlogging in low-lying section. Worried about root rot if this continues.",
        "Good monsoon so far - {plot_name} getting steady rain. About {rain}mm this week. Crop looking healthy. Humidity around {humidity}%.",
        "Unusual cold snap in {plot_name} region. Temp dropped to {temp}°C overnight. Some frost damage visible on young {crop} plants. Applied straw mulching.",
        "Heatwave warning: {temp}°C recorded near {plot_name}. Irrigated urgently. {crop} showing wilting. Applied foliar spray to reduce transpiration stress.",
    ]

    for plot in PLOTS:
        farm = next(f for f in FARMS if f["id"] == plot["farm_id"])
        for year in range(2020, 2027):
            num_observations = random.randint(2, 4)
            for obs in range(num_observations):
                date = _random_date(year, (6, 10))
                template = random.choice(templates)
                note_text = template.format(
                    plot_name=plot["name"], crop=plot["crop"],
                    days=random.randint(5, 30), temp=random.randint(18, 48),
                    rain=random.randint(20, 200), humidity=random.randint(40, 95),
                )
                notes.append({
                    "id": f"note-{plot['id']}-weather-{year}-{obs}",
                    "farm_id": plot["farm_id"],
                    "plot_id": plot["id"],
                    "category": "weather_observation",
                    "date": date,
                    "farmer": farm["owner"],
                    "text": note_text,
                })
    return notes


def generate_chemical_application_notes():
    """Generate pesticide/fertilizer application notes."""
    notes = []
    pesticides = [
        {"name": "Chlorpyrifos 20EC", "type": "insecticide", "rate": "2ml/L"},
        {"name": "Mancozeb 75WP", "type": "fungicide", "rate": "2.5g/L"},
        {"name": "Imidacloprid 17.8SL", "type": "insecticide", "rate": "0.5ml/L"},
        {"name": "Propiconazole 25EC", "type": "fungicide", "rate": "1ml/L"},
        {"name": "Lambda Cyhalothrin", "type": "insecticide", "rate": "1ml/L"},
        {"name": "Carbendazim 50WP", "type": "fungicide", "rate": "2g/L"},
        {"name": "Glyphosate 41SL", "type": "herbicide", "rate": "10ml/L"},
        {"name": "2,4-D Sodium Salt", "type": "herbicide", "rate": "2.5ml/L"},
    ]
    templates = [
        "Applied {pest_name} ({pest_type}) on {plot_name} @ {rate}. Pest pressure was {level}. Sprayed {area} ha. Weather: {weather}. Note: {note}",
        "{plot_name} - sprayed {pest_name} today ({rate}). Noticed {pest_issue} on {crop}. {coverage} coverage. Will check results in 3-5 days.",
        "Chemical application log: {pest_name} on {plot_name}. Rate: {rate}. Target: {pest_issue}. Applied early morning, wind was {wind}. {note}",
    ]
    pest_issues = ["stem borer infestation", "leaf blight symptoms", "aphid colony buildup",
                   "weed pressure", "fungal spots on leaves", "whitefly attack",
                   "brown plant hopper", "blast disease symptoms"]
    coverage_types = ["Full field", "Spot", "Border", "50%"]

    for plot in PLOTS:
        farm = next(f for f in FARMS if f["id"] == plot["farm_id"])
        for year in range(2020, 2027):
            num_apps = random.randint(1, 4)
            for app in range(num_apps):
                pest = random.choice(pesticides)
                date = _random_date(year, (5, 10))
                template = random.choice(templates)
                note_text = template.format(
                    pest_name=pest["name"], pest_type=pest["type"], rate=pest["rate"],
                    plot_name=plot["name"], crop=plot["crop"],
                    level=random.choice(["low", "moderate", "high", "severe"]),
                    area=plot["size_ha"], weather=random.choice(["clear", "cloudy", "light drizzle"]),
                    note=random.choice(["", "Worker used full PPE", "Mixed with sticker", "Double dose due to severity"]),
                    pest_issue=random.choice(pest_issues),
                    coverage=random.choice(coverage_types),
                    wind=random.choice(["calm", "light", "moderate"]),
                )
                notes.append({
                    "id": f"note-{plot['id']}-chem-{year}-{app}",
                    "farm_id": plot["farm_id"],
                    "plot_id": plot["id"],
                    "category": "chemical_application",
                    "date": date,
                    "farmer": farm["owner"],
                    "text": note_text,
                    "chemical": pest["name"],
                    "chemical_type": pest["type"],
                })
    return notes


def generate_harvest_notes():
    """Generate harvest/yield measurement notes."""
    notes = []
    templates = [
        "Harvested {crop} from {plot_name} today. Got about {yield_val} quintals from {size} ha ({yield_ha} q/ha). {quality}. {comparison}",
        "{plot_name} harvest done - {crop}: {yield_val}q total, {yield_ha} q/ha. {quality}. Stored in godown. {comparison}",
        "Harvest report {plot_name}: Yield = {yield_ha} q/ha ({yield_val}q from {size}ha). {quality}. {comparison}. Sold {sold}q @ Rs.{price}/q.",
    ]
    qualities = [
        "Grain quality looks good - no moisture issues",
        "Some grain damage from late rain",
        "Quality below average - pest damage visible",
        "Excellent quality, good grain fill",
        "Mixed quality - some sections affected by disease",
        "Grade A quality - expecting good price",
    ]

    for plot in PLOTS:
        farm = next(f for f in FARMS if f["id"] == plot["farm_id"])
        for year in range(2020, 2027):
            base_yield = random.uniform(15, 45)
            # Introduce a yield drop in specific years for specific plots (demo scenarios)
            if plot["id"] == "plot-001b" and year == 2025:
                base_yield *= 0.7  # 30% drop — the "mystery" for Cognee
            elif plot["id"] == "plot-002a" and year == 2024:
                base_yield *= 0.75  # 25% drop
            elif plot["id"] == "plot-004a" and year == 2026:
                base_yield *= 0.6  # 40% drop — severe

            yield_total = round(base_yield * plot["size_ha"], 1)
            prev_yield = round(base_yield * random.uniform(0.9, 1.15), 1)

            if base_yield < prev_yield * 0.85:
                comparison = f"Yield DOWN significantly vs last year ({prev_yield:.1f} q/ha). Very concerned."
            elif base_yield > prev_yield * 1.1:
                comparison = f"Up from last year ({prev_yield:.1f} q/ha). Happy with results."
            else:
                comparison = f"Similar to last year ({prev_yield:.1f} q/ha)."

            date = _random_date(year, (10, 12) if plot["crop"] in ["Rice", "Cotton(lint)"] else (3, 5))
            template = random.choice(templates)
            note_text = template.format(
                crop=plot["crop"], plot_name=plot["name"],
                yield_val=yield_total, size=plot["size_ha"],
                yield_ha=round(base_yield, 1), quality=random.choice(qualities),
                comparison=comparison,
                sold=round(yield_total * random.uniform(0.6, 0.9), 1),
                price=random.randint(1500, 4000),
            )
            notes.append({
                "id": f"note-{plot['id']}-harvest-{year}",
                "farm_id": plot["farm_id"],
                "plot_id": plot["id"],
                "category": "harvest_report",
                "date": date,
                "farmer": farm["owner"],
                "text": note_text,
                "yield_per_ha": round(base_yield, 1),
            })
    return notes


def generate_soil_test_notes():
    """Generate soil test result notes."""
    notes = []
    for plot in PLOTS:
        farm = next(f for f in FARMS if f["id"] == plot["farm_id"])
        for year in [2020, 2022, 2024, 2026]:
            # Simulate soil degradation over time for specific plots
            base_n = random.uniform(60, 120)
            base_p = random.uniform(15, 50)
            base_k = random.uniform(20, 45)
            base_ph = random.uniform(5.5, 8.0)

            if plot["id"] == "plot-001b":
                base_ph -= (year - 2020) * 0.15  # pH declining — ammonium fertilizer effect
                base_n += (year - 2020) * 3  # N accumulation

            note_text = (
                f"Soil test results for {plot['name']} (sample date: {_random_date(year, (2, 3))}).\n"
                f"Lab: State Agricultural Lab, {farm['state']}.\n"
                f"Results: N={base_n:.0f} kg/ha, P={base_p:.0f} kg/ha, K={base_k:.0f} kg/ha, pH={base_ph:.1f}\n"
                f"Organic Carbon: {random.uniform(0.3, 0.8):.2f}%\n"
                f"EC: {random.uniform(0.1, 0.5):.2f} dS/m\n"
                f"Recommendation: {'Increase phosphorus application' if base_p < 25 else 'Maintain current levels'}. "
                f"{'Lime application needed to raise pH' if base_ph < 6.0 else 'pH adequate'}."
            )
            notes.append({
                "id": f"note-{plot['id']}-soil-{year}",
                "farm_id": plot["farm_id"],
                "plot_id": plot["id"],
                "category": "soil_test",
                "date": _random_date(year, (2, 3)),
                "farmer": farm["owner"],
                "text": note_text,
                "soil_n": round(base_n),
                "soil_p": round(base_p),
                "soil_k": round(base_k),
                "soil_ph": round(base_ph, 1),
            })
    return notes


def main():
    print("=" * 60)
    print("TerraMind — Synthetic Field Notes Generator")
    print("=" * 60)

    all_notes = []
    all_notes.extend(generate_planting_notes())
    print(f"  ✓ Planting notes: {len([n for n in all_notes if n['category'] == 'planting_record'])}")

    all_notes.extend(generate_weather_observations())
    print(f"  ✓ Weather notes: {len([n for n in all_notes if n['category'] == 'weather_observation'])}")

    all_notes.extend(generate_chemical_application_notes())
    print(f"  ✓ Chemical notes: {len([n for n in all_notes if n['category'] == 'chemical_application'])}")

    all_notes.extend(generate_harvest_notes())
    print(f"  ✓ Harvest notes: {len([n for n in all_notes if n['category'] == 'harvest_report'])}")

    all_notes.extend(generate_soil_test_notes())
    print(f"  ✓ Soil test notes: {len([n for n in all_notes if n['category'] == 'soil_test'])}")

    print(f"\n  Total: {len(all_notes)} field notes")

    # Save all notes
    with open(os.path.join(OUTPUT_DIR, "field_notes.json"), "w") as f:
        json.dump(all_notes, f, indent=2)

    # Also save as individual text files for Cognee ingestion
    text_dir = os.path.join(OUTPUT_DIR, "field_notes_text")
    os.makedirs(text_dir, exist_ok=True)
    for note in all_notes:
        with open(os.path.join(text_dir, f"{note['id']}.txt"), "w", encoding="utf-8") as f:
            f.write(f"Date: {note['date']}\n")
            f.write(f"Farm: {note['farm_id']}\n")
            f.write(f"Plot: {note['plot_id']}\n")
            f.write(f"Category: {note['category']}\n")
            f.write(f"Farmer: {note['farmer']}\n")
            f.write(f"---\n{note['text']}\n")

    # Save seed data
    seed_data = {
        "farms": FARMS,
        "plots": PLOTS,
        "demo_scenarios": [
            {
                "question": "Why did Field B's yield drop by 30% in 2025?",
                "plot_id": "plot-001b",
                "year": 2025,
                "expected_graph_traversal": [
                    "YieldMeasurement(plot-001b, 2025) ← CORRELATED_WITH → ChemicalProduct(Chlorpyrifos, 2024)",
                    "ChemicalProduct(Chlorpyrifos, 2024) ← APPLIED_TO → Field(plot-001b)",
                    "WeatherEvent(drought, 2025) ← OCCURRED_DURING → Field(plot-001b)",
                    "SoilTest(pH_decline, 2024) ← PRECEDED → YieldMeasurement(2025)"
                ]
            },
            {
                "question": "Why is soil pH declining in Field B?",
                "plot_id": "plot-001b",
                "expected_graph_traversal": [
                    "SoilTest(pH=5.6, 2026) ← PRECEDED → SoilTest(pH=6.2, 2024)",
                    "ChemicalProduct(Ammonium Sulphate) ← APPLIED_TO → Field(plot-001b) (repeated)",
                    "Practice(no_lime_application) ← CORRELATED_WITH → pH_decline"
                ]
            },
            {
                "question": "What caused the cotton yield crash in Farm 4?",
                "plot_id": "plot-004a",
                "year": 2026,
                "expected_graph_traversal": [
                    "YieldMeasurement(plot-004a, 2026, -40%) ← CORRELATED_WITH → WeatherEvent(heatwave, 2026)",
                    "WeatherEvent(heatwave, 2026) ← PRECEDED → WeatherEvent(low_rainfall, 2025)",
                    "ChemicalProduct(excessive_pesticide, 2025) ← APPLIED_TO → Field(plot-004a)"
                ]
            }
        ]
    }
    with open(os.path.join(OUTPUT_DIR, "seed_data.json"), "w") as f:
        json.dump(seed_data, f, indent=2)

    print(f"\n✅ All field notes generated in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
