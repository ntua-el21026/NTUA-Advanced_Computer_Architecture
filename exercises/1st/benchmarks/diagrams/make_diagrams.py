#!/usr/bin/env python3
"""Generate report-ready diagrams from Assignment 1 benchmark summaries."""

from __future__ import annotations

import csv
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch


SCRIPT_DIR = Path(__file__).resolve().parent
BENCHMARK_ROOT = SCRIPT_DIR.parent

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

FAMILY_COLORS = {
    "alpha21264": "#4C78A8",
    "perceptron": "#F58518",
    "tournament": "#54A24B",
    "global-history": "#B279A2",
    "local-history": "#E45756",
    "nbit": "#72B7B2",
    "pentium-m": "#9D755D",
    "static": "#BAB0AC",
}

LABEL_OVERRIDES = {
    "Tournament-M1024-Nbit16K1-Global8K-BHR8": "Tourn M1024\nNbit16K1 + Global8K\nBHR8",
    "Tournament-M1024-Local2048x4-Global8K-BHR8": "Tourn M1024\nLocal2048x4 + Global8K\nBHR8",
    "Tournament-M2048-Nbit8K2-Perceptron16K-N8": "Tourn M2048\nNbit8K2 + Perceptron16K\nN8",
    "Tournament-M2048-Local1024x6-Perceptron16K-N8": "Tourn M2048\nLocal1024x6 + Perceptron16K\nN8",
}

SERIES_COLORS = {
    "train": "#4C78A8",
    "ref": "#F58518",
    "mean": "#4C78A8",
    "aggregate": "#E45756",
    "direction": "#4C78A8",
    "target": "#F58518",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def to_float(row: dict[str, str], key: str) -> float:
    return float(row[key])


def short_label(label: str, width: int = 24) -> str:
    hyphen_wrappable = label.replace("-", "- ")
    wrapped = textwrap.wrap(hyphen_wrappable, width=width, break_long_words=False)
    return "\n".join(line.replace("- ", "-") for line in wrapped)


def predictor_label(label: str, width: int = 24) -> str:
    if label in LABEL_OVERRIDES:
        return LABEL_OVERRIDES[label]
    if label.startswith("FSM-16K-"):
        _, _, machine, mask = label.split("-", 3)
        return f"FSM {machine}:{mask}"
    return short_label(label, width)


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


def plot_5_2_branch_frequency() -> None:
    rows = read_csv(BENCHMARK_ROOT / "5.2" / "summary.csv")
    by_input = {
        input_set: {row["benchmark"]: to_float(row, "branch_frequency_pct") for row in rows if row["input_set"] == input_set}
        for input_set in ("train", "ref")
    }

    x = np.arange(len(BENCHMARK_ORDER))
    width = 0.38
    fig, ax = plt.subplots(figsize=(10.8, 4.8))
    ax.bar(x - width / 2, [by_input["train"][b] for b in BENCHMARK_ORDER], width, label="train", color=SERIES_COLORS["train"])
    ax.bar(x + width / 2, [by_input["ref"][b] for b in BENCHMARK_ORDER], width, label="ref", color=SERIES_COLORS["ref"])
    ax.set_title("5.2 Branch frequency by benchmark")
    ax.set_ylabel("Branches / instructions (%)")
    ax.set_xticks(x, BENCHMARK_ORDER, rotation=40, ha="right")
    ax.legend(frameon=False, ncols=2)
    ax.grid(axis="y")
    ax.grid(axis="x", visible=False)
    save_figure(fig, "5_2_branch_frequency")


def plot_5_2_branch_mix() -> None:
    rows = read_csv(BENCHMARK_ROOT / "5.2" / "summary.csv")
    categories = [
        ("conditional_taken_pct", "Cond. taken", "#4C78A8"),
        ("conditional_not_taken_pct", "Cond. not taken", "#F58518"),
        ("unconditional_pct", "Unconditional", "#54A24B"),
        ("calls_pct", "Calls", "#B279A2"),
        ("returns_pct", "Returns", "#E45756"),
    ]

    fig, axes = plt.subplots(2, 1, figsize=(11, 7.2), sharex=True)
    for ax, input_set in zip(axes, ("train", "ref")):
        selected = {row["benchmark"]: row for row in rows if row["input_set"] == input_set}
        bottom = np.zeros(len(BENCHMARK_ORDER))
        x = np.arange(len(BENCHMARK_ORDER))
        for key, label, color in categories:
            values = np.array([to_float(selected[b], key) for b in BENCHMARK_ORDER])
            ax.bar(x, values, bottom=bottom, label=label, color=color, width=0.72)
            bottom += values
        ax.set_title(f"{input_set} input")
        ax.set_ylabel("Share of branches (%)")
        ax.set_ylim(0, 100)
        ax.grid(axis="y")
        ax.grid(axis="x", visible=False)
    axes[-1].set_xticks(np.arange(len(BENCHMARK_ORDER)), BENCHMARK_ORDER, rotation=40, ha="right")
    axes[0].legend(frameon=False, ncols=5, loc="upper center", bbox_to_anchor=(0.5, 1.35))
    fig.suptitle("5.2 Dynamic branch mix", y=1.01)
    save_figure(fig, "5_2_branch_mix")


def plot_5_3_predictor_groups() -> None:
    rows = read_csv(BENCHMARK_ROOT / "5.3" / "summary_by_group.csv")
    groups = [
        ("5.3.i-fixed-16K-entries", "Fixed 16K entries"),
        ("5.3.ii-2bit-nair-fsms", "2-bit Nair FSMs"),
        ("5.3.iii-fixed-32K-bits", "Fixed 32K bits"),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.8))
    for ax, (group, title) in zip(axes, groups):
        selected = [row for row in rows if row["group"] == group]
        selected.sort(key=lambda row: to_float(row, "arithmetic_mean_direction_mpki"))
        labels = [predictor_label(row["predictor"], 18) for row in selected]
        values = [to_float(row, "arithmetic_mean_direction_mpki") for row in selected]
        y = np.arange(len(selected))
        ax.barh(y, values, color="#4C78A8")
        ax.set_yticks(y, labels)
        ax.invert_yaxis()
        ax.set_title(title)
        ax.set_xlabel("Arithmetic mean direction MPKI")
        ax.grid(axis="x")
        ax.grid(axis="y", visible=False)
        for yi, value in zip(y, values):
            ax.text(value + max(values) * 0.015, yi, f"{value:.2f}", va="center", fontsize=7)
    fig.subplots_adjust(wspace=0.48)
    fig.suptitle("5.3 N-bit and FSM predictor comparison", y=1.02)
    save_figure(fig, "5_3_predictor_groups")


