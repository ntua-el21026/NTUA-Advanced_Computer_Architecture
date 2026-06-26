#!/usr/bin/env python3
"""Generate report-ready diagrams from Assignment 3 benchmark summaries."""

from __future__ import annotations

import csv
import json
import math
import textwrap
from pathlib import Path

try:
    import matplotlib
    import numpy as np
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Missing plotting dependencies. Install matplotlib and numpy, for example:\n"
        "  python3 -m pip install matplotlib numpy"
    ) from exc

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch


SCRIPT_DIR = Path(__file__).resolve().parent
BENCHMARK_ROOT = SCRIPT_DIR.parent

IMPLEMENTATION_ORDER = ["tas_cas", "tas_ts", "ttas_cas", "ttas_ts", "mutex"]
IMPLEMENTATION_LABELS = {
    "tas_cas": "TAS-CAS",
    "tas_ts": "TAS-TS",
    "ttas_cas": "TTAS-CAS",
    "ttas_ts": "TTAS-TS",
    "mutex": "Pthread mutex",
}
IMPLEMENTATION_COLORS = {
    "tas_cas": "#4C78A8",
    "tas_ts": "#72B7B2",
    "ttas_cas": "#F58518",
    "ttas_ts": "#54A24B",
    "mutex": "#E45756",
}
IMPLEMENTATION_MARKERS = {
    "tas_cas": "o",
    "tas_ts": "s",
    "ttas_cas": "^",
    "ttas_ts": "D",
    "mutex": "P",
}

THREADS = [1, 2, 4, 8, 16]
GRAINS = [1, 10, 100]
TOPOLOGY_ORDER = ["share-all", "share-l3", "share-nothing"]
TOPOLOGY_LABELS = {
    "share-all": "Share all\nL2=4, L3=4",
    "share-l3": "Share L3\nL2=1, L3=4",
    "share-nothing": "Share nothing\nL2=1, L3=1",
}
TOPOLOGY_COLORS = {
    "share-all": "#4C78A8",
    "share-l3": "#F58518",
    "share-nothing": "#54A24B",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing required summary: {path}")
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def to_float(row: dict[str, str], key: str) -> float:
    value = row.get(key, "")
    if value == "":
        return math.nan
    return float(value)


def to_int(row: dict[str, str], key: str) -> int:
    return int(row[key])


def format_metric(value: float, unit: str = "") -> str:
    if value == 0:
        return f"0{unit}"
    abs_value = abs(value)
    for scale, suffix in ((1e9, "G"), (1e6, "M"), (1e3, "k")):
        if abs_value >= scale:
            return f"{value / scale:.2f}{suffix}{unit}"
    if abs_value < 1e-6:
        return f"{value:.2e}{unit}"
    if abs_value < 1:
        return f"{value:.3f}{unit}"
    return f"{value:.2f}{unit}"


def short_label(label: str, width: int = 14) -> str:
    return "\n".join(textwrap.wrap(label, width=width, break_long_words=False))


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 140,
            "savefig.dpi": 220,
            "font.size": 9,
            "axes.titlesize": 11,
            "axes.labelsize": 9,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": "#D9D9D9",
            "grid.linewidth": 0.6,
            "grid.alpha": 0.85,
            "lines.linewidth": 2.0,
            "lines.markersize": 5.5,
        }
    )


def save_figure(fig: plt.Figure, stem: str) -> None:
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    for suffix in (".pdf", ".png"):
        fig.savefig(SCRIPT_DIR / f"{stem}{suffix}", bbox_inches="tight")
    plt.close(fig)


def implementation_legend(ncols: int = 5) -> list[Line2D]:
    return [
        Line2D(
            [0],
            [0],
            color=IMPLEMENTATION_COLORS[impl],
            marker=IMPLEMENTATION_MARKERS[impl],
            linewidth=2,
            label=IMPLEMENTATION_LABELS[impl],
        )
        for impl in IMPLEMENTATION_ORDER
    ]


def row_lookup(
    rows: list[dict[str, str]], *keys: str
) -> dict[tuple[str, ...], dict[str, str]]:
    lookup: dict[tuple[str, ...], dict[str, str]] = {}
    for row in rows:
        lookup[tuple(row[key] for key in keys)] = row
    return lookup


