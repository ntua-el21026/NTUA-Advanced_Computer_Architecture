#!/usr/bin/env python3
"""Generate report-ready diagrams from Assignment 2 benchmark summaries."""

from __future__ import annotations

import csv
import textwrap
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch


SCRIPT_DIR = Path(__file__).resolve().parent
BENCHMARK_ROOT = SCRIPT_DIR.parent

BENCHMARK_ORDER = [
    "403.gcc",
    "429.mcf",
    "433.milc",
    "444.namd",
    "450.soplex",
    "459.GemsFDTD",
    "470.lbm",
]

POLICY_ORDER = ["LRU", "Random", "SRRIP", "LIP", "LFU", "MRU"]
POLICY_COLORS = {
    "LRU": "#4C78A8",
    "Random": "#F58518",
    "SRRIP": "#54A24B",
    "LIP": "#B279A2",
    "LFU": "#E45756",
    "MRU": "#72B7B2",
}
CAPACITY_COLORS = {
    256: "#4C78A8",
    512: "#F58518",
    1024: "#54A24B",
    2048: "#B279A2",
}
BLOCK_MARKERS = {
    64: "o",
    128: "s",
    256: "^",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing required summary: {path}")
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def to_float(row: dict[str, str], key: str) -> float:
    return float(row[key])


def to_int(row: dict[str, str], key: str) -> int:
    return int(row[key])


def config_label(config: str) -> str:
    # L2_1024KB_A16_B256 -> 1024K A16 B256
    return config.replace("L2_", "").replace("KB_", "K ").replace("_", " ")


def short_label(label: str, width: int = 22) -> str:
    wrapped = textwrap.wrap(label, width=width, break_long_words=False)
    return "\n".join(wrapped)


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
            "grid.alpha": 0.8,
        }
    )


def save_figure(fig: plt.Figure, stem: str) -> None:
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    for suffix in (".pdf", ".png"):
        fig.savefig(SCRIPT_DIR / f"{stem}{suffix}", bbox_inches="tight")
    plt.close(fig)


def sorted_4_2_configs(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        rows,
        key=lambda row: (
            to_int(row, "l2_size_kb"),
            to_int(row, "l2_associativity"),
            to_int(row, "l2_block_size_b"),
        ),
    )


def plot_4_2_config_ipc_ranked() -> None:
    rows = read_csv(BENCHMARK_ROOT / "4.2" / "summary_by_config.csv")
    rows.sort(key=lambda row: to_float(row, "aggregate_ipc"))
    labels = [config_label(row["config"]) for row in rows]
    aggregate = np.array([to_float(row, "aggregate_ipc") for row in rows])
    mean = np.array([to_float(row, "arithmetic_mean_ipc") for row in rows])
    colors = [CAPACITY_COLORS[to_int(row, "l2_size_kb")] for row in rows]
    y = np.arange(len(rows))

    fig, ax = plt.subplots(figsize=(10.8, 8.2))
    ax.barh(y, aggregate, color=colors, label="Aggregate IPC")
    ax.scatter(mean, y, marker="D", color="#222222", s=20, label="Arithmetic mean IPC", zorder=3)
    ax.set_yticks(y, labels)
    ax.set_xlabel("IPC")
    ax.set_title("4.2 L2 configurations ranked by aggregate IPC")
    ax.grid(axis="x")
    ax.grid(axis="y", visible=False)
    legend_items = [
        Patch(facecolor=color, label=f"{size} KB")
        for size, color in CAPACITY_COLORS.items()
    ]
    ax.legend(
        handles=legend_items + [Line2D([0], [0], marker="D", color="#222222", linestyle="", label="Mean IPC")],
        frameon=False,
        ncols=5,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.06),
    )
    save_figure(fig, "4_2_config_ipc_ranked")


def plot_4_2_best_by_capacity() -> None:
    rows = read_csv(BENCHMARK_ROOT / "4.2" / "summary_by_config.csv")
    selected = []
    for size in (256, 512, 1024, 2048):
        size_rows = [row for row in rows if to_int(row, "l2_size_kb") == size]
        selected.append(max(size_rows, key=lambda row: to_float(row, "aggregate_ipc")))

    x = np.arange(len(selected))
    aggregate = np.array([to_float(row, "aggregate_ipc") for row in selected])
    mean = np.array([to_float(row, "arithmetic_mean_ipc") for row in selected])
    labels = [f"{row['l2_size_kb']} KB\nA{row['l2_associativity']} B{row['l2_block_size_b']}" for row in selected]

    fig, ax = plt.subplots(figsize=(8.4, 4.8))
    ax.bar(x, aggregate, color=[CAPACITY_COLORS[to_int(row, "l2_size_kb")] for row in selected], label="Aggregate IPC")
    ax.plot(x, mean, marker="D", color="#222222", linewidth=1.5, label="Arithmetic mean IPC")
    ax.set_title("4.2 Best L2 configuration within each capacity")
    ax.set_ylabel("IPC")
    ax.set_xticks(x, labels)
    ax.legend(frameon=False)
    ax.grid(axis="y")
    ax.grid(axis="x", visible=False)
    for xi, value in zip(x, aggregate):
        ax.text(xi, value + aggregate.max() * 0.018, f"{value:.3f}", ha="center", fontsize=8)
    save_figure(fig, "4_2_best_by_capacity")


