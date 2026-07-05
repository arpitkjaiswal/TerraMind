"""
TerraMind — Crop Yield Prediction Model
========================================
Ensemble model (Random Forest + XGBoost) for yield prediction.

Features:
  - Weather: temperature, rainfall, humidity
  - Soil: N, P, K, pH
  - Inputs: fertilizer, pesticide amounts
  - Categorical: crop type, season, state (label-encoded)

Training strategy:
  - Temporal split: train on 1997–2016, test on 2017–2020
  - This mimics real-world forecasting (predict future from past)

Outputs:
  - Trained model files (.joblib)
  - Performance metrics and charts
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
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import cross_val_score
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import LabelEncoder

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

PALETTE = ["#58a6ff", "#3fb950", "#d29922", "#f85149", "#bc8cff"]


def load_and_prepare():
    """Load, merge, and feature-engineer the dataset."""
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

    # Merge
    df = crop.merge(weather, on=["state", "year"], how="inner")
    df = df.merge(soil, on="state", how="inner")

    # Encode categoricals
    le_crop = LabelEncoder()
    le_season = LabelEncoder()
    le_state = LabelEncoder()

    df["crop_encoded"] = le_crop.fit_transform(df["crop"])
    df["season_encoded"] = le_season.fit_transform(df["season"])
    df["state_encoded"] = le_state.fit_transform(df["state"])

    # Feature engineering
    df["fert_per_area"] = df["fertilizer"] / (df["area"] + 1)
    df["pest_per_area"] = df["pesticide"] / (df["area"] + 1)
    df["rain_temp_ratio"] = df["total_rainfall_mm"] / (df["avg_temp_c"] + 1)
    df["npk_total"] = df["n"] + df["p"] + df["k"]

    print(f"✓ Prepared dataset: {len(df):,} rows")

    # Save encoders for later use
    encoders = {"crop": le_crop, "season": le_season, "state": le_state}

    return df, encoders


def temporal_split(df, train_end=2016):
    """Split by year — train on past, test on future."""
    feature_cols = [
        "area", "fertilizer", "pesticide",
        "avg_temp_c", "total_rainfall_mm", "avg_humidity_percent",
        "n", "p", "k", "ph",
        "crop_encoded", "season_encoded", "state_encoded",
        "fert_per_area", "pest_per_area", "rain_temp_ratio", "npk_total",
    ]
    target = "yield"

    train = df[df["year"] <= train_end].copy()
    test = df[df["year"] > train_end].copy()

    X_train = train[feature_cols].values
    y_train = train[target].values
    X_test = test[feature_cols].values
    y_test = test[target].values

    print(f"  Train: {len(train):,} rows (≤{train_end})")
    print(f"  Test:  {len(test):,} rows (>{train_end})")

    return X_train, y_train, X_test, y_test, feature_cols, test


def train_models(X_train, y_train, X_test, y_test, feature_cols):
    """Train Random Forest and Gradient Boosting models."""
    models = {}

    # 1. Random Forest
    print("\n  Training Random Forest...")
    rf = RandomForestRegressor(
        n_estimators=300, max_depth=20, min_samples_leaf=5,
        random_state=42, n_jobs=-1
    )
    rf.fit(X_train, y_train)
    y_pred_rf = rf.predict(X_test)
    models["random_forest"] = {
        "model": rf,
        "predictions": y_pred_rf,
        "mae": mean_absolute_error(y_test, y_pred_rf),
        "rmse": np.sqrt(mean_squared_error(y_test, y_pred_rf)),
        "r2": r2_score(y_test, y_pred_rf),
    }
    print(f"    R² = {models['random_forest']['r2']:.4f}, "
          f"RMSE = {models['random_forest']['rmse']:.4f}, "
          f"MAE = {models['random_forest']['mae']:.4f}")

    # 2. Gradient Boosting (XGBoost-like)
    print("  Training Gradient Boosting...")
    gb = GradientBoostingRegressor(
        n_estimators=300, max_depth=8, learning_rate=0.1,
        min_samples_leaf=10, subsample=0.8,
        random_state=42
    )
    gb.fit(X_train, y_train)
    y_pred_gb = gb.predict(X_test)
    models["gradient_boosting"] = {
        "model": gb,
        "predictions": y_pred_gb,
        "mae": mean_absolute_error(y_test, y_pred_gb),
        "rmse": np.sqrt(mean_squared_error(y_test, y_pred_gb)),
        "r2": r2_score(y_test, y_pred_gb),
    }
    print(f"    R² = {models['gradient_boosting']['r2']:.4f}, "
          f"RMSE = {models['gradient_boosting']['rmse']:.4f}, "
          f"MAE = {models['gradient_boosting']['mae']:.4f}")

    # 3. Ensemble (average)
    y_pred_ensemble = (y_pred_rf + y_pred_gb) / 2
    models["ensemble"] = {
        "predictions": y_pred_ensemble,
        "mae": mean_absolute_error(y_test, y_pred_ensemble),
        "rmse": np.sqrt(mean_squared_error(y_test, y_pred_ensemble)),
        "r2": r2_score(y_test, y_pred_ensemble),
    }
    print(f"  Ensemble: R² = {models['ensemble']['r2']:.4f}, "
          f"RMSE = {models['ensemble']['rmse']:.4f}")

    return models


def plot_model_results(models, y_test, feature_cols, X_train, y_train):
    """Generate model evaluation charts."""
    fig, axes = plt.subplots(2, 2, figsize=(16, 14))

    # 1. Actual vs Predicted scatter
    ax = axes[0, 0]
    for name, color, marker in [("random_forest", PALETTE[0], "o"),
                                 ("gradient_boosting", PALETTE[1], "s")]:
        m = models[name]
        sample_idx = np.random.choice(len(y_test), min(1500, len(y_test)), replace=False)
        ax.scatter(y_test[sample_idx], m["predictions"][sample_idx],
                   c=color, alpha=0.3, s=8, label=f"{name} (R²={m['r2']:.3f})")
    max_val = max(y_test.max(), models["random_forest"]["predictions"].max())
    ax.plot([0, max_val], [0, max_val], "--", color="#f85149", linewidth=1.5, alpha=0.7)
    ax.set_xlabel("Actual Yield")
    ax.set_ylabel("Predicted Yield")
    ax.set_title("Actual vs Predicted Yield")
    ax.legend(frameon=False)
    ax.grid(True, alpha=0.3)

    # 2. Model comparison bar chart
    ax = axes[0, 1]
    model_names = ["Random\nForest", "Gradient\nBoosting", "Ensemble"]
    r2_scores = [models[k]["r2"] for k in ["random_forest", "gradient_boosting", "ensemble"]]
    rmse_scores = [models[k]["rmse"] for k in ["random_forest", "gradient_boosting", "ensemble"]]

    x = np.arange(len(model_names))
    width = 0.35
    bars1 = ax.bar(x - width/2, r2_scores, width, label="R² Score",
                   color=PALETTE[0], alpha=0.8, edgecolor="#30363d")
    ax2 = ax.twinx()
    bars2 = ax2.bar(x + width/2, rmse_scores, width, label="RMSE",
                    color=PALETTE[3], alpha=0.8, edgecolor="#30363d")
    ax.set_xticks(x)
    ax.set_xticklabels(model_names)
    ax.set_ylabel("R² Score", color=PALETTE[0])
    ax2.set_ylabel("RMSE", color=PALETTE[3])
    ax.set_title("Model Comparison")
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, frameon=False)

    # 3. Feature importance (RF)
    ax = axes[1, 0]
    rf = models["random_forest"]["model"]
    importances = pd.Series(rf.feature_importances_, index=feature_cols).sort_values()
    nice_names = {
        "area": "Area", "fertilizer": "Fertilizer", "pesticide": "Pesticide",
        "avg_temp_c": "Temperature", "total_rainfall_mm": "Rainfall",
        "avg_humidity_percent": "Humidity", "n": "Nitrogen", "p": "Phosphorus",
        "k": "Potassium", "ph": "pH", "crop_encoded": "Crop Type",
        "season_encoded": "Season", "state_encoded": "State",
        "fert_per_area": "Fert/Area", "pest_per_area": "Pest/Area",
        "rain_temp_ratio": "Rain/Temp", "npk_total": "NPK Total",
    }
    colors = plt.cm.viridis(np.linspace(0.2, 0.9, len(importances)))
    ax.barh(range(len(importances)), importances.values,
            color=colors, edgecolor="#30363d", linewidth=0.3)
    ax.set_yticks(range(len(importances)))
    ax.set_yticklabels([nice_names.get(f, f) for f in importances.index], fontsize=9)
    ax.set_xlabel("Feature Importance")
    ax.set_title("Feature Importance (Random Forest)")
    ax.grid(True, axis="x", alpha=0.3)

    # 4. Residual distribution
    ax = axes[1, 1]
    residuals = y_test - models["ensemble"]["predictions"]
    ax.hist(residuals, bins=80, color=PALETTE[4], alpha=0.7,
            edgecolor="#30363d", linewidth=0.3)
    ax.axvline(0, color="#f85149", linestyle="--", linewidth=2)
    ax.set_xlabel("Prediction Error (Actual - Predicted)")
    ax.set_ylabel("Frequency")
    ax.set_title(f"Residual Distribution (Ensemble)\nMean Error: {residuals.mean():.3f}, Std: {residuals.std():.3f}")
    ax.grid(True, alpha=0.3)

    plt.suptitle("TerraMind — Yield Prediction Model Performance",
                 fontsize=16, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "16_model_performance.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print("  ✓ Chart: model_performance.png")


def save_models(models, encoders):
    """Save trained models."""
    joblib.dump(models["random_forest"]["model"],
                os.path.join(MODEL_DIR, "yield_predictor_rf.joblib"))
    joblib.dump(models["gradient_boosting"]["model"],
                os.path.join(MODEL_DIR, "yield_predictor_gb.joblib"))
    joblib.dump(encoders, os.path.join(MODEL_DIR, "label_encoders.joblib"))
    print(f"  ✓ Models saved to {MODEL_DIR}")


def generate_model_report(models):
    """Generate model performance report."""
    report = []
    report.append("# TerraMind — Yield Prediction Model Report\n")
    report.append("## Training Strategy")
    report.append("- **Temporal split**: Train on 1997–2016, Test on 2017–2020")
    report.append("- **Purpose**: Predict future yields from historical data")
    report.append("- **Features**: 17 engineered features from 3 merged datasets\n")

    report.append("## Model Performance")
    report.append("| Model | R² | RMSE | MAE |")
    report.append("|---|---|---|---|")
    for name in ["random_forest", "gradient_boosting", "ensemble"]:
        m = models[name]
        nice = name.replace("_", " ").title()
        report.append(f"| {nice} | {m['r2']:.4f} | {m['rmse']:.4f} | {m['mae']:.4f} |")

    report.append(f"\n## Best Model: **{'Ensemble' if models['ensemble']['r2'] > models['random_forest']['r2'] else 'Random Forest'}**")
    best = max(models.items(), key=lambda x: x[1]["r2"])
    report.append(f"- R²: **{best[1]['r2']:.4f}**")
    report.append(f"- This means the model explains **{best[1]['r2']*100:.1f}%** of yield variance")

    with open(os.path.join(REPORT_DIR, "model_performance.md"), "w") as f:
        f.write("\n".join(report))
    print("  ✓ Report: model_performance.md")


def main():
    print("=" * 60)
    print("TerraMind — Yield Prediction Model Training")
    print("=" * 60)

    df, encoders = load_and_prepare()
    X_train, y_train, X_test, y_test, feature_cols, test_df = temporal_split(df)
    models = train_models(X_train, y_train, X_test, y_test, feature_cols)
    plot_model_results(models, y_test, feature_cols, X_train, y_train)
    save_models(models, encoders)
    generate_model_report(models)

    print(f"\n✅ Yield prediction models trained and saved!")


if __name__ == "__main__":
    main()