def plot_5_3_fixed32_by_benchmark() -> None:
    rows = [
        row
        for row in read_csv(BENCHMARK_ROOT / "5.3" / "summary.csv")
        if "5.3.iii-fixed-32K-bits" in row["groups"].split(";")
    ]
    predictor_rows = read_csv(BENCHMARK_ROOT / "5.3" / "summary_by_group.csv")
    predictors = [
        row["predictor"]
        for row in predictor_rows
        if row["group"] == "5.3.iii-fixed-32K-bits"
    ]
    predictors.sort(
        key=lambda predictor: next(
            to_float(row, "arithmetic_mean_direction_mpki")
            for row in predictor_rows
            if row["group"] == "5.3.iii-fixed-32K-bits" and row["predictor"] == predictor
        )
    )
    lookup = {(row["benchmark"], row["predictor"]): to_float(row, "direction_mpki") for row in rows}
    values = np.array([[lookup[(benchmark, predictor)] for benchmark in BENCHMARK_ORDER] for predictor in predictors])

    fig, ax = plt.subplots(figsize=(10.8, 5.2))
    image = ax.imshow(values, cmap="magma_r", aspect="auto")
    ax.set_title("5.3 Fixed 32K-bit predictors by benchmark")
    ax.set_xlabel("Benchmark")
    ax.set_ylabel("Predictor")
    ax.set_xticks(np.arange(len(BENCHMARK_ORDER)), BENCHMARK_ORDER, rotation=40, ha="right")
    ax.set_yticks(np.arange(len(predictors)), [predictor_label(p, 18) for p in predictors])
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            ax.text(j, i, f"{values[i, j]:.1f}", ha="center", va="center", color="white", fontsize=6.5)
    cbar = fig.colorbar(image, ax=ax)
    cbar.set_label("Direction MPKI")
    ax.grid(False)
    save_figure(fig, "5_3_fixed32_by_benchmark")


