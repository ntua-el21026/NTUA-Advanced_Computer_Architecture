# Exercise 2 Diagrams

This directory contains report-ready plots generated from the Exercise 2
benchmark summaries. Each chart is stored as both PNG and PDF.

## Generator

- `make_diagrams.py`: reads summaries from `../4.2/` and `../4.3/` and
  regenerates all figures.

## Regeneration

After the summary CSV files exist, run from the repository root:

```bash
python3 exercises/2nd/benchmarks/diagrams/make_diagrams.py
```

The script requires `matplotlib` and `numpy`.
