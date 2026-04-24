#!/usr/bin/env python3
"""Run and summarize Assignment 1 section 5.7 ref-input validation.

The script runs cslab_branch.so with -predictor_set 5.7 on the ref inputs
for the three predictors selected from the 5.6.2 train comparison:
  - Alpha21264
  - Perceptron-M141-N32
  - Perceptron-M56-N72

It stores:
  - raw pintool output in benchmarks/5.7/ref/raw/<benchmark>.txt
  - application stdout/stderr logs in benchmarks/5.7/ref/logs/
  - per-benchmark ref metrics in benchmarks/5.7/summary.csv
  - per-predictor ref averages in benchmarks/5.7/summary_by_predictor.csv
  - train-vs-ref comparisons when benchmarks/5.6.2 summaries exist
  - a readable text summary in benchmarks/5.7/summary.txt

By default, benchmarks run from temporary scratch copies of their input
directories. That avoids modifying tracked SPEC output files.
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

PREDICTORS = [
    {"name": "Alpha21264", "family": "alpha21264", "hardware_bits": 29696},
    {"name": "Perceptron-M141-N32", "family": "perceptron", "hardware_bits": 32571},
    {"name": "Perceptron-M56-N72", "family": "perceptron", "hardware_bits": 32704},
]

EXPECTED_PREDICTORS = [item["name"] for item in PREDICTORS]
PREDICTOR_INFO = {item["name"]: item for item in PREDICTORS}

TOTAL_INSTRUCTIONS_RE = re.compile(r"^Total Instructions:\s+(\d+)\s*$")
PREDICTOR_RE = re.compile(r"^\s*(.+):\s+(\d+)\s+(\d+)\s*$")

SUMMARY_FIELDS = [
    "input_set",
    "benchmark",
    "predictor",
    "family",
    "hardware_bits",
    "correct",
    "incorrect",
    "conditional_branches",
    "total_instructions",
    "direction_mpki",
    "accuracy_pct",
    "raw_output",
]

BY_PREDICTOR_FIELDS = [
    "input_set",
    "predictor",
    "family",
    "hardware_bits",
    "benchmarks",
    "arithmetic_mean_direction_mpki",
    "aggregate_direction_mpki",
    "arithmetic_mean_accuracy_pct",
    "total_instructions",
    "total_incorrect",
]

COMPARE_PREDICTOR_FIELDS = [
    "predictor",
    "family",
    "hardware_bits",
    "train_arithmetic_mean_direction_mpki",
    "ref_arithmetic_mean_direction_mpki",
    "delta_arithmetic_mean_direction_mpki",
    "train_aggregate_direction_mpki",
    "ref_aggregate_direction_mpki",
    "delta_aggregate_direction_mpki",
    "train_arithmetic_mean_accuracy_pct",
    "ref_arithmetic_mean_accuracy_pct",
    "delta_arithmetic_mean_accuracy_pct",
]

COMPARE_BENCHMARK_FIELDS = [
    "benchmark",
    "predictor",
    "train_direction_mpki",
    "ref_direction_mpki",
    "delta_direction_mpki",
    "train_accuracy_pct",
    "ref_accuracy_pct",
    "delta_accuracy_pct",
]


@dataclass(frozen=True)
class BenchRun:
    benchmark: str
    source_dir: Path
    raw_output: Path
    stdout_log: Path
    stderr_log: Path
    command: str


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[3]


def clean_speccmd(line: str) -> str:
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


def discover_benchmarks(helpcode_dir: Path, output_root: Path) -> list[BenchRun]:
    runs: list[BenchRun] = []
    input_base = helpcode_dir / "spec_execs_ref_inputs"
    if not input_base.is_dir():
        raise FileNotFoundError(f"missing ref input directory: {input_base}")

    names = [name for name in BENCHMARK_ORDER if (input_base / name).is_dir()]
    extra = sorted(p.name for p in input_base.iterdir() if p.is_dir() and p.name not in names)
    names.extend(extra)

    for bench in names:
        source_dir = input_base / bench
        runs.append(
            BenchRun(
                benchmark=bench,
                source_dir=source_dir,
                raw_output=output_root / "ref" / "raw" / f"{bench}.txt",
                stdout_log=output_root / "ref" / "logs" / f"{bench}.stdout.txt",
                stderr_log=output_root / "ref" / "logs" / f"{bench}.stderr.txt",
                command=read_speccmd(source_dir),
            )
        )
    return runs


def ensure_output_dirs(output_root: Path) -> None:
    (output_root / "ref" / "raw").mkdir(parents=True, exist_ok=True)
    (output_root / "ref" / "logs").mkdir(parents=True, exist_ok=True)


def prepare_work_dir(
    source_dir: Path,
    work_mode: str,
    scratch_root: Path | None,
) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    if work_mode == "in-place":
        return source_dir, None

    tmp = tempfile.TemporaryDirectory(prefix=f"{source_dir.name}.", dir=str(scratch_root) if scratch_root else None)
    work_dir = Path(tmp.name) / source_dir.name
    shutil.copytree(source_dir, work_dir)
    return work_dir, tmp


def parse_raw_output(path: Path) -> tuple[int, dict[str, tuple[int, int]]] | None:
    if not path.exists() or path.stat().st_size == 0:
        return None

    total_instructions: int | None = None
    predictors: dict[str, tuple[int, int]] = {}
    in_predictor_section = False

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            total_match = TOTAL_INSTRUCTIONS_RE.match(line)
            if total_match:
                total_instructions = int(total_match.group(1))
                continue

            if line.startswith("Branch Predictors:"):
                in_predictor_section = True
                continue

            if in_predictor_section:
                if not line.strip():
                    in_predictor_section = False
                    continue

                pred_match = PREDICTOR_RE.match(line)
                if pred_match:
                    predictors[pred_match.group(1)] = (int(pred_match.group(2)), int(pred_match.group(3)))

    if total_instructions is None:
        return None

    if not set(EXPECTED_PREDICTORS).issubset(predictors):
        return None

    return total_instructions, predictors


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
        print(f"SKIP ref/{run.benchmark}: existing parseable output")
        return 0

    run.raw_output.parent.mkdir(parents=True, exist_ok=True)
    run.stdout_log.parent.mkdir(parents=True, exist_ok=True)
    run.stderr_log.parent.mkdir(parents=True, exist_ok=True)

    pin_cmd = (
        f"{shell_quote(pin_exe)} -t {shell_quote(pintool)} "
        f"-o {shell_quote(run.raw_output.resolve())} -predictor_set 5.7 -- "
        f"{run.command} "
        f"1> {shell_quote(run.stdout_log.resolve())} "
        f"2> {shell_quote(run.stderr_log.resolve())}"
    )

    if dry_run:
        print(f"DRY-RUN ref/{run.benchmark}")
        print(f"  cwd: {run.source_dir}")
        print(f"  cmd: {pin_cmd}")
        return 0

    work_dir, tmp = prepare_work_dir(run.source_dir, work_mode, scratch_root)
    started = time.monotonic()
    print(f"RUN ref/{run.benchmark}")
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
        print(f"ERROR ref/{run.benchmark}: timed out after {elapsed:.2f}s", file=sys.stderr)
        return 124
    finally:
        if tmp is not None:
            tmp.cleanup()

    elapsed = time.monotonic() - started
    if result is None:
        print(f"ERROR ref/{run.benchmark}: command did not start", file=sys.stderr)
        return 1
    print(f"  exit: {result.returncode}, elapsed: {elapsed:.2f}s")

    if result.returncode != 0:
        print(f"ERROR ref/{run.benchmark}: see {run.stderr_log}", file=sys.stderr)
        return result.returncode

    if not parse_raw_output(run.raw_output):
        print(f"ERROR ref/{run.benchmark}: output did not parse: {run.raw_output}", file=sys.stderr)
        return 1

    return 0


def direction_mpki(incorrect: int, total_instructions: int) -> float:
    if total_instructions == 0:
        return 0.0
    return incorrect / total_instructions * 1000.0


def accuracy_pct(correct: int, incorrect: int) -> float:
    total = correct + incorrect
    if total == 0:
        return 0.0
    return correct / total * 100.0


def collect_rows(runs: list[BenchRun]) -> tuple[list[dict[str, str]], list[BenchRun]]:
    rows: list[dict[str, str]] = []
    missing: list[BenchRun] = []

    for run in runs:
        parsed = parse_raw_output(run.raw_output)
        if parsed is None:
            missing.append(run)
            continue

        total_instructions, predictors = parsed
        for predictor in EXPECTED_PREDICTORS:
            correct, incorrect = predictors[predictor]
            info = PREDICTOR_INFO[predictor]
            rows.append(
                {
                    "input_set": "ref",
                    "benchmark": run.benchmark,
                    "predictor": predictor,
                    "family": str(info["family"]),
                    "hardware_bits": str(info["hardware_bits"]),
                    "correct": str(correct),
                    "incorrect": str(incorrect),
                    "conditional_branches": str(correct + incorrect),
                    "total_instructions": str(total_instructions),
                    "direction_mpki": f"{direction_mpki(incorrect, total_instructions):.6f}",
                    "accuracy_pct": f"{accuracy_pct(correct, incorrect):.6f}",
                    "raw_output": str(run.raw_output),
                }
            )

    return rows, missing


def aggregate_selected_rows(selected: list[dict[str, str]]) -> dict[str, str]:
    total_instructions = sum(int(row["total_instructions"]) for row in selected)
    total_incorrect = sum(int(row["incorrect"]) for row in selected)
    mean_mpki = sum(float(row["direction_mpki"]) for row in selected) / len(selected)
    aggregate_mpki = direction_mpki(total_incorrect, total_instructions)
    mean_accuracy = sum(float(row["accuracy_pct"]) for row in selected) / len(selected)

    return {
        "benchmark_rows": str(len(selected)),
        "arithmetic_mean_direction_mpki": f"{mean_mpki:.6f}",
        "aggregate_direction_mpki": f"{aggregate_mpki:.6f}",
        "arithmetic_mean_accuracy_pct": f"{mean_accuracy:.6f}",
        "total_instructions": str(total_instructions),
        "total_incorrect": str(total_incorrect),
    }


def aggregate_by_predictor(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for predictor in EXPECTED_PREDICTORS:
        selected = [row for row in rows if row["predictor"] == predictor]
        if not selected:
            continue
        aggregate = aggregate_selected_rows(selected)
        info = PREDICTOR_INFO[predictor]
        output.append(
            {
                "input_set": "ref",
                "predictor": predictor,
                "family": str(info["family"]),
                "hardware_bits": str(info["hardware_bits"]),
                "benchmarks": aggregate["benchmark_rows"],
                "arithmetic_mean_direction_mpki": aggregate["arithmetic_mean_direction_mpki"],
                "aggregate_direction_mpki": aggregate["aggregate_direction_mpki"],
                "arithmetic_mean_accuracy_pct": aggregate["arithmetic_mean_accuracy_pct"],
                "total_instructions": aggregate["total_instructions"],
                "total_incorrect": aggregate["total_incorrect"],
            }
        )

    output.sort(key=lambda row: float(row["arithmetic_mean_direction_mpki"]))
    return output


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def build_predictor_comparison(output_root: Path, ref_by_predictor: list[dict[str, str]]) -> list[dict[str, str]]:
    train_path = output_root.parent / "5.6.2" / "summary_by_predictor.csv"
    train_rows = {
        row["predictor"]: row
        for row in read_csv_rows(train_path)
        if row.get("predictor") in EXPECTED_PREDICTORS
    }
    if not train_rows:
        return []

    comparison: list[dict[str, str]] = []
    for ref_row in ref_by_predictor:
        predictor = ref_row["predictor"]
        train_row = train_rows.get(predictor)
        if train_row is None:
            continue

        train_mean = float(train_row["arithmetic_mean_direction_mpki"])
        ref_mean = float(ref_row["arithmetic_mean_direction_mpki"])
        train_agg = float(train_row["aggregate_direction_mpki"])
        ref_agg = float(ref_row["aggregate_direction_mpki"])
        train_acc = float(train_row["arithmetic_mean_accuracy_pct"])
        ref_acc = float(ref_row["arithmetic_mean_accuracy_pct"])
        info = PREDICTOR_INFO[predictor]
        comparison.append(
            {
                "predictor": predictor,
                "family": str(info["family"]),
                "hardware_bits": str(info["hardware_bits"]),
                "train_arithmetic_mean_direction_mpki": f"{train_mean:.6f}",
                "ref_arithmetic_mean_direction_mpki": f"{ref_mean:.6f}",
                "delta_arithmetic_mean_direction_mpki": f"{ref_mean - train_mean:.6f}",
                "train_aggregate_direction_mpki": f"{train_agg:.6f}",
                "ref_aggregate_direction_mpki": f"{ref_agg:.6f}",
                "delta_aggregate_direction_mpki": f"{ref_agg - train_agg:.6f}",
                "train_arithmetic_mean_accuracy_pct": f"{train_acc:.6f}",
                "ref_arithmetic_mean_accuracy_pct": f"{ref_acc:.6f}",
                "delta_arithmetic_mean_accuracy_pct": f"{ref_acc - train_acc:.6f}",
            }
        )

    comparison.sort(key=lambda row: float(row["ref_arithmetic_mean_direction_mpki"]))
    return comparison


def build_benchmark_comparison(output_root: Path, ref_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    train_path = output_root.parent / "5.6.2" / "summary.csv"
    train_rows = {
        (row["benchmark"], row["predictor"]): row
        for row in read_csv_rows(train_path)
        if row.get("predictor") in EXPECTED_PREDICTORS
    }
    if not train_rows:
        return []

    comparison: list[dict[str, str]] = []
    for ref_row in ref_rows:
        key = (ref_row["benchmark"], ref_row["predictor"])
        train_row = train_rows.get(key)
        if train_row is None:
            continue

        train_mpki = float(train_row["direction_mpki"])
        ref_mpki = float(ref_row["direction_mpki"])
        train_acc = float(train_row["accuracy_pct"])
        ref_acc = float(ref_row["accuracy_pct"])
        comparison.append(
            {
                "benchmark": ref_row["benchmark"],
                "predictor": ref_row["predictor"],
                "train_direction_mpki": f"{train_mpki:.6f}",
                "ref_direction_mpki": f"{ref_mpki:.6f}",
                "delta_direction_mpki": f"{ref_mpki - train_mpki:.6f}",
                "train_accuracy_pct": f"{train_acc:.6f}",
                "ref_accuracy_pct": f"{ref_acc:.6f}",
                "delta_accuracy_pct": f"{ref_acc - train_acc:.6f}",
            }
        )

    order = {name: index for index, name in enumerate(BENCHMARK_ORDER)}
    comparison.sort(key=lambda row: (order.get(row["benchmark"], len(order)), row["predictor"]))
    return comparison


def write_summaries(runs: list[BenchRun], output_root: Path) -> None:
    rows, missing = collect_rows(runs)

    output_root.mkdir(parents=True, exist_ok=True)
    summary_path = output_root / "summary.csv"
    by_predictor_path = output_root / "summary_by_predictor.csv"
    compare_predictor_path = output_root / "train_vs_ref_by_predictor.csv"
    compare_benchmark_path = output_root / "train_vs_ref_by_benchmark.csv"
    txt_path = output_root / "summary.txt"

    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    by_predictor = aggregate_by_predictor(rows)
    with by_predictor_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=BY_PREDICTOR_FIELDS)
        writer.writeheader()
        writer.writerows(by_predictor)

    predictor_comparison = build_predictor_comparison(output_root, by_predictor)
    with compare_predictor_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COMPARE_PREDICTOR_FIELDS)
        writer.writeheader()
        writer.writerows(predictor_comparison)

    benchmark_comparison = build_benchmark_comparison(output_root, rows)
    with compare_benchmark_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COMPARE_BENCHMARK_FIELDS)
        writer.writeheader()
        writer.writerows(benchmark_comparison)

    with txt_path.open("w", encoding="utf-8") as handle:
        handle.write("Assignment 1 - Section 5.7 Ref-Input Validation\n")
        handle.write(f"Parsed benchmark outputs: {len(runs) - len(missing)}\n")
        handle.write(f"Missing/unparseable benchmark outputs: {len(missing)}\n\n")

        handle.write("Selected predictors\n")
        handle.write(f"{'Predictor':<24} {'Family':<12} {'Bits':>8} {'Ref Mean MPKI':>14} {'Ref Agg MPKI':>13} {'Ref Mean Acc%':>14}\n")
        handle.write("-" * 92 + "\n")
        for row in by_predictor:
            handle.write(
                f"{row['predictor']:<24} "
                f"{row['family']:<12} "
                f"{int(row['hardware_bits']):>8} "
                f"{float(row['arithmetic_mean_direction_mpki']):>14.6f} "
                f"{float(row['aggregate_direction_mpki']):>13.6f} "
                f"{float(row['arithmetic_mean_accuracy_pct']):>14.6f}\n"
            )

        handle.write("\nTrain vs ref by predictor\n")
        if predictor_comparison:
            handle.write(f"{'Predictor':<24} {'Train Mean':>12} {'Ref Mean':>12} {'Delta':>12} {'Train Agg':>12} {'Ref Agg':>12} {'Delta':>12}\n")
            handle.write("-" * 100 + "\n")
            for row in predictor_comparison:
                handle.write(
                    f"{row['predictor']:<24} "
                    f"{float(row['train_arithmetic_mean_direction_mpki']):>12.6f} "
                    f"{float(row['ref_arithmetic_mean_direction_mpki']):>12.6f} "
                    f"{float(row['delta_arithmetic_mean_direction_mpki']):>12.6f} "
                    f"{float(row['train_aggregate_direction_mpki']):>12.6f} "
                    f"{float(row['ref_aggregate_direction_mpki']):>12.6f} "
                    f"{float(row['delta_aggregate_direction_mpki']):>12.6f}\n"
                )
        else:
            handle.write("No 5.6.2 train summary found; comparison CSVs contain headers only.\n")

        if missing:
            handle.write("\nMissing/unparseable outputs:\n")
            for run in missing:
                handle.write(f"- ref/{run.benchmark}: {run.raw_output}\n")

    print(f"Wrote {summary_path}")
    print(f"Wrote {by_predictor_path}")
    print(f"Wrote {compare_predictor_path}")
    print(f"Wrote {compare_benchmark_path}")
    print(f"Wrote {txt_path}")


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
    parser.add_argument("--output-root", type=Path, default=first_dir / "benchmarks" / "5.7")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    helpcode_dir = args.helpcode_dir.resolve()
    pin_root = args.pin_root.resolve()
    pin_exe = pin_root / "pin"
    pintool = helpcode_dir / "pintool" / "obj-intel64" / "cslab_branch.so"
    output_root = args.output_root.resolve()

    if not pin_exe.is_file():
        raise FileNotFoundError(f"PIN executable not found: {pin_exe}")
    if not pintool.is_file():
        raise FileNotFoundError(f"pintool not found; run make first: {pintool}")

    ensure_output_dirs(output_root)
    runs = discover_benchmarks(helpcode_dir, output_root)
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
