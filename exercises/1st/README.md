# 1st Exercise

This directory contains the first Advanced Computer Architecture exercise. The work focuses on branch-instruction analysis and branch-prediction experiments using Intel PIN and SPEC CPU2006 benchmark inputs.

## Contents

- `assignment/`: assignment handout and supporting papers.
- `advcomparch-ex1-helpcode/`: provided helper code, SPEC benchmark inputs, and the modified pintools.
- `scripts/`: automation scripts for running each report section and producing summaries.
- `benchmarks/`: raw benchmark outputs, CSV summaries, text summaries, and generated diagrams.
- `report/`: LaTeX report source and compiled PDF.
- `image/`: reserved image assets for theory notes or report material outside the generated benchmark diagrams.
- `decisions.md`: implementation and evaluation decisions kept while working through the assignment.
- `theory.md`: compact theory notes used to keep the report explanations consistent.

## Workflow

Build the pintools from the helper-code directory:

```bash
cd advcomparch-ex1-helpcode/pintool
make
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