def validate_inputs(
    sniper_4_1: list[dict[str, str]],
    real_4_1: list[dict[str, str]],
    real_raw_4_1: list[dict[str, str]],
    sniper_4_2: list[dict[str, str]],
) -> None:
    expected_impls = set(IMPLEMENTATION_ORDER)
    expected_threads = {str(value) for value in THREADS}
    expected_grains = {str(value) for value in GRAINS}
    expected_topologies = set(TOPOLOGY_ORDER)

    checks = [
        (
            len(sniper_4_1) == 75,
            f"4.1 Sniper summary must contain 75 rows, found {len(sniper_4_1)}",
        ),
        (
            {row["implementation"] for row in sniper_4_1} == expected_impls,
            "4.1 Sniper implementations do not match the assignment set",
        ),
        (
            {row["nthreads"] for row in sniper_4_1} == expected_threads,
            "4.1 Sniper thread counts do not match 1,2,4,8,16",
        ),
        (
            {row["grain"] for row in sniper_4_1} == expected_grains,
            "4.1 Sniper grain sizes do not match 1,10,100",
        ),
        (
            {row["iterations"] for row in sniper_4_1} == {"1000"},
            "4.1 Sniper iterations must be 1000",
        ),
        (
            {row["process_returncode"] for row in sniper_4_1} == {"0"},
            "4.1 Sniper contains nonzero process return codes",
        ),
        (
            len(real_4_1) == 75,
            f"4.1 real-machine summary must contain 75 rows, found {len(real_4_1)}",
        ),
        (
            len(real_raw_4_1) == 375,
            f"4.1 real-machine raw summary must contain 375 rows, found {len(real_raw_4_1)}",
        ),
        (
            {row["repeats"] for row in real_4_1} == {"5"},
            "4.1 real-machine summary must contain 5 repeats per case",
        ),
        (
            {row["implementation"] for row in real_4_1} == expected_impls,
            "4.1 real-machine implementations do not match the assignment set",
        ),
        (
            {row["nthreads"] for row in real_4_1} == expected_threads,
            "4.1 real-machine thread counts do not match 1,2,4,8,16",
        ),
        (
            {row["grain"] for row in real_4_1} == expected_grains,
            "4.1 real-machine grain sizes do not match 1,10,100",
        ),
        (
            len(sniper_4_2) == 15,
            f"4.2 Sniper summary must contain 15 rows, found {len(sniper_4_2)}",
        ),
        (
            {row["topology"] for row in sniper_4_2} == expected_topologies,
            "4.2 topologies do not match share-all/share-l3/share-nothing",
        ),
        (
            {row["implementation"] for row in sniper_4_2} == expected_impls,
            "4.2 implementations do not match the assignment set",
        ),
        (
            {row["nthreads"] for row in sniper_4_2} == {"4"}
            and {row["iterations"] for row in sniper_4_2} == {"1000"}
            and {row["grain"] for row in sniper_4_2} == {"1"},
            "4.2 must use nthreads=4, iterations=1000, grain=1",
        ),
        (
            {row["process_returncode"] for row in sniper_4_2} == {"0"},
            "4.2 Sniper contains nonzero process return codes",
        ),
    ]
    failures = [message for ok, message in checks if not ok]
    if failures:
        raise ValueError("Input validation failed:\n- " + "\n- ".join(failures))


def plot_4_1_sniper_cycles_required(rows: list[dict[str, str]]) -> None:
    lookup = row_lookup(rows, "implementation", "nthreads", "grain")
    for grain in GRAINS:
        fig, ax = plt.subplots(figsize=(8.2, 5.0))
        for impl in IMPLEMENTATION_ORDER:
            y = [
                to_float(lookup[(impl, str(thread), str(grain))], "total_cycles")
                for thread in THREADS
            ]
            ax.plot(
                THREADS,
                y,
                marker=IMPLEMENTATION_MARKERS[impl],
                color=IMPLEMENTATION_COLORS[impl],
                label=IMPLEMENTATION_LABELS[impl],
            )
        ax.set_title(f"4.1 Sniper scalability - grain size {grain}")
        ax.set_xlabel("Threads / simulated cores")
        ax.set_ylabel("ROI execution time (cycles)")
        ax.set_xticks(THREADS, THREADS)
        ax.grid(axis="both")
        ax.legend(frameon=False, ncols=3, loc="upper left")
        save_figure(fig, f"4_1_sniper_cycles_grain_{grain}")


