#!/usr/bin/env python3
"""Run and summarize Assignment 1 section 5.2 branch statistics.

The script runs the provided cslab_branch_stats pintool for every SPEC CPU2006
benchmark input directory and stores:
  - raw pintool output in benchmarks/5.2/<train|ref>/raw/<benchmark>.txt
  - application stdout/stderr logs in benchmarks/5.2/<train|ref>/logs/
  - aggregate summaries in benchmarks/5.2/summary.csv and summary.txt

By default, benchmarks run from temporary scratch copies of their input
directories. That avoids modifying tracked SPEC output files such as ref.out,
train.out, lbm.out, etc. Use --work-mode in-place only if you explicitly want
the faster but dirtier behavior.
"""

from __future__ import annotations

import argparse
import csv
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


BENCHMARK_ORDER = [
    "403.gcc",
    "410.bwaves",
    "416.gamess",
    "429.mcf",
    "433.milc",
    "435.gromacs",
    "436.cactusADM",
    "450.soplex",
    "459.GemsFDTD",
    "470.lbm",
    "483.xalancbmk",
]

STAT_PATTERNS = {
    "total_instructions": re.compile(r"^Total Instructions:\s+(\d+)\s*$"),
    "total_branches": re.compile(r"^\s*Total-Branches:\s+(\d+)\s*$"),
    "conditional_taken": re.compile(r"^\s*Conditional-Taken-Branches:\s+(\d+)\s*$"),
    "conditional_not_taken": re.compile(r"^\s*Conditional-NotTaken-Branches:\s+(\d+)\s*$"),
    "unconditional": re.compile(r"^\s*Unconditional-Branches:\s+(\d+)\s*$"),
    "calls": re.compile(r"^\s*Calls:\s+(\d+)\s*$"),
    "returns": re.compile(r"^\s*Returns:\s+(\d+)\s*$"),
}

SUMMARY_FIELDS = [
    "input_set",
    "benchmark",
    "total_instructions",
    "total_branches",
    "branch_frequency_pct",
    "conditional_taken_branches",
    "conditional_taken_pct",
    "conditional_not_taken_branches",
    "conditional_not_taken_pct",
    "unconditional_branches",
    "unconditional_pct",
    "calls",
    "calls_pct",
    "returns",
    "returns_pct",
    "raw_output",
]


@dataclass(frozen=True)
class BenchRun:
    input_set: str
    benchmark: str
    source_dir: Path
    raw_output: Path
    stdout_log: Path
    stderr_log: Path
    command: str


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[3]


def clean_speccmd(line: str) -> str:
    """Use the actual executable command, dropping old SPEC -o/-e wrappers.

    The helper scripts shipped with the assignment do the same substring
    extraction from the first './'. This preserves shell redirections that
    appear after the executable while ignoring legacy text before it.
    """
    stripped = line.strip()
    start = stripped.find("./")
    if start == -1:
        raise ValueError(f"speccmds.cmd line does not contain './': {line!r}")
    return stripped[start:]


def read_speccmd(bench_dir: Path) -> str:
    speccmd = bench_dir / "speccmds.cmd"
    with speccmd.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.strip():
                return clean_speccmd(line)
    raise ValueError(f"{speccmd} does not contain a command")


def shell_quote(path: Path | str) -> str:
    return shlex.quote(str(path))


def discover_benchmarks(helpcode_dir: Path, input_sets: Iterable[str], output_root: Path) -> list[BenchRun]:
    runs: list[BenchRun] = []

    for input_set in input_sets:
        input_base = helpcode_dir / f"spec_execs_{input_set}_inputs"
        if not input_base.is_dir():
            raise FileNotFoundError(f"missing input directory: {input_base}")

        names = [name for name in BENCHMARK_ORDER if (input_base / name).is_dir()]
        extra = sorted(p.name for p in input_base.iterdir() if p.is_dir() and p.name not in names)
        names.extend(extra)

        for bench in names:
            source_dir = input_base / bench
            command = read_speccmd(source_dir)
            runs.append(
                BenchRun(
                    input_set=input_set,
                    benchmark=bench,
                    source_dir=source_dir,
                    raw_output=output_root / input_set / "raw" / f"{bench}.txt",
                    stdout_log=output_root / input_set / "logs" / f"{bench}.stdout.txt",
                    stderr_log=output_root / input_set / "logs" / f"{bench}.stderr.txt",
                    command=command,
                )
            )
    return runs


def ensure_output_dirs(output_root: Path) -> None:
    for input_set in ("train", "ref"):
        (output_root / input_set / "raw").mkdir(parents=True, exist_ok=True)
        (output_root / input_set / "logs").mkdir(parents=True, exist_ok=True)


def copy_to_scratch(source_dir: Path, scratch_root: Path | None) -> tempfile.TemporaryDirectory[str]:
    return tempfile.TemporaryDirectory(prefix=f"{source_dir.name}.", dir=str(scratch_root) if scratch_root else None)


