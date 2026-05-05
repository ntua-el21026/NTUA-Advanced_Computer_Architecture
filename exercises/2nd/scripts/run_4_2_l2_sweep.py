#!/usr/bin/env python3
"""Run and summarize Assignment 2 section 4.2 L2-cache experiments.

The script runs the provided simulator pintool for all required L2 cache
configurations and all seven SPEC CPU2006 benchmarks. By default it uses one
worker per core in the --cores list and launches every benchmark/configuration
through taskset. Each worker runs one benchmark process at a time.

Outputs:
  - raw pintool output in benchmarks/4.2/raw/<benchmark>/<config>.out
  - application stdout/stderr logs in benchmarks/4.2/logs/<benchmark>/
  - per-run timing logs in benchmarks/4.2/times/<benchmark>/
  - aggregate CSV/text summaries in benchmarks/4.2/

Benchmarks run from temporary scratch copies by default. This keeps SPEC
command redirections from modifying tracked helper-code files.
"""

from __future__ import annotations

import argparse
import csv
import math
import queue
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path


BENCHMARK_ORDER = [
    "403.gcc",
    "429.mcf",
    "433.milc",
    "444.namd",
    "450.soplex",
    "459.GemsFDTD",
    "470.lbm",
]

L2_ASSOCIATIVITY_BY_SIZE = {
    256: [4],
    512: [4, 8, 16],
    1024: [8, 16],
    2048: [16],
}
L2_BLOCK_SIZES = [64, 128, 256]

L1_SIZE_KB = 32
L1_ASSOCIATIVITY = 4
L1_BLOCK_SIZE = 32

TOTAL_INSTRUCTIONS_RE = re.compile(r"^Total Instructions:\s+(\d+)\s*$")
TOTAL_CYCLES_RE = re.compile(r"^Total Cycles:\s+(\d+)\s*$")
IPC_RE = re.compile(r"^IPC:\s+([0-9.]+)\s*$")
TOTAL_CACHE_RE = re.compile(r"^L([12])-Total-(Hits|Misses|Accesses):\s+(\d+)\s+")

SUMMARY_FIELDS = [
    "benchmark",
    "config",
    "l1_size_kb",
    "l1_associativity",
    "l1_block_size_b",
    "l2_size_kb",
    "l2_associativity",
    "l2_block_size_b",
    "total_instructions",
    "total_cycles",
    "ipc",
    "l1_accesses",
    "l1_misses",
    "l1_miss_rate_pct",
    "l1_mpki",
    "l2_accesses",
    "l2_misses",
    "l2_miss_rate_pct",
    "l2_mpki",
    "mem_accesses",
    "raw_output",
    "stdout_log",
    "stderr_log",
]

BY_CONFIG_FIELDS = [
    "config",
    "l2_size_kb",
    "l2_associativity",
    "l2_block_size_b",
    "benchmarks",
    "arithmetic_mean_ipc",
    "aggregate_ipc",
    "arithmetic_mean_l1_mpki",
    "arithmetic_mean_l2_mpki",
    "aggregate_l1_mpki",
    "aggregate_l2_mpki",
    "total_instructions",
    "total_cycles",
    "total_l1_misses",
    "total_l2_misses",
]

BY_BENCHMARK_FIELDS = [
    "benchmark",
    "configs",
    "best_config_by_ipc",
    "best_ipc",
    "worst_config_by_ipc",
    "worst_ipc",
    "ipc_range",
]


@dataclass(frozen=True)
class CacheConfig:
    l2_size_kb: int
    l2_associativity: int
    l2_block_size_b: int

    @property
    def name(self) -> str:
        return f"L2_{self.l2_size_kb}KB_A{self.l2_associativity}_B{self.l2_block_size_b}"


@dataclass(frozen=True)
class BenchTask:
    benchmark: str
    source_dir: Path
    command: str
    config: CacheConfig
    raw_output: Path
    stdout_log: Path
    stderr_log: Path
    time_log: Path


