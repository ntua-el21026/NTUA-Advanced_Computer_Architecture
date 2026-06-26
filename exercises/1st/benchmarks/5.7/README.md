# Section 5.7 Results

This directory contains the ref-input validation for selected Exercise 1
predictors.

## Contents

- `summary.csv`: ref-input results for the selected predictors.
- `summary_by_predictor.csv`: aggregate ref-input view by predictor.
- `train_vs_ref_by_benchmark.csv`: train/ref comparison by benchmark.
- `train_vs_ref_by_predictor.csv`: train/ref comparison by predictor.
- `summary.txt`: human-readable summary.
- `ref/`: raw ref-input outputs.

## Regeneration

From the repository root:

```bash
./exercises/1st/scripts/run_5_7_ref_top3.py
```
