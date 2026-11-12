# NTUA Advanced Computer Architecture

Coursework repository for the NTUA ECE course "Advanced Topics in Computer
Architecture" by student `03121026`.

The repository keeps the three programming assignments, their automation
scripts, measured outputs, generated diagrams, and final reports in one
reproducible layout.

## Repository Layout

- `docs/`: lecture slides and repository-structure utilities.
- `exercises/1st/`: branch-instruction analysis and branch-prediction studies
  with Intel PIN and SPEC CPU2006 inputs.
- `exercises/2nd/`: cache-hierarchy simulation, L2 cache design-space
  exploration, and replacement-policy evaluation.
- `exercises/3rd/`: TAS/TTAS/pthread mutex synchronization experiments with
  Sniper 8.0, McPAT, Docker, and real-machine measurements.

Each exercise follows the same high-level structure:

- `assignment/`: official handout and any reference material.
- `advcomparch-*-helpcode/`: assignment helper code plus local
  implementations.
- `scripts/`: reproducible experiment automation.
- `benchmarks/`: raw outputs, summaries, and generated diagrams.
- `report/`: LaTeX source and compiled PDF.
- `decisions.md`: implementation and measurement decisions.
- `theory.md`: concise notes used while writing the report.

## Reproducibility Notes

The benchmark payloads are course-provided data and should be treated as
stable inputs. Generated binaries and local scratch directories are ignored by
Git. Large or binary artifacts such as PDFs, plots, and selected benchmark
payloads are tracked according to `.gitattributes`.

Run automation from the repository root unless a README explicitly says
otherwise. This keeps relative paths stable and makes the generated summaries
land in the expected `benchmarks/` directories.

## Portfolio status and attribution

The three submitted reports credit Michail-Athanasios Peppas (03121026), May–June 2026. The repository combines original implementations/automation, course starter code and third-party tools/inputs. Preserve local starter notices; report authorship does not grant ownership of the benchmark suite or simulators.

This is a strong conditional public systems showcase. A code-only public release can retain reviewed original source and automation while excluding licensed benchmark payloads. The complete local repository retains all original benchmark evidence; see [PUBLIC_RELEASE.md](docs/PUBLIC_RELEASE.md) for the non-destructive release procedure and required inputs.

## Setup and bounded verification

For code inspection, clone without fetching LFS payloads. Python plotting/analysis dependencies, Intel PIN, Sniper 8.0 and McPAT belong to their respective exercise workflows; there is no repository-wide environment lock. Use each exercise README and record tool/source versions, compiler flags, affinity, topology and package versions. Course-provided paths and the original machine's core counts need adjustment in local configuration before running a matrix.

The real-machine synchronization check needs only a Linux C compiler, make, pthreads and `timeout`, without SPEC, PIN or Sniper:

```bash
cd exercises/3rd/advcomparch-ex3-helpcode
make check-real TEST_THREADS=2 TEST_ITERATIONS=1000 TEST_GRAIN=1
```

Use a separate `BIN_DIR` if preserving the working tree's build products. This small counter-correctness smoke check validates five lock variants on its bounded input; it is not a scalability benchmark or a rerun of reported measurements.

The historical plots and reports distinguish PIN/Sniper simulation estimates from real-machine timing. Preserve the original raw results and seeds. CPU2006 is a retired workload suite, and results are workload/hardware-specific; these experiments do not establish general architectural superiority. No simulator matrix or historical performance run was repeated in preparation.
