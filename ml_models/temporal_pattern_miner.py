"""
TerraMind — Temporal Pattern Miner
====================================
Discovers multi-year cascading effects in agricultural data.

Core Questions:
  - Does fertilizer in year N correlate with yield in year N+1 or N+2?
  - Which sequences of (weather + chemical) events precede yield crashes?
  - Are there repeating patterns across states?

Outputs temporal relationship edges for the Cognee knowledge graph.
"""

import os
import json
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = BASE_DIR
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs", "charts")
REPORT_DIR = os.path.join(BASE_DIR, "outputs", "reports")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)

# ── Style ────────────────────────────────────────────────────────────────────
plt.rcParams.update({
    "figure.facecolor": "#0d1117",
    "axes.facecolor": "#161b22",
    "axes.edgecolor": "#30363d",
    "axes.labelcolor": "#c9d1d9",
    "text.color": "#c9d1d9",
    "xtick.color": "#8b949e",
    "ytick.color": "#8b949e",
    "grid.color": "#21262d",
    "font.family": "sans-serif",
    "font.size": 11,
})

PALETTE = ["#58a6ff", "#3fb950", "#d29922", "#f85149", "#bc8cff",
           "#39d353", "#f0883e", "#79c0ff"]


def load_merged():
    """Load and merge all datasets."""
    crop = pd.read_csv(os.path.join(DATA_DIR, "crop_yield.csv"))
    crop.columns = crop.columns.str.strip().str.lower()
    crop["state"] = crop["state"].str.strip()
    crop["season"] = crop["season"].str.strip()
    crop = crop[crop["yield"] < 500].copy()

    weather = pd.read_csv(os.path.join(DATA_DIR, "state_weather_data_1997_2020.csv"))
    weather.columns = weather.columns.str.strip().str.lower()
    weather["state"] = weather["state"].str.strip()

    df = crop.merge(weather, on=["state", "year"], how="inner")
    return df


def compute_lag_correlations(df, max_lag=5):
    """Compute cross-correlations at various time lags."""
    state_year = df.groupby(["state", "year"]).agg(
        avg_yield=("yield", "mean"),
        avg_fertilizer=("fertilizer", "mean"),
        avg_pesticide=("pesticide", "mean"),
        avg_temp=("avg_temp_c", "mean"),
        avg_rainfall=("total_rainfall_mm", "mean"),
        avg_humidity=("avg_humidity_percent", "mean"),
    ).reset_index().sort_values(["state", "year"])

    variables = ["avg_fertilizer", "avg_pesticide", "avg_temp", "avg_rainfall", "avg_humidity"]
    lag_results = {var: {} for var in variables}

    for var in variables:
        for lag in range(0, max_lag + 1):
            state_year[f"{var}_lag{lag}"] = state_year.groupby("state")[var].shift(lag)

        state_year_clean = state_year.dropna()

        for lag in range(0, max_lag + 1):
            corr = state_year_clean[f"{var}_lag{lag}"].corr(state_year_clean["avg_yield"])
            lag_results[var][lag] = round(corr, 4)

    print("✓ Lag correlation matrix computed")
    return lag_results, state_year


