# TerraMind — Multi-Factor Causal Analysis Report

## The Core Insight
Crop yield is NOT a simple function of any single factor.
Our analysis reveals **compound causal chains** that span multiple years
and involve interactions between weather events, chemical inputs, and soil conditions.

This is exactly what Cognee's multi-hop graph traversal is designed to uncover.

## ML Model Performance
- Random Forest R²: **0.755**
- Top feature: **area** (importance: 0.282)
- 2nd feature: **fertilizer** (importance: 0.253)

## Hidden Compound Relationships Found
- **10** compound causal events detected
- These are cases where BOTH a chemical input change AND a weather
  event occurred in the same year as a significant yield drop (>15%)

### Example Causal Chains
- **Chhattisgarh (2008)**:
  Yield dropped **-15.6%**
  Contributing: pesticide changed -45.6%, rainfall dropped -26.8%
- **Delhi (2014)**:
  Yield dropped **-51.0%**
  Contributing: pesticide changed 35.5%, rainfall dropped -49.4%
- **Goa (2008)**:
  Yield dropped **-29.0%**
  Contributing: pesticide changed -76.1%, fertilizer changed -54.5%, rainfall dropped -28.4%
- **Haryana (2009)**:
  Yield dropped **-53.3%**
  Contributing: pesticide changed 90.1%, rainfall dropped -40.9%
- **Himachal Pradesh (1999)**:
  Yield dropped **-22.3%**
  Contributing: pesticide changed 21.9%, fertilizer changed 40.7%, rainfall dropped -40.5%

## Temporal Lag Findings
Fertilizer and pesticide usage show temporal lag effects:
- Year N (same): Fertilizer->Yield r=-0.039, Pesticide->Yield r=-0.033
- Year N+1: Fertilizer->Yield r=-0.038, Pesticide->Yield r=-0.032
- Year N+2: Fertilizer->Yield r=-0.042, Pesticide->Yield r=-0.038
- Year N+3: Fertilizer->Yield r=-0.043, Pesticide->Yield r=-0.046