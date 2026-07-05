"""
TerraMind — Crop Yield Exploratory Data Analysis
=================================================
Produces publication-quality charts for the hackathon presentation.

Analyses:
  1. Yield trends over time (1997–2020) per major state
  2. Top crops by average yield
  3. Fertilizer vs. yield correlation
  4. Pesticide usage patterns and yield impact
  5. Season-wise crop performance
  6. State-level yield ranking
  7. Year-over-year yield volatility
"""

import os
import sys
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
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
    "figure.titlesize": 16,
    "figure.titleweight": "bold",
})

PALETTE = ["#58a6ff", "#3fb950", "#d29922", "#f85149", "#bc8cff",
           "#39d353", "#f0883e", "#79c0ff", "#56d364", "#e3b341"]


def load_data() -> pd.DataFrame:
    """Load and clean the crop yield dataset."""
    df = pd.read_csv(os.path.join(DATA_DIR, "crop_yield.csv"))
    df.columns = df.columns.str.strip().str.lower()
    df["season"] = df["season"].str.strip()
    df["state"] = df["state"].str.strip()
    df["crop"] = df["crop"].str.strip()
    # Remove extreme outliers (yield > 500 likely data errors like Coconut)
    df = df[df["yield"] < 500].copy()
    df = df.dropna(subset=["yield", "fertilizer", "pesticide"])
    print(f"✓ Loaded crop_yield.csv: {len(df):,} rows, {df['year'].min()}–{df['year'].max()}")
    return df


def plot_yield_trends(df: pd.DataFrame):
    """1. Yield trends over time for top states."""
    top_states = df.groupby("state")["yield"].mean().nlargest(8).index.tolist()
    fig, ax = plt.subplots(figsize=(14, 7))
    for i, state in enumerate(top_states):
        state_data = df[df["state"] == state].groupby("year")["yield"].mean()
        ax.plot(state_data.index, state_data.values, marker="o", markersize=3,
                linewidth=2, label=state, color=PALETTE[i % len(PALETTE)], alpha=0.85)
    ax.set_xlabel("Year")
    ax.set_ylabel("Average Yield (tonnes/ha)")
    ax.set_title("Crop Yield Trends by State (1997–2020)")
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", frameon=False)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "01_yield_trends_by_state.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print("  ✓ Chart: yield_trends_by_state.png")


def plot_top_crops(df: pd.DataFrame):
    """2. Top 15 crops by average yield."""
    crop_yield = df.groupby("crop")["yield"].agg(["mean", "std", "count"]).reset_index()
    crop_yield = crop_yield[crop_yield["count"] >= 20]  # Minimum samples
    crop_yield = crop_yield.nlargest(15, "mean")

    fig, ax = plt.subplots(figsize=(12, 7))
    bars = ax.barh(range(len(crop_yield)), crop_yield["mean"],
                   xerr=crop_yield["std"].clip(upper=crop_yield["mean"]),
                   color=PALETTE[0], alpha=0.8, edgecolor="#30363d", linewidth=0.5,
                   error_kw={"ecolor": "#8b949e", "capsize": 3, "linewidth": 1})
    ax.set_yticks(range(len(crop_yield)))
    ax.set_yticklabels(crop_yield["crop"].values)
    ax.set_xlabel("Average Yield (tonnes/ha)")
    ax.set_title("Top 15 Crops by Average Yield")
    ax.grid(True, axis="x", alpha=0.3)
    ax.invert_yaxis()
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "02_top_crops_by_yield.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print("  ✓ Chart: top_crops_by_yield.png")


