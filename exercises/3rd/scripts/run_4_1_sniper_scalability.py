#!/usr/bin/env python3
"""Run and summarize Assignment 3 section 4.1 Sniper scalability experiments."""

from __future__ import annotations

import argparse
import concurrent.futures
import subprocess
import sys
from pathlib import Path

from exercise3_common import (
    SNIPER_SUMMARY_FIELDS,
    SniperRunSpec,
    parse_implementations,
    parse_int_list,
    parse_sniper_metrics,
    repo_root_from_script,
    run_sniper_spec,
    shell_join,
    sniper_binary,
    sniper_summary_row,
    write_csv,
)


DEFAULT_THREAD_COUNTS = [1, 2, 4, 8, 16]
DEFAULT_GRAIN_SIZES = [1, 10, 100]
SHARING_BY_THREADS = {
    1: (1, 1),
    2: (2, 2),
    4: (4, 4),
    8: (4, 8),
    16: (1, 8),
}


def sharing_for_threads(nthreads: int) -> tuple[int, int]:
    if nthreads not in SHARING_BY_THREADS:
        raise ValueError(
            f"no assignment topology is defined for {nthreads} threads; "
            f"valid values: {', '.join(map(str, SHARING_BY_THREADS))}"
        )
    return SHARING_BY_THREADS[nthreads]


def discover_specs(
    output_root: Path,
    implementations: list[str],
    thread_counts: list[int],
    grain_sizes: list[int],
    iterations: int,
) -> list[SniperRunSpec]:
    specs: list[SniperRunSpec] = []
    for grain in grain_sizes:
        for nthreads in thread_counts:
            l2_shared, l3_shared = sharing_for_threads(nthreads)
            for implementation in implementations:
                specs.append(
                    SniperRunSpec(
                        implementation=implementation,
                        nthreads=nthreads,
                        iterations=iterations,
                        grain=grain,
                        l2_shared_cores=l2_shared,
                        l3_shared_cores=l3_shared,
                        result_dir=(
                            output_root
                            / "raw"
                            / implementation
                            / f"threads_{nthreads}"
                            / f"grain_{grain}"
                        ),
                        topology="scalability",
                    )
                )
    return specs


def write_summaries(specs: list[SniperRunSpec], output_root: Path) -> tuple[int, int]:
    rows: list[dict[str, str]] = []
    missing: list[SniperRunSpec] = []
    for spec in specs:
        metrics = parse_sniper_metrics(
            spec.result_dir, spec.nthreads * spec.iterations
        )
        if metrics is None:
            missing.append(spec)
        else:
            rows.append(sniper_summary_row(spec, metrics))

    rows.sort(
        key=lambda row: (
            int(row["grain"]),
            int(row["nthreads"]),
            row["implementation"],
        )
    )
    write_csv(output_root / "summary.csv", SNIPER_SUMMARY_FIELDS, rows)

    txt_path = output_root / "summary.txt"
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    with txt_path.open("w", encoding="utf-8") as handle:
        handle.write("Assignment 3 - Section 4.1 Sniper Scalability\n")
        handle.write(f"Expected outputs: {len(specs)}\n")
        handle.write(f"Parsed outputs: {len(rows)}\n")
        handle.write(f"Missing/unparseable outputs: {len(missing)}\n\n")

        for grain in sorted({spec.grain for spec in specs}):
            handle.write(f"Grain size {grain}\n")
            handle.write(
                f"{'Threads':>7} {'Implementation':<12} {'Cycles':>16} "
                f"{'Energy (J)':>14} {'EDP':>16}\n"
            )
            handle.write("-" * 72 + "\n")
            grain_rows = [row for row in rows if int(row["grain"]) == grain]
            for row in grain_rows:
                handle.write(
                    f"{int(row['nthreads']):>7} "
                    f"{row['implementation']:<12} "
                    f"{int(row['total_cycles']):>16} "
                    f"{row['energy_j'] or '-':>14} "
                    f"{row['edp_j_s'] or '-':>16}\n"
                )
            handle.write("\n")

        if missing:
            handle.write("Missing/unparseable runs:\n")
            for spec in missing:
                handle.write(
                    f"- {spec.implementation}, threads={spec.nthreads}, "
                    f"grain={spec.grain}: {spec.result_dir}\n"
                )

    print(f"Wrote {output_root / 'summary.csv'}")
    print(f"Wrote {txt_path}")
    return len(rows), len(missing)


