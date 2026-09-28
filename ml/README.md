# /ml — Intelligence Layer

Demand forecasting & Outbreak detection:
- Baselines: Seasonal Naive + Croston's SBA for intermittent items
- Main model: LightGBM with quantile loss (P10/P50/P90)
- Censored demand correction & Tobit-style imputation
- Hierarchical reconciliation (facility -> district -> country MinT/bottom-up)
- CUSUM 3σ outbreak radar
- Stock-out early warning engine (days remaining, risk scoring)
