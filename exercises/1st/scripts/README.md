# Automation Scripts

This directory contains Python automation for running the assignment experiments and summarizing results.

## Scripts

- `run_5_2_branch_stats.py`: branch mix for train and ref inputs.
- `run_5_3_predictors.py`: n-bit and alternative 2-bit predictor study.
- `run_5_4_btb.py`: BTB configuration study.
- `run_5_5_ras.py`: return-address-stack size study.
- `run_5_6_1_perceptrons.py`: perceptron parameter sweep.
- `run_5_6_2_predictors.py`: broader predictor comparison.
- `run_5_7_ref_top3.py`: ref-input validation of the selected predictors.

Run scripts from the repository root so relative paths resolve consistently:

```bash
./exercises/1st/scripts/run_5_2_branch_stats.py --input both
```

Most scripts run benchmarks from temporary scratch copies by default. This keeps SPEC command redirections from modifying tracked helper-code files.
