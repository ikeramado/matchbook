"""The injected log of BRIEF.md: python -m matchbook.inject <log.xes> --seed <n>.

Builds in memory a copy of the log with each fault (F1 to F6) and look-alike (L1 to L3) kind
in 50 items that neither matchbook nor the baseline flags on the original log, chosen by the
seed (C14). Writes nothing; prints one line per chosen item, in log order: item id, kind.
"""

import argparse
import math
import random
import sys
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, replace
from datetime import timedelta
from pathlib import Path

from matchbook.baseline import RULES
from matchbook.checks import (
    CANCEL_GOODS_RECEIPT,
    CANCEL_INVOICE_RECEIPT,
    CLEAR_INVOICE,
    CONSIGNMENT,
    GOODS_RECEIPT,
    INVOICE_AFTER_GR,
    INVOICE_BEFORE_GR,
    INVOICE_RECEIPT,
    SERVICE_ENTRY,
    TWO_WAY,
    findings,
)
from matchbook.xes import Event, Item, read_items

PER_KIND = 50
SECOND = timedelta(seconds=1)


def flagged(item: Item) -> bool:
    """Whether python -m matchbook prints a line for the item or a baseline rule flags it."""
    return bool(findings(item)) or any(rule(item) for rule in RULES)


def _indices(item: Item, activity: str) -> list[int]:
    return [i for i, event in enumerate(item.events) if event.activity == activity]


def _closed(item: Item, category: str) -> bool:
    return item.category == category and bool(_indices(item, CLEAR_INVOICE))


def _closed_goods(item: Item) -> bool:
    """A closed invoice-after-GR item with no Record Service Entry Sheet."""
    return _closed(item, INVOICE_AFTER_GR) and not _indices(item, SERVICE_ENTRY)


def _with(item: Item, events: Iterable[Event]) -> Item:
    return replace(item, events=tuple(events))


def _without(item: Item, *activities: str) -> Item:
    return _with(item, (e for e in item.events if e.activity not in activities))


def _after(item: Item, index: int, *activities: str) -> Item:
    """The item with events of the activities, one, two... seconds after the event at index
    and of its value, placed right after it."""
    anchor = item.events[index]
    added = (
        Event(activity, anchor.timestamp + (n + 1) * SECOND, anchor.net_worth)
        for n, activity in enumerate(activities)
    )
    return _with(item, (*item.events[: index + 1], *added, *item.events[index + 1 :]))


def _only(item: Item, activity: str) -> int:
    """The index of the item's one event of the activity; -1 if it has none or several."""
    indices = _indices(item, activity)
    return indices[0] if len(indices) == 1 else -1


def applies_f1(item: Item) -> bool:
    goods, invoices = _indices(item, GOODS_RECEIPT), _indices(item, INVOICE_RECEIPT)
    return _closed_goods(item) and bool(goods and invoices) and invoices[0] > goods[0]


def change_f1(item: Item) -> Item:
    """The first invoice receipt moves to one second before the first goods receipt."""
    invoice_at = _indices(item, INVOICE_RECEIPT)[0]
    goods_at = _indices(item, GOODS_RECEIPT)[0]
    invoice, goods = item.events[invoice_at], item.events[goods_at]
    moved = replace(invoice, timestamp=goods.timestamp - SECOND)
    rest = [e for i, e in enumerate(item.events) if i != invoice_at]
    return _with(item, (*rest[:goods_at], moved, *rest[goods_at:]))


def applies_f2(item: Item) -> bool:
    return _closed(item, INVOICE_BEFORE_GR)


def change_f2(item: Item) -> Item:
    """Every goods receipt and goods receipt cancellation is removed."""
    return _without(item, GOODS_RECEIPT, CANCEL_GOODS_RECEIPT)


def applies_f3(item: Item) -> bool:
    goods = _only(item, GOODS_RECEIPT)
    return (
        _closed(item, INVOICE_BEFORE_GR) and goods >= 0 and goods < _indices(item, CLEAR_INVOICE)[0]
    )


def change_f3(item: Item) -> Item:
    """A Cancel Goods Receipt of the same value one second after the one goods receipt."""
    return _after(item, _only(item, GOODS_RECEIPT), CANCEL_GOODS_RECEIPT)


def applies_f4(item: Item) -> bool:
    return _closed(item, TWO_WAY)


def change_f4(item: Item) -> Item:
    """Every invoice receipt and invoice receipt cancellation is removed."""
    return _without(item, INVOICE_RECEIPT, CANCEL_INVOICE_RECEIPT)


def applies_f5(item: Item) -> bool:
    return (
        item.category == CONSIGNMENT
        and bool(item.events)
        and not _indices(item, INVOICE_RECEIPT)
        and not _indices(item, CLEAR_INVOICE)
    )


def change_f5(item: Item) -> Item:
    """A Record Invoice Receipt of the item's value one second after its last event."""
    return _after(item, len(item.events) - 1, INVOICE_RECEIPT)


