"""
TerraMind — Weather & Soil Cross-Analysis
==========================================
Merges weather and soil data with crop yield for multi-factor insights.

Analyses:
  1. Temperature & rainfall trends per state (1997–2020)
  2. Correlation matrix: weather × soil × yield
  3. Drought year detection (rainfall anomalies)
  4. Soil nutrient impact on yield
  5. Humidity-yield relationship
  6. Climate risk mapping
"""

import os
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = BASE_DIR
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs", "charts")
os.makedirs(OUTPUT_DIR, exist_ok=True)

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


def load_data():
    """Load all three datasets."""
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

    print(f"✓ Crop yield: {len(crop):,} rows")
    print(f"✓ Weather:    {len(weather):,} rows ({weather['state'].nunique()} states)")
    print(f"✓ Soil:       {len(soil):,} rows ({soil['state'].nunique()} states)")

    return crop, weather, soil


def merge_all(crop, weather, soil):
    """Merge all datasets on state + year."""
    # Aggregate crop yield per state-year
    crop_agg = (crop.groupby(["state", "year"])
                .agg(avg_yield=("yield", "mean"),
                     total_production=("production", "sum"),
                     avg_fertilizer=("fertilizer", "mean"),
                     avg_pesticide=("pesticide", "mean"),
                     crop_count=("crop", "nunique"))
                .reset_index())

    merged = crop_agg.merge(weather, on=["state", "year"], how="inner")
    merged = merged.merge(soil, on="state", how="inner")
    print(f"✓ Merged dataset: {len(merged):,} rows\n")
    return merged


