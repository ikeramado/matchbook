"""The baseline next to matchbook on the real log: python -m matchbook.compare <log.xes>.

Prints, per baseline rule, the criterion it stands in for and the items flagged by the rule
only, by the criterion only and by both (C17). Writes nothing.
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from matchbook.baseline import RULES, STANDS_IN, name, rules
from matchbook.score import criteria
from matchbook.xes import read_items


@dataclass(frozen=True)
class Comparison:
    """One rule's counts against the criterion it stands in for."""

    rule: str
    criterion: str
    rule_only: int
    criterion_only: int
    both: int


def compare(path: Path) -> list[Comparison]:
    """Per rule in RULES order, the items of the log flagged by the rule only, by its
    criterion only and by both; "C6 not checked" is not C6."""
    names = [name(rule) for rule in RULES]
    counts = {rule: [0, 0, 0] for rule in names}
    for item in read_items(path):
        by_rules, by_criteria = rules(item), criteria(item)
        for rule in names:
            flagged = (rule in by_rules, STANDS_IN[rule] in by_criteria)
            if flagged == (True, False):
                counts[rule][0] += 1
            elif flagged == (False, True):
                counts[rule][1] += 1
            elif flagged == (True, True):
                counts[rule][2] += 1
    return [Comparison(rule, STANDS_IN[rule], *counts[rule]) for rule in names]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="matchbook.compare", description=__doc__)
    parser.add_argument("log", type=Path, help="the XES event log")
    args = parser.parse_args(argv)
    print("rule\tcriterion\trule only\tcriterion only\tboth")
    for row in compare(args.log):
        print(f"{row.rule}\t{row.criterion}\t{row.rule_only}\t{row.criterion_only}\t{row.both}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
