# Section 5.6.2 Results

This directory contains the predictor-family comparison under a roughly
32K-bit budget for Exercise 1.

## Contents

- `summary.csv`: per-benchmark predictor-family results.
- `summary_by_family.csv`: aggregate view by predictor family.
- `summary_by_predictor.csv`: aggregate view by predictor configuration.
- `summary.txt`: human-readable summary.
- `train/`: raw train-input outputs.

## Regeneration

From the repository root:

```bash
./exercises/1st/scripts/run_5_6_2_predictors.py
```
