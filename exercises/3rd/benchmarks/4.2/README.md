# Section 4.2 Results

This directory contains the thread-topology Sniper experiments for Exercise 3.

## Parameters

- Implementations: `tas_cas`, `tas_ts`, `ttas_cas`, `ttas_ts`, `mutex`.
- Iterations: `1000`.
- Threads: `4`.
- Grain size: `1`.

## Topologies

- `share-all`: L2 shared by 4 cores, L3 shared by 4 cores.
- `share-l3`: private L2, L3 shared by 4 cores.
- `share-nothing`: private L2 and private L3.

## Files

- `summary.csv`: machine-readable parsed metrics.
- `summary.txt`: human-readable table.
- `raw/`: complete Sniper result directories for every topology and
  implementation.