def plot_5_4_btb() -> None:
    rows = read_csv(BENCHMARK_ROOT / "5.4" / "summary_by_btb.csv")
    rows.sort(key=lambda row: to_float(row, "arithmetic_mean_total_miss_mpki"))

    labels = [row["btb"] for row in rows]
    direction = np.array([to_float(row, "arithmetic_mean_direction_mpki") for row in rows])
    target = np.array([to_float(row, "arithmetic_mean_target_mpki") for row in rows])
    y = np.arange(len(rows))

    fig, ax = plt.subplots(figsize=(9.6, 5.4))
    ax.barh(y, direction, color=SERIES_COLORS["direction"], label="Direction misses")
    ax.barh(y, target, left=direction, color=SERIES_COLORS["target"], label="Target misses")
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.set_xlabel("Arithmetic mean miss MPKI")
    ax.set_title("5.4 BTB direction and target miss MPKI")
    ax.legend(frameon=False)
    ax.grid(axis="x")
    ax.grid(axis="y", visible=False)
    save_figure(fig, "5_4_btb_total_miss_mpki")


def plot_5_4_btb_by_benchmark() -> None:
    rows = read_csv(BENCHMARK_ROOT / "5.4" / "summary.csv")
    btb_rows = read_csv(BENCHMARK_ROOT / "5.4" / "summary_by_btb.csv")
    btbs = [row["btb"] for row in btb_rows]
    btbs.sort(
        key=lambda btb: next(to_float(row, "arithmetic_mean_total_miss_mpki") for row in btb_rows if row["btb"] == btb)
    )
    lookup = {(row["benchmark"], row["btb"]): to_float(row, "total_miss_mpki") for row in rows}
    values = np.array([[lookup[(benchmark, btb)] for benchmark in BENCHMARK_ORDER] for btb in btbs])

    fig, ax = plt.subplots(figsize=(10.8, 5.2))
    image = ax.imshow(values, cmap="viridis_r", aspect="auto")
    ax.set_title("5.4 BTB total miss MPKI by benchmark")
    ax.set_xlabel("Benchmark")
    ax.set_ylabel("BTB organization")
    ax.set_xticks(np.arange(len(BENCHMARK_ORDER)), BENCHMARK_ORDER, rotation=40, ha="right")
    ax.set_yticks(np.arange(len(btbs)), btbs)
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            ax.text(j, i, f"{values[i, j]:.1f}", ha="center", va="center", color="white", fontsize=6.5)
    cbar = fig.colorbar(image, ax=ax)
    cbar.set_label("Total miss MPKI")
    ax.grid(False)
    save_figure(fig, "5_4_btb_by_benchmark")


def plot_5_5_ras() -> None:
    rows = read_csv(BENCHMARK_ROOT / "5.5" / "summary_by_ras.csv")
    rows.sort(key=lambda row: int(row["ras_entries"]))
    x = np.array([int(row["ras_entries"]) for row in rows])
    mean = np.array([to_float(row, "arithmetic_mean_miss_rate_pct") for row in rows])
    aggregate = np.array([to_float(row, "aggregate_miss_rate_pct") for row in rows])

    fig, ax = plt.subplots(figsize=(8.6, 4.8))
    ax.plot(x, mean, marker="o", linewidth=2, color=SERIES_COLORS["mean"], label="Arithmetic mean")
    ax.plot(x, aggregate, marker="s", linewidth=2, color=SERIES_COLORS["aggregate"], label="Aggregate")
    ax.set_title("5.5 RAS miss rate versus stack entries")
    ax.set_xlabel("RAS entries")
    ax.set_ylabel("Miss rate (%)")
    ax.set_xticks(x)
    ax.legend(frameon=False)
    ax.grid(axis="both")
    save_figure(fig, "5_5_ras_miss_rate")


