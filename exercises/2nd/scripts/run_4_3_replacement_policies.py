#!/usr/bin/env python3
"""Run and summarize Assignment 2 section 4.3 replacement-policy experiments.

The script uses the best L2 configuration for each capacity group from the
section 4.2 summary, then runs every selected replacement policy on all seven
SPEC CPU2006 benchmarks. By default it uses one worker per core in the --cores
list and launches every benchmark/configuration/policy through taskset.

Outputs:
  - raw pintool output in benchmarks/4.3/raw/<policy>/<benchmark>/<config>.out
  - application stdout/stderr logs in benchmarks/4.3/logs/<policy>/<benchmark>/
  - per-run timing logs in benchmarks/4.3/times/<policy>/<benchmark>/
  - aggregate CSV/text summaries in benchmarks/4.3/

Benchmarks run from temporary scratch copies by default. This keeps SPEC
command redirections from modifying tracked helper-code files.
"""

from __future__ import annotations

import argparse
import csv
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

from run_4_2_l2_sweep import (
    BENCHMARK_ORDER,
    L1_ASSOCIATIVITY,
    L1_BLOCK_SIZE,
    L1_SIZE_KB,
    CacheConfig,
    ParsedResult,
    mpki,
    parse_core_list,
    parse_raw_output,
    percent,
    prepare_work_dir,
    read_speccmd,
    repo_root_from_script,
    selected_benchmarks,
    shell_quote,
    write_csv,
)


POLICY_ORDER = ["LRU", "MRU", "Random", "LFU", "LIP", "SRRIP"]
POLICY_BY_LOWER = {policy.lower(): policy for policy in POLICY_ORDER}
CONFIG_NAME_RE = re.compile(r"^L2_(\d+)KB_A(\d+)_B(\d+)$")

