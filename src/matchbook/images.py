"""The README images: python -m matchbook images <report.md> <dir>.

Reads the tables of a diagnosis report written by python -m matchbook report (not the log)
and writes three SVG files to the directory (C21): controls.svg, the findings per control by
severity; injected.svg, the detection and false alarms of matchbook and of the baseline on
the injected log; baseline.svg, the overlap of each baseline rule with its criterion on the
real log. The same report gives the same bytes (C9).
"""

import argparse
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("svg")

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.typing import RcKeyType

# One colour per series in every image, validated for colour blindness on adjacent pairs.
# The findings are matchbook's, so their severities are steps of matchbook's blue.
MATCHBOOK = "#2a78d6"
BASELINE = "#eb6834"
BOTH = "#1baf7a"
SEVERITY = {"high": "#184f95", "medium": MATCHBOOK, "low": "#86b6ef"}
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e1e0d9"
# A fixed salt and no date make two runs give the same bytes (C9).
STYLE: dict[RcKeyType, Any] = {
    "svg.hashsalt": "matchbook",
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "axes.edgecolor": GRID,
    "axes.labelcolor": MUTED,
    "text.color": INK,
    "xtick.color": MUTED,
    "ytick.color": INK,
}

Table = list[dict[str, str]]


def tables(text: str) -> dict[str, Table]:
    """Each table of the report under the title of its ## section, as one dict per row from
    the header to the cells."""
    found: dict[str, Table] = {}
    title = ""
    header: list[str] | None = None
    for line in text.splitlines():
        if line.startswith("## "):
            title, header = line[3:], None
        elif line.startswith("|"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if header is None:
                header = cells
                found[title] = []
            elif not all(set(cell) <= set("-:") for cell in cells):
                found[title].append(dict(zip(header, cells, strict=True)))
    return found


def injected(found: dict[str, Table]) -> Table:
    """The table of the section Injected log, seed N."""
    return next(rows for title, rows in found.items() if title.startswith("Injected log"))


def number(cell: str) -> int:
    """A count of the report; an empty cell, as for a look-alike's detections, is 0."""
    return int(cell) if cell else 0


def _figure(height: float) -> tuple[Figure, Axes]:
    fig, ax = plt.subplots(figsize=(8, height))
    _frame(ax)
    return fig, ax


def _frame(ax: Axes) -> None:
    """Recessive axes: a hairline grid behind the bars, no box."""
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


def _stacked(
    ax: Axes, labels: list[str], segments: dict[str, list[int]], colours: dict[str, str]
) -> None:
    """Horizontal bars, first label on top, stacked by segment in order, with a gap of the
    surface between segments."""
    y = list(range(len(labels)))[::-1]
    left = [0] * len(labels)
    for name, values in segments.items():
        ax.barh(
            y, values, left=left, height=0.55, color=colours[name], label=name,
            edgecolor=SURFACE, linewidth=1.5,
        )  # fmt: skip
        left = [a + b for a, b in zip(left, values, strict=True)]
    ax.set_yticks(y, labels)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.spines["bottom"].set_visible(False)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncols=len(segments), frameon=False)


def _ends(ax: Axes, totals: list[int], texts: list[str]) -> None:
    """The text written at the end of each bar, with room for it on the right."""
    y = list(range(len(totals)))[::-1]
    pad = max(totals) * 0.015
    for row, total, text in zip(y, totals, texts, strict=True):
        ax.text(total + pad, row, text, va="center", fontsize=9, color=INK)
    ax.set_xlim(0, max(totals) * 1.9)
    # The room for the text holds no ticks: the axis ends at the longest bar.
    ax.set_xticks([tick for tick in ax.get_xticks() if tick <= max(totals)])


