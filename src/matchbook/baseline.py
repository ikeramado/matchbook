"""The spreadsheet baseline of BRIEF.md: python -m matchbook.baseline <log.xes>.

Each rule looks only at whether documents exist and whether totals agree, over every event
of the item: it ignores order, cancellations, the reversal note, the truncation to whole
euros and the window of C7 (C16). Prints one line per flag: item id, tab, rule.
"""

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from matchbook.checks import (
    CLEAR_INVOICE,
    CONSIGNMENT,
    GOODS_RECEIPT,
    INVOICE_AFTER_GR,
    INVOICE_BEFORE_GR,
    INVOICE_RECEIPT,
    SERVICE_ENTRY,
    TWO_WAY,
)
from matchbook.xes import Item, read_items


def _activities(item: Item) -> set[str]:
    return {event.activity for event in item.events}


def _total(item: Item, activity: str) -> float:
    return sum(event.net_worth for event in item.events if event.activity == activity)


def rule_b2(item: Item) -> bool:
    """B2: a closed 3-way match item (either kind) with no Record Goods Receipt."""
    activities = _activities(item)
    return (
        item.category in (INVOICE_AFTER_GR, INVOICE_BEFORE_GR)
        and CLEAR_INVOICE in activities
        and GOODS_RECEIPT not in activities
    )


def rule_b3(item: Item) -> bool:
    """B3: a closed 2-way match item with no Record Invoice Receipt."""
    activities = _activities(item)
    return (
        item.category == TWO_WAY
        and CLEAR_INVOICE in activities
        and INVOICE_RECEIPT not in activities
    )


def rule_b4(item: Item) -> bool:
    """B4: a consignment item with a Record Invoice Receipt or a Clear Invoice."""
    activities = _activities(item)
    return item.category == CONSIGNMENT and bool({INVOICE_RECEIPT, CLEAR_INVOICE} & activities)


def rule_b6(item: Item) -> bool:
    """B6: a closed invoice-after-GR item with an invoice receipt whose invoice total differs
    to the cent from its service entry total (service items) or goods receipt total (the
    rest)."""
    activities = _activities(item)
    if (
        item.category != INVOICE_AFTER_GR
        or CLEAR_INVOICE not in activities
        or INVOICE_RECEIPT not in activities
    ):
        return False
    received = SERVICE_ENTRY if SERVICE_ENTRY in activities else GOODS_RECEIPT
    return round(_total(item, INVOICE_RECEIPT), 2) != round(_total(item, received), 2)


RULES: tuple[Callable[[Item], bool], ...] = (rule_b2, rule_b3, rule_b4, rule_b6)

STANDS_IN = {"B2": "C2", "B3": "C3", "B4": "C4", "B6": "C6"}


def name(rule: Callable[[Item], bool]) -> str:
    """The rule's name: "B2" for rule_b2."""
    return rule.__name__.removeprefix("rule_").upper()


def rules(item: Item) -> set[str]:
    """The names of the rules that flag the item."""
    return {name(rule) for rule in RULES if rule(item)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="matchbook.baseline", description=__doc__)
    parser.add_argument("log", type=Path, help="the XES event log")
    args = parser.parse_args(argv)
    for item in read_items(args.log):
        for rule in RULES:
            if rule(item):
                print(f"{item.id}\t{name(rule)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