def prepare_work_dir(source_dir: Path, work_mode: str, scratch_root: Path | None) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    if work_mode == "in-place":
        return source_dir, None

    tmp = copy_to_scratch(source_dir, scratch_root)
    work_dir = Path(tmp.name) / source_dir.name
    shutil.copytree(source_dir, work_dir)
    return work_dir, tmp


def run_one(
    run: BenchRun,
    pin_exe: Path,
    pintool: Path,
    work_mode: str,
    scratch_root: Path | None,
    force: bool,
    timeout: int | None,
    dry_run: bool,
) -> int:
    if run.raw_output.exists() and not force and parse_raw_output(run.raw_output):
        print(f"SKIP {run.input_set}/{run.benchmark}: existing parseable output")
        return 0

    run.raw_output.parent.mkdir(parents=True, exist_ok=True)
    run.stdout_log.parent.mkdir(parents=True, exist_ok=True)
    run.stderr_log.parent.mkdir(parents=True, exist_ok=True)

    pin_cmd = (
        f"{shell_quote(pin_exe)} -t {shell_quote(pintool)} "
        f"-o {shell_quote(run.raw_output.resolve())} -- {run.command} "
        f"1> {shell_quote(run.stdout_log.resolve())} "
        f"2> {shell_quote(run.stderr_log.resolve())}"
    )

    if dry_run:
        print(f"DRY-RUN {run.input_set}/{run.benchmark}")
        print(f"  cwd: {run.source_dir}")
        print(f"  cmd: {pin_cmd}")
        return 0

    work_dir, tmp = prepare_work_dir(run.source_dir, work_mode, scratch_root)
    started = time.monotonic()
    print(f"RUN {run.input_set}/{run.benchmark}")
    print(f"  cwd: {work_dir}")
    print(f"  cmd: {pin_cmd}")

    result: subprocess.CompletedProcess[str] | None = None
    try:
        result = subprocess.run(
            pin_cmd,
            cwd=work_dir,
            shell=True,
            executable="/bin/bash",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - started
        print(f"ERROR {run.input_set}/{run.benchmark}: timed out after {elapsed:.2f}s", file=sys.stderr)
        return 124
    finally:
        if tmp is not None:
            tmp.cleanup()

    elapsed = time.monotonic() - started
    if result is None:
        print(f"ERROR {run.input_set}/{run.benchmark}: command did not start", file=sys.stderr)
        return 1
    print(f"  exit: {result.returncode}, elapsed: {elapsed:.2f}s")

    if result.returncode != 0:
        print(f"ERROR {run.input_set}/{run.benchmark}: see {run.stderr_log}", file=sys.stderr)
        return result.returncode

    if not parse_raw_output(run.raw_output):
        print(f"ERROR {run.input_set}/{run.benchmark}: output did not parse: {run.raw_output}", file=sys.stderr)
        return 1

    return 0


def parse_raw_output(path: Path) -> dict[str, int] | None:
    if not path.exists() or path.stat().st_size == 0:
        return None

    values: dict[str, int] = {}
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            for key, pattern in STAT_PATTERNS.items():
                match = pattern.match(line)
                if match:
                    values[key] = int(match.group(1))

    required = set(STAT_PATTERNS)
    if required.issubset(values):
        return values
    return None


def pct(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator * 100.0


def summary_row(run: BenchRun, stats: dict[str, int]) -> dict[str, str]:
    total_instructions = stats["total_instructions"]
    total_branches = stats["total_branches"]
    return {
        "input_set": run.input_set,
        "benchmark": run.benchmark,
        "total_instructions": str(total_instructions),
        "total_branches": str(total_branches),
        "branch_frequency_pct": f"{pct(total_branches, total_instructions):.6f}",
        "conditional_taken_branches": str(stats["conditional_taken"]),
        "conditional_taken_pct": f"{pct(stats['conditional_taken'], total_branches):.6f}",
        "conditional_not_taken_branches": str(stats["conditional_not_taken"]),
        "conditional_not_taken_pct": f"{pct(stats['conditional_not_taken'], total_branches):.6f}",
        "unconditional_branches": str(stats["unconditional"]),
        "unconditional_pct": f"{pct(stats['unconditional'], total_branches):.6f}",
        "calls": str(stats["calls"]),
        "calls_pct": f"{pct(stats['calls'], total_branches):.6f}",
        "returns": str(stats["returns"]),
        "returns_pct": f"{pct(stats['returns'], total_branches):.6f}",
        "raw_output": str(run.raw_output),
    }


def write_summaries(runs: list[BenchRun], output_root: Path) -> None:
    rows: list[dict[str, str]] = []
    missing: list[BenchRun] = []
    for run in runs:
        stats = parse_raw_output(run.raw_output)
        if stats is None:
            missing.append(run)
            continue
        rows.append(summary_row(run, stats))

    output_root.mkdir(parents=True, exist_ok=True)
    csv_path = output_root / "summary.csv"
    txt_path = output_root / "summary.txt"

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    with txt_path.open("w", encoding="utf-8") as handle:
        handle.write("Assignment 1 - Section 5.2 Branch Instruction Analysis\n")
        handle.write(f"Parsed outputs: {len(rows)}\n")
        handle.write(f"Missing/unparseable outputs: {len(missing)}\n\n")

        if rows:
            header = (
                f"{'Input':<6} {'Benchmark':<14} {'Instr':>15} {'Branches':>15} "
                f"{'Br%':>9} {'CT%':>9} {'CNT%':>9} {'Uncond%':>9} {'Call%':>9} {'Ret%':>9}"
            )
            handle.write(header + "\n")
            handle.write("-" * len(header) + "\n")
            for row in rows:
                handle.write(
                    f"{row['input_set']:<6} {row['benchmark']:<14} "
                    f"{int(row['total_instructions']):>15} {int(row['total_branches']):>15} "
                    f"{float(row['branch_frequency_pct']):>9.3f} "
                    f"{float(row['conditional_taken_pct']):>9.3f} "
                    f"{float(row['conditional_not_taken_pct']):>9.3f} "
                    f"{float(row['unconditional_pct']):>9.3f} "
                    f"{float(row['calls_pct']):>9.3f} "
                    f"{float(row['returns_pct']):>9.3f}\n"
                )

        if missing:
            handle.write("\nMissing/unparseable outputs:\n")
            for run in missing:
                handle.write(f"- {run.input_set}/{run.benchmark}: {run.raw_output}\n")

    print(f"Wrote {csv_path}")
    print(f"Wrote {txt_path}")


def select_input_sets(value: str) -> list[str]:
    if value == "both":
        return ["train", "ref"]
    return [value]


def filter_benchmarks(runs: list[BenchRun], selected: list[str]) -> list[BenchRun]:
    if not selected:
        return runs
    selected_set = set(selected)
    unknown = selected_set - {run.benchmark for run in runs}
    if unknown:
        raise ValueError(f"unknown benchmark(s): {', '.join(sorted(unknown))}")
    return [run for run in runs if run.benchmark in selected_set]


def parse_args(argv: list[str]) -> argparse.Namespace:
    repo = repo_root_from_script()
    first_dir = repo / "exercises" / "1st"
    helpcode = first_dir / "advcomparch-ex1-helpcode"
    pin_root = first_dir / "pin-external-4.2-99776-g21d818fa2-gcc-linux"

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", choices=["train", "ref", "both"], default="both", help="input set to run")
    parser.add_argument("--bench", action="append", default=[], help="benchmark to run; may be repeated")
    parser.add_argument("--force", action="store_true", help="rerun even if a parseable raw output already exists")
    parser.add_argument("--dry-run", action="store_true", help="print commands without running benchmarks")
    parser.add_argument("--summarize-only", action="store_true", help="only regenerate summaries from raw outputs")
    parser.add_argument(
        "--work-mode",
        choices=["scratch", "in-place"],
        default="scratch",
        help="run from scratch copies by default to avoid modifying SPEC input directories",
    )
    parser.add_argument("--timeout-sec", type=int, default=None, help="optional timeout per benchmark")
    parser.add_argument("--scratch-root", type=Path, default=None, help="optional directory for temporary scratch copies")
    parser.add_argument("--helpcode-dir", type=Path, default=helpcode)
    parser.add_argument("--pin-root", type=Path, default=pin_root)
    parser.add_argument("--output-root", type=Path, default=first_dir / "benchmarks" / "5.2")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    helpcode_dir = args.helpcode_dir.resolve()
    pin_root = args.pin_root.resolve()
    pin_exe = pin_root / "pin"
    pintool = helpcode_dir / "pintool" / "obj-intel64" / "cslab_branch_stats.so"
    output_root = args.output_root.resolve()

    if not pin_exe.is_file():
        raise FileNotFoundError(f"PIN executable not found: {pin_exe}")
    if not pintool.is_file():
        raise FileNotFoundError(f"pintool not found; run make first: {pintool}")

    ensure_output_dirs(output_root)
    runs = discover_benchmarks(helpcode_dir, select_input_sets(args.input), output_root)
    runs = filter_benchmarks(runs, args.bench)

    if args.summarize_only:
        write_summaries(runs, output_root)
        return 0

    failures = 0
    for run in runs:
        code = run_one(
            run=run,
            pin_exe=pin_exe,
            pintool=pintool,
            work_mode=args.work_mode,
            scratch_root=args.scratch_root,
            force=args.force,
            timeout=args.timeout_sec,
            dry_run=args.dry_run,
        )
        if code != 0:
            failures += 1
            if not args.dry_run:
                break

    if not args.dry_run:
        write_summaries(runs, output_root)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
