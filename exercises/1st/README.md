# Exercise 1 - Branch Prediction

This directory contains the first Advanced Computer Architecture exercise. The
work focuses on branch-instruction analysis and branch-prediction experiments
using Intel PIN and SPEC CPU2006 benchmark inputs.

## Contents

- `assignment/`: assignment handout and supporting papers.
- `advcomparch-ex1-helpcode/`: provided helper code, SPEC benchmark inputs, and the modified pintools.
- `scripts/`: automation scripts for running each report section and producing summaries.
- `benchmarks/`: raw benchmark outputs, CSV summaries, text summaries, and generated diagrams.
- `report/`: LaTeX report source and compiled PDF.
- `decisions.md`: implementation and evaluation decisions kept while working through the assignment.
- `theory.md`: compact theory notes used to keep the report explanations consistent.

## Workflow

From the repository root, build the pintools with an explicit PIN installation:

```bash
make -C exercises/1st/advcomparch-ex1-helpcode/pintool PIN_ROOT=/path/to/pin
```

Run the section-specific automation from the repository root, for example:

```bash
./exercises/1st/scripts/run_5_2_branch_stats.py --input both
./exercises/1st/scripts/run_5_3_predictors.py
./exercises/1st/scripts/run_5_4_btb.py
./exercises/1st/scripts/run_5_5_ras.py
./exercises/1st/scripts/run_5_6_1_perceptrons.py
./exercises/1st/scripts/run_5_6_2_predictors.py
./exercises/1st/scripts/run_5_7_ref_top3.py
```

Generated benchmark data is stored under `benchmarks/`, and final report material is assembled under `report/`.

## Results and Report

The completed outputs are stored in `benchmarks/` by assignment section. The
report-ready figures are under `benchmarks/diagrams/`, and the final submitted
PDF is under `report/`.

## Runtime and evidence limits

PIN and authorized SPEC CPU2006 train/reference inputs must be available before running the scripts. Inspect `--pin-root`, `--helpcode-dir`, `--output-root`, and `--dry-run` in the selected runner. Paths default to the historical PIN distribution and benchmark tree. `--summarize-only` regenerates summaries and can overwrite stored evidence; use a copied output tree when reviewing existing results. The reported predictor behavior is simulated from instrumented executions, not a direct measurement of a physical CPU's branch predictor. See the [root guide](../../README.md) for attribution and input licensing.
