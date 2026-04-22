# Assignment 1 Decisions

This file records implementation and evaluation decisions for the first assignment, so the report and scripts stay consistent.

## General Workflow

- Work paragraph by paragraph.
- Keep this file updated with material decisions, but avoid turning it into a full run log.
- For each paragraph:
  1. Understand what the assignment asks.
  2. Decide whether implementation is needed.
  3. Implement only the required support code/scripts.
  4. Run the required benchmarks.
  5. Store raw outputs and summaries under `exercises/1st/benchmarks/`.

## Directory Layout

- Benchmark outputs live under:
  - `exercises/1st/benchmarks/`
- Diagrams will be generated later, after the benchmark text/CSV outputs exist, under:
  - `exercises/1st/benchmarks/diagrams/`
- Paragraph-specific outputs should use paragraph-numbered directories, for example:
  - `exercises/1st/benchmarks/5.2/`

## Local Setup And Git Hygiene

- Intel PIN is installed/extracted locally under `exercises/1st/`, but it is not committed.
- Pintool build outputs are local artifacts and are not committed.
- Local validation outputs from manual runs are ignored.
- The assignment helper SPEC benchmark input/output payloads are treated as data and preserved byte-for-byte with Git line-ending normalization disabled.
- Large `.mps` benchmark payloads are tracked with Git LFS.

## PIN / Pintool Build

- `PIN_ROOT` in `advcomparch-ex1-helpcode/pintool/makefile` points to the local PIN 4.2 directory:
  - `exercises/1st/pin-external-4.2-99776-g21d818fa2-gcc-linux`
- `PIN_WRAPPER_GCC := /usr/bin/gcc` is exported in the makefile to avoid recursive invocation of PIN's compiler wrapper on this machine.
- Verified compiled pintools:
  - `cslab_branch_stats.so`
  - `cslab_branch.so`

## 5.1 Metrics And Averages

- For sections 5.3-5.6, use the `train` inputs unless the assignment explicitly says otherwise.
- Main branch-predictor metric:
  - `directionMPKI = direction_mispredictions / total_instructions * 1000`
- Do not use geometric mean as the main average.
- Based on `CAL-2024-geomean.pdf`, geometric mean speedup lacks physical meaning; if speedup-like quantities are reported later, prefer harmonic-mean based speedup.
- For MPKI values, which are not speedups, report:
  - primary: arithmetic mean across benchmarks,
  - secondary: instruction-weighted / aggregate MPKI, computed as `sum(mispredictions) / sum(instructions) * 1000`.
- For later speedup-like comparisons, prefer:
  - primary: equal-work speedup (EWS),
  - optional: equal-time speedup (ETS),
  - avoid: geometric mean speedup.

## 5.2 Branch Instruction Analysis

- Use the provided `cslab_branch_stats.so` pintool.
- Run all 11 benchmarks for both input sets:
  - `spec_execs_train_inputs/`
  - `spec_execs_ref_inputs/`
- Store raw per-benchmark pintool output as `.txt` files.
- Also generate machine-readable `.csv` summaries for parsing and plotting.
- Recommended output layout:
  - `exercises/1st/benchmarks/5.2/train/raw/<benchmark>.txt`
  - `exercises/1st/benchmarks/5.2/ref/raw/<benchmark>.txt`
  - `exercises/1st/benchmarks/5.2/summary.txt`
  - `exercises/1st/benchmarks/5.2/summary.csv`
- For each benchmark and input set, record:
  - total instructions,
  - total branches,
  - conditional taken branches,
  - conditional not-taken branches,
  - unconditional branches,
  - calls,
  - returns.
- Compute percentages over total branches:
  - conditional taken percentage,
  - conditional not-taken percentage,
  - unconditional branch percentage,
  - call percentage,
  - return percentage.
- Also compute branch frequency:
  - `total_branches / total_instructions * 100`.

## 5.2 Automation

- Use `exercises/1st/scripts/run_5_2_branch_stats.py` to run and summarize section 5.2.
- The script runs benchmarks from temporary scratch copies by default, so SPEC command redirections do not modify tracked helper-code files.
- The script writes:
  - raw pintool `.txt` output per benchmark,
  - application stdout/stderr logs per benchmark,
  - `summary.csv` for machine processing,
  - `summary.txt` for quick inspection and report drafting.