def plot_weather_trends(weather):
    """1. Temperature and rainfall trends."""
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))

    # National average temperature trend
    ax = axes[0, 0]
    yearly_temp = weather.groupby("year")["avg_temp_c"].mean()
    ax.plot(yearly_temp.index, yearly_temp.values, marker="o", markersize=4,
            color=PALETTE[3], linewidth=2)
    z = np.polyfit(yearly_temp.index, yearly_temp.values, 1)
    p = np.poly1d(z)
    ax.plot(yearly_temp.index, p(yearly_temp.index), "--", color=PALETTE[6],
            linewidth=1.5, alpha=0.7, label=f"Trend: +{z[0]*10:.2f}°C/decade")
    ax.set_xlabel("Year")
    ax.set_ylabel("Average Temperature (°C)")
    ax.set_title("National Avg Temperature Trend")
    ax.legend(frameon=False)
    ax.grid(True, alpha=0.3)

    # National average rainfall trend
    ax = axes[0, 1]
    yearly_rain = weather.groupby("year")["total_rainfall_mm"].mean()
    ax.bar(yearly_rain.index, yearly_rain.values, color=PALETTE[0], alpha=0.7,
           edgecolor="#30363d", linewidth=0.3)
    ax.axhline(yearly_rain.mean(), color=PALETTE[2], linestyle="--", linewidth=1.5,
               label=f"Mean: {yearly_rain.mean():.0f}mm")
    ax.set_xlabel("Year")
    ax.set_ylabel("Average Rainfall (mm)")
    ax.set_title("National Avg Rainfall by Year")
    ax.legend(frameon=False)
    ax.grid(True, alpha=0.3)

    # Temperature distribution by state
    ax = axes[1, 0]
    top_states = weather.groupby("state")["avg_temp_c"].mean().nlargest(10).index
    state_temp = weather[weather["state"].isin(top_states)]
    bp = ax.boxplot([state_temp[state_temp["state"] == s]["avg_temp_c"].values for s in top_states],
                    labels=top_states, patch_artist=True, medianprops={"color": "#f85149"})
    for i, patch in enumerate(bp["boxes"]):
        patch.set_facecolor(PALETTE[i % len(PALETTE)])
        patch.set_alpha(0.6)
    ax.set_xticklabels(top_states, rotation=45, ha="right")
    ax.set_ylabel("Avg Temperature (°C)")
    ax.set_title("Temperature Distribution — Top 10 Hottest States")
    ax.grid(True, alpha=0.3)

    # Humidity trends
    ax = axes[1, 1]
    yearly_humidity = weather.groupby("year")["avg_humidity_percent"].mean()
    ax.fill_between(yearly_humidity.index, yearly_humidity.values,
                    alpha=0.3, color=PALETTE[4])
    ax.plot(yearly_humidity.index, yearly_humidity.values, marker="o", markersize=3,
            color=PALETTE[4], linewidth=2)
    ax.set_xlabel("Year")
    ax.set_ylabel("Average Humidity (%)")
    ax.set_title("National Avg Humidity Trend")
    ax.grid(True, alpha=0.3)

    plt.suptitle("Weather Patterns Analysis (1997–2020)", fontsize=16,
                 fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "08_weather_trends.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print("  ✓ Chart: weather_trends.png")


def plot_correlation_matrix(merged):
    """2. Full correlation matrix: weather × soil × yield."""
    cols = ["avg_yield", "avg_fertilizer", "avg_pesticide",
            "avg_temp_c", "total_rainfall_mm", "avg_humidity_percent",
            "n", "p", "k", "ph"]
    corr = merged[cols].corr()

    fig, ax = plt.subplots(figsize=(12, 10))
    mask = np.triu(np.ones_like(corr, dtype=bool), k=1)
    sns.heatmap(corr, mask=mask, annot=True, fmt=".2f", cmap="coolwarm",
                center=0, ax=ax, linewidths=0.5, linecolor="#30363d",
                cbar_kws={"shrink": 0.8, "label": "Pearson Correlation"},
                annot_kws={"size": 10})
    labels = ["Avg Yield", "Fertilizer", "Pesticide",
              "Temperature", "Rainfall", "Humidity",
              "Nitrogen (N)", "Phosphorus (P)", "Potassium (K)", "pH"]
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_yticklabels(labels, rotation=0)
    ax.set_title("Multi-Factor Correlation Matrix\n(Weather × Soil × Agricultural Inputs × Yield)")
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "09_correlation_matrix.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print("  ✓ Chart: correlation_matrix.png")


def plot_drought_detection(weather, crop):
    """3. Drought year detection and yield impact."""
    # Detect drought: rainfall < mean - 1.5*std per state
    state_stats = weather.groupby("state")["total_rainfall_mm"].agg(["mean", "std"]).reset_index()
    state_stats.columns = ["state", "rain_mean", "rain_std"]
    weather_ext = weather.merge(state_stats, on="state")
    weather_ext["drought_score"] = (weather_ext["rain_mean"] - weather_ext["total_rainfall_mm"]) / (weather_ext["rain_std"] + 1e-6)
    weather_ext["is_drought"] = weather_ext["drought_score"] > 1.5

    # Merge with yield
    crop_agg = crop.groupby(["state", "year"])["yield"].mean().reset_index()
    drought_yield = crop_agg.merge(weather_ext[["state", "year", "drought_score", "is_drought"]],
                                   on=["state", "year"], how="inner")

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    # Drought frequency by year
    ax = axes[0]
    drought_by_year = weather_ext.groupby("year")["is_drought"].sum()
    colors = [PALETTE[3] if d > 3 else PALETTE[0] for d in drought_by_year.values]
    ax.bar(drought_by_year.index, drought_by_year.values, color=colors,
           alpha=0.8, edgecolor="#30363d", linewidth=0.3)
    ax.set_xlabel("Year")
    ax.set_ylabel("Number of States in Drought")
    ax.set_title("Drought Events by Year\n(Rainfall < mean - 1.5σ)")
    ax.grid(True, alpha=0.3)

    # Yield in drought vs non-drought
    ax = axes[1]
    drought_group = drought_yield.groupby("is_drought")["yield"].agg(["mean", "std"]).reset_index()
    labels = ["Normal Years", "Drought Years"]
    colors = [PALETTE[1], PALETTE[3]]
    bars = ax.bar(labels, drought_group["mean"], yerr=drought_group["std"],
                  color=colors, alpha=0.8, edgecolor="#30363d",
                  error_kw={"ecolor": "#8b949e", "capsize": 6})
    for bar, val in zip(bars, drought_group["mean"]):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                f"{val:.2f}", ha="center", fontsize=12, fontweight="bold",
                color="#c9d1d9")
    pct_drop = ((drought_group["mean"].iloc[0] - drought_group["mean"].iloc[1])
                / drought_group["mean"].iloc[0] * 100)
    ax.set_title(f"Yield Impact of Drought ({pct_drop:.1f}% average drop)")
    ax.set_ylabel("Average Yield")
    ax.grid(True, axis="y", alpha=0.3)

    plt.suptitle("Drought Detection & Agricultural Impact", fontsize=16,
                 fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "10_drought_detection.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print("  ✓ Chart: drought_detection.png")


def plot_soil_impact(merged):
    """4. Soil nutrient impact on yield."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))

    nutrients = [("n", "Nitrogen (N)", PALETTE[0]),
                 ("p", "Phosphorus (P)", PALETTE[1]),
                 ("k", "Potassium (K)", PALETTE[2]),
                 ("ph", "Soil pH", PALETTE[4])]

    for ax, (col, label, color) in zip(axes.flat, nutrients):
        state_avg = merged.groupby("state").agg(
            nutrient=(col, "first"),
            yield_avg=("avg_yield", "mean")
        ).reset_index()

        ax.scatter(state_avg["nutrient"], state_avg["yield_avg"],
                   c=color, s=80, alpha=0.8, edgecolors="#30363d", linewidth=0.5)

        # Add state labels for top/bottom
        for _, row in state_avg.nlargest(3, "yield_avg").iterrows():
            ax.annotate(row["state"][:6], (row["nutrient"], row["yield_avg"]),
                        fontsize=7, color="#8b949e", ha="center",
                        xytext=(0, 8), textcoords="offset points")

        z = np.polyfit(state_avg["nutrient"], state_avg["yield_avg"], 1)
        p = np.poly1d(z)
        x_line = np.linspace(state_avg["nutrient"].min(), state_avg["nutrient"].max(), 100)
        ax.plot(x_line, p(x_line), "--", color=color, alpha=0.5, linewidth=1.5)

        corr = state_avg["nutrient"].corr(state_avg["yield_avg"])
        ax.set_xlabel(label)
        ax.set_ylabel("Average Yield")
        ax.set_title(f"{label} vs Yield (r={corr:.3f})")
        ax.grid(True, alpha=0.3)

    plt.suptitle("Soil Nutrient Impact on Crop Yield", fontsize=16,
                 fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "11_soil_nutrient_impact.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print("  ✓ Chart: soil_nutrient_impact.png")


def plot_climate_risk_map(merged):
    """6. Climate risk scoring per state."""
    # Risk = high temp variability + low rainfall + high yield volatility
    state_risk = merged.groupby("state").agg(
        temp_volatility=("avg_temp_c", "std"),
        rain_volatility=("total_rainfall_mm", "std"),
        yield_volatility=("avg_yield", "std"),
        avg_yield=("avg_yield", "mean"),
        avg_rainfall=("total_rainfall_mm", "mean"),
    ).reset_index()

    # Normalize and compute composite risk score
    for col in ["temp_volatility", "rain_volatility", "yield_volatility"]:
        state_risk[f"{col}_norm"] = (state_risk[col] - state_risk[col].min()) / (state_risk[col].max() - state_risk[col].min() + 1e-8)

    state_risk["risk_score"] = (state_risk["temp_volatility_norm"] * 0.3 +
                                state_risk["rain_volatility_norm"] * 0.4 +
                                state_risk["yield_volatility_norm"] * 0.3)

    state_risk = state_risk.sort_values("risk_score", ascending=True)

    fig, ax = plt.subplots(figsize=(12, 10))
    colors = plt.cm.RdYlGn_r(np.linspace(0.1, 0.9, len(state_risk)))
    bars = ax.barh(range(len(state_risk)), state_risk["risk_score"],
                   color=colors, edgecolor="#30363d", linewidth=0.3)
    ax.set_yticks(range(len(state_risk)))
    ax.set_yticklabels(state_risk["state"])
    ax.set_xlabel("Climate Risk Score (0 = Low, 1 = High)")
    ax.set_title("Agricultural Climate Risk Ranking by State\n(Based on temperature, rainfall & yield volatility)")
    ax.grid(True, axis="x", alpha=0.3)

    # Highlight high-risk states
    high_risk = state_risk[state_risk["risk_score"] > 0.6]
    if not high_risk.empty:
        ax.axvline(x=0.6, color=PALETTE[3], linestyle="--", alpha=0.5,
                   label=f"High Risk Threshold ({len(high_risk)} states)")
        ax.legend(frameon=False)

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "12_climate_risk_ranking.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print("  ✓ Chart: climate_risk_ranking.png")


def main():
    print("=" * 60)
    print("TerraMind — Weather & Soil Cross-Analysis")
    print("=" * 60)

    crop, weather, soil = load_data()
    merged = merge_all(crop, weather, soil)

    print(f"Generating charts → {OUTPUT_DIR}\n")

    plot_weather_trends(weather)
    plot_correlation_matrix(merged)
    plot_drought_detection(weather, crop)
    plot_soil_impact(merged)
    plot_climate_risk_map(merged)

    print(f"\n✅ All weather & soil analysis charts generated in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