@dataclass(frozen=True)
class ParsedResult:
    total_instructions: int
    total_cycles: int
    ipc: float
    l1_accesses: int
    l1_misses: int
    l2_accesses: int
    l2_misses: int


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[3]


def shell_quote(path: Path | str) -> str:
    return shlex.quote(str(path))


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


def l2_configs() -> list[CacheConfig]:
    configs: list[CacheConfig] = []
    for size_kb in (256, 512, 1024, 2048):
        for assoc in L2_ASSOCIATIVITY_BY_SIZE[size_kb]:
            for block_size in L2_BLOCK_SIZES:
                configs.append(CacheConfig(size_kb, assoc, block_size))
    return configs


def parse_core_list(raw: str) -> list[int]:
    cores: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_raw, end_raw = part.split("-", 1)
            start = int(start_raw)
            end = int(end_raw)
            if end < start:
                raise ValueError(f"invalid core range: {part}")
            cores.extend(range(start, end + 1))
        else:
            cores.append(int(part))

    if not cores:
        raise ValueError("at least one core must be provided")

    seen: set[int] = set()
    deduped: list[int] = []
    for core in cores:
        if core < 0:
            raise ValueError(f"invalid negative core: {core}")
        if core not in seen:
            seen.add(core)
            deduped.append(core)
    return deduped


def selected_benchmarks(raw: str | None) -> list[str]:
    if raw is None:
        return BENCHMARK_ORDER
    names = [item.strip() for item in raw.split(",") if item.strip()]
    unknown = [name for name in names if name not in BENCHMARK_ORDER]
    if unknown:
        raise ValueError(f"unknown benchmark(s): {', '.join(unknown)}")
    return names


def discover_tasks(helpcode_dir: Path, output_root: Path, benchmarks: list[str]) -> list[BenchTask]:
    input_base = helpcode_dir / "spec_benchmarks"
    if not input_base.is_dir():
        raise FileNotFoundError(f"missing benchmark directory: {input_base}")

    tasks: list[BenchTask] = []
    for config in l2_configs():
        for benchmark in benchmarks:
            source_dir = input_base / benchmark
            if not source_dir.is_dir():
                raise FileNotFoundError(f"missing benchmark directory: {source_dir}")

            tasks.append(
                BenchTask(
                    benchmark=benchmark,
                    source_dir=source_dir,
                    command=read_speccmd(source_dir),
                    config=config,
                    raw_output=output_root / "raw" / benchmark / f"{config.name}.out",
                    stdout_log=output_root / "logs" / benchmark / f"{config.name}.stdout.txt",
                    stderr_log=output_root / "logs" / benchmark / f"{config.name}.stderr.txt",
                    time_log=output_root / "times" / benchmark / f"{config.name}.time.txt",
                )
            )
    return tasks


def ensure_output_dirs(tasks: list[BenchTask], output_root: Path) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    for task in tasks:
        task.raw_output.parent.mkdir(parents=True, exist_ok=True)
        task.stdout_log.parent.mkdir(parents=True, exist_ok=True)
        task.stderr_log.parent.mkdir(parents=True, exist_ok=True)
        task.time_log.parent.mkdir(parents=True, exist_ok=True)


