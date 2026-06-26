# Exercise 2 Helper Code

This directory contains the course-provided helper code and SPEC CPU2006
benchmark payloads used for the cache-hierarchy assignment.

## Layout

- `pintool/`: cache simulator pintool sources and build files.
- `spec_benchmarks/`: benchmark directories used by the automation scripts.
- `run_benchmarks.sh`: original helper script from the assignment bundle.

## Local Implementation

The key implementation work lives in `pintool/cache.h` and
`pintool/simulator.cpp`, where the cache model, replacement policies, and
statistics collection are implemented.

## Build

From the pintool directory:

```bash
cd pintool
make
```

The automation in `../scripts/` runs benchmarks from scratch copies so tracked
SPEC payload files remain stable.