def find_sequential_patterns(state_year):
    """Identify sequential event patterns that precede yield crashes."""
    patterns = []

    for state in state_year["state"].unique():
        s_data = state_year[state_year["state"] == state].sort_values("year")
        if len(s_data) < 5:
            continue

        # Calculate YoY changes
        s_data = s_data.copy()
        s_data["yield_change"] = s_data["avg_yield"].pct_change() * 100
        s_data["fert_change"] = s_data["avg_fertilizer"].pct_change() * 100
        s_data["pest_change"] = s_data["avg_pesticide"].pct_change() * 100
        s_data["rain_change"] = s_data["avg_rainfall"].pct_change() * 100
        s_data["temp_change"] = s_data["avg_temp"].pct_change() * 100

        s_data = s_data.dropna()

        # Find yield crashes (>15% drop)
        crashes = s_data[s_data["yield_change"] < -15]

        for _, crash in crashes.iterrows():
            crash_year = crash["year"]
            # Look back 1-3 years for preceding events
            preceding = s_data[(s_data["year"] >= crash_year - 3) &
                              (s_data["year"] < crash_year)]

            if len(preceding) == 0:
                continue

            sequence = []
            for _, prev in preceding.iterrows():
                events = []
                if prev["rain_change"] < -25:
                    events.append("drought")
                elif prev["rain_change"] > 40:
                    events.append("excess_rain")
                if prev["temp_change"] > 5:
                    events.append("heat_spike")
                if abs(prev["fert_change"]) > 30:
                    events.append(f"fert_{'up' if prev['fert_change'] > 0 else 'down'}")
                if abs(prev["pest_change"]) > 30:
                    events.append(f"pest_{'up' if prev['pest_change'] > 0 else 'down'}")
                if events:
                    sequence.append({
                        "year": int(prev["year"]),
                        "events": events,
                        "years_before_crash": int(crash_year - prev["year"])
                    })

            if sequence:
                patterns.append({
                    "state": state,
                    "crash_year": int(crash_year),
                    "yield_drop_pct": round(float(crash["yield_change"]), 1),
                    "preceding_sequence": sequence,
                    "pattern_length": len(sequence),
                })

    print(f"✓ Found {len(patterns)} sequential patterns preceding yield crashes")
    return patterns


def find_repeating_patterns(patterns):
    """Find patterns that repeat across multiple states."""
    # Extract event sequences as strings for comparison
    sequence_map = {}
    for p in patterns:
        # Create a normalized sequence key
        seq_events = []
        for step in sorted(p["preceding_sequence"], key=lambda x: x["years_before_crash"], reverse=True):
            seq_events.extend(sorted(step["events"]))
        seq_key = " → ".join(seq_events)

        if seq_key not in sequence_map:
            sequence_map[seq_key] = []
        sequence_map[seq_key].append(p)

    # Find sequences that repeat in 2+ states
    repeating = {k: v for k, v in sequence_map.items() if len(v) >= 2}
    repeating = dict(sorted(repeating.items(), key=lambda x: len(x[1]), reverse=True))

    print(f"✓ Found {len(repeating)} repeating pattern types across states")
    return repeating


