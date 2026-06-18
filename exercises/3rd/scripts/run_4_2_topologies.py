#!/usr/bin/env python3
"""Run and summarize Assignment 3 section 4.2 Sniper topology experiments."""

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
    parse_sniper_metrics,
    repo_root_from_script,
    run_sniper_spec,
    shell_join,
    sniper_binary,
    sniper_summary_row,
    write_csv,
)


TOPOLOGIES = {
    "share-all": (4, 4),
    "share-l3": (1, 4),
    "share-nothing": (1, 1),
}


def parse_topologies(raw: str | None) -> list[str]:
    if raw is None:
        return list(TOPOLOGIES)
    values = [item.strip().lower() for item in raw.split(",") if item.strip()]
    unknown = [item for item in values if item not in TOPOLOGIES]
    if unknown:
        raise ValueError(
            f"unknown topology: {', '.join(unknown)}; "
            f"valid choices: {', '.join(TOPOLOGIES)}"
        )
    return list(dict.fromkeys(values))


def discover_specs(
    output_root: Path,
    implementations: list[str],
    topologies: list[str],
) -> list[SniperRunSpec]:
    specs: list[SniperRunSpec] = []
    for topology in topologies:
        l2_shared, l3_shared = TOPOLOGIES[topology]
        for implementation in implementations:
            specs.append(
                SniperRunSpec(
                    implementation=implementation,
                    nthreads=4,
                    iterations=1000,
                    grain=1,
                    l2_shared_cores=l2_shared,
                    l3_shared_cores=l3_shared,
                    result_dir=output_root / "raw" / topology / implementation,
                    topology=topology,
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
    rows.sort(key=lambda row: (row["topology"], row["implementation"]))
    write_csv(output_root / "summary.csv", SNIPER_SUMMARY_FIELDS, rows)

    txt_path = output_root / "summary.txt"
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    with txt_path.open("w", encoding="utf-8") as handle:
        handle.write("Assignment 3 - Section 4.2 Thread Topology\n")
        handle.write(f"Expected outputs: {len(specs)}\n")
        handle.write(f"Parsed outputs: {len(rows)}\n")
        handle.write(f"Missing/unparseable outputs: {len(missing)}\n\n")
        handle.write(
            f"{'Topology':<15} {'Implementation':<12} {'Cycles':>16} "
            f"{'Energy (J)':>14} {'EDP':>16}\n"
        )
        handle.write("-" * 78 + "\n")
        for row in rows:
            handle.write(
                f"{row['topology']:<15} {row['implementation']:<12} "
                f"{int(row['total_cycles']):>16} "
                f"{row['energy_j'] or '-':>14} "
                f"{row['edp_j_s'] or '-':>16}\n"
            )
        if missing:
            handle.write("\nMissing/unparseable runs:\n")
            for spec in missing:
                handle.write(
                    f"- {spec.topology}/{spec.implementation}: {spec.result_dir}\n"
                )
    print(f"Wrote {output_root / 'summary.csv'}")
    print(f"Wrote {txt_path}")
    return len(rows), len(missing)


def parse_args(argv: list[str]) -> argparse.Namespace:
    repo = repo_root_from_script()
    exercise = repo / "exercises" / "3rd"
    helpcode = exercise / "advcomparch-ex3-helpcode"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--implementations")
    parser.add_argument("--topologies")
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--timeout", type=int, default=7200)
    parser.add_argument("--output-root", type=Path, default=exercise / "benchmarks" / "4.2")
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
    if args.jobs <= 0:
        raise ValueError("--jobs must be positive")
    implementations = parse_implementations(args.implementations)
    topologies = parse_topologies(args.topologies)
    specs = discover_specs(args.output_root, implementations, topologies)
    if args.limit is not None:
        specs = specs[: args.limit]

    if args.list_runs:
        for spec in specs:
            print(
                f"{spec.topology} {spec.implementation} "
                f"L2share={spec.l2_shared_cores} L3share={spec.l3_shared_cores}"
            )
        return 0
    if args.summarize_only:
        _, missing = write_summaries(specs, args.output_root)
        return 1 if missing else 0

    build_command = [
        "make",
        "-C",
        str(args.helpcode_dir),
        "sniper",
        f"SNIPER_BASE_DIR={args.sniper_base_dir}",
    ]
    if not args.no_build:
        if args.dry_run:
            print(f"DRY-RUN build: {shell_join(build_command)}")
        else:
            subprocess.run(build_command, check=True)

    if not args.dry_run:
        required = [args.run_sniper, args.config]
        required.extend(sniper_binary(args.binary_dir, impl) for impl in implementations)
        if not args.skip_mcpat:
            required.append(args.mcpat_script)
        missing_paths = [path for path in required if not path.is_file()]
        if missing_paths:
            raise FileNotFoundError(
                "missing runtime files: " + ", ".join(map(str, missing_paths))
            )

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
