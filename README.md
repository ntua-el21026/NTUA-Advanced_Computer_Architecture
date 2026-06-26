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
