# Yield regression model card

## Intended use

Research on historical Indian state-level crop yields with accompanying annual
weather and soil measurements. This model is not integrated into the dashboard,
validated for individual farms, or suitable for chemical recommendations.

## Evaluation protocol

The pipeline merges three repository CSVs, drops rows with yield >=500, and
engineers 17 features. The resulting 19,524 rows split by year: 16,299 training
rows through 2016 and 3,225 held-out rows after 2016 (through 2020). Crop, season,
and state vocabularies are fit on training years only. Unknown future values use
-1. Yield and production are excluded from features. All estimators use seed 42;
Random Forest uses at most four CPU workers.

The test set reports performance; it is not a hyperparameter tuning set. The
mean regressor baseline is fit on training targets. Gradient Boosting has the
highest observed R² (0.6360); Random Forest has the lowest MAE (1.5755). Reporting
both avoids hiding the tradeoff between large errors and typical absolute error.
The ensemble is an unweighted mean, not automatically the best model.

See `outputs/reports/model_metrics.json` for all metrics. The reported run uses
Python 3.12 and the installed scikit-learn implementation; numerical results can
vary across dependency releases. Current training artifacts are written to
`TERRAMIND_OUTPUT_DIR`; committed older joblib files are historical and should
not be assumed to match this report.

## Limitations

- Annual weather and fertilizer totals may only be known after the season.
  A prospective forecast requires features available at the forecast date.
- Static state-level soil measurements do not capture within-state variation or
  historical changes in soil conditions.
- The yield <500 filter removes part of the target distribution. Reported scores
  apply to the filtered sample only.
- Crop units/scales may differ. Aggregate RMSE and R² can hide weak performance
  on particular crops, states, and rare categories.
- Inner joins can exclude underrepresented state/year combinations.
- No uncertainty calibration, prospective deployment evaluation, or external
  validation has been performed. Feature importance does not establish causes.

## Next experiments

Use rolling-year validation within the training period for tuning, compare
crop-specific baselines and per-crop errors, audit units and missingness, and
reserve a new untouched holdout before claiming improvements from tuning.
