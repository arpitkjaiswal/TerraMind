"""
TerraMind — Yield Anomaly Detector
====================================
Detects anomalous yield drops and attributes them to causal factors.

This is the engine behind "Why did Field B's yield drop by 20%?"

Algorithm:
  1. For each (crop, state, season), compute expected yield using
     rolling mean + linear trend
  2. Flag years where actual yield deviates > 1.5σ from expected
  3. For each anomaly, examine weather + chemical deviations
  4. Produce structured "causal attribution" output for Cognee graph
"""

import os
import json
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import IsolationForest

warnings.filterwarnings("ignore")

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = BASE_DIR
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs", "charts")
MODEL_DIR = os.path.join(BASE_DIR, "outputs", "models")
REPORT_DIR = os.path.join(BASE_DIR, "outputs", "reports")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)
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
    crop["crop"] = crop["crop"].str.strip()
    crop = crop[crop["yield"] < 500].copy()

    weather = pd.read_csv(os.path.join(DATA_DIR, "state_weather_data_1997_2020.csv"))
    weather.columns = weather.columns.str.strip().str.lower()
    weather["state"] = weather["state"].str.strip()

    soil = pd.read_csv(os.path.join(DATA_DIR, "state_soil_data.csv"))
    soil.columns = soil.columns.str.strip().str.lower()
    soil["state"] = soil["state"].str.strip()
    soil = soil.dropna(subset=["state"])

    merged = crop.merge(weather, on=["state", "year"], how="inner")
    merged = merged.merge(soil, on="state", how="inner")
    return merged


def detect_yield_anomalies(df):
    """Detect anomalous yield drops using z-score method."""
    # Group by crop-state-season and compute rolling stats
    groups = df.groupby(["crop", "state", "season"])

    all_anomalies = []

    for (crop, state, season), group in groups:
        if len(group) < 5:
            continue

        group = group.sort_values("year")
        group = group.copy()

        # Rolling mean and std (window=5 years)
        group["yield_rolling_mean"] = group["yield"].rolling(window=5, min_periods=3).mean()
        group["yield_rolling_std"] = group["yield"].rolling(window=5, min_periods=3).std()
        group = group.dropna(subset=["yield_rolling_mean", "yield_rolling_std"])

        if len(group) == 0:
            continue

        # Z-score
        group["yield_zscore"] = (group["yield"] - group["yield_rolling_mean"]) / (group["yield_rolling_std"] + 1e-8)

        # Flag anomalies: yield drop > 1.5 sigma
        anomalies = group[group["yield_zscore"] < -1.5].copy()

        for _, row in anomalies.iterrows():
            # Find the previous year for comparison
            prev_year = group[group["year"] == row["year"] - 1]

            anomaly_record = {
                "crop": crop,
                "state": state,
                "season": season,
                "year": int(row["year"]),
                "actual_yield": round(float(row["yield"]), 3),
                "expected_yield": round(float(row["yield_rolling_mean"]), 3),
                "z_score": round(float(row["yield_zscore"]), 3),
                "deviation_pct": round(float((row["yield"] - row["yield_rolling_mean"]) / row["yield_rolling_mean"] * 100), 1),
                "severity": "critical" if row["yield_zscore"] < -2.5 else ("high" if row["yield_zscore"] < -2.0 else "moderate"),
                "weather_context": {
                    "temperature": round(float(row["avg_temp_c"]), 1),
                    "rainfall": round(float(row["total_rainfall_mm"]), 0),
                    "humidity": round(float(row["avg_humidity_percent"]), 1),
                },
                "chemical_context": {
                    "fertilizer": round(float(row["fertilizer"]), 0),
                    "pesticide": round(float(row["pesticide"]), 0),
                },
                "soil_context": {
                    "n": float(row["n"]),
                    "p": float(row["p"]),
                    "k": float(row["k"]),
                    "ph": float(row["ph"]),
                },
                "causal_factors": [],
            }

            # Attribute causes
            if not prev_year.empty:
                prev = prev_year.iloc[0]

                # Weather changes
                temp_change = row["avg_temp_c"] - prev["avg_temp_c"]
                rain_change_pct = (row["total_rainfall_mm"] - prev["total_rainfall_mm"]) / (prev["total_rainfall_mm"] + 1) * 100

                if temp_change > 1.5:
                    anomaly_record["causal_factors"].append({
                        "type": "WeatherEvent",
                        "event": "temperature_spike",
                        "detail": f"Temperature increased by {temp_change:.1f}°C vs previous year",
                        "confidence": "statistical_association",
                    })
                if rain_change_pct < -30:
                    anomaly_record["causal_factors"].append({
                        "type": "WeatherEvent",
                        "event": "drought",
                        "detail": f"Rainfall dropped by {abs(rain_change_pct):.0f}% vs previous year",
                        "confidence": "statistical_association",
                    })
                if rain_change_pct > 50:
                    anomaly_record["causal_factors"].append({
                        "type": "WeatherEvent",
                        "event": "flooding",
                        "detail": f"Rainfall increased by {rain_change_pct:.0f}% vs previous year",
                        "confidence": "statistical_association",
                    })

                # Chemical changes
                fert_change_pct = (row["fertilizer"] - prev["fertilizer"]) / (prev["fertilizer"] + 1) * 100
                pest_change_pct = (row["pesticide"] - prev["pesticide"]) / (prev["pesticide"] + 1) * 100

                if abs(fert_change_pct) > 30:
                    direction = "increase" if fert_change_pct > 0 else "decrease"
                    anomaly_record["causal_factors"].append({
                        "type": "ChemicalProduct",
                        "event": f"fertilizer_{direction}",
                        "detail": f"Fertilizer {direction}d by {abs(fert_change_pct):.0f}%",
                        "confidence": "statistical_association",
                    })
                if abs(pest_change_pct) > 30:
                    direction = "increase" if pest_change_pct > 0 else "decrease"
                    anomaly_record["causal_factors"].append({
                        "type": "ChemicalProduct",
                        "event": f"pesticide_{direction}",
                        "detail": f"Pesticide {direction}d by {abs(pest_change_pct):.0f}%",
                        "confidence": "statistical_association",
                    })

            all_anomalies.append(anomaly_record)

    print(f"✓ Detected {len(all_anomalies)} yield anomalies")
    return all_anomalies


