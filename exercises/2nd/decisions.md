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

## Section 4.3 Replacement Policy Study

- Implement replacement policies in the pintool so the policy can be selected at runtime with:
  - `-repl LRU`,
  - `-repl MRU`,
  - `-repl Random`,
  - `-repl LFU`,
  - `-repl LIP`,
  - `-repl SRRIP`.
- Use the same replacement policy in both L1 and L2 for each 4.3 simulation. This keeps one controlled variable: the policy applied by the cache hierarchy.
- Keep LRU in the 4.3 runner as a rerun baseline, even though section 4.2 already used LRU. This gives a clean same-script comparison against the new policies.
- Random replacement uses deterministic seed `21026`, the last five digits of AM `03121026`.
- LFU starts a newly inserted block with use count `1`; on a hit, the count increments by `1`; ties are resolved by the earliest matching block in the set.
- LIP keeps the same hit behavior as LRU, but inserts missed blocks at the LRU position instead of the MRU position.
- SRRIP uses static RRIP with hit priority:
  - each block stores an RRPV counter,
  - counter width is `n` bits where `n` is the cache associativity,
  - new blocks are inserted with RRPV `max - 1`,
  - hits set RRPV to `0`,
  - replacement searches for RRPV `max`; if none exists, it increments all non-maximum counters until a victim appears.
- Section 4.3 outputs use:
  - `exercises/2nd/benchmarks/4.3/raw/<policy>/<benchmark>/<config>.out`
  - `exercises/2nd/benchmarks/4.3/logs/<policy>/<benchmark>/<config>.stdout.txt`
  - `exercises/2nd/benchmarks/4.3/logs/<policy>/<benchmark>/<config>.stderr.txt`
  - `exercises/2nd/benchmarks/4.3/times/<policy>/<benchmark>/<config>.time.txt`
  - `exercises/2nd/benchmarks/4.3/summary.csv`
  - `exercises/2nd/benchmarks/4.3/summary_by_policy.csv`
  - `exercises/2nd/benchmarks/4.3/summary_by_config_policy.csv`
  - `exercises/2nd/benchmarks/4.3/summary_best_policy_by_config.csv`
  - `exercises/2nd/benchmarks/4.3/summary.txt`
- The section 4.3 runner selects the four L2 configurations automatically from `exercises/2nd/benchmarks/4.2/summary_by_config.csv`, choosing the best row per L2 capacity by `aggregate_ipc`.
- Manual selection remains available with `--selected-configs` for debugging or if the final 4.2 choice is adjusted during report writing.
- Use `taskset` worker processes pinned to cores `0-7`, following the same execution model as section 4.2.
