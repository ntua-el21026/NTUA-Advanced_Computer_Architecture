# Exercise 1 Pintools

This directory contains the Intel PIN pintool sources used by Exercise 1.

## Main Files

- `cslab_branch_stats.cpp`: branch-category statistics collector.
- `cslab_branch.cpp`: branch predictor, BTB, RAS, and ref-validation
  experiment pintool.
- `branch_predictor.h`: local predictor implementations used by the
  assignment sections.
- `ras.h`: return-address-stack model.
- `pentium_m_predictor/`: provided Pentium-M predictor components.
- `makefile` and `makefile.rules`: PIN build integration.

## Build

From this directory:

```bash
make
```

The makefile expects the local Intel PIN kit at the path configured by
`PIN_ROOT`.
