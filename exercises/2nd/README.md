# 2nd Exercise

This directory contains the second Advanced Computer Architecture exercise. The work focuses on memory hierarchy simulation with Intel PIN and SPEC CPU2006 benchmark inputs.

## Contents

- `assignment/`: assignment handout.
- `advcomparch-ex2-helpcode/`: provided helper code, SPEC benchmark payloads, and the cache simulator pintool.
- `scripts/`: automation scripts for running and summarizing experiments.
- `benchmarks/`: generated raw outputs, logs, CSV summaries, and diagrams.
- `report/`: final report source and compiled output.
- `decisions.md`: implementation and evaluation decisions kept while working through the assignment.
- `theory.md`: compact theory notes used to keep the report explanations consistent.

## Current Workflow

Build the simulator pintool:

```bash
cd exercises/2nd/advcomparch-ex2-helpcode/pintool
make
```

Run the section 4.2 L2-cache sweep from the repository root:

```bash
./exercises/2nd/scripts/run_4_2_l2_sweep.py
```

The runner uses `taskset` worker processes pinned to cores `0-7` by default, writes raw outputs and logs under `exercises/2nd/benchmarks/4.2/`, and emits progress as each benchmark/configuration finishes.
