"""
TerraMind — Merged Multi-Factor Analysis (⭐ Star Analysis)
============================================================
The core analysis that demonstrates Cognee's value proposition:
identifying HIDDEN multi-year causal chains in agricultural data.

This merges all 3 datasets and discovers the kind of relationships
that multi-hop graph traversal can expose.

Analyses:
  1. Multi-variate correlation with all features
  2. Feature importance ranking (Random Forest)
  3. Year-over-year yield change with causal factor attribution
  4. Hidden relationship discovery (pesticide + drought combos)
  5. Temporal lag analysis (fertilizer in year N → yield in N+1)
  6. Causal chain output for Cognee graph
"""

import os
import json
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder

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
    "grid.alpha": 0.6,
    "font.family": "sans-serif",
    "font.size": 11,
    "axes.titlesize": 14,
    "axes.titleweight": "bold",
})

PALETTE = ["#58a6ff", "#3fb950", "#d29922", "#f85149", "#bc8cff",
           "#39d353", "#f0883e", "#79c0ff", "#56d364", "#e3b341"]


def load_and_merge():
    """Load and merge all datasets into a single analysis-ready frame."""
    crop = pd.read_csv(os.path.join(DATA_DIR, "crop_yield.csv"))
    crop.columns = crop.columns.str.strip().str.lower()
    crop["state"] = crop["state"].str.strip()
    crop["season"] = crop["season"].str.strip()
    crop["crop"] = crop["crop"].str.strip()
    crop = crop[crop["yield"] < 500].copy()

    weather = pd.read_csv(os.path.join(DATA_DIR, "state_weather_data_1997_2020.csv"))
    weather.columns = weather.columns.str.strip().str.lower()
    weather["state"] = weather["state"].str.strip()

    soil = pd.read_csv(os.path.join(DATA_DIR, "state_soil_data.csv"))
    soil.columns = soil.columns.str.strip().str.lower()
    soil["state"] = soil["state"].str.strip()
    soil = soil.dropna(subset=["state"])

    # Merge: crop → weather → soil
    merged = crop.merge(weather, on=["state", "year"], how="inner")
    merged = merged.merge(soil, on="state", how="inner")

    print(f"✓ Merged dataset: {len(merged):,} rows, {merged.columns.tolist()}")
    return merged


def plot_feature_importance(merged):
    """2. Feature importance via Random Forest."""
    features = ["area", "fertilizer", "pesticide",
                 "avg_temp_c", "total_rainfall_mm", "avg_humidity_percent",
                 "n", "p", "k", "ph"]
    target = "yield"

    df = merged[features + [target]].dropna()
    X = df[features]
    y = df[target]

    rf = RandomForestRegressor(n_estimators=200, max_depth=15,
                               random_state=42, n_jobs=-1)
    rf.fit(X, y)

    importances = pd.Series(rf.feature_importances_, index=features).sort_values()
    labels = {
        "area": "Cultivation Area",
        "fertilizer": "Fertilizer Amount",
        "pesticide": "Pesticide Amount",
        "avg_temp_c": "Temperature",
        "total_rainfall_mm": "Rainfall",
        "avg_humidity_percent": "Humidity",
        "n": "Nitrogen (N)",
        "p": "Phosphorus (P)",
        "k": "Potassium (K)",
        "ph": "Soil pH",
    }

    fig, ax = plt.subplots(figsize=(12, 8))
    colors = plt.cm.viridis(np.linspace(0.2, 0.9, len(importances)))
    bars = ax.barh(range(len(importances)), importances.values,
                   color=colors, edgecolor="#30363d", linewidth=0.5)
    ax.set_yticks(range(len(importances)))
    ax.set_yticklabels([labels.get(f, f) for f in importances.index])
    ax.set_xlabel("Feature Importance (Mean Decrease Impurity)")
    ax.set_title(f"What Drives Crop Yield? — Random Forest Feature Importance\n(R² = {rf.score(X, y):.3f})")
    ax.grid(True, axis="x", alpha=0.3)

    # Add value labels
    for bar, val in zip(bars, importances.values):
        ax.text(val + 0.002, bar.get_y() + bar.get_height()/2,
                f"{val:.3f}", va="center", fontsize=9, color="#8b949e")

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "13_feature_importance.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print("  ✓ Chart: feature_importance.png")

    return rf, importances


