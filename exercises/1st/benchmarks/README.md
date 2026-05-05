# Benchmark Results

This directory contains the generated outputs for the first exercise experiments.

## Layout

- `5.2/`: branch-instruction mix for train and ref inputs.
- `5.3/`: n-bit and 2-bit FSM branch-predictor comparisons.
- `5.4/`: BTB configuration study.
- `5.5/`: return-address-stack size study.
- `5.6.1/`: perceptron predictor sweep.
- `5.6.2/`: predictor-family comparison under a roughly 32K-bit budget.
- `5.7/`: ref-input validation for the selected predictors.
- `diagrams/`: plots generated from the CSV summaries and used by the report.

Each numbered directory stores raw pintool output, application logs, CSV summaries, and a readable `summary.txt` when applicable.

## Regeneration

Run the scripts from the repository root:

```bash
./exercises/1st/scripts/run_5_2_branch_stats.py --input both
./exercises/1st/scripts/run_5_3_predictors.py
./exercises/1st/scripts/run_5_4_btb.py
./exercises/1st/scripts/run_5_5_ras.py
./exercises/1st/scripts/run_5_6_1_perceptrons.py
./exercises/1st/scripts/run_5_6_2_predictors.py
./exercises/1st/scripts/run_5_7_ref_top3.py
```

Diagram images are generated from `diagrams/make_diagrams.py` after the summary CSV files exist.
