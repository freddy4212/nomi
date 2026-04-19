#!/usr/bin/env python3
"""
Academic-style result plots for the Skeleton-Only vs. Skeleton+Environment A/B evaluation.

Usage:
    python plot_results.py [path/to/eval_*.json]

If no path is supplied, the most recent JSON file in the 'results/' sub-directory
next to this script is loaded automatically.

Output files are written to  results/figures/<eval_timestamp>/
    fig1_accuracy.pdf        — per-scenario grouped-bar accuracy comparison
    fig2_per_run.pdf         — per-run score trajectories (5 × 1 panel grid)
    fig3_delta.pdf           — accuracy-gain bar chart  (B − A per scenario)
"""

import json
import pathlib
import statistics
import sys

import matplotlib as mpl
import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

# ─── Matplotlib global style ─────────────────────────────────────────────────
mpl.rcParams.update({
    "font.family":        "DejaVu Sans",
    "font.size":          12,
    "axes.titlesize":     12,
    "axes.labelsize":     12,
    "xtick.labelsize":    11,
    "ytick.labelsize":    11,
    "legend.fontsize":    11,
    "legend.frameon":     True,
    "legend.framealpha":  0.92,
    "legend.edgecolor":   "#cccccc",
    "figure.dpi":         200,
    "savefig.dpi":        400,
    "savefig.bbox":       "tight",
    "axes.spines.top":    False,
    "axes.spines.right":  False,
    "axes.grid":          True,
    "grid.color":         "#e0e0e0",
    "grid.linewidth":     0.9,
    "grid.linestyle":     "-",
    "axes.axisbelow":     True,
})

# ─── Visual design constants ─────────────────────────────────────────────────
COL_A      = "#6c9fc2"   # skeleton-only  — steel blue (light)
COL_B      = "#1d4e7f"   # skeleton+env   — deep navy  (dark)
HATCH_A    = "///"       # bar hatch for skeleton-only
HATCH_B    = ""          # solid fill for skeleton+env
LS_A       = "--"        # line style for skeleton-only
LS_B       = "-"         # line style for skeleton+env
LW         = 2.5         # default line width
MARKER_A   = "o"
MARKER_B   = "s"
TARGET_ACC = 85.0        # reference line

# ─── English labels for scenarios ────────────────────────────────────────────
SCENARIO_NAMES = {
    "fall":               "Fall\nIncident",
    "abnormal_stay":      "Abnormal\nOverstay",
    "sleep_late":         "Late-Night\nWakefulness",
    "prolonged_sitting":  "Prolonged\nSitting",
    "family_fight":       "Physical\nAltercation",
}
# Short versions for panel titles
SCENARIO_NAMES_SHORT = {
    "fall":               "Fall Incident",
    "abnormal_stay":      "Abnormal Overstay",
    "sleep_late":         "Late-Night Wakefulness",
    "prolonged_sitting":  "Prolonged Sitting",
    "family_fight":       "Physical Altercation",
}
CATEGORY_NAMES = {
    "short_term_accident": "Short-Term Incident",
    "long_term_habit":     "Long-Term Habit",
    "argument":            "Conflict",
}

# ─── Legend proxy handles (shared across figures) ───────────────────────────
LEGEND_HANDLES = [
    Patch(facecolor=COL_A, edgecolor="white", hatch=HATCH_A, label="Skeleton Only"),
    Patch(facecolor=COL_B, edgecolor="white", hatch=HATCH_B, label="Skeleton + Environment"),
]
LEGEND_LINES = [
    Line2D([0], [0], color=COL_A, lw=LW, ls=LS_A, marker=MARKER_A,
           markersize=8, label="Skeleton Only"),
    Line2D([0], [0], color=COL_B, lw=LW, ls=LS_B, marker=MARKER_B,
           markersize=8, label="Skeleton + Environment"),
]


# ─── Helper: flatten scenarios from JSON ────────────────────────────────────
def iter_scenarios(data):
    """Yield (category_id, scenario_dict) in order."""
    for cat in data["categories"]:
        cid = cat["category_id"]
        for sc in cat["scenarios"]:
            yield cid, sc


