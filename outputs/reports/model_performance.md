# TerraMind — Yield Prediction Model Report

## Training Strategy
- **Temporal split**: Train on 1997–2016, Test on 2017–2020
- **Purpose**: Predict future yields from historical data
- **Features**: 17 engineered features from 3 merged datasets

## Model Performance
| Model | R² | RMSE | MAE |
|---|---|---|---|
| Random Forest | 0.6088 | 9.0098 | 1.7317 |
| Gradient Boosting | 0.6340 | 8.7157 | 1.9224 |
| Ensemble | 0.6302 | 8.7605 | 1.7348 |

## Best Model: **Ensemble**
- R²: **0.6340**
- This means the model explains **63.4%** of yield variance