"""
Chart generation service — matplotlib-based paper-quality chart PNGs.

Generates per-scenario bar+line charts matching the ECharts frontend style,
but with full control over fonts, line widths, and DPI for academic papers.
"""

import io
from typing import Any, Dict, List, Optional

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

# ─── Non-interactive backend (safe for server use) ───────────────────────────
mpl.use("Agg")

# ─── Matplotlib global style ────────────────────────────────────────────────
mpl.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 16,
    "axes.titlesize": 18,
    "axes.labelsize": 16,
    "xtick.labelsize": 14,
    "ytick.labelsize": 14,
    "legend.fontsize": 14,
    "legend.frameon": True,
    "legend.framealpha": 0.92,
    "legend.edgecolor": "#cccccc",
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": "#e0e0e0",
    "grid.linewidth": 0.9,
    "grid.linestyle": "-",
    "axes.axisbelow": True,
})

# ─── Visual constants ───────────────────────────────────────────────────────
COL_A_BAR = "#b0c4de"  # light steel blue
COL_A_LINE = "#6c9fc2"  # medium steel blue
COL_B_BAR = "#1d4e7f"  # deep navy
COL_B_LINE = "#1d4e7f"  # deep navy
TARGET_ACC = 85.0

# ─── English labels for scenarios (avoid CJK font issues) ───────────────────
SCENARIO_NAMES_EN = {
    "fall":               "Fall Incident",
    "abnormal_stay":      "Abnormal Overstay",
    "sleep_late":         "Late-Night Wakefulness",
    "prolonged_sitting":  "Prolonged Sitting",
    "family_fight":       "Physical Altercation",
}