def plot_4_1_real_runtime_required(rows: list[dict[str, str]]) -> None:
    lookup = row_lookup(rows, "implementation", "nthreads", "grain")
    for grain in GRAINS:
        fig, ax = plt.subplots(figsize=(8.2, 5.0))
        for impl in IMPLEMENTATION_ORDER:
            y = [
                to_float(lookup[(impl, str(thread), str(grain))], "median_runtime_seconds")
                for thread in THREADS
            ]
            ax.plot(
                THREADS,
                y,
                marker=IMPLEMENTATION_MARKERS[impl],
                color=IMPLEMENTATION_COLORS[impl],
                label=IMPLEMENTATION_LABELS[impl],
            )
        ax.set_title(f"4.1 Real-machine scalability - grain size {grain}")
        ax.set_xlabel("Threads pinned to physical-core representatives")
        ax.set_ylabel("Median ROI runtime (seconds)")
        ax.set_xticks(THREADS, THREADS)
        ax.grid(axis="both")
        ax.legend(frameon=False, ncols=3, loc="upper left")
        save_figure(fig, f"4_1_real_runtime_grain_{grain}")


def plot_4_1_sniper_metric_grid(
    rows: list[dict[str, str]], metric: str, ylabel: str, stem: str, log_y: bool
) -> None:
    lookup = row_lookup(rows, "implementation", "nthreads", "grain")
    fig, axes = plt.subplots(1, 3, figsize=(13.8, 4.4), sharey=log_y)
    for ax, grain in zip(axes, GRAINS):
        for impl in IMPLEMENTATION_ORDER:
            y = [
                to_float(lookup[(impl, str(thread), str(grain))], metric)
                for thread in THREADS
            ]
            ax.plot(
                THREADS,
                y,
                marker=IMPLEMENTATION_MARKERS[impl],
                color=IMPLEMENTATION_COLORS[impl],
            )
        if log_y:
            ax.set_yscale("log")
        ax.set_title(f"Grain {grain}")
        ax.set_xlabel("Threads")
        ax.set_xticks(THREADS, THREADS)
        ax.grid(axis="both", which="major")
    axes[0].set_ylabel(ylabel)
    fig.suptitle(stem.replace("_", " ").title(), y=1.03)
    fig.legend(
        handles=implementation_legend(),
        frameon=False,
        ncols=5,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.08),
    )
    save_figure(fig, stem)


def plot_4_1_real_variability(rows: list[dict[str, str]]) -> None:
    lookup = row_lookup(rows, "implementation", "nthreads", "grain")
    fig, axes = plt.subplots(1, 3, figsize=(13.8, 4.4), sharey=False)
    for ax, grain in zip(axes, GRAINS):
        for impl in IMPLEMENTATION_ORDER:
            medians = []
            lower = []
            upper = []
            for thread in THREADS:
                row = lookup[(impl, str(thread), str(grain))]
                median = to_float(row, "median_runtime_seconds")
                low = to_float(row, "min_runtime_seconds")
                high = to_float(row, "max_runtime_seconds")
                medians.append(median)
                lower.append(median - low)
                upper.append(high - median)
            ax.errorbar(
                THREADS,
                medians,
                yerr=np.array([lower, upper]),
                marker=IMPLEMENTATION_MARKERS[impl],
                color=IMPLEMENTATION_COLORS[impl],
                capsize=3,
                linewidth=1.7,
            )
        ax.set_title(f"Grain {grain}")
        ax.set_xlabel("Threads")
        ax.set_xticks(THREADS, THREADS)
        ax.grid(axis="both")
    axes[0].set_ylabel("Median runtime with min/max range (seconds)")
    fig.suptitle("4.1 Real-machine measurement variability", y=1.03)
    fig.legend(
        handles=implementation_legend(),
        frameon=False,
        ncols=5,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.08),
    )
    save_figure(fig, "4_1_real_runtime_variability")


