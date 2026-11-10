"""Measure how the log stores net worth: python -m matchbook.measure <log.xes>.

Reads the log once and prints, per item category and per activity, the measurements that
fix the values and tolerance of C5 and C6. Writes nothing but stdout.
"""

import argparse
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path

from matchbook.xes import Item, read_items

CREATE = "Create Purchase Order Item"
INVOICE_RECEIPT = "Record Invoice Receipt"
GOODS_RECEIPT = "Record Goods Receipt"
MOVERS = (
    "Change Price",
    "Change Quantity",
    "Change Currency",
    "Cancel Goods Receipt",
    "Cancel Invoice Receipt",
)
SERVICE_ENTRY = "Record Service Entry Sheet"
CANCEL_GOODS_RECEIPT = "Cancel Goods Receipt"
CANCEL_INVOICE_RECEIPT = "Cancel Invoice Receipt"
CLEAR_INVOICE = "Clear Invoice"
INVOICE_AFTER_GR = "3-way match, invoice after GR"
# Activities that undo or reprice documents: an item with any of them is measured apart.
HISTORY = (
    CANCEL_GOODS_RECEIPT,
    CANCEL_INVOICE_RECEIPT,
    "Change Price",
    "Change Quantity",
    "Record Subsequent Invoice",
    "Cancel Subsequent Invoice",
)
PERCENTILES = (0, 1, 5, 25, 50, 75, 95, 99, 100)
# Values are stored with two decimals; anything closer than this is the same amount.
CENT = 0.005


def _sign(difference: float) -> str:
    if abs(difference) < CENT:
        return "equal"
    return "larger" if difference > 0 else "smaller"


def _against(
    invoiced: list[float],
    invoiced_back: list[float],
    received: list[float],
    received_back: list[float],
) -> str:
    """Compare net invoiced with net received, documents minus the cancellations of them.

    Each stored value v is a whole euro truncated from an amount in [v, v + 1), so the true
    net difference can be zero only when the stored one lies in the open range below.
    """
    difference = sum(invoiced) - sum(invoiced_back) - sum(received) + sum(received_back)
    if -(len(invoiced) + len(received_back)) < difference < len(received) + len(invoiced_back):
        return "consistent"
    return "invoiced above" if difference > 0 else "invoiced below"


class Measurement:
    """Counts and differences gathered one item at a time."""

    def __init__(self) -> None:
        self.items: Counter[tuple[str, str]] = Counter()
        self.step: Counter[tuple[str, str, str]] = Counter()
        self.step_differences: defaultdict[tuple[str, str], list[float]] = defaultdict(list)
        self.versus: Counter[tuple[str, str, str]] = Counter()
        self.versus_differences: defaultdict[tuple[str, str], list[float]] = defaultdict(list)
        self.versus_relative: defaultdict[tuple[str, str], list[float]] = defaultdict(list)
        self.whole: Counter[str] = Counter()
        self.after_gr: Counter[tuple[str, str, str, str]] = Counter()
        self.cancels: Counter[tuple[str, str, str]] = Counter()
        self.over_order: Counter[tuple[str, str]] = Counter()

    def _compare(self, category: str, pair: str, value: float, reference: float) -> None:
        difference = value - reference
        self.versus[category, pair, _sign(difference)] += 1
        self.versus_differences[category, pair].append(difference)
        if reference != 0:
            self.versus_relative[category, pair].append(difference / reference)

    def add(self, item: Item) -> None:
        category = item.category
        values = {event.net_worth for event in item.events}
        self.items[category, "constant" if len(values) <= 1 else "varies"] += 1

        previous = None
        for event in item.events:
            if previous is not None:
                difference = event.net_worth - previous
                self.step[category, event.activity, _sign(difference)] += 1
                if event.activity in MOVERS:
                    self.step_differences[category, event.activity].append(difference)
            previous = event.net_worth

        create = next((e.net_worth for e in item.events if e.activity == CREATE), None)
        last_goods_receipt = None
        for event in item.events:
            if create is not None and event.activity in (INVOICE_RECEIPT, GOODS_RECEIPT):
                self._compare(category, f"{event.activity} vs create", event.net_worth, create)
            if event.activity == GOODS_RECEIPT:
                last_goods_receipt = event.net_worth
            elif event.activity == INVOICE_RECEIPT and last_goods_receipt is not None:
                pair = "Record Invoice Receipt vs last goods receipt before it"
                self._compare(category, pair, event.net_worth, last_goods_receipt)

        for event in item.events:
            self.whole["whole euros" if event.net_worth == int(event.net_worth) else "cents"] += 1
        self._documents(item)

    def _documents(self, item: Item) -> None:
        """Read each event's value as its own document's amount."""
        values: defaultdict[str, list[float]] = defaultdict(list)
        for event in item.events:
            values[event.activity].append(event.net_worth)
        if INVOICE_RECEIPT not in values:
            return
        history = "with" if any(a in values for a in HISTORY) else "without"
        history += " cancellations or changes"
        services = SERVICE_ENTRY in values
        group = item.category
        if item.category == INVOICE_AFTER_GR:
            group = f"{item.category}, {'services' if services else 'goods'}"

        order = None
        for event in item.events:
            if event.activity in (CREATE, "Change Price", "Change Quantity"):
                order = event.net_worth
        invoiced, invoiced_back = values[INVOICE_RECEIPT], values[CANCEL_INVOICE_RECEIPT]
        if order is not None:
            self.over_order[group, _against(invoiced, invoiced_back, [order], [])] += 1

        if item.category != INVOICE_AFTER_GR:
            return
        kind = "services" if services else "goods"
        for cancel, cancelled in (
            (CANCEL_INVOICE_RECEIPT, INVOICE_RECEIPT),
            (CANCEL_GOODS_RECEIPT, GOODS_RECEIPT),
        ):
            earlier: list[float] = []
            for event in item.events:
                if event.activity == cancelled:
                    earlier.append(event.net_worth)
                elif event.activity == cancel:
                    match = any(abs(event.net_worth - v) < CENT for v in earlier)
                    found = "equals an earlier document" if match else "equals none before it"
                    self.cancels[kind, cancel, found] += 1

        if services:
            received, received_back = values[SERVICE_ENTRY], []
        else:
            received, received_back = values[GOODS_RECEIPT], values[CANCEL_GOODS_RECEIPT]
        verdict = _against(invoiced, invoiced_back, received, received_back)
        state = "closed" if CLEAR_INVOICE in values else "open"
        self.after_gr[kind, history, state, verdict] += 1


