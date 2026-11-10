"""Command line: python -m matchbook <log.xes> prints one line per flagged item on stdout;
python -m matchbook report <log.xes> <output.md> writes the diagnosis report;
python -m matchbook images <report.md> <dir> draws the README images from it."""

import argparse
import sys
from pathlib import Path

from matchbook import images, report
from matchbook.checks import Finding, findings, severity
from matchbook.xes import read_items


def format_finding(finding: Finding) -> str:
    """Item, criterion, euros at stake, severity, each event as activity, timestamp and net
    worth, then any note. The euros and severity are empty when the finding has none."""
    events = "; ".join(
        f"{e.activity} {e.timestamp.isoformat()} {e.net_worth} EUR" for e in finding.events
    )
    at_stake = "" if finding.at_stake is None else f"{finding.at_stake:.2f}"
    line = f"{finding.item_id}\t{finding.criterion}\t{at_stake}\t{severity(finding)}\t{events}"
    return f"{line}\t{finding.note}" if finding.note else line


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["report"]:
        return report.main(argv[1:])
    if argv[:1] == ["images"]:
        return images.main(argv[1:])
    parser = argparse.ArgumentParser(prog="matchbook", description=__doc__)
    parser.add_argument("log", type=Path, help="the XES event log")
    args = parser.parse_args(argv)
    for item in read_items(args.log):
        for finding in findings(item):
            print(format_finding(finding))
    return 0


if __name__ == "__main__":
    sys.exit(main())
