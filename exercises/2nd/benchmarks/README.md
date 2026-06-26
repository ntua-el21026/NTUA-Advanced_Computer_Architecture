# Exercise 2 Benchmark Results

This directory contains generated outputs for the second exercise.

## Layout

- `4.2/`: L2 cache capacity, associativity, and block-size sweep with LRU.
- `4.3/`: replacement-policy comparison over the best configurations selected
  from section 4.2.
- `diagrams/`: report-ready plots generated from the summary CSV files.

Each section directory keeps raw pintool outputs, logs, timing files, CSV
summaries, and a readable `summary.txt`.

## Regeneration

From the repository root:

```bash
./exercises/2nd/scripts/run_4_2_l2_sweep.py
./exercises/2nd/scripts/run_4_3_replacement_policies.py
python3 exercises/2nd/benchmarks/diagrams/make_diagrams.py
```

Run 4.3 after 4.2, because it uses the best 4.2 configurations as input.