def plot_4_2_block_size_sensitivity() -> None:
    rows = read_csv(BENCHMARK_ROOT / "4.2" / "summary_by_config.csv")
    sizes = [256, 512, 1024, 2048]
    blocks = [64, 128, 256]
    values = np.zeros((len(blocks), len(sizes)))
    for i, block in enumerate(blocks):
        for j, size in enumerate(sizes):
            candidates = [
                row
                for row in rows
                if to_int(row, "l2_size_kb") == size and to_int(row, "l2_block_size_b") == block
            ]
            values[i, j] = max(to_float(row, "aggregate_ipc") for row in candidates)

    x = np.arange(len(sizes))
    width = 0.24
    fig, ax = plt.subplots(figsize=(8.6, 4.8))
    for i, block in enumerate(blocks):
        ax.bar(x + (i - 1) * width, values[i], width, label=f"{block} B")
    ax.set_title("4.2 Block-size sensitivity using best associativity per capacity")
    ax.set_xlabel("L2 capacity")
    ax.set_ylabel("Best aggregate IPC")
    ax.set_xticks(x, [f"{size} KB" for size in sizes])
    ax.legend(title="Block size", frameon=False, ncols=3)
    ax.grid(axis="y")
    ax.grid(axis="x", visible=False)
    save_figure(fig, "4_2_block_size_sensitivity")


def plot_4_2_associativity_sensitivity() -> None:
    rows = read_csv(BENCHMARK_ROOT / "4.2" / "summary_by_config.csv")
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.6), sharey=True)
    for ax, size in zip(axes, (512, 1024)):
        for block in (64, 128, 256):
            selected = [
                row
                for row in rows
                if to_int(row, "l2_size_kb") == size and to_int(row, "l2_block_size_b") == block
            ]
            selected.sort(key=lambda row: to_int(row, "l2_associativity"))
            x = [to_int(row, "l2_associativity") for row in selected]
            y = [to_float(row, "aggregate_ipc") for row in selected]
            ax.plot(x, y, marker=BLOCK_MARKERS[block], linewidth=2, label=f"{block} B")
        ax.set_title(f"{size} KB L2")
        ax.set_xlabel("Associativity")
        ax.set_xticks(sorted({to_int(row, "l2_associativity") for row in rows if to_int(row, "l2_size_kb") == size}))
        ax.grid(axis="both")
    axes[0].set_ylabel("Aggregate IPC")
    axes[1].legend(title="Block size", frameon=False)
    fig.suptitle("4.2 Associativity sensitivity for capacities with alternatives", y=1.03)
    save_figure(fig, "4_2_associativity_sensitivity")


def plot_4_2_l2_mpki_vs_ipc() -> None:
    rows = read_csv(BENCHMARK_ROOT / "4.2" / "summary_by_config.csv")
    fig, ax = plt.subplots(figsize=(8.4, 5.4))
    for row in rows:
        size = to_int(row, "l2_size_kb")
        block = to_int(row, "l2_block_size_b")
        ax.scatter(
            to_float(row, "aggregate_l2_mpki"),
            to_float(row, "aggregate_ipc"),
            s=78,
            marker=BLOCK_MARKERS[block],
            color=CAPACITY_COLORS[size],
            edgecolor="#222222",
            linewidth=0.4,
        )
    ax.set_title("4.2 Aggregate IPC versus L2 MPKI")
    ax.set_xlabel("Aggregate L2 MPKI")
    ax.set_ylabel("Aggregate IPC")
    capacity_handles = [Patch(facecolor=color, label=f"{size} KB") for size, color in CAPACITY_COLORS.items()]
    block_handles = [
        Line2D([0], [0], marker=marker, color="#222222", linestyle="", label=f"{block} B")
        for block, marker in BLOCK_MARKERS.items()
    ]
    ax.legend(
        handles=capacity_handles + block_handles,
        frameon=False,
        ncols=4,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.12),
    )
    ax.grid(axis="both")
    save_figure(fig, "4_2_l2_mpki_vs_ipc")


