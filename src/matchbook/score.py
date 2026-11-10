"""Detection on the injected log: python -m matchbook.score <log.xes> --seed <n>.

Runs the checks of matchbook on the injected log of the seed and prints, per kind, its items,
how many are detected and how many are false alarms (C15), and the same two counts for the
baseline (C17). Writes nothing.
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from matchbook.baseline import STANDS_IN, rules
from matchbook.checks import findings
from matchbook.inject import KINDS, Kind, choose
from matchbook.xes import Item, read_items


def criteria(item: Item) -> set[str]:
    """The criteria of the item's findings; "C6 not checked" is one of its own."""
    return {finding.criterion for finding in findings(item)}


@dataclass(frozen=True)
class Score:
    """One kind's counts, of matchbook and of the baseline. Detected is None for a look-alike
    kind."""

    kind: Kind
    items: int
    detected: int | None
    false_alarms: int
    baseline_detected: int | None
    baseline_false_alarms: int


def _counts(criterion: str, flagged: list[set[str]]) -> tuple[int | None, int]:
    """Detected and false alarms of items flagged by the criteria given per item."""
    if not criterion:
        return None, sum(1 for found in flagged if found)
    detected = sum(1 for found in flagged if criterion in found)
    false_alarms = sum(1 for found in flagged if found - {criterion})
    return detected, false_alarms


def count(kind: Kind, items: list[Item]) -> Score:
    """A fault item is detected when its kind's criterion flags it and a false alarm when any
    other criterion does (it can be both); a look-alike flagged by any is a false alarm. The
    baseline counts the same way, a rule flagging for the criterion it stands in for, so with
    no rule for C1 an F1 item is always missed."""
    detected, false_alarms = _counts(kind.criterion, [criteria(item) for item in items])
    baseline_detected, baseline_false_alarms = _counts(
        kind.criterion, [{STANDS_IN[rule] for rule in rules(item)} for item in items]
    )
    return Score(kind, len(items), detected, false_alarms, baseline_detected, baseline_false_alarms)


def score(path: Path, seed: int) -> list[Score]:
    """Per kind in KINDS order, the counts on its changed items in the injected log."""
    chosen = choose(read_items(path), seed)
    changed: dict[str, list[Item]] = {kind.name: [] for kind in KINDS}
    for item in read_items(path):
        if item.id in chosen:
            kind = chosen[item.id]
            changed[kind.name].append(kind.change(item))
    return [count(kind, changed[kind.name]) for kind in KINDS]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="matchbook.score", description=__doc__)
    parser.add_argument("log", type=Path, help="the XES event log")
    parser.add_argument("--seed", type=int, required=True, help="the seed that picks the items")
    args = parser.parse_args(argv)
    print(
        "kind\tcriterion\titems\tdetected\tfalse alarms\tbaseline detected\tbaseline false alarms"
    )
    for row in score(args.log, args.seed):
        detected = "" if row.detected is None else row.detected
        baseline = "" if row.baseline_detected is None else row.baseline_detected
        print(
            f"{row.kind.name}\t{row.kind.criterion}\t{row.items}\t{detected}"
            f"\t{row.false_alarms}\t{baseline}\t{row.baseline_false_alarms}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
