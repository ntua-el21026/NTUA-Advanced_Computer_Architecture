# NTUA Advanced Computer Architecture

Three programming assignments for NTUA ECE's **Advanced Topics in Computer Architecture** course, by **Michail-Athanasios Peppas (03121026)**. The repository retains simulator implementations, experiment automation, raw outputs, plots, and the submitted May–June 2026 reports.

## Assignments

| Assignment | Implementation | Evidence and interpretation |
| --- | --- | --- |
| [1: Branch prediction](exercises/1st/README.md) | Intel PIN instruction/branch statistics; predictor comparisons, branch-target buffers, return-address stacks, and perceptron-based studies | [Section results](exercises/1st/benchmarks/) and [report](exercises/1st/report/); instrumentation-driven simulated predictor behavior |
| [2: Cache hierarchy](exercises/2nd/README.md) | Two-level cache pintool, L2 capacity/associativity/block-size sweeps, and LRU/MRU/Random/LFU/LIP/SRRIP comparisons | [Section results](exercises/2nd/benchmarks/) and [report](exercises/2nd/report/); modeled cache/IPC estimates |
| [3: Synchronization and coherence](exercises/3rd/README.md) | TAS/TTAS with compare-and-swap or test-and-set, plus pthread mutex; real-machine and Sniper 8.0/McPAT workflows | [Section results](exercises/3rd/benchmarks/) and [report](exercises/3rd/report/); separate measured host timing, simulated timing, and modeled power/energy |

The [exercise index](exercises/README.md) describes the common layout. Local `decisions.md` and `theory.md` files record modeling/measurement choices; [docs/](docs/README.md) contains course-level supporting material.

## Prerequisites and external inputs

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/ntua-el21026/ntua-advanced-computer-architecture.git
cd ntua-advanced-computer-architecture
```

A source-inspection clone can omit large LFS objects. Seven tracked soplex input paths are LFS pointers in such a checkout; they represent four distinct payloads, with identity/size recorded in each pointer. A pointer is not usable benchmark data. Preserve the existing LFS arrangement and obtain authorized payloads only when needed for an experiment.

Assignments 1–2 require Intel PIN, a compatible Linux compiler/toolchain, and the matching course-distributed SPEC CPU2006 executables/input classes. These tools and licensed data are not supplied by a Python package install. The pintool makefiles retain a historical default `PIN_ROOT`; override it with your actual PIN installation. The branch runners expose `--pin-root`, `--helpcode-dir`, and `--output-root`; the cache runners expose `--pin`, `--pintool`, and `--cores`. Read each runner's `--help` before execution.

Assignment 3's real-machine path needs Linux, GCC, GNU Make, pthreads, CPU-affinity support, and `timeout`. Its simulator path additionally needs Sniper 8.0 and McPAT; the existing [container scripts](exercises/3rd/scripts/README.md) describe the original Docker workflow. Docker is not needed for source inspection or the bounded real-machine check. Python analysis/plotting dependencies are local to the relevant scripts; there is no repository-wide environment lock.

## Build and bounded verification

For Assignment 1, an explicit PIN path avoids the original workstation default:

```bash
make -C exercises/1st/advcomparch-ex1-helpcode/pintool PIN_ROOT=/path/to/pin
```

Use the corresponding Assignment 2 pintool directory for its cache simulator. Section runners should be launched from the repository root; their default output roots point into the existing `benchmarks/` trees. Configure a separate output root where supported or use a disposable working copy for new runs.

The small lock-counter check builds and runs five real-machine variants without PIN, SPEC, Sniper, or McPAT:

```bash
make -C exercises/3rd/advcomparch-ex3-helpcode check-real \
  BIN_DIR=/tmp/ntua-lock-check \
  TEST_THREADS=2 TEST_ITERATIONS=1000 TEST_GRAIN=1
```

Choose a new writable `BIN_DIR` for each independent run. The program supports an allowed CPU list through `LOCKS_CPU_LIST` and otherwise chooses CPUs from its current affinity mask. The bounded check validates the final counter for its input; it does not reproduce scalability measurements. This documentation update inspected source, script options, and Makefile expansion. No executable correctness test, simulator run, container build, or benchmark was executed.

## Measurement scope

PIN branch/cache outputs describe the implemented models and workload traces. Sniper timing and McPAT power/energy are model-derived estimates; host real-machine lock timings are separate measurements. Do not compare those values as interchangeable observations. Historical CPU topology, core pinning, iterations, grain, compiler flags, and benchmark classes are part of each experiment's context.

CPU2006 is a retired workload suite. The stored measurements support workload/hardware-specific coursework conclusions, not general architectural superiority. Preserve raw outputs, reports, and seeds; record exact source/tool/configuration/input fingerprints and hardware for any new run.

## Attribution and licensing

The reports credit Michail-Athanasios Peppas. The tree also contains NTUA starter code, licensed benchmark payloads, third-party tools, teaching material, and papers, whose notices and rights remain separate. Original contributions are offered under [MIT](LICENSE) within the author's rights. [PUBLIC_RELEASE.md](docs/PUBLIC_RELEASE.md) explains SPEC/input restrictions and a non-destructive source-only export procedure; it does not authorize publication or change the repository's visibility.