def plot_4_1_normalized_scaling(
    sniper_rows: list[dict[str, str]], real_rows: list[dict[str, str]]
) -> None:
    sniper = row_lookup(sniper_rows, "implementation", "nthreads", "grain")
    real = row_lookup(real_rows, "implementation", "nthreads", "grain")
    fig, axes = plt.subplots(1, 3, figsize=(13.8, 4.5), sharey=False)
    for ax, grain in zip(axes, GRAINS):
        for impl in IMPLEMENTATION_ORDER:
            base_sniper = to_float(sniper[(impl, "1", str(grain))], "total_cycles")
            base_real = to_float(real[(impl, "1", str(grain))], "median_runtime_seconds")
            sniper_ratios = [
                to_float(sniper[(impl, str(thread), str(grain))], "total_cycles")
                / base_sniper
                for thread in THREADS
            ]
            real_ratios = [
                to_float(real[(impl, str(thread), str(grain))], "median_runtime_seconds")
                / base_real
                for thread in THREADS
            ]
            ax.plot(
                THREADS,
                sniper_ratios,
                marker=IMPLEMENTATION_MARKERS[impl],
                color=IMPLEMENTATION_COLORS[impl],
                linestyle="-",
                alpha=0.95,
            )
            ax.plot(
                THREADS,
                real_ratios,
                marker=IMPLEMENTATION_MARKERS[impl],
                color=IMPLEMENTATION_COLORS[impl],
                linestyle="--",
                alpha=0.75,
            )
        ax.axhline(1.0, color="#222222", linewidth=0.8)
        ax.set_title(f"Grain {grain}")
        ax.set_xlabel("Threads")
        ax.set_xticks(THREADS, THREADS)
        ax.set_yscale("log")
        ax.grid(axis="both", which="major")
    axes[0].set_ylabel("Runtime normalized to each 1-thread case")
    line_handles = [
        Line2D([0], [0], color="#222222", linestyle="-", label="Sniper cycles"),
        Line2D([0], [0], color="#222222", linestyle="--", label="Real median time"),
    ]
    fig.suptitle("4.1 Normalized scaling: Sniper versus real machine", y=1.03)
    fig.legend(
        handles=implementation_legend() + line_handles,
        frameon=False,
        ncols=4,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.12),
    )
    save_figure(fig, "4_1_sniper_vs_real_normalized_scaling")


def plot_4_1_energy_delay_tradeoff(rows: list[dict[str, str]]) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(13.8, 4.4), sharey=True)
    for ax, grain in zip(axes, GRAINS):
        grain_rows = [row for row in rows if to_int(row, "grain") == grain]
        for impl in IMPLEMENTATION_ORDER:
            impl_rows = [
                row
                for row in grain_rows
                if row["implementation"] == impl
            ]
            impl_rows.sort(key=lambda row: to_int(row, "nthreads"))
            x = [to_float(row, "runtime_seconds") * 1e6 for row in impl_rows]
            y = [to_float(row, "energy_j") for row in impl_rows]
            sizes = [35 + 7 * to_int(row, "nthreads") for row in impl_rows]
            ax.scatter(
                x,
                y,
                s=sizes,
                color=IMPLEMENTATION_COLORS[impl],
                edgecolor="#222222",
                linewidth=0.4,
                alpha=0.9,
                label=IMPLEMENTATION_LABELS[impl],
            )
            for row, xi, yi in zip(impl_rows, x, y):
                ax.text(
                    xi,
                    yi,
                    row["nthreads"],
                    fontsize=6.4,
                    ha="center",
                    va="center",
                    color="#111111",
                )
        ax.set_title(f"Grain {grain}")
        ax.set_xlabel("Simulated runtime (microseconds)")
        ax.set_xscale("log")
        ax.grid(axis="both", which="major")
    axes[0].set_ylabel("Energy (J)")
    fig.suptitle("4.1 Sniper energy-delay tradeoff", y=1.03)
    fig.legend(
        handles=implementation_legend(),
        frameon=False,
        ncols=5,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.08),
    )
    save_figure(fig, "4_1_sniper_energy_delay_tradeoff")


def plot_4_2_metric_bars(
    rows: list[dict[str, str]], metric: str, ylabel: str, stem: str, log_y: bool = False
) -> None:
    lookup = row_lookup(rows, "topology", "implementation")
    x = np.arange(len(TOPOLOGY_ORDER))
    width = 0.15
    fig, ax = plt.subplots(figsize=(9.2, 5.2))
    for i, impl in enumerate(IMPLEMENTATION_ORDER):
        offset = (i - (len(IMPLEMENTATION_ORDER) - 1) / 2) * width
        values = [
            to_float(lookup[(topology, impl)], metric)
            for topology in TOPOLOGY_ORDER
        ]
        bars = ax.bar(
            x + offset,
            values,
            width,
            label=IMPLEMENTATION_LABELS[impl],
            color=IMPLEMENTATION_COLORS[impl],
        )
        if metric in {"total_cycles", "energy_j"}:
            for bar, value in zip(bars, values):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    value,
                    format_metric(value),
                    ha="center",
                    va="bottom",
                    fontsize=6.5,
                    rotation=90,
                )
    if log_y:
        ax.set_yscale("log")
    ax.set_title(stem.replace("_", " ").title())
    ax.set_ylabel(ylabel)
    ax.set_xticks(x, [TOPOLOGY_LABELS[topology] for topology in TOPOLOGY_ORDER])
    ax.grid(axis="y")
    ax.grid(axis="x", visible=False)
    ax.legend(frameon=False, ncols=3, loc="upper left")
    save_figure(fig, stem)