# ═══════════════════════════════════════════════════════════════════════════
# Figure 1 — Per-Scenario Grouped-Bar Accuracy
# ═══════════════════════════════════════════════════════════════════════════
def fig1_accuracy(data, out_dir: pathlib.Path):
    scenarios = list(iter_scenarios(data))
    n = len(scenarios)
    x = np.arange(n)
    bar_w = 0.32
    gap   = 0.06

    fig, ax = plt.subplots(figsize=(8.0, 4.5))

    acc_a_vals, acc_b_vals = [], []
    std_a_vals, std_b_vals = [], []

    for _, sc in scenarios:
        sa = sc["scores_no_env"]
        sb = sc["scores_with_env"]
        acc_a_vals.append(sum(sa) / len(sa) * 100)
        acc_b_vals.append(sum(sb) / len(sb) * 100)
        std_a_vals.append((statistics.stdev(sa) if len(sa) > 1 else 0) * 100)
        std_b_vals.append((statistics.stdev(sb) if len(sb) > 1 else 0) * 100)

    bars_a = ax.bar(
        x - (bar_w / 2 + gap / 2), acc_a_vals,
        width=bar_w, color=COL_A, hatch=HATCH_A,
        edgecolor="white", linewidth=1.0, zorder=3,
        yerr=std_a_vals, error_kw=dict(ecolor="#444444", capsize=5, capthick=1.5, lw=1.5),
    )
    bars_b = ax.bar(
        x + (bar_w / 2 + gap / 2), acc_b_vals,
        width=bar_w, color=COL_B, hatch=HATCH_B,
        edgecolor="white", linewidth=1.0, zorder=3,
        yerr=std_b_vals, error_kw=dict(ecolor="#888888", capsize=5, capthick=1.5, lw=1.5),
    )

    # Score labels above bars
    for bar, val, std in zip(bars_a, acc_a_vals, std_a_vals):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + std + 1.5,
            f"{val:.0f}",
            ha="center", va="bottom", fontsize=10, color="#444444",
        )
    for bar, val, std in zip(bars_b, acc_b_vals, std_b_vals):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + std + 1.5,
            f"{val:.0f}",
            ha="center", va="bottom", fontsize=10, color=COL_B,
        )

    # Reference line
    ax.axhline(TARGET_ACC, ls=":", lw=1.5, color="#999999", zorder=2)
    ax.text(n - 0.05, TARGET_ACC + 1, f"{TARGET_ACC:.0f}% Target",
            ha="right", va="bottom", fontsize=10, color="#999999")

    # Category separator lines + labels
    cat_ids    = [c for c, _ in scenarios]
    cat_breaks = []
    prev = cat_ids[0]
    for i, cid in enumerate(cat_ids[1:], 1):
        if cid != prev:
            cat_breaks.append(i - 0.5)
            prev = cid
    for xb in cat_breaks:
        ax.axvline(xb, ls="--", lw=0.9, color="#cccccc", zorder=1)

    # Category span annotations
    cat_spans = []
    prev_cid, start_i = cat_ids[0], 0
    for i, cid in enumerate(cat_ids + ["_end"]):
        if cid != prev_cid:
            cat_spans.append((prev_cid, start_i, i - 1))
            prev_cid, start_i = cid, i
    for (cid, i0, i1) in cat_spans:
        mid = (i0 + i1) / 2
        label = CATEGORY_NAMES.get(cid, cid)
        ax.text(mid, -12, label, ha="center", va="top", fontsize=10,
                style="italic", color="#666666")

    ax.set_xticks(x)
    ax.set_xticklabels([SCENARIO_NAMES.get(sc["id"], sc["id"])
                        for _, sc in scenarios], fontsize=10)
    ax.set_ylabel("Mean Score (%)")
    ax.set_ylim(0, 115)
    ax.set_xlim(-0.6, n - 0.4)
    ax.legend(handles=LEGEND_HANDLES, loc="upper left", ncol=1)
    ax.tick_params(bottom=False)

    fig.tight_layout(rect=[0, 0.04, 1, 1])
    out = out_dir / "fig1_accuracy.pdf"
    fig.savefig(out)
    out_png = out_dir / "fig1_accuracy.png"
    fig.savefig(out_png)
    plt.close(fig)
    print(f"  Saved {out.name}")


