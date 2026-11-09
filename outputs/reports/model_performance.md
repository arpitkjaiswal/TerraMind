# TerraMind — Yield Prediction Model Report

## Training Strategy
- **Temporal split**: Train on 1997–2016, Test on 2017–2020
- **Purpose**: Predict future yields from historical data
- **Features**: 17 engineered features from 3 merged datasets

## Model Performance
| Model | R² | RMSE | MAE |
|---|---|---|---|
| Mean Baseline | -0.0011 | 14.4138 | 5.4791 |
| Random Forest | 0.6099 | 8.9980 | 1.5755 |
| Gradient Boosting | 0.6360 | 8.6911 | 2.0435 |
| Ensemble | 0.6317 | 8.7429 | 1.7223 |

## Best held-out score: **Gradient Boosting**
The test set is used for reporting, not hyperparameter tuning. Annual weather and input totals must be available at inference time; this is not a pre-season forecast.
Categorical vocabularies are fit on training years only; unseen test categories map to -1. Mixed-crop aggregate scores do not establish per-crop accuracy or causal effects.
- R²: **0.6360**
- This means the model explains **63.6%** of yield variance