def plot_4_2_benchmark_ipc_heatmap() -> None:
    rows = read_csv(BENCHMARK_ROOT / "4.2" / "summary.csv")
    config_rows = sorted_4_2_configs(read_csv(BENCHMARK_ROOT / "4.2" / "summary_by_config.csv"))
    configs = [row["config"] for row in config_rows]
    lookup = {(row["benchmark"], row["config"]): to_float(row, "ipc") for row in rows}
    values = np.array([[lookup[(benchmark, config)] for benchmark in BENCHMARK_ORDER] for config in configs])

    fig, ax = plt.subplots(figsize=(10.6, 8.4))
    image = ax.imshow(values, cmap="viridis", aspect="auto")
    ax.set_title("4.2 IPC by benchmark and L2 configuration")
    ax.set_xlabel("Benchmark")
    ax.set_ylabel("L2 configuration")
    ax.set_xticks(np.arange(len(BENCHMARK_ORDER)), BENCHMARK_ORDER, rotation=40, ha="right")
    ax.set_yticks(np.arange(len(configs)), [config_label(config) for config in configs])
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            color = "white" if values[i, j] < values.max() * 0.45 else "#222222"
            ax.text(j, i, f"{values[i, j]:.2f}", ha="center", va="center", color=color, fontsize=6.2)
    cbar = fig.colorbar(image, ax=ax)
    cbar.set_label("IPC")
    ax.grid(False)
    save_figure(fig, "4_2_benchmark_ipc_heatmap")


def plot_4_3_policy_overall() -> None:
    rows = read_csv(BENCHMARK_ROOT / "4.3" / "summary_by_policy.csv")
    rows.sort(key=lambda row: POLICY_ORDER.index(row["policy"]))
    policies = [row["policy"] for row in rows]
    colors = [POLICY_COLORS[policy] for policy in policies]
    x = np.arange(len(policies))

    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.8))
    aggregate_ipc = [to_float(row, "aggregate_ipc") for row in rows]
    mean_ipc = [to_float(row, "arithmetic_mean_ipc") for row in rows]
    axes[0].bar(x, aggregate_ipc, color=colors, label="Aggregate IPC")
    axes[0].plot(x, mean_ipc, marker="D", color="#222222", linewidth=1.5, label="Arithmetic mean IPC")
    axes[0].set_title("Policy performance")
    axes[0].set_ylabel("IPC")
    axes[0].set_xticks(x, policies, rotation=30, ha="right")
    axes[0].legend(frameon=False)
    axes[0].grid(axis="y")
    axes[0].grid(axis="x", visible=False)

    l2_mpki = [to_float(row, "aggregate_l2_mpki") for row in rows]
    axes[1].bar(x, l2_mpki, color=colors)
    axes[1].set_title("Policy memory pressure")
    axes[1].set_ylabel("Aggregate L2 MPKI")
    axes[1].set_xticks(x, policies, rotation=30, ha="right")
    axes[1].grid(axis="y")
    axes[1].grid(axis="x", visible=False)

    fig.suptitle("4.3 Overall replacement-policy comparison", y=1.02)
    save_figure(fig, "4_3_policy_overall")