def plot_fertilizer_yield_correlation(df: pd.DataFrame):
    """3. Fertilizer vs. yield — scatter + regression."""
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    # Log-scale scatter
    sample = df.sample(min(3000, len(df)), random_state=42)
    ax = axes[0]
    scatter = ax.scatter(np.log1p(sample["fertilizer"]), sample["yield"],
                         c=sample["year"], cmap="cool", alpha=0.4, s=10, edgecolors="none")
    plt.colorbar(scatter, ax=ax, label="Year", shrink=0.8)
    ax.set_xlabel("log(Fertilizer + 1)")
    ax.set_ylabel("Yield (tonnes/ha)")
    ax.set_title("Fertilizer Use vs. Yield")
    ax.grid(True, alpha=0.3)

    # Binned average
    ax = axes[1]
    df_temp = df.copy()
    df_temp["fert_bin"] = pd.qcut(df_temp["fertilizer"], q=10, duplicates="drop")
    binned = df_temp.groupby("fert_bin", observed=True)["yield"].agg(["mean", "std"]).reset_index()
    binned["label"] = binned["fert_bin"].astype(str)
    ax.bar(range(len(binned)), binned["mean"], yerr=binned["std"].clip(upper=binned["mean"]),
           color=PALETTE[1], alpha=0.8, edgecolor="#30363d", linewidth=0.5,
           error_kw={"ecolor": "#8b949e", "capsize": 3})
    ax.set_xticks(range(len(binned)))
    ax.set_xticklabels([f"Q{i+1}" for i in range(len(binned))], rotation=0)
    ax.set_xlabel("Fertilizer Decile (Q1=lowest, Q10=highest)")
    ax.set_ylabel("Average Yield")
    ax.set_title("Yield by Fertilizer Decile")
    ax.grid(True, axis="y", alpha=0.3)

    plt.suptitle("Fertilizer–Yield Relationship Analysis", fontsize=16, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "03_fertilizer_yield_correlation.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print("  ✓ Chart: fertilizer_yield_correlation.png")


def plot_pesticide_analysis(df: pd.DataFrame):
    """4. Pesticide usage patterns and yield impact."""
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    # Pesticide usage over time
    ax = axes[0]
    pest_by_year = df.groupby("year")["pesticide"].agg(["mean", "median"]).reset_index()
    ax.plot(pest_by_year["year"], pest_by_year["mean"], marker="o", markersize=4,
            color=PALETTE[3], linewidth=2, label="Mean")
    ax.plot(pest_by_year["year"], pest_by_year["median"], marker="s", markersize=4,
            color=PALETTE[4], linewidth=2, label="Median", linestyle="--")
    ax.set_xlabel("Year")
    ax.set_ylabel("Pesticide Usage")
    ax.set_title("Pesticide Usage Trend (1997–2020)")
    ax.legend(frameon=False)
    ax.grid(True, alpha=0.3)

    # Pesticide vs yield binned
    ax = axes[1]
    df_temp = df.copy()
    df_temp["pest_bin"] = pd.qcut(df_temp["pesticide"], q=8, duplicates="drop")
    binned = df_temp.groupby("pest_bin", observed=True)["yield"].mean().reset_index()
    ax.bar(range(len(binned)), binned["yield"],
           color=PALETTE[5], alpha=0.8, edgecolor="#30363d", linewidth=0.5)
    ax.set_xticks(range(len(binned)))
    ax.set_xticklabels([f"Q{i+1}" for i in range(len(binned))], rotation=0)
    ax.set_xlabel("Pesticide Decile")
    ax.set_ylabel("Average Yield")
    ax.set_title("Yield by Pesticide Usage Level")
    ax.grid(True, axis="y", alpha=0.3)

    plt.suptitle("Pesticide Usage Analysis", fontsize=16, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "04_pesticide_analysis.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print("  ✓ Chart: pesticide_analysis.png")


def plot_season_performance(df: pd.DataFrame):
    """5. Season-wise crop performance."""
    seasons = df["season"].unique()
    fig, ax = plt.subplots(figsize=(10, 6))

    season_data = df.groupby("season")["yield"].agg(["mean", "std", "count"]).reset_index()
    season_data = season_data.sort_values("mean", ascending=True)

    colors = [PALETTE[i % len(PALETTE)] for i in range(len(season_data))]
    bars = ax.barh(season_data["season"], season_data["mean"],
                   xerr=season_data["std"].clip(upper=season_data["mean"]),
                   color=colors, alpha=0.85, edgecolor="#30363d",
                   error_kw={"ecolor": "#8b949e", "capsize": 4})
    for i, (_, row) in enumerate(season_data.iterrows()):
        ax.text(row["mean"] + 0.1, i, f'n={row["count"]:,.0f}',
                va="center", fontsize=9, color="#8b949e")
    ax.set_xlabel("Average Yield (tonnes/ha)")
    ax.set_title("Crop Yield by Growing Season")
    ax.grid(True, axis="x", alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "05_season_performance.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print("  ✓ Chart: season_performance.png")


def plot_state_ranking(df: pd.DataFrame):
    """6. State-level yield ranking heatmap."""
    # Average yield per state per year
    pivot = df.groupby(["state", "year"])["yield"].mean().reset_index()
    heatmap_data = pivot.pivot_table(index="state", columns="year", values="yield", aggfunc="mean")

    # Normalize per state (z-score) to see relative trends
    heatmap_norm = heatmap_data.apply(lambda x: (x - x.mean()) / (x.std() + 1e-8), axis=1)

    fig, ax = plt.subplots(figsize=(18, 12))
    sns.heatmap(heatmap_norm, cmap="RdYlGn", center=0, ax=ax,
                linewidths=0.3, linecolor="#30363d",
                cbar_kws={"label": "Z-Score (relative to state mean)", "shrink": 0.6})
    ax.set_xlabel("Year")
    ax.set_ylabel("State")
    ax.set_title("Relative Yield Performance by State & Year\n(Green = above average, Red = below average)")
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "06_state_yield_heatmap.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print("  ✓ Chart: state_yield_heatmap.png")


def plot_yield_volatility(df: pd.DataFrame):
    """7. Year-over-year yield volatility analysis."""
    # Calculate YoY change per state-crop
    yoy = (df.groupby(["state", "crop", "year"])["yield"]
             .mean().reset_index()
             .sort_values(["state", "crop", "year"]))
    yoy["yield_change"] = yoy.groupby(["state", "crop"])["yield"].pct_change() * 100
    yoy = yoy.dropna(subset=["yield_change"])
    yoy["yield_change"] = yoy["yield_change"].clip(-100, 200)  # Clip extreme outliers

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    # Distribution of YoY changes
    ax = axes[0]
    ax.hist(yoy["yield_change"], bins=80, color=PALETTE[0], alpha=0.7,
            edgecolor="#30363d", linewidth=0.3)
    ax.axvline(x=0, color=PALETTE[3], linestyle="--", linewidth=2, alpha=0.8)
    ax.axvline(x=-20, color="#f85149", linestyle=":", linewidth=1.5, alpha=0.6, label="–20% threshold")
    ax.axvline(x=20, color="#3fb950", linestyle=":", linewidth=1.5, alpha=0.6, label="+20% threshold")
    ax.set_xlabel("Year-over-Year Yield Change (%)")
    ax.set_ylabel("Frequency")
    ax.set_title("Distribution of YoY Yield Changes")
    ax.legend(frameon=False)
    ax.grid(True, alpha=0.3)

    # Volatility by state
    ax = axes[1]
    state_vol = yoy.groupby("state")["yield_change"].std().sort_values(ascending=True)
    top_vol = state_vol.tail(12)
    ax.barh(range(len(top_vol)), top_vol.values,
            color=PALETTE[3], alpha=0.8, edgecolor="#30363d")
    ax.set_yticks(range(len(top_vol)))
    ax.set_yticklabels(top_vol.index)
    ax.set_xlabel("Yield Volatility (Std Dev of YoY %)")
    ax.set_title("Most Volatile States (Yield Instability)")
    ax.grid(True, axis="x", alpha=0.3)

    plt.suptitle("Yield Volatility & Risk Analysis", fontsize=16, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "07_yield_volatility.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print("  ✓ Chart: yield_volatility.png")


def generate_summary_stats(df: pd.DataFrame):
    """Generate summary statistics markdown."""
    report_dir = os.path.join(BASE_DIR, "outputs", "reports")
    os.makedirs(report_dir, exist_ok=True)

    summary = []
    summary.append("# Crop Yield EDA — Key Findings\n")
    summary.append(f"**Dataset**: {len(df):,} records | {df['year'].min()}–{df['year'].max()}")
    summary.append(f"**States**: {df['state'].nunique()} | **Crops**: {df['crop'].nunique()} | **Seasons**: {df['season'].nunique()}\n")

    summary.append("## Key Statistics")
    summary.append(f"- Mean yield: **{df['yield'].mean():.2f}** tonnes/ha")
    summary.append(f"- Median yield: **{df['yield'].median():.2f}** tonnes/ha")
    summary.append(f"- Yield std dev: **{df['yield'].std():.2f}**")
    summary.append(f"- Mean fertilizer: **{df['fertilizer'].mean():,.0f}**")
    summary.append(f"- Mean pesticide: **{df['pesticide'].mean():,.0f}**\n")

    # Correlation findings
    corr_fert = df[["fertilizer", "yield"]].corr().iloc[0, 1]
    corr_pest = df[["pesticide", "yield"]].corr().iloc[0, 1]
    summary.append("## Correlations")
    summary.append(f"- Fertilizer <-> Yield: **{corr_fert:.3f}**")
    summary.append(f"- Pesticide <-> Yield: **{corr_pest:.3f}**\n")

    # Top performing states
    top_states = df.groupby("state")["yield"].mean().nlargest(5)
    summary.append("## Top 5 States by Avg Yield")
    for state, yld in top_states.items():
        summary.append(f"- {state}: **{yld:.2f}**")

    with open(os.path.join(report_dir, "eda_crop_yield_summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(summary))
    print("  [OK] Report: eda_crop_yield_summary.md")


def main():
    print("=" * 60)
    print("TerraMind — Crop Yield EDA")
    print("=" * 60)

    df = load_data()
    print(f"\nGenerating charts → {OUTPUT_DIR}\n")

    plot_yield_trends(df)
    plot_top_crops(df)
    plot_fertilizer_yield_correlation(df)
    plot_pesticide_analysis(df)
    plot_season_performance(df)
    plot_state_ranking(df)
    plot_yield_volatility(df)
    generate_summary_stats(df)

    print(f"\n✅ All crop yield EDA charts generated in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
