# Assignment 1 Helper Code

This directory contains the helper code and benchmark inputs used for the first exercise.

## Main Files

- `pintool/`: PIN pintool sources, predictor implementations, RAS support, and build files.
- `spec_execs_train_inputs/`: SPEC CPU2006 benchmark payloads for the train input set.
- `spec_execs_ref_inputs/`: SPEC CPU2006 benchmark payloads for the ref input set.
- `run_train_stats.sh` and `run_train_predictors.sh`: original helper scripts for train-input runs.
- `plot_mpki_ipc.py`: plotting helper from the assignment support code.

## Pintools

The assignment uses two main pintools:

- `cslab_branch_stats.cpp` for branch-category statistics.
- `cslab_branch.cpp` for direction predictors, BTB experiments, RAS experiments, and ref-input validation.

Build from the `pintool/` directory:

```bash
cd pintool
make PIN_ROOT=/path/to/pin
```

`PIN_ROOT` defaults to a historical absolute workstation path in `pintool/makefile`. Override it with the path to your actual Intel PIN kit, as shown above.

## Notes

The benchmark input directories are treated as assignment data and should be kept stable. The automation scripts in `../scripts/` run benchmarks from scratch copies by default so command redirections do not modify tracked SPEC outputs.
