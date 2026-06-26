# Exercise 3 - Synchronization and Coherence

This directory contains the third Advanced Computer Architecture exercise. The
work studies TAS, TTAS, and pthread mutex synchronization under cache
coherence using Sniper 8.0, McPAT, and real-machine measurements.

## Contents

- `assignment/`: official assignment handout.
- `advcomparch-ex3-helpcode/`: extracted helper code, implemented locks,
  configuration, McPAT helper, and build system.
- `docker/`: reproducible Sniper 8.0 image wrapper and compatibility fixes.
- `scripts/`: real-machine and Sniper experiment runners.
- `benchmarks/`: generated raw results, summaries, and diagrams.
- `report/`: final report source and compiled output.
- `theory.md`: synchronization and coherence theory notes.
- `decisions.md`: material implementation and evaluation decisions.

## Build

Build and validate all real-machine variants:

```bash
cd exercises/3rd/advcomparch-ex3-helpcode
make check-real TEST_THREADS=8 TEST_ITERATIONS=100000 TEST_GRAIN=1
```

Inside the Sniper container:

```bash
make sniper SNIPER_BASE_DIR=/root/sniper
```

See `scripts/README.md` for the experiment commands and output layout.

On the 16-physical/24-logical target laptop, start with:

```bash
./exercises/3rd/scripts/preflight_16core.py
./exercises/3rd/scripts/run_sniper_docker.sh build-image
./exercises/3rd/scripts/run_sniper_docker.sh smoke
```

Run the full matrices only after the smoke test passes:

```bash
./exercises/3rd/scripts/run_sniper_docker.sh run-4.1
./exercises/3rd/scripts/run_sniper_docker.sh run-4.2
./exercises/3rd/scripts/run_4_1_real_scalability.py \
  --iterations 50000000 \
  --repeats 5 \
  --warmups 1
```

Generate report diagrams after all summaries exist:

```bash
python3 exercises/3rd/benchmarks/diagrams/make_diagrams.py
```

## Results and Report

Completed Sniper and real-machine summaries are stored under `benchmarks/4.1/`
and `benchmarks/4.2/`. The plotting workflow writes report-ready PNG/PDF
figures under `benchmarks/diagrams/`. The final report source and compiled PDF
are stored under `report/`.