def applies_f6(item: Item) -> bool:
    return _closed_goods(item) and bool(_indices(item, INVOICE_RECEIPT))


def change_f6(item: Item) -> Item:
    """The last invoice receipt v rises to v + max(floor(0.1 * v), 100)."""
    at = _indices(item, INVOICE_RECEIPT)[-1]
    invoice = item.events[at]
    value = invoice.net_worth + max(math.floor(0.1 * invoice.net_worth), 100)
    events = list(item.events)
    events[at] = replace(invoice, net_worth=value)
    return _with(item, events)


def applies_l1(item: Item) -> bool:
    goods, invoices = _only(item, GOODS_RECEIPT), _indices(item, INVOICE_RECEIPT)
    return _closed_goods(item) and goods >= 0 and bool(invoices) and goods < invoices[0]


def change_l1(item: Item) -> Item:
    """A receipt corrected: a cancellation and a new receipt one and two seconds after it."""
    return _after(item, _only(item, GOODS_RECEIPT), CANCEL_GOODS_RECEIPT, GOODS_RECEIPT)


def applies_l2(item: Item) -> bool:
    return _closed_goods(item) and _only(item, INVOICE_RECEIPT) >= 0


def change_l2(item: Item) -> Item:
    """An invoice corrected: a cancellation and a new invoice one and two seconds after it."""
    return _after(item, _only(item, INVOICE_RECEIPT), CANCEL_INVOICE_RECEIPT, INVOICE_RECEIPT)


def applies_l3(item: Item) -> bool:
    goods = _only(item, GOODS_RECEIPT)
    return _closed_goods(item) and goods >= 0 and item.events[goods].net_worth >= 2


def change_l3(item: Item) -> Item:
    """The one goods receipt v becomes two at its time, of floor(v / 2) and
    v - floor(v / 2) - 1."""
    at = _only(item, GOODS_RECEIPT)
    goods = item.events[at]
    half = math.floor(goods.net_worth / 2)
    parts = (
        replace(goods, net_worth=half),
        replace(goods, net_worth=goods.net_worth - half - 1),
    )
    return _with(item, (*item.events[:at], *parts, *item.events[at + 1 :]))


@dataclass(frozen=True)
class Kind:
    name: str
    applies: Callable[[Item], bool]
    change: Callable[[Item], Item]
    # The criterion of BRIEF.md that must flag the kind; empty for a look-alike.
    criterion: str = ""


# In the order of BRIEF.md: the faults, then the look-alikes.
KINDS: tuple[Kind, ...] = (
    Kind("F1", applies_f1, change_f1, "C1"),
    Kind("F2", applies_f2, change_f2, "C2"),
    Kind("F3", applies_f3, change_f3, "C2"),
    Kind("F4", applies_f4, change_f4, "C3"),
    Kind("F5", applies_f5, change_f5, "C4"),
    Kind("F6", applies_f6, change_f6, "C6"),
    Kind("L1", applies_l1, change_l1),
    Kind("L2", applies_l2, change_l2),
    Kind("L3", applies_l3, change_l3),
)


def candidates(items: Iterable[Item]) -> dict[str, list[str]]:
    """Per kind name, the ids of the items it applies to that no one flags, in log order."""
    found: dict[str, list[str]] = {kind.name: [] for kind in KINDS}
    for item in items:
        if flagged(item):
            continue
        for kind in KINDS:
            if kind.applies(item):
                found[kind.name].append(item.id)
    return found


def choose(items: Iterable[Item], seed: int) -> dict[str, Kind]:
    """From item id to kind: with one generator, each kind in KINDS order samples 50 of its
    candidates not taken by an earlier kind. Raises ValueError for a kind short of them."""
    rng = random.Random(seed)
    found = candidates(items)
    chosen: dict[str, Kind] = {}
    for kind in KINDS:
        left = [item_id for item_id in found[kind.name] if item_id not in chosen]
        if len(left) < PER_KIND:
            raise ValueError(f"{kind.name}: {len(left)} candidates left, {PER_KIND} needed")
        chosen.update(dict.fromkeys(rng.sample(left, PER_KIND), kind))
    return chosen


def inject(path: Path, seed: int) -> Iterator[Item]:
    """The items of the log in log order, each chosen one changed by its kind."""
    chosen = choose(read_items(path), seed)
    return (
        chosen[item.id].change(item) if item.id in chosen else item for item in read_items(path)
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="matchbook.inject", description=__doc__)
    parser.add_argument("log", type=Path, help="the XES event log")
    parser.add_argument("--seed", type=int, required=True, help="the seed that picks the items")
    args = parser.parse_args(argv)
    chosen = choose(read_items(args.log), args.seed)
    for item in read_items(args.log):
        if item.id in chosen:
            print(f"{item.id}\t{chosen[item.id].name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
