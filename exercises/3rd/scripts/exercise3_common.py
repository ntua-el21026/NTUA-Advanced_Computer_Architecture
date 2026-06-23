#!/usr/bin/env python3
"""Shared helpers for Assignment 3 experiment runners."""

from __future__ import annotations

import csv
import math
import os
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


IMPLEMENTATIONS = ("tas_cas", "tas_ts", "ttas_cas", "ttas_ts", "mutex")
IMPLEMENTATION_SET = set(IMPLEMENTATIONS)

VALIDATION_RE = re.compile(r"Validation:\s+PASS\s+\(val=([0-9]+)\)")
REAL_TIME_RE = re.compile(r"Execution time:\s*([0-9.eE+-]+)\s+seconds")
SNIPER_STDOUT_RE = re.compile(
    r"Simulated\s+([0-9.]+[kMGT]?)\s+instructions,\s+"
    r"([0-9.]+[kMGT]?)\s+cycles",
    re.IGNORECASE,
)
TOTAL_POWER_RE = re.compile(
    r"^\s*total\s+([0-9.eE+-]+)\s+W\s+"
    r"([0-9.eE+-]+)\s*([munpfkMGT]?)J\b",
    re.MULTILINE,
)

SUMMARY_FLOAT_DIGITS = 12


@dataclass(frozen=True)
class SniperRunSpec:
    implementation: str
    nthreads: int
    iterations: int
    grain: int
    l2_shared_cores: int
    l3_shared_cores: int
    result_dir: Path
    topology: str = ""


@dataclass(frozen=True)
class SniperMetrics:
    total_instructions: int
    total_cycles: int
    runtime_seconds: float
    validation_value: int
    power_w: float | None
    energy_j: float | None


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[3]


def shell_join(args: Iterable[str | Path]) -> str:
    return shlex.join(str(arg) for arg in args)


def parse_int_list(raw: str) -> list[int]:
    values: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_raw, end_raw = part.split("-", 1)
            start, end = int(start_raw), int(end_raw)
            if start < 0 or end < start:
                raise ValueError(f"invalid integer range: {part}")
            values.extend(range(start, end + 1))
        else:
            value = int(part)
            if value < 0:
                raise ValueError(f"negative value is not allowed: {value}")
            values.append(value)

    deduped = list(dict.fromkeys(values))
    if not deduped:
        raise ValueError("at least one integer value is required")
    return deduped


def parse_implementations(raw: str | None) -> list[str]:
    if raw is None:
        return list(IMPLEMENTATIONS)
    values = [item.strip().lower() for item in raw.split(",") if item.strip()]
    unknown = [item for item in values if item not in IMPLEMENTATION_SET]
    if unknown:
        raise ValueError(
            f"unknown implementation(s): {', '.join(unknown)}; "
            f"valid choices: {', '.join(IMPLEMENTATIONS)}"
        )
    return list(dict.fromkeys(values))


def format_float(value: float | None) -> str:
    if value is None or not math.isfinite(value):
        return ""
    return f"{value:.{SUMMARY_FLOAT_DIGITS}f}"


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def parse_human_number(raw: str) -> float:
    match = re.fullmatch(r"([0-9.]+)([kMGT]?)", raw.strip())
    if not match:
        raise ValueError(f"invalid scaled number: {raw!r}")
    scales = {"": 1.0, "k": 1e3, "M": 1e6, "G": 1e9, "T": 1e12}
    return float(match.group(1)) * scales[match.group(2)]


def parse_simout_row(text: str, label: str) -> list[float]:
    for line in text.splitlines():
        cells = [cell.strip() for cell in line.split("|")]
        if cells and cells[0] == label:
            values: list[float] = []
            for cell in cells[1:]:
                cleaned = cell.replace(",", "")
                try:
                    values.append(float(cleaned))
                except ValueError:
                    continue
            return values
    return []


def parse_frequency_ghz(sim_cfg: Path, default: float = 2.66) -> float:
    text = read_text(sim_cfg)
    in_core_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_core_section = stripped == "[perf_model/core]"
            continue
        if in_core_section:
            match = re.match(r"frequency\s*=\s*([0-9.]+)", stripped)
            if match:
                return float(match.group(1))
    return default


def parse_validation(stdout_text: str, expected: int) -> int | None:
    match = VALIDATION_RE.search(stdout_text)
    if not match:
        return None
    value = int(match.group(1))
    return value if value == expected else None