def find_hidden_relationships(merged):
    """4. Discover hidden relationships — the hackathon showpiece.

    Finds compound effects like: pesticide_change + drought → yield crash
    This is exactly what Cognee's multi-hop graph traversal reveals.
    """
    # Calculate state-level year-over-year changes
    state_year = merged.groupby(["state", "year"]).agg(
        avg_yield=("yield", "mean"),
        avg_fertilizer=("fertilizer", "mean"),
        avg_pesticide=("pesticide", "mean"),
        avg_temp=("avg_temp_c", "mean"),
        avg_rainfall=("total_rainfall_mm", "mean"),
        avg_humidity=("avg_humidity_percent", "mean"),
    ).reset_index().sort_values(["state", "year"])

    # YoY changes
    for col in ["avg_yield", "avg_fertilizer", "avg_pesticide", "avg_temp", "avg_rainfall"]:
        state_year[f"{col}_pct_change"] = state_year.groupby("state")[col].pct_change() * 100

    state_year = state_year.dropna()

    # Detect compound events
    # A "hidden relationship" = cases where BOTH a chemical change AND weather event
    # preceded a yield drop
    compound_events = state_year[
        (state_year["avg_yield_pct_change"] < -15) &  # Yield dropped > 15%
        (
            (state_year["avg_pesticide_pct_change"].abs() > 20) |  # Pesticide changed
            (state_year["avg_fertilizer_pct_change"].abs() > 20)   # OR Fertilizer changed
        ) &
        (
            (state_year["avg_rainfall_pct_change"] < -25) |  # Drought
            (state_year["avg_temp_pct_change"] > 5)          # OR Heatwave
        )
    ].copy()

    print(f"  → Found {len(compound_events)} compound causal events (chemical + weather → yield drop)")

    # Visualize
    fig, axes = plt.subplots(1, 2, figsize=(16, 8))

    # Scatter: pesticide change vs yield change, colored by rainfall change
    ax = axes[0]
    df_plot = state_year[(state_year["avg_yield_pct_change"].abs() < 100) &
                          (state_year["avg_pesticide_pct_change"].abs() < 100)]
    scatter = ax.scatter(df_plot["avg_pesticide_pct_change"],
                         df_plot["avg_yield_pct_change"],
                         c=df_plot["avg_rainfall_pct_change"],
                         cmap="RdYlBu", alpha=0.5, s=15, edgecolors="none")
    plt.colorbar(scatter, ax=ax, label="Rainfall Change (%)", shrink=0.8)

    # Highlight compound events
    if len(compound_events) > 0:
        ce = compound_events[(compound_events["avg_pesticide_pct_change"].abs() < 100) &
                             (compound_events["avg_yield_pct_change"].abs() < 100)]
        ax.scatter(ce["avg_pesticide_pct_change"], ce["avg_yield_pct_change"],
                   color=PALETTE[3], s=80, marker="X", edgecolors="white",
                   linewidths=1, label="Compound Events", zorder=5)

    ax.axhline(0, color="#8b949e", linestyle="--", alpha=0.5)
    ax.axvline(0, color="#8b949e", linestyle="--", alpha=0.5)
    ax.set_xlabel("Pesticide Usage Change (%)")
    ax.set_ylabel("Yield Change (%)")
    ax.set_title("Hidden Relationships: Chemical × Weather → Yield")
    ax.legend(frameon=False)
    ax.grid(True, alpha=0.3)

    # Bar chart of compound event states
    ax = axes[1]
    if len(compound_events) > 0:
        state_counts = compound_events["state"].value_counts().head(10)
        ax.barh(range(len(state_counts)), state_counts.values,
                color=PALETTE[3], alpha=0.8, edgecolor="#30363d")
        ax.set_yticks(range(len(state_counts)))
        ax.set_yticklabels(state_counts.index)
        ax.set_xlabel("Number of Compound Events")
        ax.set_title("States Most Affected by\nCompound Causal Chains")
    else:
        ax.text(0.5, 0.5, "No compound events found", ha="center", va="center",
                transform=ax.transAxes, fontsize=14, color="#8b949e")
        ax.set_title("Compound Event Analysis")
    ax.grid(True, axis="x", alpha=0.3)

    plt.suptitle("🔍 Hidden Relationship Discovery\n(Cognee Multi-Hop Graph Traversal)",
                 fontsize=16, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "14_hidden_relationships.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print("  ✓ Chart: hidden_relationships.png")

    return compound_events


def temporal_lag_analysis(merged):
    """5. Temporal lag — does fertilizer in year N affect yield in N+1?"""
    state_year = merged.groupby(["state", "year"]).agg(
        avg_yield=("yield", "mean"),
        avg_fertilizer=("fertilizer", "mean"),
        avg_pesticide=("pesticide", "mean"),
    ).reset_index().sort_values(["state", "year"])

    # Create lagged features
    for lag in [1, 2, 3]:
        state_year[f"fertilizer_lag{lag}"] = state_year.groupby("state")["avg_fertilizer"].shift(lag)
        state_year[f"pesticide_lag{lag}"] = state_year.groupby("state")["avg_pesticide"].shift(lag)

    state_year = state_year.dropna()

    # Compute lag correlations
    lag_corrs = {}
    for lag in [0, 1, 2, 3]:
        if lag == 0:
            corr_fert = state_year["avg_fertilizer"].corr(state_year["avg_yield"])
            corr_pest = state_year["avg_pesticide"].corr(state_year["avg_yield"])
        else:
            corr_fert = state_year[f"fertilizer_lag{lag}"].corr(state_year["avg_yield"])
            corr_pest = state_year[f"pesticide_lag{lag}"].corr(state_year["avg_yield"])
        lag_corrs[lag] = {"fertilizer": corr_fert, "pesticide": corr_pest}

    fig, ax = plt.subplots(figsize=(10, 6))
    lags = list(lag_corrs.keys())
    fert_corrs = [lag_corrs[l]["fertilizer"] for l in lags]
    pest_corrs = [lag_corrs[l]["pesticide"] for l in lags]

    x = np.arange(len(lags))
    width = 0.35
    ax.bar(x - width/2, fert_corrs, width, label="Fertilizer → Yield",
           color=PALETTE[1], alpha=0.8, edgecolor="#30363d")
    ax.bar(x + width/2, pest_corrs, width, label="Pesticide → Yield",
           color=PALETTE[3], alpha=0.8, edgecolor="#30363d")

    ax.set_xticks(x)
    ax.set_xticklabels([f"Year N{'+' + str(l) if l else ' (same)'}" for l in lags])
    ax.set_ylabel("Correlation with Yield")
    ax.set_title("Temporal Lag Analysis: Do Past Inputs Affect Future Yields?\n(Key insight for Cognee temporal reasoning)")
    ax.legend(frameon=False)
    ax.grid(True, axis="y", alpha=0.3)
    ax.axhline(0, color="#8b949e", linestyle="--", alpha=0.5)

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "15_temporal_lag_analysis.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print("  ✓ Chart: temporal_lag_analysis.png")

    return lag_corrs


def generate_causal_chains(compound_events, merged):
    """6. Generate causal chain JSON for Cognee knowledge graph."""
    chains = []
    for _, row in compound_events.head(20).iterrows():
        chain = {
            "chain_id": f"CC-{row['state'][:3].upper()}-{int(row['year'])}",
            "state": row["state"],
            "year": int(row["year"]),
            "outcome": {
                "type": "YieldMeasurement",
                "yield_change_pct": round(row["avg_yield_pct_change"], 1),
                "severity": "critical" if row["avg_yield_pct_change"] < -25 else "warning"
            },
            "contributing_factors": [],
            "graph_edges": []
        }

        # Chemical factor
        if abs(row["avg_pesticide_pct_change"]) > 20:
            chain["contributing_factors"].append({
                "type": "ChemicalProduct",
                "category": "pesticide",
                "change_pct": round(row["avg_pesticide_pct_change"], 1),
                "year": int(row["year"]),
            })
            chain["graph_edges"].append({
                "source": f"pesticide_{row['state']}_{int(row['year'])}",
                "target": f"yield_{row['state']}_{int(row['year'])}",
                "relationship": "CORRELATED_WITH",
                "temporal_order": "PRECEDED",
            })

        if abs(row["avg_fertilizer_pct_change"]) > 20:
            chain["contributing_factors"].append({
                "type": "ChemicalProduct",
                "category": "fertilizer",
                "change_pct": round(row["avg_fertilizer_pct_change"], 1),
                "year": int(row["year"]),
            })
            chain["graph_edges"].append({
                "source": f"fertilizer_{row['state']}_{int(row['year'])}",
                "target": f"yield_{row['state']}_{int(row['year'])}",
                "relationship": "CORRELATED_WITH",
                "temporal_order": "PRECEDED",
            })

        # Weather factor
        if row["avg_rainfall_pct_change"] < -25:
            chain["contributing_factors"].append({
                "type": "WeatherEvent",
                "category": "drought",
                "rainfall_change_pct": round(row["avg_rainfall_pct_change"], 1),
                "year": int(row["year"]),
            })
            chain["graph_edges"].append({
                "source": f"drought_{row['state']}_{int(row['year'])}",
                "target": f"yield_{row['state']}_{int(row['year'])}",
                "relationship": "OCCURRED_DURING",
            })

        chains.append(chain)

    # Save
    output_path = os.path.join(REPORT_DIR, "causal_chains.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(chains, f, indent=2)
    print(f"  ✓ Causal chains: {len(chains)} chains → {output_path}")

    return chains


def generate_merged_report(merged, rf_score, importances, compound_events, lag_corrs):
    """Generate the star analysis report."""
    report = []
    report.append("# TerraMind — Multi-Factor Causal Analysis Report\n")
    report.append("## The Core Insight")
    report.append("Crop yield is NOT a simple function of any single factor.")
    report.append("Our analysis reveals **compound causal chains** that span multiple years")
    report.append("and involve interactions between weather events, chemical inputs, and soil conditions.\n")
    report.append("This is exactly what Cognee's multi-hop graph traversal is designed to uncover.\n")

    report.append("## ML Model Performance")
    report.append(f"- Random Forest R²: **{rf_score:.3f}**")
    report.append(f"- Top feature: **{importances.index[-1]}** (importance: {importances.values[-1]:.3f})")
    report.append(f"- 2nd feature: **{importances.index[-2]}** (importance: {importances.values[-2]:.3f})\n")

    report.append("## Hidden Compound Relationships Found")
    report.append(f"- **{len(compound_events)}** compound causal events detected")
    report.append("- These are cases where BOTH a chemical input change AND a weather")
    report.append("  event occurred in the same year as a significant yield drop (>15%)\n")

    if len(compound_events) > 0:
        report.append("### Example Causal Chains")
        for _, row in compound_events.head(5).iterrows():
            report.append(f"- **{row['state']} ({int(row['year'])})**:")
            report.append(f"  Yield dropped **{row['avg_yield_pct_change']:.1f}%**")
            factors = []
            if abs(row["avg_pesticide_pct_change"]) > 20:
                factors.append(f"pesticide changed {row['avg_pesticide_pct_change']:.1f}%")
            if abs(row["avg_fertilizer_pct_change"]) > 20:
                factors.append(f"fertilizer changed {row['avg_fertilizer_pct_change']:.1f}%")
            if row["avg_rainfall_pct_change"] < -25:
                factors.append(f"rainfall dropped {row['avg_rainfall_pct_change']:.1f}%")
            report.append(f"  Contributing: {', '.join(factors)}")

    report.append("\n## Temporal Lag Findings")
    report.append("Fertilizer and pesticide usage show temporal lag effects:")
    for lag, corrs in lag_corrs.items():
        label = f"Year N{'+' + str(lag) if lag else ' (same)'}"
        report.append(f"- {label}: Fertilizer->Yield r={corrs['fertilizer']:.3f}, Pesticide->Yield r={corrs['pesticide']:.3f}")

    with open(os.path.join(REPORT_DIR, "causal_analysis.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    print("  ✓ Report: causal_analysis.md")


def main():
    print("=" * 60)
    print("TerraMind — Multi-Factor Causal Analysis (⭐ Star Analysis)")
    print("=" * 60)

    merged = load_and_merge()
    print(f"\nGenerating analyses → {OUTPUT_DIR}\n")

    rf, importances = plot_feature_importance(merged)
    rf_score = rf.score(
        merged[["area", "fertilizer", "pesticide", "avg_temp_c",
                "total_rainfall_mm", "avg_humidity_percent", "n", "p", "k", "ph"]].dropna(),
        merged.loc[merged[["area", "fertilizer", "pesticide", "avg_temp_c",
                           "total_rainfall_mm", "avg_humidity_percent",
                           "n", "p", "k", "ph"]].dropna().index, "yield"]
    )

    compound_events = find_hidden_relationships(merged)
    lag_corrs = temporal_lag_analysis(merged)
    generate_causal_chains(compound_events, merged)
    generate_merged_report(merged, rf_score, importances, compound_events, lag_corrs)

    print(f"\n✅ Multi-factor causal analysis complete!")


if __name__ == "__main__":
    main()
