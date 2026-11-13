# Code-only public release preparation

The working evidence repository includes course-distributed SPEC CPU2006 executables and reference/train inputs. Distribution through a course establishes provenance, not public redistribution rights. The [SPEC CPU2006 legal notice](https://www.spec.org/cpu2006/docs/legal.html) describes benchmark-suite licensing. Original MIT contributions do not relicense SPEC, Intel PIN, Sniper, McPAT or course materials.

## Non-destructive route

1. Preserve this source/evidence repository and its hashes in access-controlled storage. Do not delete payloads, rewrite history, or publish this full history as a shortcut to a code-only release.
2. Construct a fresh export outside this repository from an explicit, reviewed source-file allowlist. Exclude `.git`, LFS payload/pointer files, binaries, archives, datasets, lectures, assignment handouts and benchmark input trees. Retain required copyright/license notices with adapted source. Generate a new manifest for that concrete export listing exact relative paths, sizes, SHA-256 values, and exclusions. No temporary manifest from an earlier preparation workspace is required or assumed to exist.
3. Review ownership/notices for the selected helper-code adaptations and automation. Add applicable notices and describe the assignment/starter provenance; do not label all files solely authored by the report author.
4. Use fresh release metadata and obtain the user's publication authorization for the concrete export. This preparation does not publish, change visibility, or modify remote history.

## Required external licensed inputs

The default excluded trees are:

- `exercises/1st/advcomparch-ex1-helpcode/spec_execs_ref_inputs/`
- `exercises/1st/advcomparch-ex1-helpcode/spec_execs_train_inputs/`
- `exercises/2nd/advcomparch-ex2-helpcode/spec_benchmarks/`

Licensed users must obtain the benchmark suite/input classes through their authorized source, then supply the matching tree in private local storage. Match the executable/input versions used by the historical report; do not replace them with arbitrary downloads or claim exact replay from a benchmark name. Inspect runner paths and configure local roots before execution. Version and license Intel PIN, Sniper 8.0 and McPAT separately. The real-machine lock check documented in the root README needs none of these benchmark payloads.

Raw benchmark outputs, reports and diagrams remain preserved in the evidence repository. A public source-only export excludes them by default pending individual rights/content review, so it cannot itself reproduce historical numerical results. A later reviewed results package may reference fingerprints and methodology without redistributing licensed inputs.
