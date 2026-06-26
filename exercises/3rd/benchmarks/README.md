# Exercise 3 Benchmark Results

This directory contains generated outputs for the synchronization and
coherence experiments.

## Layout

- `4.1/`: scalability experiments for Sniper and the real machine.
- `4.2/`: Sniper thread-topology experiments.
- `diagrams/`: report-ready plots generated from the summary CSV files.

The raw Sniper result directories preserve `sim.out`, `sim.cfg`, `sim.info`,
`sim.stats.sqlite3`, command logs, return codes, and McPAT outputs. The
real-machine raw directories preserve per-repeat stdout/stderr logs.

## Regeneration

From the repository root, after preflight and Sniper smoke validation:

```bash
./exercises/3rd/scripts/run_sniper_docker.sh run-4.1
./exercises/3rd/scripts/run_sniper_docker.sh run-4.2
./exercises/3rd/scripts/run_4_1_real_scalability.py \
  --iterations 50000000 \
  --repeats 5 \
  --warmups 1
python3 exercises/3rd/benchmarks/diagrams/make_diagrams.py
```

Do not start the full Sniper matrices until `run_sniper_docker.sh smoke`
completes successfully.