def parse_power(power_text: str) -> tuple[float | None, float | None]:
    match = TOTAL_POWER_RE.search(power_text)
    if not match:
        return None, None
    scales = {
        "": 1.0,
        "m": 1e-3,
        "u": 1e-6,
        "n": 1e-9,
        "p": 1e-12,
        "f": 1e-15,
        "k": 1e3,
        "M": 1e6,
        "G": 1e9,
        "T": 1e12,
    }
    return float(match.group(1)), float(match.group(2)) * scales[match.group(3)]


def parse_sniper_metrics(result_dir: Path, expected_value: int) -> SniperMetrics | None:
    simout = read_text(result_dir / "sim.out")
    stdout_text = read_text(result_dir / "run.stdout.txt")
    validation_value = parse_validation(stdout_text, expected_value)
    if validation_value is None:
        return None

    instruction_values = parse_simout_row(simout, "Instructions")
    cycle_values = parse_simout_row(simout, "Cycles")
    time_ns_values = parse_simout_row(simout, "Time (ns)")

    total_instructions = int(sum(instruction_values)) if instruction_values else 0
    total_cycles = int(max(cycle_values)) if cycle_values else 0
    runtime_seconds = max(time_ns_values) * 1e-9 if time_ns_values else 0.0

    if total_cycles == 0:
        match = SNIPER_STDOUT_RE.search(stdout_text)
        if match:
            total_instructions = int(parse_human_number(match.group(1)))
            total_cycles = int(parse_human_number(match.group(2)))

    frequency_ghz = parse_frequency_ghz(result_dir / "sim.cfg")
    if runtime_seconds == 0.0 and total_cycles:
        runtime_seconds = total_cycles / (frequency_ghz * 1e9)
    if total_cycles == 0 and runtime_seconds:
        total_cycles = int(runtime_seconds * frequency_ghz * 1e9)

    if total_cycles == 0 or runtime_seconds == 0.0:
        return None

    power_w, energy_j = parse_power(read_text(result_dir / "power.total.out"))
    return SniperMetrics(
        total_instructions=total_instructions,
        total_cycles=total_cycles,
        runtime_seconds=runtime_seconds,
        validation_value=validation_value,
        power_w=power_w,
        energy_j=energy_j,
    )


def sniper_binary(binary_dir: Path, implementation: str) -> Path:
    return binary_dir / f"locks_{implementation}_sniper"


def build_sniper_command(
    spec: SniperRunSpec,
    run_sniper: Path,
    config: Path,
    binary_dir: Path,
) -> list[str]:
    return [
        str(run_sniper),
        "-d",
        str(spec.result_dir),
        "-c",
        str(config),
        "-n",
        str(spec.nthreads),
        "--roi",
        "-c",
        "--traceinput/mirror_output=true",
        "-c",
        "--perf_model/l1_icache/shared_cores=1",
        "-c",
        "--perf_model/l1_dcache/shared_cores=1",
        "-c",
        f"--perf_model/l2_cache/shared_cores={spec.l2_shared_cores}",
        "-c",
        f"--perf_model/l3_cache/shared_cores={spec.l3_shared_cores}",
        "--",
        str(sniper_binary(binary_dir, spec.implementation)),
        str(spec.nthreads),
        str(spec.iterations),
        str(spec.grain),
    ]