def plot_4_3_policy_by_config_ipc() -> None:
    rows = read_csv(BENCHMARK_ROOT / "4.3" / "summary_by_config_policy.csv")
    configs = sorted(
        {row["config"] for row in rows},
        key=lambda config: next(to_int(row, "l2_size_kb") for row in rows if row["config"] == config),
    )
    lookup = {(row["config"], row["policy"]): to_float(row, "aggregate_ipc") for row in rows}
    x = np.arange(len(configs))
    width = 0.12

    fig, ax = plt.subplots(figsize=(11.2, 5.2))
    for i, policy in enumerate(POLICY_ORDER):
        offset = (i - (len(POLICY_ORDER) - 1) / 2) * width
        ax.bar(x + offset, [lookup[(config, policy)] for config in configs], width, label=policy, color=POLICY_COLORS[policy])
    ax.set_title("4.3 Aggregate IPC by replacement policy and selected L2 config")
    ax.set_ylabel("Aggregate IPC")
    ax.set_xticks(x, [short_label(config_label(config), 14) for config in configs])
    ax.legend(frameon=False, ncols=6, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    ax.grid(axis="y")
    ax.grid(axis="x", visible=False)
    save_figure(fig, "4_3_policy_by_config_ipc")


def plot_4_3_policy_by_config_l2_mpki() -> None:
    rows = read_csv(BENCHMARK_ROOT / "4.3" / "summary_by_config_policy.csv")
    configs = sorted(
        {row["config"] for row in rows},
        key=lambda config: next(to_int(row, "l2_size_kb") for row in rows if row["config"] == config),
    )
    lookup = {(row["config"], row["policy"]): to_float(row, "aggregate_l2_mpki") for row in rows}
    x = np.arange(len(configs))
    width = 0.12

    fig, ax = plt.subplots(figsize=(11.2, 5.2))
    for i, policy in enumerate(POLICY_ORDER):
        offset = (i - (len(POLICY_ORDER) - 1) / 2) * width
        ax.bar(x + offset, [lookup[(config, policy)] for config in configs], width, label=policy, color=POLICY_COLORS[policy])
    ax.set_title("4.3 Aggregate L2 MPKI by replacement policy and selected L2 config")
    ax.set_ylabel("Aggregate L2 MPKI")
    ax.set_xticks(x, [short_label(config_label(config), 14) for config in configs])
    ax.legend(frameon=False, ncols=6, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    ax.grid(axis="y")
    ax.grid(axis="x", visible=False)
    save_figure(fig, "4_3_policy_by_config_l2_mpki")


def plot_4_3_policy_benchmark_heatmap() -> None:
    rows = read_csv(BENCHMARK_ROOT / "4.3" / "summary.csv")
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rows:
        grouped[(row["policy"], row["benchmark"])].append(to_float(row, "ipc"))
    values = np.array(
        [
            [sum(grouped[(policy, benchmark)]) / len(grouped[(policy, benchmark)]) for benchmark in BENCHMARK_ORDER]
            for policy in POLICY_ORDER
        ]
    )

    fig, ax = plt.subplots(figsize=(9.6, 4.8))
    image = ax.imshow(values, cmap="viridis", aspect="auto")
    ax.set_title("4.3 Mean IPC by policy and benchmark across selected L2 configs")
    ax.set_xlabel("Benchmark")
    ax.set_ylabel("Policy")
    ax.set_xticks(np.arange(len(BENCHMARK_ORDER)), BENCHMARK_ORDER, rotation=40, ha="right")
    ax.set_yticks(np.arange(len(POLICY_ORDER)), POLICY_ORDER)
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            color = "white" if values[i, j] < values.max() * 0.45 else "#222222"
            ax.text(j, i, f"{values[i, j]:.2f}", ha="center", va="center", color=color, fontsize=7)
    cbar = fig.colorbar(image, ax=ax)
    cbar.set_label("Mean IPC")
    ax.grid(False)
    save_figure(fig, "4_3_policy_benchmark_heatmap")


def plot_4_3_lru_random_delta_by_benchmark() -> None:
    rows = read_csv(BENCHMARK_ROOT / "4.3" / "summary.csv")
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rows:
        if row["policy"] in {"LRU", "Random"}:
            grouped[(row["policy"], row["benchmark"])].append(to_float(row, "ipc"))
    deltas = []
    for benchmark in BENCHMARK_ORDER:
        random_mean = sum(grouped[("Random", benchmark)]) / len(grouped[("Random", benchmark)])
        lru_mean = sum(grouped[("LRU", benchmark)]) / len(grouped[("LRU", benchmark)])
        deltas.append(random_mean - lru_mean)
    colors = ["#54A24B" if value >= 0 else "#E45756" for value in deltas]
    x = np.arange(len(BENCHMARK_ORDER))

    fig, ax = plt.subplots(figsize=(8.8, 4.6))
    ax.bar(x, deltas, color=colors)
    ax.axhline(0, color="#222222", linewidth=0.8)
    ax.set_title("4.3 Random minus LRU mean IPC by benchmark")
    ax.set_ylabel("IPC delta")
    ax.set_xticks(x, BENCHMARK_ORDER, rotation=40, ha="right")
    ax.grid(axis="y")
    ax.grid(axis="x", visible=False)
    save_figure(fig, "4_3_lru_random_delta_by_benchmark")


def main() -> int:
    setup_style()
    plot_4_2_config_ipc_ranked()
    plot_4_2_best_by_capacity()
    plot_4_2_block_size_sensitivity()
    plot_4_2_associativity_sensitivity()
    plot_4_2_l2_mpki_vs_ipc()
    plot_4_2_benchmark_ipc_heatmap()
    plot_4_3_policy_overall()
    plot_4_3_policy_by_config_ipc()
    plot_4_3_policy_by_config_l2_mpki()
    plot_4_3_policy_benchmark_heatmap()
    plot_4_3_lru_random_delta_by_benchmark()
    print(f"Wrote diagrams to {SCRIPT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
