# Section 5.6.1 Results

This directory contains the perceptron predictor parameter sweep for Exercise
1.

## Contents

- `summary.csv`: per-benchmark perceptron results.
- `summary_by_m.csv`: aggregate view grouped by table size.
- `summary_by_n.csv`: aggregate view grouped by history length.
- `summary_by_predictor.csv`: aggregate view by complete predictor
  configuration.
- `summary.txt`: human-readable summary.
- `train/`: raw train-input outputs.

## Regeneration

From the repository root:

```bash
./exercises/1st/scripts/run_5_6_1_perceptrons.py
```
