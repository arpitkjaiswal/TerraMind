# TerraMind — Demo Query Results

Generated: 2026-07-05T22:50:56.874364

## demo-query-001: Why did Field B's yield drop by 30% in 2025?

**Confidence**: unconfirmed_hypothesis (0.25)
**Graph Hops**: 0

**Expected Insight**: Traces to combination of heavy Chlorpyrifos 20EC application in Kharif 2024 and severe drought in 2025. Soil pH had been declining from repeated Ammonium Sulphate use.


## demo-query-002: What is the relationship between pesticide use in 2024 and crop failure in 2025?

**Confidence**: statistical_association (0.55)
**Graph Hops**: 0

**Expected Insight**: High-dose Chlorpyrifos (2000-3000 ml/ha) in 2024 Kharif damaged soil microbiome, which combined with 2025 drought reduced the soil's water retention capacity.

**Evidence Trail**:
- [APPLIED_TO] node-00183 → node-00007 (hop 0)
- [CORRELATED_WITH] node-00183 → node-00675 (hop 0)
- [APPLIED_TO] node-00203 → node-00008 (hop 0)
- [CORRELATED_WITH] node-00203 → node-00679 (hop 0)
- [APPLIED_TO] node-00204 → node-00008 (hop 0)

## demo-query-003: Why is soil pH declining in Field B (plot-001b)?

**Confidence**: statistical_association (0.55)
**Graph Hops**: 1

**Expected Insight**: Repeated application of Ammonium Sulphate (120-180 kg/ha) across 2020-2026 without lime application caused progressive pH decline from ~6.2 to ~5.2.

**Evidence Trail**:
- [APPLIED_TO] node-00878 → node-00007 (hop 0)
- [APPLIED_TO] node-00879 → node-00007 (hop 0)
- [APPLIED_TO] node-00880 → node-00007 (hop 0)
- [APPLIED_TO] node-00881 → node-00007 (hop 0)
- [CONTAINS] node-00007 → node-00001 (hop 1)

## demo-query-004: What caused the cotton yield crash in Farm 4 (Vidarbha)?

**Confidence**: unconfirmed_hypothesis (0.25)
**Graph Hops**: 0

**Expected Insight**: 2026 heatwave (48°C, 18 days) combined with 2025 fertilizer reduction (-60%) and excessive pesticide use created a compound crisis.


## demo-query-005: Which plots are most at risk for yield decline next season?

**Confidence**: statistical_association (0.55)
**Graph Hops**: 0

**Expected Insight**: Plots with declining soil health (pH drop), increasing chemical dependency, and exposure to climate volatility are highest risk.

**Evidence Trail**:
- [PRODUCED] node-00664 → node-00006 (hop 0)
- [PRECEDED] node-00664 → node-00665 (hop 0)
- [CORRELATED_WITH] node-00664 → node-00128 (hop 0)
- [CORRELATED_WITH] node-00664 → node-00129 (hop 0)
- [CORRELATED_WITH] node-00664 → node-00130 (hop 0)

## demo-query-006: How did the 2024 flood affect Block 1 in Farm 2?

**Confidence**: statistical_association (0.55)
**Graph Hops**: 1

**Expected Insight**: Moderate flooding (180mm in 5 days) caused rice paddy submersion for 8 days, leading to root rot and 25% yield reduction.

**Evidence Trail**:
- [OCCURRED_DURING] node-00045 → node-00009 (hop 0)
- [CORRELATED_WITH] node-00045 → node-00689 (hop 0)
- [OCCURRED_DURING] node-00046 → node-00009 (hop 0)
- [CORRELATED_WITH] node-00046 → node-00689 (hop 0)
- [CONTAINS] node-00009 → node-00002 (hop 1)

## demo-query-007: What is the long-term trend of fertilizer effectiveness?

**Confidence**: statistical_association (0.55)
**Graph Hops**: 0

**Expected Insight**: Lag analysis shows fertilizer-yield correlation weakening over time (r=0.15 at lag-0 to r=0.08 at lag-2), suggesting diminishing returns from increasing application rates.

**Evidence Trail**:
- [APPLIED_TO] node-00128 → node-00006 (hop 0)
- [CORRELATED_WITH] node-00128 → node-00664 (hop 0)
- [APPLIED_TO] node-00129 → node-00006 (hop 0)
- [CORRELATED_WITH] node-00129 → node-00664 (hop 0)
- [APPLIED_TO] node-00130 → node-00006 (hop 0)

## demo-query-008: Are there recurring weather patterns that precede yield drops?

**Confidence**: statistical_association (0.55)
**Graph Hops**: 0

**Expected Insight**: Drought events followed by excess rain in consecutive years show the strongest correlation with yield crashes (pattern found in 5+ states).

**Evidence Trail**:
- [OCCURRED_DURING] node-00021 → node-00006 (hop 0)
- [CORRELATED_WITH] node-00021 → node-00664 (hop 0)
- [OCCURRED_DURING] node-00022 → node-00006 (hop 0)
- [CORRELATED_WITH] node-00022 → node-00664 (hop 0)
- [OCCURRED_DURING] node-00023 → node-00006 (hop 0)

## demo-query-009: How do soil nutrients interact with weather to affect Rice yields?

**Confidence**: unconfirmed_hypothesis (0.25)
**Graph Hops**: 0

**Expected Insight**: Low soil phosphorus (<25 kg/ha) combined with below-average rainfall creates compounding stress. States with higher NPK totals show more resilience to drought.


## demo-query-010: What is the optimal fertilizer-pesticide balance for wheat in Punjab?

**Confidence**: unconfirmed_hypothesis (0.25)
**Graph Hops**: 0

**Expected Insight**: Historical data shows peak wheat yields at 100-120 kg/ha fertilizer and minimal pesticide (<500 ml/ha). Over-application of either shows negative returns.

