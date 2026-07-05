"""
TerraMind — Weather Event Generator
======================================
Generates extreme weather event records for synthetic farms.
Links to actual weather data patterns from state_weather_data.
"""

import os
import json
import random

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "data_generation", "generated")
os.makedirs(OUTPUT_DIR, exist_ok=True)

random.seed(42)

PLOT_STATE_MAP = {
    "plot-001a": "Punjab", "plot-001b": "Punjab", "plot-001c": "Punjab",
    "plot-002a": "Karnataka", "plot-002b": "Karnataka", "plot-002c": "Karnataka",
    "plot-003a": "Assam", "plot-003b": "Assam", "plot-003c": "Assam",
    "plot-004a": "Maharashtra", "plot-004b": "Maharashtra", "plot-004c": "Maharashtra",
    "plot-005a": "Uttar Pradesh", "plot-005b": "Uttar Pradesh", "plot-005c": "Uttar Pradesh",
}

EVENT_TEMPLATES = {
    "drought": {
        "descriptions": [
            "Extended dry spell of {duration} days. No significant rainfall recorded. Soil moisture critically low.",
            "Severe drought conditions. Rainfall deficit of {deficit}mm vs normal. Crop stress visible across all plots.",
            "Monsoon failure in {state}. Only {actual}mm rain vs {normal}mm expected. Emergency irrigation deployed.",
        ],
        "severity_map": {
            "mild": {"duration": (15, 30), "deficit_pct": (20, 35)},
            "moderate": {"duration": (30, 60), "deficit_pct": (35, 55)},
            "severe": {"duration": (60, 120), "deficit_pct": (55, 80)},
        }
    },
    "flood": {
        "descriptions": [
            "Heavy continuous rainfall — {actual}mm in {duration} days. Waterlogging in low-lying fields.",
            "Flash flooding in {state}. River overflow affected nearby fields. Standing water for {duration} days.",
            "Excessive monsoon rain ({actual}mm vs {normal}mm normal). Crop submersion in multiple plots.",
        ],
        "severity_map": {
            "mild": {"duration": (3, 7), "excess_pct": (30, 60)},
            "moderate": {"duration": (7, 15), "excess_pct": (60, 100)},
            "severe": {"duration": (15, 30), "excess_pct": (100, 200)},
        }
    },
    "heatwave": {
        "descriptions": [
            "Heatwave: temperatures reached {max_temp}°C for {duration} consecutive days. Crop wilting observed.",
            "Extreme heat event in {state}. Max temp {max_temp}°C. Significant evapotranspiration stress.",
            "Prolonged high temperatures ({max_temp}°C) for {duration} days. Irrigated fields 3x normal.",
        ],
        "severity_map": {
            "mild": {"duration": (3, 7), "max_temp": (40, 43)},
            "moderate": {"duration": (7, 14), "max_temp": (43, 46)},
            "severe": {"duration": (14, 25), "max_temp": (46, 50)},
        }
    },
    "frost": {
        "descriptions": [
            "Unexpected frost event. Temperature dropped to {min_temp}°C. Frost damage on {crop} plants.",
            "Cold wave in {state}. Min temp {min_temp}°C for {duration} nights. Significant crop damage.",
            "Late season frost — {min_temp}°C recorded. Young {crop} seedlings damaged.",
        ],
        "severity_map": {
            "mild": {"duration": (1, 3), "min_temp": (2, 5)},
            "moderate": {"duration": (3, 7), "min_temp": (0, 2)},
            "severe": {"duration": (7, 15), "min_temp": (-3, 0)},
        }
    },
    "unseasonal_rain": {
        "descriptions": [
            "Unseasonal rainfall during harvest period. {actual}mm in {duration} days. Crop damage at maturity stage.",
            "Unexpected rain during {crop} harvesting. Grain damage and quality loss reported.",
            "Off-season wet spell — {actual}mm over {duration} days. Stored grain at risk of moisture damage.",
        ],
        "severity_map": {
            "mild": {"duration": (2, 5), "rainfall": (30, 60)},
            "moderate": {"duration": (5, 10), "rainfall": (60, 120)},
            "severe": {"duration": (10, 20), "rainfall": (120, 250)},
        }
    },
}


