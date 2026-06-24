#!/usr/bin/env python3
"""Run and summarize Assignment 3 section 4.1 real-machine experiments."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from exercise3_common import (
    REAL_TIME_RE,
    VALIDATION_RE,
    format_float,
    parse_implementations,
    parse_int_list,
    read_text,
    repo_root_from_script,
    shell_join,
    write_csv,
)


DEFAULT_THREAD_COUNTS = [1, 2, 4, 8, 16]
DEFAULT_GRAIN_SIZES = [1, 10, 100]

RAW_FIELDS = [
    "implementation",
    "nthreads",
    "iterations",
    "grain",
    "repeat",
    "cpu_ids",
    "runtime_seconds",
    "validation_value",
    "stdout_log",
    "stderr_log",
]

SUMMARY_FIELDS = [
    "implementation",
    "nthreads",
    "iterations",
    "grain",
    "repeats",
    "cpu_ids",
    "median_runtime_seconds",
    "mean_runtime_seconds",
    "min_runtime_seconds",
    "max_runtime_seconds",
    "stdev_runtime_seconds",
]


@dataclass(frozen=True)
class PhysicalCpu:
    representative: int
    siblings: tuple[int, ...]
    core: int
    socket: int


@dataclass(frozen=True)
class RealRunSpec:
    implementation: str
    nthreads: int
    iterations: int
    grain: int
    repeat: int
    cpu_ids: tuple[int, ...]
    stdout_log: Path
    stderr_log: Path


WINDOWS_CORE_TOPOLOGY_SCRIPT = r"""
$code = @"
using System;
using System.Runtime.InteropServices;

public static class CpuTopo {
  [DllImport("kernel32.dll", SetLastError=true)]
  static extern bool GetLogicalProcessorInformationEx(
    int relationshipType, IntPtr buffer, ref int returnedLength);

