# Assignment 2 Decisions

This file records implementation and evaluation decisions for the second assignment, so the report and scripts stay consistent.

## General Workflow

- Work section by section.
- Keep this file updated with material decisions, but avoid turning it into a full run log.
- For each section:
  1. Understand what the assignment asks.
  2. Decide whether simulator implementation changes are needed.
  3. Implement only the required support code/scripts.
  4. Run the required benchmarks.
  5. Store raw outputs and summaries under `exercises/2nd/benchmarks/`.

## Directory Layout

- Benchmark outputs live under:
  - `exercises/2nd/benchmarks/`
- Section-specific outputs use section-numbered directories, for example:
  - `exercises/2nd/benchmarks/4.2/`
- Section 4.2 outputs use:
  - `exercises/2nd/benchmarks/4.2/raw/<benchmark>/<config>.out`
  - `exercises/2nd/benchmarks/4.2/logs/<benchmark>/<config>.stdout.txt`
  - `exercises/2nd/benchmarks/4.2/logs/<benchmark>/<config>.stderr.txt`
  - `exercises/2nd/benchmarks/4.2/times/<benchmark>/<config>.time.txt`
  - `exercises/2nd/benchmarks/4.2/summary.csv`
  - `exercises/2nd/benchmarks/4.2/summary_by_config.csv`
  - `exercises/2nd/benchmarks/4.2/summary_by_benchmark.csv`
  - `exercises/2nd/benchmarks/4.2/summary.txt`

## Local Setup And Git Hygiene

- Reuse the Intel PIN 4.2 kit already installed for exercise 1:
  - `exercises/1st/pin-external-4.2-99776-g21d818fa2-gcc-linux`
- Pintool build outputs are local artifacts and are not committed.
- Smoke outputs, scratch copies, and partial benchmark run directories are ignored.
- The assignment helper SPEC benchmark payloads are treated as data and preserved byte-for-byte with Git line-ending normalization disabled.
- Large `.mps` benchmark payloads are tracked with Git LFS.

## PIN / Pintool Build

- `PIN_ROOT` in `advcomparch-ex2-helpcode/pintool/makefile` points to the local PIN 4.2 directory from exercise 1.
- `PIN_WRAPPER_GCC := /usr/bin/gcc` is exported in the makefile to avoid recursive invocation of PIN's compiler wrapper on this machine.
- The simulator was adjusted to use the assignment latency model:
  - L1 hit: 1 cycle,
  - L2 hit: 10 cycles,
  - main memory access: 200 cycles.
- Verified compiled pintool:
  - `simulator.so`

## Section 4.2 L2 Cache Study

- Use the fixed L1 required by the assignment:
  - 32 KB,
  - 4-way,
  - 32 B block size.
- Use LRU replacement for section 4.2. The replacement-policy comparison belongs to section 4.3.
- Evaluate all required L2 configurations:
  - 256 KB, 4-way, blocks 64/128/256 B,
  - 512 KB, 4/8/16-way, blocks 64/128/256 B,
  - 1024 KB, 8/16-way, blocks 64/128/256 B,
  - 2048 KB, 16-way, blocks 64/128/256 B.
- This gives 21 L2 configurations and 147 total benchmark runs.
- Main metric:
  - `IPC = total_instructions / total_cycles`.
- Supporting metrics:
  - L1 miss rate,
  - L2 miss rate,
  - L1 MPKI,
  - L2 MPKI.
- Treat L2 misses as main-memory accesses for this simulator.
- Run benchmarks from temporary scratch copies by default, so benchmark redirections do not modify tracked helper-code files.
- Use `taskset` to pin worker processes to cores `0-7`.
- The section 4.2 runner uses one worker per listed core. Each worker executes one benchmark/configuration process at a time and reports progress when each run finishes.
- Use `exercises/2nd/scripts/run_4_2_l2_sweep.py` to run and summarize section 4.2.
- The script does not select final report conclusions automatically. It writes summaries that make the per-capacity choice and parameter-impact discussion straightforward.