def generate_weather_events():
    """Generate weather events with embedded causal patterns."""
    events = []
    event_id = 0

    for plot_id, state in PLOT_STATE_MAP.items():
        for year in range(2020, 2027):
            # Random events
            num_events = random.randint(0, 2)
            for _ in range(num_events):
                event_type = random.choice(list(EVENT_TEMPLATES.keys()))
                severity = random.choices(["mild", "moderate", "severe"],
                                         weights=[0.5, 0.35, 0.15])[0]
                _make_event(events, event_id, plot_id, state, year, event_type, severity)
                event_id += 1

            # CAUSAL PATTERN: plot-001b drought in 2025
            if plot_id == "plot-001b" and year == 2025:
                _make_event(events, event_id, plot_id, state, year, "drought", "severe",
                            override_desc="Severe drought in Punjab — no rain for 75 days during critical grain filling stage. "
                                          "Combined with heavy Chlorpyrifos application from 2024 Kharif season, "
                                          "soil microbiome severely impacted. This is the worst drought in 15 years.")
                event_id += 1

            # CAUSAL PATTERN: plot-004a heatwave in 2026
            if plot_id == "plot-004a" and year == 2026:
                _make_event(events, event_id, plot_id, state, year, "heatwave", "severe",
                            override_desc="Record heatwave in Vidarbha region — 48°C for 18 days. "
                                          "Cotton crop devastated. Combined with depleted soil from reduced "
                                          "fertilizer in 2025 and excessive pesticide use.")
                event_id += 1

            # CAUSAL PATTERN: plot-002a flood in 2024
            if plot_id == "plot-002a" and year == 2024:
                _make_event(events, event_id, plot_id, state, year, "flood", "moderate",
                            override_desc="Heavy unseasonal flooding in Block 1. 180mm rainfall in 5 days. "
                                          "Rice paddies submerged for 8 days. Significant yield loss expected.")
                event_id += 1

    return events


def _make_event(events, event_id, plot_id, state, year, event_type, severity,
                override_desc=None):
    """Create a single weather event record."""
    template_info = EVENT_TEMPLATES[event_type]
    severity_params = template_info["severity_map"][severity]

    duration = random.randint(*severity_params.get("duration", (3, 10)))

    if override_desc:
        description = override_desc
    else:
        desc_template = random.choice(template_info["descriptions"])
        format_args = {
            "duration": duration, "state": state,
            "crop": random.choice(["Rice", "Wheat", "Cotton", "Maize"]),
        }
        if "deficit_pct" in severity_params:
            normal = random.randint(800, 1500)
            deficit_pct = random.uniform(*severity_params["deficit_pct"])
            actual = round(normal * (1 - deficit_pct / 100))
            format_args.update({"deficit": round(normal - actual), "actual": actual, "normal": normal})
        if "excess_pct" in severity_params:
            normal = random.randint(800, 1500)
            excess_pct = random.uniform(*severity_params["excess_pct"])
            actual = round(normal * (1 + excess_pct / 100))
            format_args.update({"actual": actual, "normal": normal})
        if "max_temp" in severity_params:
            format_args["max_temp"] = round(random.uniform(*severity_params["max_temp"]), 1)
        if "min_temp" in severity_params:
            format_args["min_temp"] = round(random.uniform(*severity_params["min_temp"]), 1)
        if "rainfall" in severity_params:
            format_args["actual"] = random.randint(*severity_params["rainfall"])

        try:
            description = desc_template.format(**format_args)
        except KeyError:
            description = f"{event_type.title()} event in {state} affecting {plot_id}."

    month = random.randint(5, 10)
    day = random.randint(1, 28)

    events.append({
        "event_id": f"WE-{event_id:04d}",
        "plot_id": plot_id,
        "state": state,
        "year": year,
        "date_start": f"{year}-{month:02d}-{day:02d}",
        "date_end": f"{year}-{month:02d}-{min(28, day + duration):02d}",
        "event_type": event_type,
        "severity": severity,
        "duration_days": duration,
        "description": description,
        "affected_crop": random.choice(["Rice", "Wheat", "Cotton", "Maize", "Sugarcane"]),
        "estimated_damage_pct": round(random.uniform(5, 60) if severity != "mild" else random.uniform(0, 15), 1),
    })


def main():
    print("=" * 60)
    print("TerraMind — Weather Event Generator")
    print("=" * 60)

    events = generate_weather_events()
    print(f"  ✓ Generated {len(events)} weather events")

    # Save
    with open(os.path.join(OUTPUT_DIR, "weather_events.json"), "w") as f:
        json.dump(events, f, indent=2)

    # Summary
    by_type = {}
    for e in events:
        by_type[e["event_type"]] = by_type.get(e["event_type"], 0) + 1
    print("\n  Event types:")
    for t, c in sorted(by_type.items()):
        print(f"    {t}: {c}")

    by_severity = {}
    for e in events:
        by_severity[e["severity"]] = by_severity.get(e["severity"], 0) + 1
    print("\n  Severities:")
    for s, c in sorted(by_severity.items()):
        print(f"    {s}: {c}")

    print(f"\n✅ Weather events generated!")


if __name__ == "__main__":
    main()
