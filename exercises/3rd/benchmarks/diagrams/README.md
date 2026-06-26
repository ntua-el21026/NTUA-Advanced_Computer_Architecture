# Exercise 3 Diagrams

This directory contains report-ready figures for Exercise 3. Each chart is
stored as both PNG and PDF.

## Generator

- `make_diagrams.py`: validates the Exercise 3 summary CSV files and
  regenerates all figures.

## Required Assignment Figures

- `4_1_sniper_cycles_grain_*.{png,pdf}`: Sniper cycles versus thread count for
  each grain size.
- `4_1_real_runtime_grain_*.{png,pdf}`: real-machine median runtime versus
  thread count for each grain size.
- `4_2_topology_cycles.{png,pdf}`: topology comparison in cycles.

## Additional Report Figures

The directory also includes energy, EDP, ED2P, normalized scaling,
measurement-variability, topology-normalization, and host-CPU-mapping figures.

## Regeneration

After all summaries exist, run from the repository root:

```bash
python3 exercises/3rd/benchmarks/diagrams/make_diagrams.py
```

The script requires `matplotlib` and `numpy`.
