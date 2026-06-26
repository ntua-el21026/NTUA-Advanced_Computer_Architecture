# Section 4.1 Results

This directory contains the scalability experiments for Exercise 3.

## Layout

- `sniper/`: 75 Sniper simulations for five implementations, five thread
  counts, and three grain sizes.
- `real/`: 75 real-machine summary cases and 375 raw repeated measurements.

## Sniper Parameters

- Implementations: `tas_cas`, `tas_ts`, `ttas_cas`, `ttas_ts`, `mutex`.
- Iterations: `1000`.
- Threads: `1,2,4,8,16`.
- Grain sizes: `1,10,100`.
- Cache sharing follows the assignment topology table.

## Real-Machine Parameters

- Implementations, thread counts, and grain sizes match the Sniper matrix.
- Iterations: `50000000`.
- Repeats: `5`.
- Threads are pinned to physical-core representatives recorded in
  `real/machine.json`.

The real-machine iteration count is a practical runtime compromise. The
fastest one-thread, grain-size-1 medians are below one second, while all other
summary medians are at least one second.