def generate_scenario_chart_png(
    scenario_id: str,
    runs: List[Dict[str, Any]],
    *,
    width: float = 17.0,
    height: float = 4.8,
    dpi: int = 200,
) -> bytes:
    """
    Generate a per-scenario bar+line chart as PNG bytes.

    Parameters
    ----------
    scenario_id : str
        Scenario ID (e.g. 'fall', 'abnormal_stay'). Mapped to English display title.
    runs : list[dict]
        Each run dict should have:
          - no_env.score  (0.0–1.0)
          - with_env.score (0.0–1.0)
    width, height : figure size in inches
    dpi : output DPI

    Returns
    -------
    bytes : PNG image data
    """
    n = len(runs)
    if n == 0:
        raise ValueError("No runs provided")

    # ── Extract scores ───────────────────────────────────────────────────
    scores_a = []
    scores_b = []
    for r in runs:
        sa = (r.get("no_env") or {}).get("score", 0.0)
        sb = (r.get("with_env") or {}).get("score", 0.0)
        scores_a.append(sa * 100)
        scores_b.append(sb * 100)

    # Cumulative averages
    cum_a = [sum(scores_a[: i + 1]) / (i + 1) for i in range(n)]
    cum_b = [sum(scores_b[: i + 1]) / (i + 1) for i in range(n)]

    x = np.arange(n)
    trial_labels = [f"Trial {i + 1}" for i in range(n)]

    # ── Figure ───────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(width, height))

    # Only horizontal grid lines
    ax.yaxis.grid(True, color="#e0e0e0", linewidth=0.9, linestyle="-")
    ax.xaxis.grid(False)

    bar_w = 0.32
    gap = 0.06

    # Bars
    bars_a = ax.bar(
        x - (bar_w / 2 + gap / 2),
        scores_a,
        width=bar_w,
        color=COL_A_BAR,
        edgecolor="white",
        linewidth=1.2,
        zorder=3,
        label="Skeleton Only",
    )
    bars_b = ax.bar(
        x + (bar_w / 2 + gap / 2),
        scores_b,
        width=bar_w,
        color=COL_B_BAR,
        edgecolor="white",
        linewidth=1.2,
        zorder=3,
        label="Skeleton + Env",
    )

    # Bar value labels — only show when bars are different heights
    # to avoid overlapping text at the top
    for i in range(n):
        va, vb = scores_a[i], scores_b[i]
        bar_a, bar_b = bars_a[i], bars_b[i]
        # Skip label if value is 0
        if va > 0:
            # Place inside bar if tall enough, otherwise above
            if va >= 20:
                ax.text(bar_a.get_x() + bar_a.get_width() / 2, va / 2,
                        f"{va:.0f}%", ha="center", va="center",
                        fontsize=9, color="#444", fontweight="bold")
            else:
                ax.text(bar_a.get_x() + bar_a.get_width() / 2, va + 1.5,
                        f"{va:.0f}%", ha="center", va="bottom",
                        fontsize=9, color="#555")
        if vb > 0:
            if vb >= 20:
                ax.text(bar_b.get_x() + bar_b.get_width() / 2, vb / 2,
                        f"{vb:.0f}%", ha="center", va="center",
                        fontsize=9, color="white", fontweight="bold")
            else:
                ax.text(bar_b.get_x() + bar_b.get_width() / 2, vb + 1.5,
                        f"{vb:.0f}%", ha="center", va="bottom",
                        fontsize=9, color=COL_B_LINE)

    # Lines (cumulative averages)
    lw_a = 2.5
    lw_b = 3.0
    ms = 7

    ax.plot(
        x,
        cum_a,
        color=COL_A_LINE,
        lw=lw_a,
        ls="--",
        marker="o",
        markersize=ms,
        markeredgecolor="white",
        markeredgewidth=1.2,
        zorder=10,
        label="Skeleton Only (avg)",
    )
    ax.plot(
        x,
        cum_b,
        color=COL_B_LINE,
        lw=lw_b,
        ls="-",
        marker="D",
        markersize=ms,
        markeredgecolor="white",
        markeredgewidth=1.2,
        zorder=10,
        label="Skeleton + Env (avg)",
    )

    # 85% Target reference line
    ax.axhline(
        TARGET_ACC,
        ls=":",
        lw=2.0,
        color="#c0392b",
        zorder=15,
    )
    ax.text(
        -0.45,
        TARGET_ACC + 1.5,
        f"{TARGET_ACC:.0f}% Target",
        ha="left",
        va="bottom",
        fontsize=10,
        color="#c0392b",
        fontweight="bold",
    )

    # Axes
    ax.set_xticks(x)
    ax.set_xticklabels(trial_labels, fontsize=11)
    ax.set_ylabel("Score (%)", fontsize=13, fontweight="bold")
    ax.set_ylim(0, 105)
    ax.set_xlim(-0.6, n - 0.4)
    ax.yaxis.set_major_formatter(mpl.ticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.tick_params(bottom=False)

    # Legend at top center (like the vue-echarts layout, no title)
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, 1.12),
        ncol=4,
        fontsize=10,
        framealpha=0.95,
        edgecolor="#cccccc",
    )

    fig.tight_layout()

    # ── Export PNG ────────────────────────────────────────────────────────
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", transparent=True)
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def generate_all_scenarios_chart_png(
    categories: List[Dict[str, Any]],
    *,
    dpi: int = 300,
) -> bytes:
    """
    Generate a multi-panel figure with one subplot per scenario (like fig2_per_run).

    Returns PNG bytes.
    """
    scenarios = []
    for cat in categories:
        for sc in cat.get("scenarios", []):
            if "error" in sc:
                continue
            scenarios.append(sc)

    n = len(scenarios)
    if n == 0:
        raise ValueError("No scenarios")

    n_cols = min(3, n)
    n_rows = (n + n_cols - 1) // n_cols

    fig, axes = plt.subplots(
        n_rows,
        n_cols,
        figsize=(7.0 * n_cols, 5.0 * n_rows),
        sharex=False,
        sharey=True,
        squeeze=False,
    )

    for idx, sc in enumerate(scenarios):
        row, col = divmod(idx, n_cols)
        ax = axes[row][col]
        runs = sc.get("runs", [])
        nr = len(runs)
        if nr == 0:
            ax.set_visible(False)
            continue

        scores_a = [
            (r.get("no_env") or {}).get("score", 0.0) * 100 for r in runs
        ]
        scores_b = [
            (r.get("with_env") or {}).get("score", 0.0) * 100 for r in runs
        ]
        cum_a = [sum(scores_a[: i + 1]) / (i + 1) for i in range(nr)]
        cum_b = [sum(scores_b[: i + 1]) / (i + 1) for i in range(nr)]
        x = np.arange(nr)

        bar_w = 0.30
        gap = 0.06

        ax.bar(
            x - (bar_w / 2 + gap / 2),
            scores_a,
            width=bar_w,
            color=COL_A_BAR,
            edgecolor="white",
            linewidth=1.0,
            zorder=3,
        )
        ax.bar(
            x + (bar_w / 2 + gap / 2),
            scores_b,
            width=bar_w,
            color=COL_B_BAR,
            edgecolor="white",
            linewidth=1.0,
            zorder=3,
        )

        ax.plot(
            x, cum_a,
            color=COL_A_LINE, lw=2.5, ls="--",
            marker="o", markersize=8, markeredgecolor="white", markeredgewidth=1,
            zorder=10,
        )
        ax.plot(
            x, cum_b,
            color=COL_B_LINE, lw=3.0, ls="-",
            marker="D", markersize=8, markeredgecolor="white", markeredgewidth=1,
            zorder=10,
        )

        ax.axhline(TARGET_ACC, ls=":", lw=1.8, color="#c0392b", zorder=2)
        ax.set_title(sc.get("name", sc.get("id", "")), fontsize=16, fontweight="bold")
        ax.set_ylim(-5, 115)
        ax.set_xticks(x)
        ax.set_xticklabels([f"T{i + 1}" for i in range(nr)], fontsize=12)
        ax.set_ylabel("Score (%)", fontsize=13)
        ax.yaxis.set_major_formatter(
            mpl.ticker.FuncFormatter(lambda v, _: f"{v:.0f}%")
        )

    # Hide unused subplots
    for idx in range(n, n_rows * n_cols):
        row, col = divmod(idx, n_cols)
        axes[row][col].set_visible(False)

    # Shared legend
    legend_handles = [
        Patch(facecolor=COL_A_BAR, edgecolor="white", label="Skeleton Only"),
        Patch(facecolor=COL_B_BAR, edgecolor="white", label="Skeleton + Env"),
        Line2D([0], [0], color=COL_A_LINE, lw=2.5, ls="--", marker="o",
               markersize=8, label="Skeleton Only (avg)"),
        Line2D([0], [0], color=COL_B_LINE, lw=3.0, ls="-", marker="D",
               markersize=8, label="Skeleton + Env (avg)"),
    ]
    fig.legend(
        handles=legend_handles,
        loc="lower center",
        ncol=4,
        fontsize=14,
        bbox_to_anchor=(0.5, -0.02),
        frameon=True,
        framealpha=0.9,
    )

    fig.tight_layout(rect=[0, 0.05, 1, 1])

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", transparent=True)
    plt.close(fig)
    buf.seek(0)
    return buf.read()