def parse_raw_output(path: Path) -> ParsedResult | None:
    if not path.exists() or path.stat().st_size == 0:
        return None

    total_instructions: int | None = None
    total_cycles: int | None = None
    ipc: float | None = None
    cache_totals: dict[tuple[str, str], int] = {}

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if match := TOTAL_INSTRUCTIONS_RE.match(line):
                total_instructions = int(match.group(1))
                continue
            if match := TOTAL_CYCLES_RE.match(line):
                total_cycles = int(match.group(1))
                continue
            if match := IPC_RE.match(line):
                ipc = float(match.group(1))
                continue
            if match := TOTAL_CACHE_RE.match(line):
                level = match.group(1)
                metric = match.group(2).lower()
                cache_totals[(level, metric)] = int(match.group(3))

    required = [
        total_instructions,
        total_cycles,
        ipc,
        cache_totals.get(("1", "accesses")),
        cache_totals.get(("1", "misses")),
        cache_totals.get(("2", "accesses")),
        cache_totals.get(("2", "misses")),
    ]
    if any(value is None for value in required):
        return None

    return ParsedResult(
        total_instructions=total_instructions or 0,
        total_cycles=total_cycles or 0,
        ipc=ipc or 0.0,
        l1_accesses=cache_totals[("1", "accesses")],
        l1_misses=cache_totals[("1", "misses")],
        l2_accesses=cache_totals[("2", "accesses")],
        l2_misses=cache_totals[("2", "misses")],
    )


def prepare_work_dir(
    source_dir: Path,
    work_mode: str,
    scratch_root: Path,
) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    if work_mode == "in-place":
        return source_dir, None

    scratch_root.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.TemporaryDirectory(prefix=f"{source_dir.name}.", dir=str(scratch_root))
    work_dir = Path(tmp.name) / source_dir.name
    shutil.copytree(source_dir, work_dir)
    return work_dir, tmp


def build_pin_command(task: BenchTask, pin_exe: Path, pintool: Path, core: int) -> str:
    inner = (
        f"{shell_quote(pin_exe)} -t {shell_quote(pintool)} "
        f"-o {shell_quote(task.raw_output.resolve())} "
        f"-L1c {L1_SIZE_KB} -L1a {L1_ASSOCIATIVITY} -L1b {L1_BLOCK_SIZE} "
        f"-L2c {task.config.l2_size_kb} "
        f"-L2a {task.config.l2_associativity} "
        f"-L2b {task.config.l2_block_size_b} -- "
        f"{task.command}"
    )
    return (
        f"taskset -c {core} /bin/bash -lc {shlex.quote(inner)} "
        f"1> {shell_quote(task.stdout_log.resolve())} "
        f"2> {shell_quote(task.stderr_log.resolve())}"
    )


