"""The diagnosis report: python -m matchbook report <log.xes> <output.md> --seed <n>.

Writes a Markdown file with the status of each control on the log and the keep, fix or
replace plan (C18), the findings per severity and per criterion, and the tables of
matchbook.score and matchbook.compare (C19). Writes nothing else, and never inside the
directory of the log (C10).
"""

import argparse
import sys
from pathlib import Path

from matchbook.checks import SEVERITIES, Finding, findings, severity
from matchbook.compare import Comparison, compare
from matchbook.score import Score, score
from matchbook.xes import read_items

# "C6 not checked" and C7 are data quality, not controls (BRIEF.md).
CONTROLS = ("C1", "C2", "C3", "C4", "C6")
PLAN = {"PASS": "keep", "HOLD": "fix", "FAIL": "replace"}


def status(found: list[Finding]) -> str:
    """C18: for the findings of one control, PASS with none, FAIL with a high one, HOLD
    otherwise."""
    if not found:
        return "PASS"
    return "FAIL" if any(severity(f) == "high" for f in found) else "HOLD"


def decides(found: list[Finding]) -> Finding | None:
    """C18: the finding the plan names, None for PASS: for HOLD the finding with the most
    euros at stake, for FAIL the high finding with the most euros at stake; on a tie, the
    first in log order."""
    if status(found) == "FAIL":
        found = [f for f in found if severity(f) == "high"]
    # max keeps the first of equal keys, so a tie goes to the first in log order.
    return max(found, key=lambda f: f.at_stake or 0.0, default=None)


def euros(found: list[Finding]) -> str:
    """The euros at stake of the findings, with a thousands separator and two decimals."""
    return f"{sum(f.at_stake or 0.0 for f in found):,.2f}"


def _table(header: list[str], rows: list[list[object]], right: int) -> list[str]:
    """A Markdown table whose columns from index right on are aligned right."""
    align = ["---" if i < right else "---:" for i in range(len(header))]
    lines = [header, align, *[["" if cell is None else str(cell) for cell in r] for r in rows]]
    return ["| " + " | ".join(line) + " |" for line in lines]


def render(
    found: list[Finding], scores: list[Score], comparisons: list[Comparison], seed: int
) -> str:
    """The report's Markdown text from the findings of the log, score(log, seed) and
    compare(log). It holds no date, time or path, so the same input gives the same text (C9)."""
    per_control = {c: [f for f in found if f.criterion == c] for c in CONTROLS}
    levels = [name for _, name in SEVERITIES]
    lines = ["# Diagnosis report", "", "## Controls", ""]
    lines += _table(
        ["Control", "Status", "Findings", "EUR at stake"],
        [[c, status(fs), len(fs), euros(fs)] for c, fs in per_control.items()],
        right=2,
    )
    lines += ["", "## Plan", ""]
    for control, fs in per_control.items():
        line = f"- {control}: {PLAN[status(fs)]}"
        decisive = decides(fs)
        if decisive is not None:
            line += (
                f", decided by {decisive.item_id}"
                f" at {decisive.at_stake or 0.0:,.2f} EUR, {severity(decisive)}"
            )
        lines.append(line + ".")
    controlled = [f for fs in per_control.values() for f in fs]
    lines += ["", "## Findings by severity", ""]
    lines += _table(
        ["Severity", "Findings", "EUR at stake"],
        [
            [level, len(fs), euros(fs)]
            for level in levels
            for fs in [[f for f in controlled if severity(f) == level]]
        ],
        right=1,
    )
    lines += ["", "## Findings by criterion", ""]
    lines += _table(
        ["Criterion", "Findings", "EUR at stake", *(level.capitalize() for level in levels)],
        [
            [c, len(fs), euros(fs), *(sum(severity(f) == level for f in fs) for level in levels)]
            for c, fs in per_control.items()
        ],
        right=1,
    )
    lines += ["", f"## Injected log, seed {seed}", ""]
    lines += _table(
        [
            "Kind",
            "Criterion",
            "Items",
            "Detected",
            "False alarms",
            "Baseline detected",
            "Baseline false alarms",
        ],
        [
            [
                s.kind.name,
                s.kind.criterion,
                s.items,
                s.detected,
                s.false_alarms,
                s.baseline_detected,
                s.baseline_false_alarms,
            ]
            for s in scores
        ],
        right=2,
    )
    lines += ["", "## Baseline on the real log", ""]
    lines += _table(
        ["Rule", "Criterion", "Rule only", "Criterion only", "Both"],
        [[c.rule, c.criterion, c.rule_only, c.criterion_only, c.both] for c in comparisons],
        right=2,
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="matchbook report", description=__doc__)
    parser.add_argument("log", type=Path, help="the XES event log")
    parser.add_argument("output", type=Path, help="the Markdown file to write")
    parser.add_argument("--seed", type=int, default=1, help="the seed of the injected log")
    args = parser.parse_args(argv)
    if args.output.resolve().is_relative_to(args.log.resolve().parent):
        print(
            f"matchbook report: {args.output} is inside the directory of the log;"
            " write the report elsewhere (C10)",
            file=sys.stderr,
        )
        return 2
    found = [f for item in read_items(args.log) for f in findings(item)]
    text = render(found, score(args.log, args.seed), compare(args.log), args.seed)
    args.output.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
