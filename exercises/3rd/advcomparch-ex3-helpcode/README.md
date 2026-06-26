# Exercise 3 Helper Code

This directory contains the synchronization benchmark, Sniper configuration,
McPAT helper, and build system used by Exercise 3.

## Main Files

- `locks_scalability.c`: pthread benchmark that executes a protected critical
  section under real-machine timing or Sniper ROI measurement.
- `lock.h`: TAS and TTAS spin-lock implementations.
- `ask3.cfg`: Sniper configuration used by sections 4.1 and 4.2.
- `advcomparch_mcpat.py`: assignment-provided McPAT helper script.
- `Makefile`: builds the five real-machine binaries and five Sniper binaries.
- `bin/`: generated binaries when locally built; ignored by Git.

## Implemented Lock Variants

- `tas_cas`: TAS using `__sync_val_compare_and_swap`.
- `tas_ts`: TAS using `__sync_lock_test_and_set`.
- `ttas_cas`: TTAS with read spinning followed by compare-and-swap.
- `ttas_ts`: TTAS with read spinning followed by test-and-set.
- `mutex`: pthread mutex baseline.

Every run validates the protected counter against `nthreads * iterations` and
prints `Validation: PASS` on success.

## Build

Build and validate real-machine binaries:

```bash
make check-real TEST_THREADS=16 TEST_ITERATIONS=100000 TEST_GRAIN=1
```

Build Sniper binaries inside the Sniper container environment:

```bash
make sniper SNIPER_BASE_DIR=/root/sniper
```

Remove generated binaries:

```bash
make clean
```