SUMMARY_FIELDS = [
    "policy",
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

BY_POLICY_FIELDS = [
    "policy",
    "runs",
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

BY_CONFIG_POLICY_FIELDS = [
    "config",
    "policy",
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

BEST_BY_CONFIG_FIELDS = [
    "config",
    "l2_size_kb",
    "best_policy_by_aggregate_ipc",
    "best_aggregate_ipc",
    "best_arithmetic_mean_ipc",
    "worst_policy_by_aggregate_ipc",
    "worst_aggregate_ipc",
    "ipc_range",
]


@dataclass(frozen=True)
class BenchTask:
    policy: str
    benchmark: str
    source_dir: Path
    command: str
    config: CacheConfig
    raw_output: Path
    stdout_log: Path
    stderr_log: Path
    time_log: Path


def parse_config_name(raw: str) -> CacheConfig:
    match = CONFIG_NAME_RE.match(raw.strip())
    if not match:
        raise ValueError(f"invalid config name {raw!r}; expected L2_<size>KB_A<assoc>_B<block>")
    return CacheConfig(
        l2_size_kb=int(match.group(1)),
        l2_associativity=int(match.group(2)),
        l2_block_size_b=int(match.group(3)),
    )


def parse_selected_configs(raw: str) -> list[CacheConfig]:
    configs = [parse_config_name(item) for item in raw.split(",") if item.strip()]
    if not configs:
        raise ValueError("--selected-configs did not contain any configurations")

    seen: set[str] = set()
    deduped: list[CacheConfig] = []
    for config in configs:
        if config.name not in seen:
            seen.add(config.name)
            deduped.append(config)
    return deduped


def parse_policies(raw: str | None) -> list[str]:
    if raw is None:
        return POLICY_ORDER
    policies: list[str] = []
    for item in raw.split(","):
        key = item.strip().lower()
        if not key:
            continue
        if key not in POLICY_BY_LOWER:
            raise ValueError(f"unknown replacement policy {item!r}; valid choices: {', '.join(POLICY_ORDER)}")
        policy = POLICY_BY_LOWER[key]
        if policy not in policies:
            policies.append(policy)
    if not policies:
        raise ValueError("--policies did not contain any policies")
    return policies


def select_configs_from_4_2(summary_path: Path, metric: str) -> list[CacheConfig]:
    if not summary_path.is_file():
        raise FileNotFoundError(
            f"missing 4.2 summary: {summary_path}. Run section 4.2 first or pass --selected-configs."
        )

    rows: list[dict[str, str]] = []
    with summary_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or metric not in reader.fieldnames:
            fields = ", ".join(reader.fieldnames or [])
            raise ValueError(f"metric {metric!r} is not present in {summary_path}; available fields: {fields}")
        for row in reader:
            rows.append(row)

    grouped: dict[int, list[dict[str, str]]] = {}
    for row in rows:
        try:
            grouped.setdefault(int(row["l2_size_kb"]), []).append(row)
        except (KeyError, ValueError) as exc:
            raise ValueError(f"invalid 4.2 summary row: {row}") from exc

    selected: list[CacheConfig] = []
    for size_kb in (256, 512, 1024, 2048):
        if size_kb not in grouped:
            raise ValueError(f"4.2 summary does not contain any rows for L2 size {size_kb}KB")
        best = max(grouped[size_kb], key=lambda row: float(row[metric]))
        selected.append(
            CacheConfig(
                l2_size_kb=int(best["l2_size_kb"]),
                l2_associativity=int(best["l2_associativity"]),
                l2_block_size_b=int(best["l2_block_size_b"]),
            )
        )
    return selected


def discover_tasks(
    helpcode_dir: Path,
    output_root: Path,
    benchmarks: list[str],
    configs: list[CacheConfig],
    policies: list[str],
) -> list[BenchTask]:
    input_base = helpcode_dir / "spec_benchmarks"
    if not input_base.is_dir():
        raise FileNotFoundError(f"missing benchmark directory: {input_base}")

    tasks: list[BenchTask] = []
    for config in configs:
        for policy in policies:
            for benchmark in benchmarks:
                source_dir = input_base / benchmark
                if not source_dir.is_dir():
                    raise FileNotFoundError(f"missing benchmark directory: {source_dir}")

                tasks.append(
                    BenchTask(
                        policy=policy,
                        benchmark=benchmark,
                        source_dir=source_dir,
                        command=read_speccmd(source_dir),
                        config=config,
                        raw_output=output_root / "raw" / policy / benchmark / f"{config.name}.out",
                        stdout_log=output_root / "logs" / policy / benchmark / f"{config.name}.stdout.txt",
                        stderr_log=output_root / "logs" / policy / benchmark / f"{config.name}.stderr.txt",
                        time_log=output_root / "times" / policy / benchmark / f"{config.name}.time.txt",
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


def build_pin_command(task: BenchTask, pin_exe: Path, pintool: Path, core: int) -> str:
    inner = (
        f"{shell_quote(pin_exe)} -t {shell_quote(pintool)} "
        f"-o {shell_quote(task.raw_output.resolve())} "
        f"-L1c {L1_SIZE_KB} -L1a {L1_ASSOCIATIVITY} -L1b {L1_BLOCK_SIZE} "
        f"-L2c {task.config.l2_size_kb} "
        f"-L2a {task.config.l2_associativity} "
        f"-L2b {task.config.l2_block_size_b} "
        f"-repl {shlex.quote(task.policy)} -- "
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
            f"[SKIP] core={core} {task.benchmark} {task.config.name} {task.policy} "
            f"existing parseable output ipc={existing.ipc:.6f}",
            flush=True,
        )
        return 0

    command = build_pin_command(task, pin_exe, pintool, core)
    if dry_run:
        print(
            f"[DRY] core={core} {task.benchmark} {task.config.name} {task.policy}\n"
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
                    f"policy={task.policy}",
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


def summary_row(task: BenchTask, parsed: ParsedResult) -> dict[str, str | int | float]:
    return {
        "policy": task.policy,
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
    rows.sort(key=lambda row: (str(row["config"]), str(row["policy"]), str(row["benchmark"])))
    write_csv(output_root / "summary.csv", SUMMARY_FIELDS, rows)

    by_policy_rows = summarize_by_policy(parsed_by_task)
    write_csv(output_root / "summary_by_policy.csv", BY_POLICY_FIELDS, by_policy_rows)

    by_config_policy_rows = summarize_by_config_policy(parsed_by_task)
    write_csv(output_root / "summary_by_config_policy.csv", BY_CONFIG_POLICY_FIELDS, by_config_policy_rows)

    best_by_config_rows = summarize_best_by_config(by_config_policy_rows)
    write_csv(output_root / "summary_best_policy_by_config.csv", BEST_BY_CONFIG_FIELDS, best_by_config_rows)

    write_text_summary(
        output_root / "summary.txt",
        tasks,
        parsed_by_task,
        missing,
        by_policy_rows,
        by_config_policy_rows,
        best_by_config_rows,
    )
    return len(parsed_by_task), len(missing)


def aggregate_row(policy: str, items: list[tuple[BenchTask, ParsedResult]]) -> dict[str, object]:
    total_instructions = sum(parsed.total_instructions for _, parsed in items)
    total_cycles = sum(parsed.total_cycles for _, parsed in items)
    total_l1_misses = sum(parsed.l1_misses for _, parsed in items)
    total_l2_misses = sum(parsed.l2_misses for _, parsed in items)
    mean_ipc = sum(parsed.ipc for _, parsed in items) / len(items)
    mean_l1_mpki = sum(mpki(parsed.l1_misses, parsed.total_instructions) for _, parsed in items) / len(items)
    mean_l2_mpki = sum(mpki(parsed.l2_misses, parsed.total_instructions) for _, parsed in items) / len(items)
    return {
        "policy": policy,
        "runs": len(items),
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


def summarize_by_policy(parsed_by_task: list[tuple[BenchTask, ParsedResult]]) -> list[dict[str, object]]:
    grouped: dict[str, list[tuple[BenchTask, ParsedResult]]] = {}
    for task, parsed in parsed_by_task:
        grouped.setdefault(task.policy, []).append((task, parsed))

    rows = [aggregate_row(policy, items) for policy, items in grouped.items()]
    rows.sort(key=lambda row: (-float(row["aggregate_ipc"]), POLICY_ORDER.index(str(row["policy"]))))
    return rows


def summarize_by_config_policy(parsed_by_task: list[tuple[BenchTask, ParsedResult]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[tuple[BenchTask, ParsedResult]]] = {}
    for task, parsed in parsed_by_task:
        grouped.setdefault((task.config.name, task.policy), []).append((task, parsed))

    rows: list[dict[str, object]] = []
    for (config_name, policy), items in sorted(grouped.items()):
        config = items[0][0].config
        row = aggregate_row(policy, items)
        row.update(
            {
                "config": config_name,
                "l2_size_kb": config.l2_size_kb,
                "l2_associativity": config.l2_associativity,
                "l2_block_size_b": config.l2_block_size_b,
                "benchmarks": row.pop("runs"),
            }
        )
        rows.append(row)

    rows.sort(key=lambda row: (int(row["l2_size_kb"]), str(row["config"]), -float(row["aggregate_ipc"])))
    return rows


def summarize_best_by_config(by_config_policy_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in by_config_policy_rows:
        grouped.setdefault(str(row["config"]), []).append(row)

    rows: list[dict[str, object]] = []
    for config_name, items in sorted(grouped.items(), key=lambda item: int(item[1][0]["l2_size_kb"])):
        best = max(items, key=lambda row: float(row["aggregate_ipc"]))
        worst = min(items, key=lambda row: float(row["aggregate_ipc"]))
        rows.append(
            {
                "config": config_name,
                "l2_size_kb": best["l2_size_kb"],
                "best_policy_by_aggregate_ipc": best["policy"],
                "best_aggregate_ipc": best["aggregate_ipc"],
                "best_arithmetic_mean_ipc": best["arithmetic_mean_ipc"],
                "worst_policy_by_aggregate_ipc": worst["policy"],
                "worst_aggregate_ipc": worst["aggregate_ipc"],
                "ipc_range": f"{float(best['aggregate_ipc']) - float(worst['aggregate_ipc']):.9f}",
            }
        )
    return rows


def write_text_summary(
    path: Path,
    tasks: list[BenchTask],
    parsed_by_task: list[tuple[BenchTask, ParsedResult]],
    missing: list[BenchTask],
    by_policy_rows: list[dict[str, object]],
    by_config_policy_rows: list[dict[str, object]],
    best_by_config_rows: list[dict[str, object]],
) -> None:
    lines: list[str] = []
    lines.append("Assignment 2 - Section 4.3 Replacement Policy Study")
    lines.append(f"Expected outputs: {len(tasks)}")
    lines.append(f"Parsed outputs: {len(parsed_by_task)}")
    lines.append(f"Missing/unparseable outputs: {len(missing)}")
    lines.append("")

    lines.append("Policies by aggregate IPC")
    lines.append(f"{'Policy':10} {'Runs':>5} {'Mean IPC':>12} {'Agg IPC':>12} {'Mean L2 MPKI':>14} {'Agg L2 MPKI':>13}")
    lines.append("-" * 82)
    for row in by_policy_rows:
        lines.append(
            f"{row['policy']:10} "
            f"{int(row['runs']):5d} "
            f"{float(row['arithmetic_mean_ipc']):12.6f} "
            f"{float(row['aggregate_ipc']):12.6f} "
            f"{float(row['arithmetic_mean_l2_mpki']):14.6f} "
            f"{float(row['aggregate_l2_mpki']):13.6f}"
        )
    lines.append("")

    lines.append("Best policy for each selected L2 configuration")
    lines.append(f"{'Config':28} {'Best':>8} {'Best IPC':>12} {'Worst':>8} {'Range':>12}")
    lines.append("-" * 76)
    for row in best_by_config_rows:
        lines.append(
            f"{row['config']:28} "
            f"{row['best_policy_by_aggregate_ipc']:>8} "
            f"{float(row['best_aggregate_ipc']):12.6f} "
            f"{row['worst_policy_by_aggregate_ipc']:>8} "
            f"{float(row['ipc_range']):12.6f}"
        )
    lines.append("")

    lines.append("Per-config/policy aggregate IPC")
    lines.append(f"{'Config':28} {'Policy':10} {'Runs':>5} {'Mean IPC':>12} {'Agg IPC':>12}")
    lines.append("-" * 74)
    for row in by_config_policy_rows:
        lines.append(
            f"{row['config']:28} "
            f"{row['policy']:10} "
            f"{int(row['benchmarks']):5d} "
            f"{float(row['arithmetic_mean_ipc']):12.6f} "
            f"{float(row['aggregate_ipc']):12.6f}"
        )

    if missing:
        lines.append("")
        lines.append("Missing/unparseable outputs")
        for task in missing[:50]:
            lines.append(f"- {task.policy} {task.benchmark} {task.config.name}: {task.raw_output}")
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
                f"{task.benchmark} {task.config.name} {task.policy}",
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
                    f"{task.benchmark} {task.config.name} {task.policy} elapsed={elapsed:.1f}s {detail}",
                    flush=True,
                )
            else:
                print(
                    f"[FAIL]  core={core} done={completed[0]}/{total_tasks} "
                    f"{task.benchmark} {task.config.name} {task.policy} rc={return_code} elapsed={elapsed:.1f}s",
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
    print(f"Total benchmark/configuration/policy tasks: {len(tasks)}", flush=True)
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Assignment 2 section 4.3 replacement-policy study.")
    parser.add_argument("--cores", default="0-7", help="Comma/range core list for taskset workers. Default: 0-7")
    parser.add_argument("--benchmarks", default=None, help="Comma-separated benchmark subset for debugging.")
    parser.add_argument("--policies", default=None, help=f"Comma-separated policies. Default: {','.join(POLICY_ORDER)}")
    parser.add_argument(
        "--selected-configs",
        default=None,
        help="Comma-separated L2 configs, e.g. L2_256KB_A4_B64,L2_512KB_A8_B128.",
    )
    parser.add_argument(
        "--selection-summary",
        type=Path,
        default=None,
        help="Path to 4.2 summary_by_config.csv. Default: exercises/2nd/benchmarks/4.2/summary_by_config.csv",
    )
    parser.add_argument(
        "--selection-metric",
        choices=("aggregate_ipc", "arithmetic_mean_ipc"),
        default="aggregate_ipc",
        help="4.2 summary metric used to select the best config per L2 capacity.",
    )
    parser.add_argument("--print-selected-configs", action="store_true", help="Print selected 4.3 L2 configs and exit.")
    parser.add_argument("--force", action="store_true", help="Rerun even if parseable output already exists.")
    parser.add_argument("--dry-run", action="store_true", help="Print taskset commands without running simulations.")
    parser.add_argument("--list-policies", action="store_true", help="Print supported replacement policies and exit.")
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
    output_root = repo_root / "exercises" / "2nd" / "benchmarks" / "4.3"
    scratch_root = args.scratch_root or (output_root / ".scratch")
    selection_summary = args.selection_summary or (
        repo_root / "exercises" / "2nd" / "benchmarks" / "4.2" / "summary_by_config.csv"
    )

    if args.list_policies:
        print("Section 4.3 replacement policies:")
        for policy in POLICY_ORDER:
            print(f"- {policy}")
        return 0

    policies = parse_policies(args.policies)
    if args.selected_configs:
        configs = parse_selected_configs(args.selected_configs)
    else:
        configs = select_configs_from_4_2(selection_summary, args.selection_metric)

    if args.print_selected_configs:
        print(f"Section 4.3 selected L2 configurations by {args.selection_metric}:")
        for config in configs:
            print(f"- {config.name}: size={config.l2_size_kb}KB assoc={config.l2_associativity} block={config.l2_block_size_b}B")
        print(f"Total configurations: {len(configs)}")
        print(f"Policies: {','.join(policies)}")
        print(f"Total runs for 7 benchmarks: {len(configs) * len(policies) * len(BENCHMARK_ORDER)}")
        return 0

    cores = parse_core_list(args.cores)
    benchmarks = selected_benchmarks(args.benchmarks)
    tasks = discover_tasks(helpcode_dir, output_root, benchmarks, configs, policies)
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

    print("Selected L2 configurations:")
    for config in configs:
        print(f"- {config.name}")
    print(f"Replacement policies: {','.join(policies)}")

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