def _percentiles(values: Iterable[float]) -> str:
    ordered = sorted(values)
    if not ordered:
        return "-"
    last = len(ordered) - 1
    return "  ".join(f"p{p}={ordered[round(p / 100 * last)]:.2f}" for p in PERCENTILES)


def report(measurement: Measurement) -> str:
    m = measurement
    categories = sorted({category for category, _ in m.items})
    lines = ["# 1. Items whose net worth is the same on every event, per category", ""]
    for category in categories:
        constant, varies = m.items[category, "constant"], m.items[category, "varies"]
        lines.append(f"{category}: {constant + varies} items, {constant} constant, {varies} vary")

    lines += ["", "# 1. Net worth of each event against the event before it", ""]
    for category in categories:
        lines.append(f"## {category}")
        activities = sorted({a for c, a, _ in m.step if c == category})
        for activity in activities:
            counts = [m.step[category, activity, s] for s in ("equal", "larger", "smaller")]
            lines.append(
                f"{activity}: {sum(counts)} events, {counts[0]} equal, {counts[1]} larger, "
                f"{counts[2]} smaller"
            )
        lines.append("")

    lines += ["# 2. Receipts against the order (and the invoice against the goods receipt)", ""]
    for category in categories:
        pairs = sorted({p for c, p, _ in m.versus if c == category})
        if not pairs:
            continue
        lines.append(f"## {category}")
        for pair in pairs:
            counts = [m.versus[category, pair, s] for s in ("equal", "larger", "smaller")]
            lines.append(
                f"{pair}: {sum(counts)} events, {counts[0]} equal, {counts[1]} larger, "
                f"{counts[2]} smaller"
            )
            lines.append(f"  EUR difference: {_percentiles(m.versus_differences[category, pair])}")
            lines.append(f"  relative:       {_percentiles(m.versus_relative[category, pair])}")
        lines.append("")

    lines += ["# 3. How changes and cancellations move the value (EUR, against the event before)"]
    lines.append("")
    for category in categories:
        movers = [a for a in MOVERS if (category, a) in m.step_differences]
        if not movers:
            continue
        lines.append(f"## {category}")
        for activity in movers:
            differences = m.step_differences[category, activity]
            lines.append(f"{activity}: {len(differences)} events  {_percentiles(differences)}")
        lines.append("")

    lines += ["# 4. Each event's value as its own document's amount", ""]
    lines.append(
        f"Values in whole euros: {m.whole['whole euros']} events, with cents: {m.whole['cents']}"
    )
    lines.append("")
    lines.append("## Cancellations against the documents of their kind before them")
    for kind, cancel, found in sorted(m.cancels):
        lines.append(f"{kind}, {cancel}: {m.cancels[kind, cancel, found]} {found}")
    lines.append("")
    verdicts = ("consistent", "invoiced above", "invoiced below")
    lines.append(f"## {INVOICE_AFTER_GR}: net invoiced against net received, per item")
    lines.append("(received: service entry sheets if the item has any, else goods receipts;")
    lines.append(f" closed: the item has a {CLEAR_INVOICE})")
    for kind, history, state in sorted({(k, h, s) for k, h, s, _ in m.after_gr}):
        counts = [m.after_gr[kind, history, state, v] for v in verdicts]
        lines.append(
            f"{kind}, {history}, {state}: {sum(counts)} items, "
            + ", ".join(f"{n} {v}" for n, v in zip(counts, verdicts, strict=True))
        )
    lines.append("")
    lines.append("## Net invoiced against the last order value, per item")
    for group in sorted({g for g, _ in m.over_order}):
        counts = [m.over_order[group, v] for v in verdicts]
        lines.append(
            f"{group}: {sum(counts)} items, "
            + ", ".join(f"{n} {v}" for n, v in zip(counts, verdicts, strict=True))
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="matchbook.measure", description=__doc__)
    parser.add_argument("log", type=Path, help="the XES event log")
    args = parser.parse_args(argv)
    measurement = Measurement()
    for item in read_items(args.log):
        measurement.add(item)
    print(report(measurement))
    return 0


if __name__ == "__main__":
    sys.exit(main())