def run_sniper_spec(
    spec: SniperRunSpec,
    *,
    run_sniper: Path,
    config: Path,
    binary_dir: Path,
    mcpat_script: Path,
    force: bool,
    timeout: int | None,
    dry_run: bool,
    skip_mcpat: bool,
) -> tuple[int, SniperMetrics | None]:
    expected_value = spec.nthreads * spec.iterations
    existing = parse_sniper_metrics(spec.result_dir, expected_value)
    if existing is not None and not force:
        print(f"SKIP {spec.result_dir}: existing parseable output")
        return 0, existing

    command = build_sniper_command(spec, run_sniper, config, binary_dir)
    if dry_run:
        print(f"DRY-RUN {spec.result_dir}")
        print(f"  {shell_join(command)}")
        return 0, None

    if force and spec.result_dir.exists():
        shutil.rmtree(spec.result_dir)
    spec.result_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = spec.result_dir / "run.stdout.txt"
    stderr_path = spec.result_dir / "run.stderr.txt"
    (spec.result_dir / "command.txt").write_text(
        shell_join(command) + "\n", encoding="utf-8"
    )

    print(
        f"RUN {spec.implementation} threads={spec.nthreads} "
        f"grain={spec.grain} topology={spec.topology or 'scalability'}"
    )
    try:
        env = os.environ.copy()
        env.pop("LOCKS_CPU_LIST", None)
        with (
            stdout_path.open("w", encoding="utf-8") as stdout_handle,
            stderr_path.open("w", encoding="utf-8") as stderr_handle,
        ):
            completed = subprocess.run(
                command,
                env=env,
                stdout=stdout_handle,
                stderr=stderr_handle,
                timeout=timeout,
                check=False,
                text=True,
            )
        returncode = completed.returncode
        (spec.result_dir / "process.returncode.txt").write_text(
            f"{returncode}\n", encoding="utf-8"
        )
    except subprocess.TimeoutExpired:
        (spec.result_dir / "timeout.txt").write_text(
            f"Timed out after {timeout} seconds\n", encoding="utf-8"
        )
        return 124, None

    preliminary = parse_sniper_metrics(spec.result_dir, expected_value)
    if preliminary is None:
        print(f"ERROR unparseable Sniper result: {spec.result_dir}")
        return returncode or 1, None

    if not skip_mcpat:
        power_output = spec.result_dir / "power.total.out"
        power_stderr = spec.result_dir / "power.stderr.txt"
        mcpat_command = [
            str(mcpat_script),
            "-d",
            str(spec.result_dir),
            "-t",
            "total",
            "-o",
            str(spec.result_dir / "power"),
            "--no-graph",
        ]
        with (
            power_output.open("w", encoding="utf-8") as stdout_handle,
            power_stderr.open("w", encoding="utf-8") as stderr_handle,
        ):
            mcpat = subprocess.run(
                mcpat_command,
                stdout=stdout_handle,
                stderr=stderr_handle,
                check=False,
                text=True,
            )
        if mcpat.returncode != 0:
            print(f"ERROR McPAT failed for {spec.result_dir}")
            return mcpat.returncode, None

    metrics = parse_sniper_metrics(spec.result_dir, expected_value)
    if metrics is None:
        return returncode or 1, None

    if returncode != 0:
        print(
            f"ACCEPT nonzero Sniper exit {returncode}: "
            "validation and simulation outputs are complete"
        )
    return 0, metrics


def sniper_summary_row(
    spec: SniperRunSpec,
    metrics: SniperMetrics,
    process_returncode: int | None = None,
) -> dict[str, str]:
    if process_returncode is None:
        try:
            process_returncode = int(
                read_text(spec.result_dir / "process.returncode.txt").strip() or "0"
            )
        except ValueError:
            process_returncode = 0
    energy_j = metrics.energy_j
    edp = energy_j * metrics.runtime_seconds if energy_j is not None else None
    ed2p = (
        energy_j * metrics.runtime_seconds**2 if energy_j is not None else None
    )
    return {
        "topology": spec.topology,
        "implementation": spec.implementation,
        "nthreads": str(spec.nthreads),
        "iterations": str(spec.iterations),
        "grain": str(spec.grain),
        "l2_shared_cores": str(spec.l2_shared_cores),
        "l3_shared_cores": str(spec.l3_shared_cores),
        "total_instructions": str(metrics.total_instructions),
        "total_cycles": str(metrics.total_cycles),
        "runtime_seconds": format_float(metrics.runtime_seconds),
        "power_w": format_float(metrics.power_w),
        "energy_j": format_float(energy_j),
        "edp_j_s": format_float(edp),
        "ed2p_j_s2": format_float(ed2p),
        "validation_value": str(metrics.validation_value),
        "process_returncode": str(process_returncode),
        "result_dir": str(spec.result_dir),
    }


SNIPER_SUMMARY_FIELDS = [
    "topology",
    "implementation",
    "nthreads",
    "iterations",
    "grain",
    "l2_shared_cores",
    "l3_shared_cores",
    "total_instructions",
    "total_cycles",
    "runtime_seconds",
    "power_w",
    "energy_j",
    "edp_j_s",
    "ed2p_j_s2",
    "validation_value",
    "process_returncode",
    "result_dir",
]
