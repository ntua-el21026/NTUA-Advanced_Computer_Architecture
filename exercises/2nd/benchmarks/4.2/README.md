# Section 4.2 Results

This directory contains the L2 cache design-space sweep for Exercise 2.

## Contents

- `summary.csv`: per-benchmark results for every L2 configuration.
- `summary_by_benchmark.csv`: aggregate view grouped by benchmark.
- `summary_by_config.csv`: aggregate view grouped by cache configuration.
- `summary.txt`: human-readable summary.
- `logs/`: benchmark stdout/stderr logs.
- `times/`: timing information for each run.

## Regeneration

From the repository root:

```bash
./exercises/2nd/scripts/run_4_2_l2_sweep.py
```