- The full 5.2 benchmark sweep should be run with:
  - `./exercises/1st/scripts/run_5_2_branch_stats.py --input both`
- For reruns of already existing parseable outputs, use `--force`.

## 5.3 N-bit Predictors

- Use only the `train` inputs, as required by 5.1.
- Metric remains `directionMPKI = direction_mispredictions / total_instructions * 1000`.
- Existing `NbitPredictor` covers standard saturating up/down counters, but `cslab_branch.cpp` must be configured to instantiate the predictors required by 5.3.
- Section 5.3(ii) also needs a small custom 4-state FSM predictor for the non-standard alternatives in Table VI of Nair's "Optimal 2-Bit Branch Predictors".
- The Table VI first row, `ABACBDCD:3`, is the standard 2-bit saturating counter and is represented by `Nbit-16K-2`.
- Custom FSM entries start from state `A`, consistent with the zero-initialized n-bit predictors; Table VI ignores starting state.
- For fixed 32K-bit hardware in 5.3(iii), compare 7 predictors:
  - 1-bit saturating, 32K entries,
  - 2-bit saturating, 16K entries,
  - four non-standard 2-bit Table VI FSMs, 16K entries each,
  - 4-bit saturating, 8K entries.
- Use `exercises/1st/scripts/run_5_3_predictors.py` to run and summarize 5.3 once 5.2 has finished.

## 5.4 BTB Study

- Use only the `train` inputs, as required by 5.1.
- Treat `BTB entries` in the assignment table as total BTB capacity:
  - `BTB-512-2` means 512 total entries, 2-way associative, 256 sets.
- Implement the BTB as a cache-like structure:
  - index from the branch PC,
  - full branch PC match as the tag,
  - stored target address,
  - LRU replacement inside each set.
- Prediction convention:
  - BTB hit predicts `Taken` and uses the stored target,
  - BTB miss predicts `Not Taken`,
  - allocate/update BTB entries only when the real branch outcome is `Taken`.
- Evaluate the 8 assignment configurations:
  - `BTB-512-1`, `BTB-512-2`,
  - `BTB-256-2`, `BTB-256-4`,
  - `BTB-128-2`, `BTB-128-4`,
  - `BTB-64-4`, `BTB-64-8`.
- Report direction misses separately from target misses:
  - direction miss: wrong `Taken`/`Not Taken` decision,
  - target miss: direction was correctly predicted as `Taken`, but the stored target was wrong.
- Use `exercises/1st/scripts/run_5_4_btb.py` to run and summarize 5.4 once 5.2 and 5.3 have finished.

## 5.5 RAS Study

- Use only the `train` inputs, as required by 5.1.
- Use the provided RAS algorithm in `ras.h`:
  - on a call, push `call_ip + instruction_size`,
  - on a return, pop and compare against the actual return target.
- Add a dedicated `5.5` pintool mode that instantiates exactly the assignment sizes:
  - 4, 8, 16, 32, 48, 64 entries.
- Main metric:
  - `RAS miss rate = incorrect_returns / (correct_returns + incorrect_returns) * 100`.
- Also report `RAS miss MPKI = incorrect_returns / total_instructions * 1000` as a secondary normalized metric.
- Use `exercises/1st/scripts/run_5_5_ras.py` to run and summarize 5.5 after the current benchmark sweeps finish.
- The final RAS size should be chosen in the report after inspecting the miss-rate curve; prefer the smallest size near the point where larger stacks stop providing meaningful improvement.

## 5.6.1 Perceptrons

- Use only the `train` inputs, as required by 5.1.
- Use the provided `PerceptronPredictor` implementation in `branch_predictor.h`.
- Add a dedicated `5.6.1` pintool mode that instantiates all assignment configurations:
  - `M = 32, 512, 1024` perceptrons,
  - `n = 4, 8, 32, 60, 72` global-history bits.
- Name outputs as `Perceptron-M<M>-N<n>` so benchmark summaries can parse configurations reliably.
- Record the training threshold with each result:
  - `theta = floor(1.93 * n + 14)`.
- Main metric remains:
  - `directionMPKI = direction_mispredictions / total_instructions * 1000`.
- Use `exercises/1st/scripts/run_5_6_1_perceptrons.py` to run and summarize 5.6.1 after the currently running sweeps finish and the pintool is rebuilt.
