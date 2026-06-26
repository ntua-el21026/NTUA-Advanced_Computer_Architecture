# Exercise 1 Diagrams

This directory contains report-ready plots generated from the Exercise 1
benchmark summaries. Each figure is stored as both PNG and PDF so it can be
viewed quickly and included cleanly in LaTeX.

## Generator

- `make_diagrams.py`: reads CSV summaries from `../5.2/` through `../5.7/` and
  regenerates all plots.

## Regeneration

After the section summaries exist, run from the repository root:

```bash
python3 exercises/1st/benchmarks/diagrams/make_diagrams.py
```

The script requires `matplotlib` and `numpy`.