def plot_lag_correlations(lag_results):
    """Visualize lag correlation matrix."""
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    # Heatmap of lag correlations
    ax = axes[0]
    variables = list(lag_results.keys())
    nice_names = {
        "avg_fertilizer": "Fertilizer",
        "avg_pesticide": "Pesticide",
        "avg_temp": "Temperature",
        "avg_rainfall": "Rainfall",
        "avg_humidity": "Humidity",
    }
    lags = list(range(0, 6))

    data = np.array([[lag_results[var].get(lag, 0) for lag in lags] for var in variables])
    im = ax.imshow(data, cmap="RdYlGn", aspect="auto", vmin=-0.5, vmax=0.5)
    ax.set_xticks(range(len(lags)))
    ax.set_xticklabels([f"Lag {l}" for l in lags])
    ax.set_yticks(range(len(variables)))
    ax.set_yticklabels([nice_names.get(v, v) for v in variables])
    plt.colorbar(im, ax=ax, shrink=0.8, label="Correlation with Yield")

    # Annotate
    for i in range(len(variables)):
        for j in range(len(lags)):
            text = f"{data[i, j]:.3f}"
            color = "white" if abs(data[i, j]) > 0.15 else "#8b949e"
            ax.text(j, i, text, ha="center", va="center", fontsize=9, color=color)

    ax.set_title("Temporal Lag Correlations\n(Variable at Lag N → Yield at Year 0)")

    # Line plot showing strongest lags
    ax = axes[1]
    for i, var in enumerate(variables):
        corrs = [lag_results[var].get(lag, 0) for lag in lags]
        ax.plot(lags, corrs, marker="o", markersize=5, linewidth=2,
                label=nice_names.get(var, var), color=PALETTE[i])
    ax.axhline(0, color="#8b949e", linestyle="--", alpha=0.5)
    ax.set_xlabel("Time Lag (years)")
    ax.set_ylabel("Correlation with Yield")
    ax.set_title("How Past Events Affect Future Yields")
    ax.legend(frameon=False, loc="upper right")
    ax.grid(True, alpha=0.3)

    plt.suptitle("TerraMind — Temporal Pattern Mining",
                 fontsize=16, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "18_temporal_patterns.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print("  ✓ Chart: temporal_patterns.png")


def plot_sequential_patterns(patterns, repeating):
    """Visualize sequential patterns."""
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    # Pattern length distribution
    ax = axes[0]
    if patterns:
        lengths = [p["pattern_length"] for p in patterns]
        ax.hist(lengths, bins=range(1, max(lengths) + 2), color=PALETTE[4],
                alpha=0.8, edgecolor="#30363d", linewidth=0.5, align="left")
    ax.set_xlabel("Pattern Length (years of preceding events)")
    ax.set_ylabel("Frequency")
    ax.set_title("How Many Years of Events\nPrecede a Yield Crash?")
    ax.grid(True, axis="y", alpha=0.3)

    # Top repeating patterns
    ax = axes[1]
    if repeating:
        top_patterns = list(repeating.items())[:8]
        labels = [k[:40] + "..." if len(k) > 40 else k for k, _ in top_patterns]
        counts = [len(v) for _, v in top_patterns]
        ax.barh(range(len(labels)), counts,
                color=PALETTE[2], alpha=0.8, edgecolor="#30363d")
        ax.set_yticks(range(len(labels)))
        ax.set_yticklabels(labels, fontsize=8)
        ax.set_xlabel("States Affected")
        ax.set_title("Most Common Repeating Patterns\nAcross Multiple States")
    ax.grid(True, axis="x", alpha=0.3)

    plt.suptitle("Sequential Pattern Analysis",
                 fontsize=16, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "19_sequential_patterns.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print("  ✓ Chart: sequential_patterns.png")


def generate_temporal_edges(patterns, lag_results):
    """Generate temporal edges for Cognee knowledge graph."""
    edges = []

    # From lag analysis — global temporal relationships
    for var, lags in lag_results.items():
        for lag, corr in lags.items():
            if abs(corr) > 0.05 and lag > 0:
                edges.append({
                    "source_type": var.replace("avg_", "").title(),
                    "target_type": "YieldMeasurement",
                    "relationship": "PRECEDED",
                    "temporal_lag_years": lag,
                    "correlation": corr,
                    "scope": "national",
                    "confidence": "statistical_association",
                })

    # From sequential patterns — specific causal chains
    for p in patterns[:50]:  # Top 50 patterns
        for step in p["preceding_sequence"]:
            for event in step["events"]:
                edges.append({
                    "source_type": "WeatherEvent" if event in ["drought", "excess_rain", "heat_spike"] else "ChemicalProduct",
                    "source_event": event,
                    "target_type": "YieldMeasurement",
                    "target_state": p["state"],
                    "target_year": p["crash_year"],
                    "relationship": "PRECEDED",
                    "temporal_lag_years": step["years_before_crash"],
                    "yield_impact_pct": p["yield_drop_pct"],
                    "confidence": "statistical_association",
                })

    with open(os.path.join(REPORT_DIR, "temporal_edges.json"), "w") as f:
        json.dump(edges, f, indent=2)
    print(f"  ✓ Temporal edges: {len(edges)} edges → temporal_edges.json")

    return edges


def main():
    print("=" * 60)
    print("TerraMind — Temporal Pattern Mining")
    print("=" * 60)

    df = load_merged()
    print(f"Dataset: {len(df):,} rows\n")

    lag_results, state_year = compute_lag_correlations(df)
    patterns = find_sequential_patterns(state_year)
    repeating = find_repeating_patterns(patterns)

    print(f"\nGenerating charts → {OUTPUT_DIR}\n")
    plot_lag_correlations(lag_results)
    plot_sequential_patterns(patterns, repeating)
    generate_temporal_edges(patterns, lag_results)

    print(f"\n✅ Temporal pattern mining complete!")


if __name__ == "__main__":
    main()