def controls(found: dict[str, Table]) -> Figure:
    """The findings per control stacked by severity, the euros at stake at the end."""
    status = {row["Control"]: row for row in found["Controls"]}
    rows = found["Findings by criterion"]
    levels = list(SEVERITY)
    segments = {level: [number(row[level.capitalize()]) for row in rows] for level in levels}
    fig, ax = _figure(3.6)
    _stacked(
        ax, [f"{row['Criterion']} {status[row['Criterion']]['Status']}" for row in rows],
        segments, SEVERITY,
    )  # fmt: skip
    texts = []
    for i, row in enumerate(rows):
        counts = ", ".join(f"{segments[level][i]} {level}" for level in levels)
        eur = status[row["Criterion"]]["EUR at stake"]
        texts.append(f"{counts}\n{eur} EUR at stake")
    _ends(ax, [number(row["Findings"]) for row in rows], texts)
    ax.set_xlabel("Findings on the full log")
    fig.tight_layout()
    return fig


def _paired(ax: Axes, rows: Table, ours: str, theirs: str, title: str) -> None:
    """For each kind, a bar for matchbook and one for the baseline, out of the items."""
    width = 0.38
    x = list(range(len(rows)))
    for shift, column, name, colour in (
        (-width / 2, ours, "matchbook", MATCHBOOK),
        (width / 2, theirs, "baseline", BASELINE),
    ):
        values = [number(row[column]) for row in rows]
        bars = ax.bar(
            [i + shift for i in x], values, width, color=colour, label=name,
            edgecolor=SURFACE, linewidth=1.5,
        )  # fmt: skip
        ax.bar_label(bars, padding=2, fontsize=9, color=INK)
    items = number(rows[0]["Items"])
    ax.set_xticks(x, [row["Kind"] for row in rows])
    ax.set_ylim(0, items * 1.15)
    ax.set_yticks([0, items // 2, items])
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_title(title, fontsize=10, loc="left", color=INK)


def injected_figure(found: dict[str, Table]) -> Figure:
    """Faults detected out of 50 per kind F1 to F6, false alarms per kind L1 to L3."""
    rows = injected(found)
    faults = [row for row in rows if row["Kind"].startswith("F")]
    lookalikes = [row for row in rows if row["Kind"].startswith("L")]
    fig, (left, right) = plt.subplots(
        1, 2, figsize=(8, 3.4), width_ratios=[len(faults), len(lookalikes)]
    )
    for ax in (left, right):
        _frame(ax)
    _paired(left, faults, "Detected", "Baseline detected", "Faults detected (higher is better)")
    _paired(
        right, lookalikes, "False alarms", "Baseline false alarms",
        "False alarms (lower is better)",
    )  # fmt: skip
    left.set_ylabel(f"Items of {number(rows[0]['Items'])}")
    fig.legend(*left.get_legend_handles_labels(), loc="upper center", ncols=2, frameon=False)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    return fig


def baseline(found: dict[str, Table]) -> Figure:
    """Per baseline rule, the items flagged by the rule only, by both, by the criterion
    only."""
    rows = found["Baseline on the real log"]
    columns = {"rule only": "Rule only", "both": "Both", "criterion only": "Criterion only"}
    segments = {name: [number(row[column]) for row in rows] for name, column in columns.items()}
    colours = {"rule only": BASELINE, "both": BOTH, "criterion only": MATCHBOOK}
    fig, ax = _figure(3.2)
    _stacked(ax, [f"{row['Rule']} vs {row['Criterion']}" for row in rows], segments, colours)
    texts = [", ".join(f"{segments[name][i]} {name}" for name in columns) for i in range(len(rows))]
    _ends(ax, [sum(values) for values in zip(*segments.values(), strict=True)], texts)
    ax.set_xlabel("Items on the full log")
    fig.tight_layout()
    return fig


def draw(report: str, directory: Path) -> list[Path]:
    """Writes the three images of the report text into the directory."""
    found = tables(report)
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    with plt.rc_context(STYLE):
        for name, make in (
            ("controls", controls),
            ("injected", injected_figure),
            ("baseline", baseline),
        ):
            fig = make(found)
            path = directory / f"{name}.svg"
            fig.savefig(path, format="svg", metadata={"Date": None})
            plt.close(fig)
            written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="matchbook images", description=__doc__)
    parser.add_argument("report", type=Path, help="the Markdown report of matchbook report")
    parser.add_argument("directory", type=Path, help="the directory to write the images to")
    args = parser.parse_args(argv)
    draw(args.report.read_text(encoding="utf-8"), args.directory)
    return 0


if __name__ == "__main__":
    sys.exit(main())