def train_isolation_forest(df):
    """Train Isolation Forest for multivariate anomaly detection."""
    features = ["yield", "fertilizer", "pesticide",
                "avg_temp_c", "total_rainfall_mm", "avg_humidity_percent"]

    # Aggregate per state-year
    agg = df.groupby(["state", "year"])[features].mean().reset_index()
    X = agg[features].values

    iso_forest = IsolationForest(
        n_estimators=200, contamination=0.1,
        random_state=42, n_jobs=-1
    )
    iso_forest.fit(X)
    agg["anomaly_score"] = iso_forest.decision_function(X)
    agg["is_anomaly"] = iso_forest.predict(X) == -1

    # Save model
    joblib.dump(iso_forest, os.path.join(MODEL_DIR, "anomaly_detector.joblib"))
    print(f"✓ Isolation Forest trained ({agg['is_anomaly'].sum()} anomalies detected)")

    return agg, iso_forest


def plot_anomaly_results(anomalies, iso_df):
    """Generate anomaly detection visualizations."""
    fig, axes = plt.subplots(2, 2, figsize=(16, 14))

    # 1. Anomaly distribution by severity
    ax = axes[0, 0]
    if anomalies:
        severity_counts = pd.Series([a["severity"] for a in anomalies]).value_counts()
        colors = {"critical": PALETTE[3], "high": PALETTE[6], "moderate": PALETTE[2]}
        bars = ax.bar(severity_counts.index, severity_counts.values,
                      color=[colors.get(s, PALETTE[0]) for s in severity_counts.index],
                      alpha=0.8, edgecolor="#30363d")
        for bar, val in zip(bars, severity_counts.values):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                    str(val), ha="center", fontsize=12, fontweight="bold", color="#c9d1d9")
    ax.set_title("Anomaly Severity Distribution")
    ax.set_ylabel("Count")
    ax.grid(True, axis="y", alpha=0.3)

    # 2. Anomalies by year
    ax = axes[0, 1]
    if anomalies:
        year_counts = pd.Series([a["year"] for a in anomalies]).value_counts().sort_index()
        ax.bar(year_counts.index, year_counts.values,
               color=PALETTE[3], alpha=0.7, edgecolor="#30363d", linewidth=0.3)
    ax.set_xlabel("Year")
    ax.set_ylabel("Number of Anomalies")
    ax.set_title("Yield Anomalies Over Time")
    ax.grid(True, alpha=0.3)

    # 3. Causal factor frequency
    ax = axes[1, 0]
    if anomalies:
        all_factors = []
        for a in anomalies:
            for f in a["causal_factors"]:
                all_factors.append(f["event"])
        if all_factors:
            factor_counts = pd.Series(all_factors).value_counts().head(8)
            ax.barh(range(len(factor_counts)), factor_counts.values,
                    color=PALETTE[4], alpha=0.8, edgecolor="#30363d")
            ax.set_yticks(range(len(factor_counts)))
            ax.set_yticklabels(factor_counts.index)
            ax.set_xlabel("Frequency")
    ax.set_title("Most Common Causal Factors")
    ax.grid(True, axis="x", alpha=0.3)

    # 4. Isolation Forest anomaly scores
    ax = axes[1, 1]
    normal = iso_df[~iso_df["is_anomaly"]]
    anomaly = iso_df[iso_df["is_anomaly"]]
    ax.scatter(normal["total_rainfall_mm"], normal["yield"],
               c=PALETTE[1], alpha=0.3, s=15, label="Normal")
    ax.scatter(anomaly["total_rainfall_mm"], anomaly["yield"],
               c=PALETTE[3], alpha=0.8, s=40, marker="X",
               edgecolors="white", linewidths=0.5, label="Anomaly")
    ax.set_xlabel("Rainfall (mm)")
    ax.set_ylabel("Yield")
    ax.set_title("Isolation Forest: Multivariate Anomaly Detection")
    ax.legend(frameon=False)
    ax.grid(True, alpha=0.3)

    plt.suptitle("TerraMind — Yield Anomaly Detection & Causal Attribution",
                 fontsize=16, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "17_anomaly_detection.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print("  ✓ Chart: anomaly_detection.png")


def save_anomaly_report(anomalies):
    """Save anomaly findings."""
    # Save JSON for Cognee ingestion
    with open(os.path.join(REPORT_DIR, "yield_anomalies.json"), "w", encoding="utf-8") as f:
        json.dump(anomalies, f, indent=2)

    # Save markdown report
    report = []
    report.append("# TerraMind — Yield Anomaly Detection Report\n")
    report.append(f"**Total anomalies detected**: {len(anomalies)}\n")

    severity_counts = {}
    for a in anomalies:
        severity_counts[a["severity"]] = severity_counts.get(a["severity"], 0) + 1
    report.append("## Severity Breakdown")
    for sev, count in sorted(severity_counts.items()):
        emoji = "[CRITICAL]" if sev == "critical" else ("[HIGH]" if sev == "high" else "[MODERATE]")
        report.append(f"- {emoji} **{sev.title()}**: {count}")

    # Top anomalies
    critical = [a for a in anomalies if a["severity"] == "critical"]
    if critical:
        report.append("\n## Critical Anomalies (Top 10)")
        for a in sorted(critical, key=lambda x: x["z_score"])[:10]:
            report.append(f"\n### {a['crop']} — {a['state']} ({a['year']}, {a['season']})")
            report.append(f"- Yield: **{a['actual_yield']:.2f}** (expected: {a['expected_yield']:.2f})")
            report.append(f"- Deviation: **{a['deviation_pct']:.1f}%** (z-score: {a['z_score']:.2f})")
            if a["causal_factors"]:
                report.append("- **Contributing factors**:")
                for f in a["causal_factors"]:
                    report.append(f"  - [{f['type']}] {f['detail']}")

    with open(os.path.join(REPORT_DIR, "anomaly_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    print(f"  [OK] Reports saved: yield_anomalies.json, anomaly_report.md")


def main():
    print("=" * 60)
    print("TerraMind — Yield Anomaly Detection")
    print("=" * 60)

    df = load_merged()
    print(f"Merged dataset: {len(df):,} rows\n")

    anomalies = detect_yield_anomalies(df)
    iso_df, iso_model = train_isolation_forest(df)
    plot_anomaly_results(anomalies, iso_df)
    save_anomaly_report(anomalies)

    print(f"\n✅ Anomaly detection complete! {len(anomalies)} anomalies found")


if __name__ == "__main__":
    main()