def plot_4_2_topology_dashboard(rows: list[dict[str, str]]) -> None:
    metrics = [
        ("total_cycles", "Cycles", False),
        ("energy_j", "Energy (J)", False),
        ("edp_j_s", "EDP (J*s)", True),
    ]
    lookup = row_lookup(rows, "topology", "implementation")
    x = np.arange(len(TOPOLOGY_ORDER))
    width = 0.15
    fig, axes = plt.subplots(1, 3, figsize=(14.0, 4.8))
    for ax, (metric, ylabel, log_y) in zip(axes, metrics):
        for i, impl in enumerate(IMPLEMENTATION_ORDER):
            offset = (i - (len(IMPLEMENTATION_ORDER) - 1) / 2) * width
            values = [
                to_float(lookup[(topology, impl)], metric)
                for topology in TOPOLOGY_ORDER
            ]
            ax.bar(
                x + offset,
                values,
                width,
                color=IMPLEMENTATION_COLORS[impl],
            )
        if log_y:
            ax.set_yscale("log")
        ax.set_title(ylabel)
        ax.set_ylabel(ylabel)
        ax.set_xticks(x, [TOPOLOGY_LABELS[topology] for topology in TOPOLOGY_ORDER])
        ax.grid(axis="y")
        ax.grid(axis="x", visible=False)
    fig.suptitle("4.2 Thread topology comparison", y=1.03)
    fig.legend(
        handles=[Patch(facecolor=IMPLEMENTATION_COLORS[impl], label=IMPLEMENTATION_LABELS[impl]) for impl in IMPLEMENTATION_ORDER],
        frameon=False,
        ncols=5,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.08),
    )
    save_figure(fig, "4_2_topology_runtime_energy_edp")


def plot_4_2_normalized_cycles(rows: list[dict[str, str]]) -> None:
    lookup = row_lookup(rows, "topology", "implementation")
    x = np.arange(len(IMPLEMENTATION_ORDER))
    width = 0.24
    fig, ax = plt.subplots(figsize=(9.4, 5.2))
    for i, topology in enumerate(TOPOLOGY_ORDER):
        baseline = {
            impl: to_float(lookup[("share-all", impl)], "total_cycles")
            for impl in IMPLEMENTATION_ORDER
        }
        values = [
            to_float(lookup[(topology, impl)], "total_cycles") / baseline[impl]
            for impl in IMPLEMENTATION_ORDER
        ]
        ax.bar(
            x + (i - 1) * width,
            values,
            width,
            color=TOPOLOGY_COLORS[topology],
            label=topology,
        )
    ax.axhline(1.0, color="#222222", linewidth=0.8)
    ax.set_title("4.2 Topology impact normalized to share-all")
    ax.set_ylabel("Cycle ratio")
    ax.set_xticks(
        x,
        [short_label(IMPLEMENTATION_LABELS[impl], width=12) for impl in IMPLEMENTATION_ORDER],
    )
    ax.legend(
        handles=[
            Patch(facecolor=TOPOLOGY_COLORS[topology], label=topology)
            for topology in TOPOLOGY_ORDER
        ],
        frameon=False,
        ncols=3,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.12),
    )
    ax.grid(axis="y")
    ax.grid(axis="x", visible=False)
    save_figure(fig, "4_2_topology_cycles_normalized")