def run_task(
    task: BenchTask,
    pin_exe: Path,
    pintool: Path,
    core: int,
    work_mode: str,
    scratch_root: Path,
    force: bool,
    timeout: int | None,
    dry_run: bool,
) -> int:
    existing = parse_raw_output(task.raw_output)
    if existing is not None and not force:
        print(
            f"[SKIP] core={core} {task.benchmark} {task.config.name} "
            f"existing parseable output ipc={existing.ipc:.6f}",
            flush=True,
        )
        return 0

    command = build_pin_command(task, pin_exe, pintool, core)
    if dry_run:
        print(
            f"[DRY] core={core} {task.benchmark} {task.config.name}\n"
            f"      cwd: {task.source_dir}\n"
            f"      cmd: {command}",
            flush=True,
        )
        return 0

    work_dir, tmp = prepare_work_dir(task.source_dir, work_mode, scratch_root)
    started = time.monotonic()
    return_code = 1
    try:
        result = subprocess.run(
            command,
            cwd=work_dir,
            shell=True,
            executable="/bin/bash",
            timeout=timeout,
            check=False,
        )
        return_code = result.returncode
        return return_code
    except subprocess.TimeoutExpired:
        return_code = 124
        return return_code
    finally:
        elapsed = time.monotonic() - started
        task.time_log.write_text(
            "\n".join(
                [
                    f"benchmark={task.benchmark}",
                    f"config={task.config.name}",
                    f"core={core}",
                    f"return_code={return_code}",
                    f"elapsed_seconds={elapsed:.3f}",
                    f"work_dir={work_dir}",
                    f"command={command}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        if tmp is not None:
            tmp.cleanup()


def percent(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return 100.0 * numerator / denominator


def mpki(misses: int, instructions: int) -> float:
    if instructions == 0:
        return 0.0
    return misses / instructions * 1000.0


def summary_row(task: BenchTask, parsed: ParsedResult) -> dict[str, str | int | float]:
    return {
        "benchmark": task.benchmark,
        "config": task.config.name,
        "l1_size_kb": L1_SIZE_KB,
        "l1_associativity": L1_ASSOCIATIVITY,
        "l1_block_size_b": L1_BLOCK_SIZE,
        "l2_size_kb": task.config.l2_size_kb,
        "l2_associativity": task.config.l2_associativity,
        "l2_block_size_b": task.config.l2_block_size_b,
        "total_instructions": parsed.total_instructions,
        "total_cycles": parsed.total_cycles,
        "ipc": f"{parsed.ipc:.9f}",
        "l1_accesses": parsed.l1_accesses,
        "l1_misses": parsed.l1_misses,
        "l1_miss_rate_pct": f"{percent(parsed.l1_misses, parsed.l1_accesses):.9f}",
        "l1_mpki": f"{mpki(parsed.l1_misses, parsed.total_instructions):.9f}",
        "l2_accesses": parsed.l2_accesses,
        "l2_misses": parsed.l2_misses,
        "l2_miss_rate_pct": f"{percent(parsed.l2_misses, parsed.l2_accesses):.9f}",
        "l2_mpki": f"{mpki(parsed.l2_misses, parsed.total_instructions):.9f}",
        "mem_accesses": parsed.l2_misses,
        "raw_output": str(task.raw_output),
        "stdout_log": str(task.stdout_log),
        "stderr_log": str(task.stderr_log),
    }


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def summarize(tasks: list[BenchTask], output_root: Path) -> tuple[int, int]:
    parsed_by_task: list[tuple[BenchTask, ParsedResult]] = []
    missing: list[BenchTask] = []

    for task in tasks:
        parsed = parse_raw_output(task.raw_output)
        if parsed is None:
            missing.append(task)
        else:
            parsed_by_task.append((task, parsed))

    rows = [summary_row(task, parsed) for task, parsed in parsed_by_task]
    rows.sort(key=lambda row: (str(row["config"]), str(row["benchmark"])))
    write_csv(output_root / "summary.csv", SUMMARY_FIELDS, rows)

    by_config_rows = summarize_by_config(parsed_by_task)
    write_csv(output_root / "summary_by_config.csv", BY_CONFIG_FIELDS, by_config_rows)

    by_benchmark_rows = summarize_by_benchmark(parsed_by_task)
    write_csv(output_root / "summary_by_benchmark.csv", BY_BENCHMARK_FIELDS, by_benchmark_rows)

    write_text_summary(output_root / "summary.txt", tasks, parsed_by_task, missing, by_config_rows, by_benchmark_rows)
    return len(parsed_by_task), len(missing)


def summarize_by_config(parsed_by_task: list[tuple[BenchTask, ParsedResult]]) -> list[dict[str, object]]:
    grouped: dict[str, list[tuple[BenchTask, ParsedResult]]] = {}
    for task, parsed in parsed_by_task:
        grouped.setdefault(task.config.name, []).append((task, parsed))

    rows: list[dict[str, object]] = []
    for config_name, items in sorted(grouped.items()):
        config = items[0][0].config
        total_instructions = sum(parsed.total_instructions for _, parsed in items)
        total_cycles = sum(parsed.total_cycles for _, parsed in items)
        total_l1_misses = sum(parsed.l1_misses for _, parsed in items)
        total_l2_misses = sum(parsed.l2_misses for _, parsed in items)
        mean_ipc = sum(parsed.ipc for _, parsed in items) / len(items)
        mean_l1_mpki = sum(mpki(parsed.l1_misses, parsed.total_instructions) for _, parsed in items) / len(items)
        mean_l2_mpki = sum(mpki(parsed.l2_misses, parsed.total_instructions) for _, parsed in items) / len(items)
        rows.append(
            {
                "config": config_name,
                "l2_size_kb": config.l2_size_kb,
                "l2_associativity": config.l2_associativity,
                "l2_block_size_b": config.l2_block_size_b,
                "benchmarks": len(items),
                "arithmetic_mean_ipc": f"{mean_ipc:.9f}",
                "aggregate_ipc": f"{(total_instructions / total_cycles) if total_cycles else 0.0:.9f}",
                "arithmetic_mean_l1_mpki": f"{mean_l1_mpki:.9f}",
                "arithmetic_mean_l2_mpki": f"{mean_l2_mpki:.9f}",
                "aggregate_l1_mpki": f"{mpki(total_l1_misses, total_instructions):.9f}",
                "aggregate_l2_mpki": f"{mpki(total_l2_misses, total_instructions):.9f}",
                "total_instructions": total_instructions,
                "total_cycles": total_cycles,
                "total_l1_misses": total_l1_misses,
                "total_l2_misses": total_l2_misses,
            }
        )

    rows.sort(key=lambda row: (-float(row["aggregate_ipc"]), -float(row["arithmetic_mean_ipc"])))
    return rows


def summarize_by_benchmark(parsed_by_task: list[tuple[BenchTask, ParsedResult]]) -> list[dict[str, object]]:
    grouped: dict[str, list[tuple[BenchTask, ParsedResult]]] = {}
    for task, parsed in parsed_by_task:
        grouped.setdefault(task.benchmark, []).append((task, parsed))

    rows: list[dict[str, object]] = []
    for benchmark, items in sorted(grouped.items()):
        best_task, best_result = max(items, key=lambda item: item[1].ipc)
        worst_task, worst_result = min(items, key=lambda item: item[1].ipc)
        rows.append(
            {
                "benchmark": benchmark,
                "configs": len(items),
                "best_config_by_ipc": best_task.config.name,
                "best_ipc": f"{best_result.ipc:.9f}",
                "worst_config_by_ipc": worst_task.config.name,
                "worst_ipc": f"{worst_result.ipc:.9f}",
                "ipc_range": f"{best_result.ipc - worst_result.ipc:.9f}",
            }
        )
    return rows


def write_text_summary(
    path: Path,
    tasks: list[BenchTask],
    parsed_by_task: list[tuple[BenchTask, ParsedResult]],
    missing: list[BenchTask],
    by_config_rows: list[dict[str, object]],
    by_benchmark_rows: list[dict[str, object]],
) -> None:
    lines: list[str] = []
    lines.append("Assignment 2 - Section 4.2 L2 Cache Study")
    lines.append(f"Expected outputs: {len(tasks)}")
    lines.append(f"Parsed outputs: {len(parsed_by_task)}")
    lines.append(f"Missing/unparseable outputs: {len(missing)}")
    lines.append("")

    lines.append("Top configurations by aggregate IPC")
    lines.append(f"{'Config':28} {'Mean IPC':>12} {'Agg IPC':>12} {'Mean L2 MPKI':>14} {'Agg L2 MPKI':>13}")
    lines.append("-" * 84)
    for row in by_config_rows[:10]:
        lines.append(
            f"{row['config']:28} "
            f"{float(row['arithmetic_mean_ipc']):12.6f} "
            f"{float(row['aggregate_ipc']):12.6f} "
            f"{float(row['arithmetic_mean_l2_mpki']):14.6f} "
            f"{float(row['aggregate_l2_mpki']):13.6f}"
        )
    lines.append("")

    lines.append("Best configuration within each L2 capacity by aggregate IPC")
    lines.append(f"{'L2 size':>8} {'Config':28} {'Agg IPC':>12} {'Mean IPC':>12}")
    lines.append("-" * 68)
    for size in (256, 512, 1024, 2048):
        size_rows = [row for row in by_config_rows if int(row["l2_size_kb"]) == size]
        if not size_rows:
            continue
        best = max(size_rows, key=lambda row: float(row["aggregate_ipc"]))
        lines.append(
            f"{size:8d} {best['config']:28} "
            f"{float(best['aggregate_ipc']):12.6f} "
            f"{float(best['arithmetic_mean_ipc']):12.6f}"
        )
    lines.append("")

    lines.append("Per-benchmark IPC spread")
    lines.append(f"{'Benchmark':14} {'Best config':28} {'Best IPC':>10} {'Worst IPC':>10} {'Range':>10}")
    lines.append("-" * 80)
    for row in by_benchmark_rows:
        lines.append(
            f"{row['benchmark']:14} {row['best_config_by_ipc']:28} "
            f"{float(row['best_ipc']):10.6f} "
            f"{float(row['worst_ipc']):10.6f} "
            f"{float(row['ipc_range']):10.6f}"
        )

    if missing:
        lines.append("")
        lines.append("Missing/unparseable outputs")
        for task in missing[:50]:
            lines.append(f"- {task.benchmark} {task.config.name}: {task.raw_output}")
        if len(missing) > 50:
            lines.append(f"- ... {len(missing) - 50} more")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def worker_loop(
    core: int,
    initial_task: tuple[int, BenchTask] | None,
    task_queue: queue.Queue[tuple[int, BenchTask]],
    total_tasks: int,
    completed: list[int],
    lock: threading.Lock,
    args: argparse.Namespace,
    pin_exe: Path,
    pintool: Path,
    scratch_root: Path,
) -> None:
    pending_initial = initial_task
    while True:
        if pending_initial is not None:
            task_number, task = pending_initial
            pending_initial = None
            queue_item = False
        else:
            try:
                task_number, task = task_queue.get_nowait()
                queue_item = True
            except queue.Empty:
                return

        with lock:
            print(
                f"[START] core={core} task={task_number}/{total_tasks} "
                f"{task.benchmark} {task.config.name}",
                flush=True,
            )

        started = time.monotonic()
        return_code = run_task(
            task=task,
            pin_exe=pin_exe,
            pintool=pintool,
            core=core,
            work_mode=args.work_mode,
            scratch_root=scratch_root,
            force=args.force,
            timeout=args.timeout,
            dry_run=args.dry_run,
        )
        elapsed = time.monotonic() - started
        parsed = parse_raw_output(task.raw_output)

        with lock:
            completed[0] += 1
            if return_code == 0:
                if parsed is not None:
                    detail = f"ipc={parsed.ipc:.6f}"
                else:
                    detail = "dry-run" if args.dry_run else "no parsed stats yet"
                print(
                    f"[DONE]  core={core} done={completed[0]}/{total_tasks} "
                    f"{task.benchmark} {task.config.name} elapsed={elapsed:.1f}s {detail}",
                    flush=True,
                )
            else:
                print(
                    f"[FAIL]  core={core} done={completed[0]}/{total_tasks} "
                    f"{task.benchmark} {task.config.name} rc={return_code} elapsed={elapsed:.1f}s",
                    flush=True,
                )
        if queue_item:
            task_queue.task_done()


def run_tasks(
    tasks: list[BenchTask],
    cores: list[int],
    args: argparse.Namespace,
    pin_exe: Path,
    pintool: Path,
    scratch_root: Path,
) -> None:
    task_queue: queue.Queue[tuple[int, BenchTask]] = queue.Queue()
    initial_tasks: dict[int, tuple[int, BenchTask] | None] = {}
    for index, core in enumerate(cores):
        if index < len(tasks):
            initial_tasks[core] = (index + 1, tasks[index])
        else:
            initial_tasks[core] = None

    for index, task in enumerate(tasks[len(cores):], start=len(cores) + 1):
        task_queue.put((index, task))

    lock = threading.Lock()
    completed = [0]
    threads = [
        threading.Thread(
            target=worker_loop,
            args=(core, initial_tasks[core], task_queue, len(tasks), completed, lock, args, pin_exe, pintool, scratch_root),
            daemon=False,
        )
        for core in cores
    ]

    print(f"Launching {len(threads)} taskset workers on cores: {','.join(str(core) for core in cores)}", flush=True)
    print(f"Total benchmark/configuration tasks: {len(tasks)}", flush=True)
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Assignment 2 section 4.2 L2-cache sweep.")
    parser.add_argument("--cores", default="0-7", help="Comma/range core list for taskset workers. Default: 0-7")
    parser.add_argument("--benchmarks", default=None, help="Comma-separated benchmark subset for debugging.")
    parser.add_argument("--force", action="store_true", help="Rerun even if parseable output already exists.")
    parser.add_argument("--dry-run", action="store_true", help="Print taskset commands without running simulations.")
    parser.add_argument("--list-configs", action="store_true", help="Print required L2 configurations and exit.")
    parser.add_argument("--summarize-only", action="store_true", help="Regenerate summaries from existing raw outputs.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of tasks, intended only for dry-run/debugging.")
    parser.add_argument("--timeout", type=int, default=None, help="Per-task timeout in seconds.")
    parser.add_argument("--work-mode", choices=("scratch", "in-place"), default="scratch")
    parser.add_argument("--scratch-root", type=Path, default=None)
    parser.add_argument("--pin", type=Path, default=None, help="PIN executable path override.")
    parser.add_argument("--pintool", type=Path, default=None, help="simulator.so path override.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = repo_root_from_script()
    helpcode_dir = repo_root / "exercises" / "2nd" / "advcomparch-ex2-helpcode"
    output_root = repo_root / "exercises" / "2nd" / "benchmarks" / "4.2"
    scratch_root = args.scratch_root or (output_root / ".scratch")

    configs = l2_configs()
    if args.list_configs:
        print("Section 4.2 L2 configurations:")
        for config in configs:
            print(f"- {config.name}: size={config.l2_size_kb}KB assoc={config.l2_associativity} block={config.l2_block_size_b}B")
        print(f"Total configurations: {len(configs)}")
        print(f"Total runs for 7 benchmarks: {len(configs) * len(BENCHMARK_ORDER)}")
        return 0

    cores = parse_core_list(args.cores)
    benchmarks = selected_benchmarks(args.benchmarks)
    tasks = discover_tasks(helpcode_dir, output_root, benchmarks)
    if args.limit is not None:
        if args.limit <= 0:
            raise ValueError("--limit must be positive")
        tasks = tasks[: args.limit]

    pin_exe = args.pin or (
        repo_root
        / "exercises"
        / "1st"
        / "pin-external-4.2-99776-g21d818fa2-gcc-linux"
        / "pin"
    )
    pintool = args.pintool or (helpcode_dir / "pintool" / "obj-intel64" / "simulator.so")

    if not args.dry_run and not args.summarize_only:
        if shutil.which("taskset") is None:
            raise FileNotFoundError("taskset is required but was not found in PATH")
        if not pin_exe.is_file():
            raise FileNotFoundError(f"missing PIN executable: {pin_exe}")
        if not pintool.is_file():
            raise FileNotFoundError(f"missing simulator pintool: {pintool}")

    if not args.dry_run:
        ensure_output_dirs(tasks, output_root)

    if not args.summarize_only:
        run_tasks(tasks, cores, args, pin_exe, pintool, scratch_root)

    if args.dry_run:
        print("Dry run complete; no simulations or summaries were written.")
        return 0

    parsed, missing = summarize(tasks, output_root)
    print(f"Summary written under {output_root}")
    print(f"Parsed outputs: {parsed}")
    print(f"Missing/unparseable outputs: {missing}")

    if missing and not args.dry_run:
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        raise SystemExit(130)