# ═══════════════════════════════════════════════════════════════════════════
# Figure 2 — Per-Run Score Trajectories
# ═══════════════════════════════════════════════════════════════════════════
def fig2_per_run(data, out_dir: pathlib.Path):
    scenarios = list(iter_scenarios(data))
    n = len(scenarios)
    n_cols = 3
    n_rows = (n + n_cols - 1) // n_cols

    fig, axes = plt.subplots(n_rows, n_cols,
                             figsize=(8.5, 3.2 * n_rows),
                             sharex=True, sharey=True)
    axes_flat = np.array(axes).flatten()

    for idx, (cat_id, sc) in enumerate(scenarios):
        ax = axes_flat[idx]
        scores_a = [s * 100 for s in sc["scores_no_env"]]
        scores_b = [s * 100 for s in sc["scores_with_env"]]
        runs = list(range(1, len(scores_a) + 1))

        ax.plot(runs, scores_a, color=COL_A, lw=LW, ls=LS_A,
                marker=MARKER_A, markersize=8, zorder=3)
        ax.plot(runs, scores_b, color=COL_B, lw=LW, ls=LS_B,
                marker=MARKER_B, markersize=8, zorder=3)

        # Shaded area between the two lines to highlight gap
        ax.fill_between(runs, scores_a, scores_b,
                        where=[b >= a for a, b in zip(scores_a, scores_b)],
                        alpha=0.08, color=COL_B, zorder=2)

        # Cumulative mean lines
        cum_a = [sum(scores_a[:i+1]) / (i+1) for i in range(len(scores_a))]
        cum_b = [sum(scores_b[:i+1]) / (i+1) for i in range(len(scores_b))]

        ax.plot(runs, cum_a, color=COL_A, lw=1.5, ls=":", alpha=0.7, zorder=2)
        ax.plot(runs, cum_b, color=COL_B, lw=1.5, ls=":", alpha=0.7, zorder=2)

        # Reference line
        ax.axhline(TARGET_ACC, ls=":", lw=1.0, color="#bbbbbb", zorder=1)

        label = SCENARIO_NAMES_SHORT.get(sc["id"], sc["id"])
        cat   = CATEGORY_NAMES.get(cat_id, cat_id)
        ax.set_title(f"{label}\n({cat})", fontsize=11, pad=4)
        ax.set_ylim(-5, 110)
        ax.set_xticks(runs)

    # Hide unused subplots
    for idx in range(n, len(axes_flat)):
        axes_flat[idx].set_visible(False)

    # Shared axis labels
    for ax in axes_flat[n_cols*(n_rows-1):n_cols*n_rows]:
        ax.set_xlabel("Trial")
    for row in range(n_rows):
        axes_flat[row * n_cols].set_ylabel("Score (%)")

    # Shared legend (bottom)
    fig.legend(handles=LEGEND_LINES,
               loc="lower center", ncol=2,
               bbox_to_anchor=(0.5, -0.02),
               frameon=True, framealpha=0.9)

    fig.tight_layout(rect=[0, 0.06, 1, 1])
    out = out_dir / "fig2_per_run.pdf"
    fig.savefig(out)
    out_png = out_dir / "fig2_per_run.png"
    fig.savefig(out_png)
    plt.close(fig)
    print(f"  Saved {out.name}")