def plot_5_5_ras_by_benchmark() -> None:
    rows = read_csv(BENCHMARK_ROOT / "5.5" / "summary.csv")
    ras_entries = sorted({int(row["ras_entries"]) for row in rows})
    lookup = {(row["benchmark"], int(row["ras_entries"])): to_float(row, "miss_rate_pct") for row in rows}
    values = np.array([[lookup[(benchmark, entries)] for benchmark in BENCHMARK_ORDER] for entries in ras_entries])

    fig, ax = plt.subplots(figsize=(10.8, 4.8))
    image = ax.imshow(values, cmap="magma_r", aspect="auto")
    ax.set_title("5.5 RAS miss rate by benchmark")
    ax.set_xlabel("Benchmark")
    ax.set_ylabel("RAS entries")
    ax.set_xticks(np.arange(len(BENCHMARK_ORDER)), BENCHMARK_ORDER, rotation=40, ha="right")
    ax.set_yticks(np.arange(len(ras_entries)), [str(entries) for entries in ras_entries])
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            ax.text(j, i, f"{values[i, j]:.2f}", ha="center", va="center", color="white", fontsize=6.5)
    cbar = fig.colorbar(image, ax=ax)
    cbar.set_label("Miss rate (%)")
    ax.grid(False)
    save_figure(fig, "5_5_ras_by_benchmark")


def plot_5_6_1_perceptrons() -> None:
    rows = read_csv(BENCHMARK_ROOT / "5.6.1" / "summary_by_predictor.csv")
    ms = sorted({int(row["m"]) for row in rows})
    ns = sorted({int(row["n"]) for row in rows})
    values = np.zeros((len(ms), len(ns)))
    lookup = {(int(row["m"]), int(row["n"])): to_float(row, "arithmetic_mean_direction_mpki") for row in rows}
    for i, m in enumerate(ms):
        for j, n in enumerate(ns):
            values[i, j] = lookup[(m, n)]

    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    image = ax.imshow(values, cmap="viridis_r", aspect="auto")
    ax.set_title("5.6.1 Perceptron arithmetic mean direction MPKI")
    ax.set_xlabel("Global history length n")
    ax.set_ylabel("Perceptrons M")
    ax.set_xticks(np.arange(len(ns)), [str(n) for n in ns])
    ax.set_yticks(np.arange(len(ms)), [str(m) for m in ms])
    for i in range(len(ms)):
        for j in range(len(ns)):
            ax.text(j, i, f"{values[i, j]:.2f}", ha="center", va="center", color="white", fontsize=8)
    cbar = fig.colorbar(image, ax=ax)
    cbar.set_label("MPKI")
    ax.grid(False)
    save_figure(fig, "5_6_1_perceptron_heatmap")


def plot_5_6_2_predictor_comparison() -> None:
    rows = read_csv(BENCHMARK_ROOT / "5.6.2" / "summary_by_predictor.csv")
    rows.sort(key=lambda row: to_float(row, "arithmetic_mean_direction_mpki"), reverse=True)
    labels = [predictor_label(row["predictor"], 28) for row in rows]
    values = [to_float(row, "arithmetic_mean_direction_mpki") for row in rows]
    aggregate = [to_float(row, "aggregate_direction_mpki") for row in rows]
    colors = [FAMILY_COLORS[row["family"]] for row in rows]
    y = np.arange(len(rows))

    fig, ax = plt.subplots(figsize=(10.6, 8.2))
    ax.barh(y, values, color=colors)
    ax.scatter(aggregate, y, marker="D", color="#222222", s=18, label="Aggregate MPKI", zorder=3)
    ax.set_yticks(y, labels)
    ax.set_xlabel("Direction MPKI")
    ax.set_title("5.6.2 Cross-family predictor comparison")
    ax.grid(axis="x")
    ax.grid(axis="y", visible=False)
    legend_items = [Patch(facecolor=color, label=family) for family, color in FAMILY_COLORS.items()]
    ax.legend(
        handles=legend_items + [plt.Line2D([0], [0], marker="D", color="#222222", linestyle="", label="Aggregate MPKI")],
        frameon=False,
        ncols=3,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.08),
    )
    save_figure(fig, "5_6_2_predictor_comparison")