def validate_runtime_paths(
    run_sniper: Path,
    config: Path,
    binary_dir: Path,
    mcpat_script: Path,
    implementations: list[str],
    skip_mcpat: bool,
) -> None:
    if not run_sniper.is_file():
        raise FileNotFoundError(f"missing run-sniper: {run_sniper}")
    if not config.is_file():
        raise FileNotFoundError(f"missing Sniper config: {config}")
    missing_binaries = [
        sniper_binary(binary_dir, implementation)
        for implementation in implementations
        if not sniper_binary(binary_dir, implementation).is_file()
    ]
    if missing_binaries:
        raise FileNotFoundError(
            "missing Sniper binaries: " + ", ".join(map(str, missing_binaries))
        )
    if not skip_mcpat and not mcpat_script.is_file():
        raise FileNotFoundError(
            f"missing McPAT helper: {mcpat_script}. Copy advcomparch_mcpat.py "
            "to /root/sniper/tools or pass --mcpat-script."
        )


def build_sniper_binaries(
    helpcode_dir: Path, sniper_base_dir: Path, dry_run: bool
) -> None:
    command = [
        "make",
        "-C",
        str(helpcode_dir),
        "sniper",
        f"SNIPER_BASE_DIR={sniper_base_dir}",
    ]
    if dry_run:
        print(f"DRY-RUN build: {shell_join(command)}")
        return
    subprocess.run(command, check=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    repo = repo_root_from_script()
    exercise = repo / "exercises" / "3rd"
    helpcode = exercise / "advcomparch-ex3-helpcode"

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--implementations")
    parser.add_argument("--thread-counts", default="1,2,4,8,16")
    parser.add_argument("--grain-sizes", default="1,10,100")
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--timeout", type=int, default=7200)
    parser.add_argument("--output-root", type=Path, default=exercise / "benchmarks" / "4.1" / "sniper")
    parser.add_argument("--helpcode-dir", type=Path, default=helpcode)
    parser.add_argument("--binary-dir", type=Path, default=helpcode / "bin")
    parser.add_argument("--sniper-base-dir", type=Path, default=Path("/root/sniper"))
    parser.add_argument("--run-sniper", type=Path, default=Path("/root/sniper/run-sniper"))
    parser.add_argument("--config", type=Path, default=helpcode / "ask3.cfg")
    parser.add_argument(
        "--mcpat-script",
        type=Path,
        default=Path("/root/sniper/tools/advcomparch_mcpat.py"),
    )
    parser.add_argument("--no-build", action="store_true")
    parser.add_argument("--skip-mcpat", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--summarize-only", action="store_true")
    parser.add_argument("--list-runs", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.iterations <= 0 or args.jobs <= 0:
        raise ValueError("--iterations and --jobs must be positive")

    implementations = parse_implementations(args.implementations)
    thread_counts = parse_int_list(args.thread_counts)
    grain_sizes = parse_int_list(args.grain_sizes)
    if any(value <= 0 for value in thread_counts + grain_sizes):
        raise ValueError("thread counts and grain sizes must be positive")
    for nthreads in thread_counts:
        sharing_for_threads(nthreads)

    specs = discover_specs(
        args.output_root,
        implementations,
        thread_counts,
        grain_sizes,
        args.iterations,
    )
    if args.limit is not None:
        specs = specs[: args.limit]

    if args.list_runs:
        for spec in specs:
            print(
                f"{spec.implementation} threads={spec.nthreads} "
                f"grain={spec.grain} L2share={spec.l2_shared_cores} "
                f"L3share={spec.l3_shared_cores}"
            )
        return 0

    if args.summarize_only:
        _, missing = write_summaries(specs, args.output_root)
        return 1 if missing else 0

    if not args.no_build:
        build_sniper_binaries(
            args.helpcode_dir, args.sniper_base_dir, args.dry_run
        )
    if not args.dry_run:
        validate_runtime_paths(
            args.run_sniper,
            args.config,
            args.binary_dir,
            args.mcpat_script,
            implementations,
            args.skip_mcpat,
        )

    failures = 0

    def execute(spec: SniperRunSpec) -> tuple[int, object]:
        return run_sniper_spec(
            spec,
            run_sniper=args.run_sniper,
            config=args.config,
            binary_dir=args.binary_dir,
            mcpat_script=args.mcpat_script,
            force=args.force,
            timeout=args.timeout,
            dry_run=args.dry_run,
            skip_mcpat=args.skip_mcpat,
        )

    if args.jobs == 1:
        results = [execute(spec) for spec in specs]
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
            results = list(executor.map(execute, specs))
    failures = sum(status != 0 for status, _ in results)

    if not args.dry_run:
        _, missing = write_summaries(specs, args.output_root)
        failures += missing
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