def plot_host_core_mapping() -> None:
    path = BENCHMARK_ROOT / "4.1" / "real" / "machine.json"
    if not path.is_file():
        return
    machine = json.loads(path.read_text(encoding="utf-8"))
    mapping = machine.get("physical_cpu_mapping", [])
    if not mapping:
        return

    fig, ax = plt.subplots(figsize=(11.4, 3.6))
    ax.set_title("Host CPU mapping used for real-machine runs")
    ax.set_xlabel("Representative logical CPU (physical core labels below)")
    ax.set_ylabel("Logical CPU sibling slot")
    xs = np.arange(len(mapping))
    max_siblings = max(len(item["siblings"]) for item in mapping)
    for i, item in enumerate(mapping):
        siblings = item["siblings"]
        for j, cpu in enumerate(siblings):
            is_rep = cpu == item["representative"]
            ax.scatter(
                i,
                j,
                s=260 if is_rep else 180,
                color="#4C78A8" if is_rep else "#C9D6EA",
                edgecolor="#222222",
                linewidth=0.8,
                zorder=3,
            )
            ax.text(
                i,
                j,
                str(cpu),
                ha="center",
                va="center",
                fontsize=7,
                color="#111111",
            )
        ax.text(
            i,
            -0.55,
            f"C{item['core']}",
            ha="center",
            va="top",
            fontsize=7,
            color="#333333",
        )
    ax.set_xticks(xs, [str(item["representative"]) for item in mapping], rotation=0)
    ax.set_ylim(-0.85, max_siblings - 0.35)
    ax.set_yticks(range(max_siblings), [f"Sibling {i + 1}" for i in range(max_siblings)])
    ax.grid(axis="x")
    ax.grid(axis="y", visible=False)
    legend = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#4C78A8", markeredgecolor="#222222", markersize=9, label="Representative CPU"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#C9D6EA", markeredgecolor="#222222", markersize=8, label="SMT sibling"),
    ]
    ax.legend(handles=legend, frameon=False, ncols=2, loc="upper right")
    note = (
        f"{machine.get('physical_cores_available', len(mapping))} physical cores, "
        f"{len(machine.get('sched_affinity', []))} logical CPUs visible to WSL"
    )
    fig.text(0.5, -0.04, note, ha="center", fontsize=8, color="#444444")
    save_figure(fig, "host_cpu_physical_core_mapping")


def main() -> int:
    setup_style()
    sniper_4_1 = read_csv(BENCHMARK_ROOT / "4.1" / "sniper" / "summary.csv")
    real_4_1 = read_csv(BENCHMARK_ROOT / "4.1" / "real" / "summary.csv")
    real_raw_4_1 = read_csv(BENCHMARK_ROOT / "4.1" / "real" / "summary_raw.csv")
    sniper_4_2 = read_csv(BENCHMARK_ROOT / "4.2" / "summary.csv")

    validate_inputs(sniper_4_1, real_4_1, real_raw_4_1, sniper_4_2)

    plot_4_1_sniper_cycles_required(sniper_4_1)
    plot_4_1_real_runtime_required(real_4_1)

    plot_4_1_sniper_metric_grid(
        sniper_4_1,
        "energy_j",
        "Energy (J)",
        "4_1_sniper_energy_by_grain",
        log_y=False,
    )
    plot_4_1_sniper_metric_grid(
        sniper_4_1,
        "edp_j_s",
        "EDP (J*s)",
        "4_1_sniper_edp_by_grain",
        log_y=True,
    )
    plot_4_1_sniper_metric_grid(
        sniper_4_1,
        "ed2p_j_s2",
        "ED2P (J*s^2)",
        "4_1_sniper_ed2p_by_grain",
        log_y=True,
    )
    plot_4_1_real_variability(real_4_1)
    plot_4_1_normalized_scaling(sniper_4_1, real_4_1)
    plot_4_1_energy_delay_tradeoff(sniper_4_1)

    plot_4_2_metric_bars(
        sniper_4_2,
        "total_cycles",
        "ROI execution time (cycles)",
        "4_2_topology_cycles",
    )
    plot_4_2_metric_bars(
        sniper_4_2,
        "energy_j",
        "Energy (J)",
        "4_2_topology_energy",
    )
    plot_4_2_metric_bars(
        sniper_4_2,
        "edp_j_s",
        "EDP (J*s)",
        "4_2_topology_edp",
        log_y=True,
    )
    plot_4_2_metric_bars(
        sniper_4_2,
        "ed2p_j_s2",
        "ED2P (J*s^2)",
        "4_2_topology_ed2p",
        log_y=True,
    )
    plot_4_2_topology_dashboard(sniper_4_2)
    plot_4_2_normalized_cycles(sniper_4_2)
    plot_host_core_mapping()

    outputs = sorted(SCRIPT_DIR.glob("*.png")) + sorted(SCRIPT_DIR.glob("*.pdf"))
    print(f"Wrote {len(outputs)} diagrams to {SCRIPT_DIR}")
    for output in outputs:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