  public static void Main() {
    int len = 0;
    GetLogicalProcessorInformationEx(0, IntPtr.Zero, ref len);
    IntPtr buf = Marshal.AllocHGlobal(len);
    try {
      if (!GetLogicalProcessorInformationEx(0, buf, ref len)) {
        Console.Error.WriteLine(
          "GetLogicalProcessorInformationEx failed: "
          + Marshal.GetLastWin32Error());
        Environment.Exit(1);
      }
      long ptr = buf.ToInt64();
      long end = ptr + len;
      int index = 0;
      while (ptr < end) {
        int rel = Marshal.ReadInt32(new IntPtr(ptr));
        int size = Marshal.ReadInt32(new IntPtr(ptr + 4));
        if (rel == 0) {
          byte flags = Marshal.ReadByte(new IntPtr(ptr + 8));
          byte efficiency = Marshal.ReadByte(new IntPtr(ptr + 9));
          ushort groupCount =
            (ushort)Marshal.ReadInt16(new IntPtr(ptr + 30));
          for (int g = 0; g < groupCount; g++) {
            long ga = ptr + 32 + g * 16;
            ulong mask = (ulong)Marshal.ReadInt64(new IntPtr(ga));
            ushort group = (ushort)Marshal.ReadInt16(new IntPtr(ga + 8));
            Console.WriteLine(string.Format(
              "{0},{1},{2},{3},{4:X}",
              index, flags, efficiency, group, mask));
          }
          index++;
        }
        ptr += size;
      }
    } finally {
      Marshal.FreeHGlobal(buf);
    }
  }
}
"@
Add-Type -TypeDefinition $code
[CpuTopo]::Main()
"""


def cpu_ids_from_mask(mask: int) -> tuple[int, ...]:
    return tuple(cpu for cpu in range(mask.bit_length()) if mask & (1 << cpu))


def is_wsl() -> bool:
    for path in (Path("/proc/sys/kernel/osrelease"), Path("/proc/version")):
        try:
            if "microsoft" in path.read_text(encoding="utf-8").lower():
                return True
        except FileNotFoundError:
            pass
    return False


def discover_physical_cpus_from_lscpu() -> list[PhysicalCpu]:
    completed = subprocess.run(
        ["lscpu", "--parse=CPU,CORE,SOCKET,ONLINE"],
        check=True,
        capture_output=True,
        text=True,
    )
    allowed = set(os.sched_getaffinity(0))
    groups: dict[tuple[int, int], list[int]] = {}
    for line in completed.stdout.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        cpu_raw, core_raw, socket_raw, online_raw = stripped.split(",")
        cpu = int(cpu_raw)
        if online_raw != "Y" or cpu not in allowed:
            continue
        key = (int(socket_raw), int(core_raw))
        groups.setdefault(key, []).append(cpu)

    physical = [
        PhysicalCpu(
            representative=min(cpus),
            siblings=tuple(sorted(cpus)),
            core=core,
            socket=socket,
        )
        for (socket, core), cpus in groups.items()
    ]
    # On hybrid CPUs, SMT-capable performance cores are used first for the
    # smaller thread-count experiments, followed by single-threaded cores.
    physical.sort(key=lambda item: (-len(item.siblings), item.representative))
    if not physical:
        raise RuntimeError("no online physical CPUs discovered through lscpu")
    return physical


def discover_physical_cpus_from_windows() -> list[PhysicalCpu]:
    if not is_wsl() or shutil.which("powershell.exe") is None:
        return []

    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            WINDOWS_CORE_TOPOLOGY_SCRIPT,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return []

    physical: list[PhysicalCpu] = []
    for line in completed.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split(",")
        if len(parts) != 5:
            return []
        core_raw, _flags_raw, _efficiency_raw, group_raw, mask_raw = parts
        if int(group_raw) != 0:
            return []
        siblings = cpu_ids_from_mask(int(mask_raw, 16))
        if not siblings:
            return []
        physical.append(
            PhysicalCpu(
                representative=min(siblings),
                siblings=siblings,
                core=int(core_raw),
                socket=0,
            )
        )

    allowed = set(os.sched_getaffinity(0))
    discovered = {cpu for item in physical for cpu in item.siblings}
    if discovered != allowed:
        return []
    physical.sort(key=lambda item: (-len(item.siblings), item.representative))
    return physical


def discover_physical_cpus() -> list[PhysicalCpu]:
    physical = discover_physical_cpus_from_lscpu()
    windows_physical = discover_physical_cpus_from_windows()
    if len(windows_physical) > len(physical):
        return windows_physical
    return physical


def parse_existing_run(spec: RealRunSpec) -> tuple[float, int] | None:
    stdout_text = read_text(spec.stdout_log)
    validation = VALIDATION_RE.search(stdout_text)
    runtime = REAL_TIME_RE.search(stdout_text)
    expected = spec.nthreads * spec.iterations
    if not validation or not runtime or int(validation.group(1)) != expected:
        return None
    return float(runtime.group(1)), int(validation.group(1))


def real_binary(binary_dir: Path, implementation: str) -> Path:
    return binary_dir / f"locks_{implementation}_real"


def discover_specs(
    output_root: Path,
    implementations: list[str],
    thread_counts: list[int],
    grain_sizes: list[int],
    iterations: int,
    repeats: int,
    cpu_ids: list[int],
) -> list[RealRunSpec]:
    specs: list[RealRunSpec] = []
    for grain in grain_sizes:
        for nthreads in thread_counts:
            selected_cpus = tuple(cpu_ids[:nthreads])
            for implementation in implementations:
                run_dir = (
                    output_root
                    / "raw"
                    / implementation
                    / f"threads_{nthreads}"
                    / f"grain_{grain}"
                )
                for repeat in range(1, repeats + 1):
                    specs.append(
                        RealRunSpec(
                            implementation=implementation,
                            nthreads=nthreads,
                            iterations=iterations,
                            grain=grain,
                            repeat=repeat,
                            cpu_ids=selected_cpus,
                            stdout_log=run_dir / f"repeat_{repeat}.stdout.txt",
                            stderr_log=run_dir / f"repeat_{repeat}.stderr.txt",
                        )
                    )
    return specs


def execute_run(
    spec: RealRunSpec,
    binary_dir: Path,
    force: bool,
    timeout: int | None,
    dry_run: bool,
) -> int:
    existing = parse_existing_run(spec)
    if existing is not None and not force:
        print(
            f"SKIP {spec.implementation} threads={spec.nthreads} "
            f"grain={spec.grain} repeat={spec.repeat}"
        )
        return 0

    binary = real_binary(binary_dir, spec.implementation)
    command = [
        str(binary),
        str(spec.nthreads),
        str(spec.iterations),
        str(spec.grain),
    ]
    cpu_list = ",".join(map(str, spec.cpu_ids))
    if dry_run:
        print(
            f"DRY-RUN LOCKS_CPU_LIST={cpu_list} {shell_join(command)} "
            f"# repeat {spec.repeat}"
        )
        return 0

    spec.stdout_log.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["LOCKS_CPU_LIST"] = cpu_list
    try:
        with (
            spec.stdout_log.open("w", encoding="utf-8") as stdout_handle,
            spec.stderr_log.open("w", encoding="utf-8") as stderr_handle,
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
    except subprocess.TimeoutExpired:
        print(f"ERROR timeout: {spec.stdout_log}")
        return 124

    parsed = parse_existing_run(spec)
    if completed.returncode != 0 or parsed is None:
        print(f"ERROR failed/unparseable: {spec.stdout_log}")
        return completed.returncode or 1
    runtime, _ = parsed
    print(
        f"PASS {spec.implementation} threads={spec.nthreads} "
        f"grain={spec.grain} repeat={spec.repeat}: {runtime:.6f}s"
    )
    return 0


def run_warmup(
    implementation: str,
    nthreads: int,
    iterations: int,
    grain: int,
    cpu_ids: list[int],
    binary_dir: Path,
    repeat: int,
    timeout: int | None,
    dry_run: bool,
) -> int:
    command = [
        str(real_binary(binary_dir, implementation)),
        str(nthreads),
        str(iterations),
        str(grain),
    ]
    cpu_list = ",".join(map(str, cpu_ids[:nthreads]))
    if dry_run:
        print(
            f"DRY-RUN warmup {repeat}: LOCKS_CPU_LIST={cpu_list} "
            f"{shell_join(command)}"
        )
        return 0
    env = os.environ.copy()
    env["LOCKS_CPU_LIST"] = cpu_list
    try:
        completed = subprocess.run(
            command,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        print(
            f"ERROR warmup timeout: {implementation} "
            f"threads={nthreads} grain={grain} repeat={repeat}"
        )
        return 124
    return completed.returncode


def write_machine_info(output_root: Path, physical: list[PhysicalCpu]) -> None:
    lscpu_text = subprocess.run(
        ["lscpu"], check=True, capture_output=True, text=True
    ).stdout
    data = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "sched_affinity": sorted(os.sched_getaffinity(0)),
        "physical_cores_available": len(physical),
        "physical_cpu_mapping": [
            {
                "representative": cpu.representative,
                "siblings": list(cpu.siblings),
                "core": cpu.core,
                "socket": cpu.socket,
            }
            for cpu in physical
        ],
        "lscpu": lscpu_text,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "machine.json").write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )


def write_summaries(specs: list[RealRunSpec], output_root: Path) -> tuple[int, int]:
    raw_rows: list[dict[str, str]] = []
    missing: list[RealRunSpec] = []
    for spec in specs:
        parsed = parse_existing_run(spec)
        if parsed is None:
            missing.append(spec)
            continue
        runtime, validation_value = parsed
        raw_rows.append(
            {
                "implementation": spec.implementation,
                "nthreads": str(spec.nthreads),
                "iterations": str(spec.iterations),
                "grain": str(spec.grain),
                "repeat": str(spec.repeat),
                "cpu_ids": ",".join(map(str, spec.cpu_ids)),
                "runtime_seconds": format_float(runtime),
                "validation_value": str(validation_value),
                "stdout_log": str(spec.stdout_log),
                "stderr_log": str(spec.stderr_log),
            }
        )
    raw_rows.sort(
        key=lambda row: (
            int(row["grain"]),
            int(row["nthreads"]),
            row["implementation"],
            int(row["repeat"]),
        )
    )
    write_csv(output_root / "summary_raw.csv", RAW_FIELDS, raw_rows)

    grouped: dict[tuple[str, int, int], list[dict[str, str]]] = {}
    for row in raw_rows:
        key = (
            row["implementation"],
            int(row["nthreads"]),
            int(row["grain"]),
        )
        grouped.setdefault(key, []).append(row)

    summary_rows: list[dict[str, str]] = []
    for (implementation, nthreads, grain), rows in sorted(
        grouped.items(), key=lambda item: (item[0][2], item[0][1], item[0][0])
    ):
        runtimes = [float(row["runtime_seconds"]) for row in rows]
        summary_rows.append(
            {
                "implementation": implementation,
                "nthreads": str(nthreads),
                "iterations": rows[0]["iterations"],
                "grain": str(grain),
                "repeats": str(len(rows)),
                "cpu_ids": rows[0]["cpu_ids"],
                "median_runtime_seconds": format_float(statistics.median(runtimes)),
                "mean_runtime_seconds": format_float(statistics.mean(runtimes)),
                "min_runtime_seconds": format_float(min(runtimes)),
                "max_runtime_seconds": format_float(max(runtimes)),
                "stdev_runtime_seconds": format_float(
                    statistics.stdev(runtimes) if len(runtimes) > 1 else 0.0
                ),
            }
        )
    write_csv(output_root / "summary.csv", SUMMARY_FIELDS, summary_rows)

    txt_path = output_root / "summary.txt"
    with txt_path.open("w", encoding="utf-8") as handle:
        handle.write("Assignment 3 - Section 4.1 Real-Machine Scalability\n")
        handle.write(f"Expected outputs: {len(specs)}\n")
        handle.write(f"Parsed outputs: {len(raw_rows)}\n")
        handle.write(f"Missing/unparseable outputs: {len(missing)}\n\n")
        handle.write(
            f"{'Grain':>5} {'Threads':>7} {'Implementation':<12} "
            f"{'Median (s)':>14} {'Stdev (s)':>14}\n"
        )
        handle.write("-" * 60 + "\n")
        for row in summary_rows:
            handle.write(
                f"{int(row['grain']):>5} {int(row['nthreads']):>7} "
                f"{row['implementation']:<12} "
                f"{row['median_runtime_seconds']:>14} "
                f"{row['stdev_runtime_seconds']:>14}\n"
            )
        if missing:
            handle.write("\nMissing/unparseable runs:\n")
            for spec in missing:
                handle.write(f"- {spec.stdout_log}\n")

    print(f"Wrote {output_root / 'summary_raw.csv'}")
    print(f"Wrote {output_root / 'summary.csv'}")
    print(f"Wrote {txt_path}")
    return len(raw_rows), len(missing)


def parse_args(argv: list[str]) -> argparse.Namespace:
    repo = repo_root_from_script()
    exercise = repo / "exercises" / "3rd"
    helpcode = exercise / "advcomparch-ex3-helpcode"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--implementations")
    parser.add_argument("--thread-counts", default="1,2,4,8,16")
    parser.add_argument("--grain-sizes", default="1,10,100")
    parser.add_argument("--iterations", type=int, default=1_000_000)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--cpu-list")
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--timeout",
        type=int,
        default=0,
        help="seconds per program execution; 0 disables the timeout",
    )
    parser.add_argument("--output-root", type=Path, default=exercise / "benchmarks" / "4.1" / "real")
    parser.add_argument("--helpcode-dir", type=Path, default=helpcode)
    parser.add_argument("--binary-dir", type=Path, default=helpcode / "bin")
    parser.add_argument("--no-build", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--summarize-only", action="store_true")
    parser.add_argument("--list-cpus", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if (
        args.iterations <= 0
        or args.repeats <= 0
        or args.warmups < 0
        or args.timeout < 0
    ):
        raise ValueError(
            "iterations/repeats must be positive and timeout must be non-negative"
        )
    timeout = None if args.timeout == 0 else args.timeout

    physical = discover_physical_cpus()
    discovered_ids = [cpu.representative for cpu in physical]
    cpu_ids = parse_int_list(args.cpu_list) if args.cpu_list else discovered_ids
    unavailable = sorted(set(cpu_ids) - set(os.sched_getaffinity(0)))
    if unavailable:
        raise ValueError(
            "requested logical CPUs outside this process's allowed affinity: "
            + ",".join(map(str, unavailable))
        )

    if args.list_cpus:
        for index, cpu in enumerate(physical):
            print(
                f"{index:>2}: cpu={cpu.representative} "
                f"socket={cpu.socket} core={cpu.core} "
                f"siblings={','.join(map(str, cpu.siblings))}"
            )
        print("Selected representatives:", ",".join(map(str, cpu_ids)))
        return 0

    implementations = parse_implementations(args.implementations)
    thread_counts = parse_int_list(args.thread_counts)
    grain_sizes = parse_int_list(args.grain_sizes)
    if any(value <= 0 for value in thread_counts + grain_sizes):
        raise ValueError("thread counts and grain sizes must be positive")
    if max(thread_counts) > len(cpu_ids):
        raise ValueError(
            f"requested {max(thread_counts)} threads but only {len(cpu_ids)} "
            "physical-core CPU representatives are available"
        )

    specs = discover_specs(
        args.output_root,
        implementations,
        thread_counts,
        grain_sizes,
        args.iterations,
        args.repeats,
        cpu_ids,
    )
    if args.limit is not None:
        specs = specs[: args.limit]

    if args.summarize_only:
        _, missing = write_summaries(specs, args.output_root)
        return 1 if missing else 0

    build_command = ["make", "-C", str(args.helpcode_dir), "real"]
    if not args.no_build:
        if args.dry_run:
            print(f"DRY-RUN build: {shell_join(build_command)}")
        else:
            subprocess.run(build_command, check=True)

    if not args.dry_run:
        missing_binaries = [
            real_binary(args.binary_dir, implementation)
            for implementation in implementations
            if not real_binary(args.binary_dir, implementation).is_file()
        ]
        if missing_binaries:
            raise FileNotFoundError(
                "missing real binaries: " + ", ".join(map(str, missing_binaries))
            )
        write_machine_info(args.output_root, physical)

    failures = 0
    warmed: set[tuple[str, int, int]] = set()
    for spec in specs:
        warmup_key = (spec.implementation, spec.nthreads, spec.grain)
        if warmup_key not in warmed:
            key_specs = [
                item
                for item in specs
                if (item.implementation, item.nthreads, item.grain) == warmup_key
            ]
            all_key_outputs_exist = (
                not args.force
                and not args.dry_run
                and all(parse_existing_run(item) is not None for item in key_specs)
            )
            if not all_key_outputs_exist:
                for repeat in range(1, args.warmups + 1):
                    status = run_warmup(
                        spec.implementation,
                        spec.nthreads,
                        spec.iterations,
                        spec.grain,
                        cpu_ids,
                        args.binary_dir,
                        repeat,
                        timeout,
                        args.dry_run,
                    )
                    failures += status != 0
            warmed.add(warmup_key)
        failures += (
            execute_run(
                spec,
                args.binary_dir,
                args.force,
                timeout,
                args.dry_run,
            )
            != 0
        )

    if not args.dry_run:
        _, missing = write_summaries(specs, args.output_root)
        failures += missing
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