def plot_5_6_2_predictor_by_benchmark() -> None:
    rows = read_csv(BENCHMARK_ROOT / "5.6.2" / "summary.csv")
    predictor_rows = read_csv(BENCHMARK_ROOT / "5.6.2" / "summary_by_predictor.csv")
    predictors = [row["predictor"] for row in predictor_rows]
    predictors.sort(
        key=lambda predictor: next(
            to_float(row, "arithmetic_mean_direction_mpki")
            for row in predictor_rows
            if row["predictor"] == predictor
        )
    )
    lookup = {(row["benchmark"], row["predictor"]): to_float(row, "direction_mpki") for row in rows}
    values = np.array([[lookup[(benchmark, predictor)] for benchmark in BENCHMARK_ORDER] for predictor in predictors])

    fig, ax = plt.subplots(figsize=(11.8, 8.8))
    image = ax.imshow(values, cmap="magma_r", aspect="auto")
    ax.set_title("5.6.2 Direction MPKI by benchmark and predictor")
    ax.set_xlabel("Benchmark")
    ax.set_ylabel("Predictor")
    ax.set_xticks(np.arange(len(BENCHMARK_ORDER)), BENCHMARK_ORDER, rotation=40, ha="right")
    ax.set_yticks(np.arange(len(predictors)), [predictor_label(p, 26) for p in predictors])
    cbar = fig.colorbar(image, ax=ax)
    cbar.set_label("Direction MPKI")
    ax.grid(False)
    save_figure(fig, "5_6_2_predictor_by_benchmark")


def plot_5_7_train_vs_ref() -> None:
    rows = read_csv(BENCHMARK_ROOT / "5.7" / "train_vs_ref_by_predictor.csv")
    rows.sort(key=lambda row: to_float(row, "ref_arithmetic_mean_direction_mpki"))
    labels = [short_label(row["predictor"], 20) for row in rows]
    train = np.array([to_float(row, "train_arithmetic_mean_direction_mpki") for row in rows])
    ref = np.array([to_float(row, "ref_arithmetic_mean_direction_mpki") for row in rows])
    x = np.arange(len(rows))
    width = 0.36

    fig, ax = plt.subplots(figsize=(7.8, 4.8))
    ax.bar(x - width / 2, train, width, label="train", color=SERIES_COLORS["train"])
    ax.bar(x + width / 2, ref, width, label="ref", color=SERIES_COLORS["ref"])
    ax.set_title("5.7 Train versus ref arithmetic mean MPKI")
    ax.set_ylabel("Direction MPKI")
    ax.set_xticks(x, labels)
    ax.legend(frameon=False, ncols=2)
    ax.grid(axis="y")
    ax.grid(axis="x", visible=False)
    save_figure(fig, "5_7_train_vs_ref")


def plot_5_7_ref_delta_heatmap() -> None:
    rows = read_csv(BENCHMARK_ROOT / "5.7" / "train_vs_ref_by_benchmark.csv")
    predictors = ["Alpha21264", "Perceptron-M141-N32", "Perceptron-M56-N72"]
    lookup = {(row["benchmark"], row["predictor"]): to_float(row, "delta_direction_mpki") for row in rows}
    values = np.array([[lookup[(bench, pred)] for pred in predictors] for bench in BENCHMARK_ORDER])

    fig, ax = plt.subplots(figsize=(7.8, 6.2))
    vmax = max(abs(values.min()), abs(values.max()))
    image = ax.imshow(values, cmap="RdBu_r", vmin=-vmax, vmax=vmax, aspect="auto")
    ax.set_title("5.7 Ref - train direction MPKI delta")
    ax.set_xticks(np.arange(len(predictors)), [short_label(p, 16) for p in predictors])
    ax.set_yticks(np.arange(len(BENCHMARK_ORDER)), BENCHMARK_ORDER)
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            color = "white" if abs(values[i, j]) > vmax * 0.55 else "#222222"
            ax.text(j, i, f"{values[i, j]:+.2f}", ha="center", va="center", color=color, fontsize=7)
    cbar = fig.colorbar(image, ax=ax)
    cbar.set_label("MPKI delta")
    ax.grid(False)
    save_figure(fig, "5_7_ref_delta_heatmap")


def main() -> int:
    setup_style()
    plot_5_2_branch_frequency()
    plot_5_2_branch_mix()
    plot_5_3_predictor_groups()
    plot_5_3_fixed32_by_benchmark()
    plot_5_4_btb()
    plot_5_4_btb_by_benchmark()
    plot_5_5_ras()
    plot_5_5_ras_by_benchmark()
    plot_5_6_1_perceptrons()
    plot_5_6_2_predictor_comparison()
    plot_5_6_2_predictor_by_benchmark()
    plot_5_7_train_vs_ref()
    plot_5_7_ref_delta_heatmap()
    print(f"Wrote diagrams to {SCRIPT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