# ═══════════════════════════════════════════════════════════════════════════
# Figure 3 — Accuracy-Gain Bar Chart  (ΔAcc = B − A per scenario)
# ═══════════════════════════════════════════════════════════════════════════
def fig3_delta(data, out_dir: pathlib.Path):
    scenarios = list(iter_scenarios(data))
    n = len(scenarios)
    x = np.arange(n)

    sc_labels = [SCENARIO_NAMES.get(sc["id"], sc["id"]) for _, sc in scenarios]
    deltas     = [sc.get("accuracy_delta", 0) for _, sc in scenarios]
    acc_a      = [sc.get("accuracy_no_env", 0) for _, sc in scenarios]
    acc_b      = [sc.get("accuracy_with_env", 0) for _, sc in scenarios]

    # Color each bar by magnitude (gradient from light to dark navy)
    norm = mpl.colors.Normalize(vmin=0, vmax=100)
    cmap = mpl.colors.LinearSegmentedColormap.from_list(
        "ab_grad", [COL_A, COL_B])

    fig, ax = plt.subplots(figsize=(7.5, 4.2))

    for i, (delta, a, b) in enumerate(zip(deltas, acc_a, acc_b)):
        color = cmap(norm(delta))
        bar = ax.bar(i, delta, width=0.55, color=color, edgecolor="white",
                      linewidth=1.0, zorder=3)
        # Annotate with A acc → B acc
        ax.text(i, delta + 1.0,
                f"+{delta:.0f}%",
                ha="center", va="bottom", fontsize=11, fontweight="bold",
                color=cmap(norm(delta + 20)))
        ax.text(i, -4.5,
                f"{a:.0f}→{b:.0f}",
                ha="center", va="top", fontsize=10, color="#555555")

    ax.axhline(0, color="#aaaaaa", lw=1.2)
    ax.set_xticks(x)
    ax.set_xticklabels(sc_labels, fontsize=10)
    ax.set_ylabel("Accuracy Gain, ΔAcc (%)")
    ax.set_ylim(-10, 115)
    ax.set_xlim(-0.55, n - 0.45)
    ax.tick_params(bottom=False)

    # Colorbar as legend
    sm = mpl.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, orientation="vertical",
                        fraction=0.03, pad=0.02)
    cbar.set_label("Gain (%)", fontsize=11)
    cbar.ax.tick_params(labelsize=10)

    # Category annotations (same as fig1)
    cat_ids    = [c for c, _ in scenarios]
    cat_breaks = []
    prev = cat_ids[0]
    for i, cid in enumerate(cat_ids[1:], 1):
        if cid != prev:
            cat_breaks.append(i - 0.5)
            prev = cid
    for xb in cat_breaks:
        ax.axvline(xb, ls="--", lw=0.9, color="#cccccc", zorder=1)

    cat_spans = []
    prev_cid, start_i = cat_ids[0], 0
    for i, cid in enumerate(cat_ids + ["_end"]):
        if cid != prev_cid:
            cat_spans.append((prev_cid, start_i, i - 1))
            prev_cid, start_i = cid, i
    for (cid, i0, i1) in cat_spans:
        mid = (i0 + i1) / 2
        label = CATEGORY_NAMES.get(cid, cid)
        ax.text(mid, -10, label, ha="center", va="top", fontsize=10,
                style="italic", color="#666666")

    fig.tight_layout(rect=[0, 0.04, 1, 1])
    out = out_dir / "fig3_delta.pdf"
    fig.savefig(out)
    out_png = out_dir / "fig3_delta.png"
    fig.savefig(out_png)
    plt.close(fig)
    print(f"  Saved {out.name}")


# ═══════════════════════════════════════════════════════════════════════════
# Figure 4 — Robustness (Std-dev) Comparison  (bonus chart)
# ═══════════════════════════════════════════════════════════════════════════
def fig4_robustness(data, out_dir: pathlib.Path):
    scenarios = list(iter_scenarios(data))
    n = len(scenarios)
    x = np.arange(n)
    bar_w = 0.32
    gap   = 0.06

    sc_labels = [SCENARIO_NAMES.get(sc["id"], sc["id"]) for _, sc in scenarios]
    rob_a = [sc.get("robustness_no_env", 0) for _, sc in scenarios]
    rob_b = [sc.get("robustness_with_env", 0) for _, sc in scenarios]
    std_a = [sc.get("std_no_env", 0) * 100 for _, sc in scenarios]
    std_b = [sc.get("std_with_env", 0) * 100 for _, sc in scenarios]

    fig, (ax_top, ax_bot) = plt.subplots(
        2, 1, figsize=(8.0, 6.5), gridspec_kw={"height_ratios": [1.2, 1]})

    # Top: Robustness (consistency index)
    ax_top.bar(x - (bar_w / 2 + gap / 2), rob_a, width=bar_w,
               color=COL_A, hatch=HATCH_A, edgecolor="white", lw=1.0, zorder=3)
    ax_top.bar(x + (bar_w / 2 + gap / 2), rob_b, width=bar_w,
               color=COL_B, hatch=HATCH_B, edgecolor="white", lw=1.0, zorder=3)
    ax_top.axhline(100, ls=":", lw=1.2, color="#bbbbbb", zorder=1)
    ax_top.set_xticks(x)
    ax_top.set_xticklabels([""] * n)
    ax_top.set_ylabel("Consistency Index (%)")
    ax_top.set_ylim(0, 115)
    ax_top.legend(handles=LEGEND_HANDLES, loc="lower right", ncol=1)
    ax_top.tick_params(bottom=False)

    # Bottom: Std dev
    ax_bot.bar(x - (bar_w / 2 + gap / 2), std_a, width=bar_w,
               color=COL_A, hatch=HATCH_A, edgecolor="white", lw=1.0, zorder=3)
    ax_bot.bar(x + (bar_w / 2 + gap / 2), std_b, width=bar_w,
               color=COL_B, hatch=HATCH_B, edgecolor="white", lw=1.0, zorder=3)
    ax_bot.set_xticks(x)
    ax_bot.set_xticklabels(sc_labels, fontsize=10)
    ax_bot.set_ylabel("Score Std. Dev. (%)")
    ax_bot.set_ylim(0, 60)
    ax_bot.tick_params(bottom=False)

    # Category separators on both panels
    cat_ids = [c for c, _ in scenarios]
    cat_breaks = []
    prev = cat_ids[0]
    for i, cid in enumerate(cat_ids[1:], 1):
        if cid != prev:
            cat_breaks.append(i - 0.5)
            prev = cid
    for ax in (ax_top, ax_bot):
        for xb in cat_breaks:
            ax.axvline(xb, ls="--", lw=0.9, color="#cccccc", zorder=1)

    cat_spans = []
    prev_cid, start_i = cat_ids[0], 0
    for i, cid in enumerate(cat_ids + ["_end"]):
        if cid != prev_cid:
            cat_spans.append((prev_cid, start_i, i - 1))
            prev_cid, start_i = cid, i
    for (cid, i0, i1) in cat_spans:
        mid = (i0 + i1) / 2
        label = CATEGORY_NAMES.get(cid, cid)
        ax_bot.text(mid, -11, label, ha="center", va="top", fontsize=10,
                    style="italic", color="#666666")

    fig.tight_layout(rect=[0, 0.04, 1, 1])
    out = out_dir / "fig4_robustness.pdf"
    fig.savefig(out)
    out_png = out_dir / "fig4_robustness.png"
    fig.savefig(out_png)
    plt.close(fig)
    print(f"  Saved {out.name}")


# ═══════════════════════════════════════════════════════════════════════════
# Main entry point
# ═══════════════════════════════════════════════════════════════════════════
def main():
    script_dir = pathlib.Path(__file__).parent

    # Resolve input JSON
    if len(sys.argv) > 1:
        json_path = pathlib.Path(sys.argv[1])
    else:
        results_dir = script_dir / "results"
        candidates = sorted(results_dir.glob("eval_*.json"))
        if not candidates:
            sys.exit("No eval_*.json files found in results/")
        json_path = candidates[-1]  # most recent

    print(f"Loading: {json_path.name}")
    data = json.loads(json_path.read_text(encoding="utf-8"))

    # Output directory
    ts = data.get("timestamp", "unknown").replace(":", "").replace(".", "")[:15]
    out_dir = script_dir / "results" / "figures" / ts
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output : {out_dir}")

    fig1_accuracy(data, out_dir)
    fig2_per_run(data, out_dir)
    fig3_delta(data, out_dir)
    fig4_robustness(data, out_dir)

    print("Done.")


if __name__ == "__main__":
    main()
