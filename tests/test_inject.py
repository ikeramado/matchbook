from datetime import UTC, datetime, timedelta

import pytest

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
)
from matchbook.inject import KINDS, PER_KIND, choose, flagged
from matchbook.xes import Event, Item

ORDER = "Create Purchase Order Item"
KIND = {kind.name: kind for kind in KINDS}


def at(day: int, seconds: int = 0) -> datetime:
    """Day n of 2018 (from 1), plus some seconds."""
    return datetime(2018, 1, day, tzinfo=UTC) + timedelta(seconds=seconds)


def item(category: str, *events: tuple[str, float], item_id: str = "A_1") -> Item:
    """An item whose events are a day apart, in the order given, from 2018-01-01."""
    return Item(
        item_id,
        category,
        tuple(
            Event(activity, at(day + 1), net_worth)
            for day, (activity, net_worth) in enumerate(events)
        ),
    )


def goods_item(item_id: str = "A_1") -> Item:
    """A closed invoice-after-GR goods item no one flags: every after-GR kind applies."""
    return item(
        INVOICE_AFTER_GR,
        (ORDER, 100),
        (GOODS_RECEIPT, 100),
        (INVOICE_RECEIPT, 100),
        (CLEAR_INVOICE, 100),
        item_id=item_id,
    )


def before_item(item_id: str = "A_1") -> Item:
    """A closed invoice-before-GR item no one flags: F2 and F3 apply."""
    return item(
        INVOICE_BEFORE_GR,
        (ORDER, 100),
        (INVOICE_RECEIPT, 100),
        (GOODS_RECEIPT, 100),
        (CLEAR_INVOICE, 100),
        item_id=item_id,
    )


def two_way_item(item_id: str = "A_1") -> Item:
    return item(
        TWO_WAY, (ORDER, 100), (INVOICE_RECEIPT, 100), (CLEAR_INVOICE, 100), item_id=item_id
    )


def consignment_item(item_id: str = "A_1") -> Item:
    return item(CONSIGNMENT, (ORDER, 100), (GOODS_RECEIPT, 100), item_id=item_id)


@pytest.mark.criterion("C14")
def test_c14_the_kinds_are_those_of_the_brief_in_order() -> None:
    assert [kind.name for kind in KINDS] == ["F1", "F2", "F3", "F4", "F5", "F6", "L1", "L2", "L3"]


@pytest.mark.criterion("C14")
@pytest.mark.parametrize(
    "candidate", [goods_item(), before_item(), two_way_item(), consignment_item()]
)
def test_c14_the_example_items_are_flagged_by_no_one(candidate: Item) -> None:
    assert not flagged(candidate)


@pytest.mark.criterion("C14")
@pytest.mark.parametrize(
    "candidate",
    [
        pytest.param(
            item(
                INVOICE_AFTER_GR,
                (ORDER, 100),
                (INVOICE_RECEIPT, 100),
                (GOODS_RECEIPT, 100),
                (CLEAR_INVOICE, 100),
            ),
            id="C1",
        ),
        pytest.param(
            item(
                INVOICE_AFTER_GR,
                (ORDER, 100),
                (GOODS_RECEIPT, 100.5),
                (INVOICE_RECEIPT, 100),
                (CLEAR_INVOICE, 100),
            ),
            id="B6 baseline only",
        ),
        pytest.param(
            item(
                INVOICE_AFTER_GR,
                (ORDER, 100),
                (GOODS_RECEIPT, 100),
                (INVOICE_RECEIPT, 300),
                (CLEAR_INVOICE, 100),
            ),
            id="C6",
        ),
        pytest.param(
            Item(
                "A_1",
                TWO_WAY,
                (
                    Event(ORDER, datetime(2017, 12, 1, tzinfo=UTC), 100),
                    Event(INVOICE_RECEIPT, at(1), 100),
                    Event(CLEAR_INVOICE, at(2), 100),
                ),
            ),
            id="C7",
        ),
    ],
)
def test_c14_flagged_is_matchbook_or_the_baseline(candidate: Item) -> None:
    assert flagged(candidate)


@pytest.mark.criterion("C14")
@pytest.mark.parametrize(
    ("kind", "candidate"),
    [
        ("F1", goods_item()),
        ("F2", before_item()),
        ("F2", item(INVOICE_BEFORE_GR, (ORDER, 100), (INVOICE_RECEIPT, 100), (CLEAR_INVOICE, 100))),
        ("F3", before_item()),
        ("F4", two_way_item()),
        ("F5", consignment_item()),
        ("F6", goods_item()),
        ("L1", goods_item()),
        ("L2", goods_item()),
        ("L3", goods_item()),
    ],
)
def test_c14_a_kind_applies_to_the_items_of_its_column(kind: str, candidate: Item) -> None:
    assert KIND[kind].applies(candidate)


@pytest.mark.criterion("C14")
@pytest.mark.parametrize(
    ("kind", "candidate"),
    [
        pytest.param(
            "F1",
            item(
                INVOICE_AFTER_GR,
                (ORDER, 100),
                (INVOICE_RECEIPT, 100),
                (GOODS_RECEIPT, 100),
                (CLEAR_INVOICE, 100),
            ),
            id="F1 invoice first",
        ),
        pytest.param(
            "F1",
            item(
                INVOICE_AFTER_GR,
                (ORDER, 100),
                (GOODS_RECEIPT, 100),
                (SERVICE_ENTRY, 100),
                (INVOICE_RECEIPT, 100),
                (CLEAR_INVOICE, 100),
            ),
            id="F1 service item",
        ),
        pytest.param(
            "F1",
            item(INVOICE_AFTER_GR, (ORDER, 100), (GOODS_RECEIPT, 100), (INVOICE_RECEIPT, 100)),
            id="F1 open",
        ),
        pytest.param("F1", before_item(), id="F1 invoice before GR"),
        pytest.param(
            "F2",
            item(INVOICE_BEFORE_GR, (ORDER, 100), (INVOICE_RECEIPT, 100), (GOODS_RECEIPT, 100)),
            id="F2 open",
        ),
        pytest.param("F2", goods_item(), id="F2 invoice after GR"),
        pytest.param(
            "F3",
            item(
                INVOICE_BEFORE_GR,
                (ORDER, 100),
                (INVOICE_RECEIPT, 100),
                (GOODS_RECEIPT, 50),
                (GOODS_RECEIPT, 50),
                (CLEAR_INVOICE, 100),
            ),
            id="F3 two receipts",
        ),
        pytest.param(
            "F3",
            item(
                INVOICE_BEFORE_GR,
                (ORDER, 100),
                (INVOICE_RECEIPT, 100),
                (CLEAR_INVOICE, 100),
                (GOODS_RECEIPT, 100),
            ),
            id="F3 receipt after the clearing",
        ),
        pytest.param(
            "F3",
            item(INVOICE_BEFORE_GR, (ORDER, 100), (INVOICE_RECEIPT, 100), (CLEAR_INVOICE, 100)),
            id="F3 no receipt",
        ),
        pytest.param(
            "F3",
            item(INVOICE_BEFORE_GR, (ORDER, 100), (INVOICE_RECEIPT, 100), (GOODS_RECEIPT, 100)),
            id="F3 open",
        ),
        pytest.param("F4", item(TWO_WAY, (ORDER, 100), (INVOICE_RECEIPT, 100)), id="F4 open"),
        pytest.param("F4", goods_item(), id="F4 3-way match"),
        pytest.param(
            "F5",
            item(CONSIGNMENT, (ORDER, 100), (GOODS_RECEIPT, 100), (INVOICE_RECEIPT, 100)),
            id="F5 invoiced",
        ),
        pytest.param(
            "F5",
            item(CONSIGNMENT, (ORDER, 100), (GOODS_RECEIPT, 100), (CLEAR_INVOICE, 100)),
            id="F5 cleared",
        ),
        pytest.param(
            "F5", item(TWO_WAY, (ORDER, 100), (GOODS_RECEIPT, 100)), id="F5 not consignment"
        ),
        pytest.param(
            "F6",
            item(INVOICE_AFTER_GR, (ORDER, 100), (GOODS_RECEIPT, 100), (CLEAR_INVOICE, 100)),
            id="F6 no invoice",
        ),
        pytest.param(
            "F6",
            item(
                INVOICE_AFTER_GR,
                (ORDER, 100),
                (SERVICE_ENTRY, 100),
                (INVOICE_RECEIPT, 100),
                (CLEAR_INVOICE, 100),
            ),
            id="F6 service item",
        ),
        pytest.param(
            "F6",
            item(INVOICE_AFTER_GR, (ORDER, 100), (GOODS_RECEIPT, 100), (INVOICE_RECEIPT, 100)),
            id="F6 open",
        ),
        pytest.param(
            "L1",
            item(
                INVOICE_AFTER_GR,
                (ORDER, 100),
                (GOODS_RECEIPT, 50),
                (GOODS_RECEIPT, 50),
                (INVOICE_RECEIPT, 100),
                (CLEAR_INVOICE, 100),
            ),
            id="L1 two receipts",
        ),
        pytest.param(
            "L1",
            item(
                INVOICE_AFTER_GR,
                (ORDER, 100),
                (INVOICE_RECEIPT, 100),
                (GOODS_RECEIPT, 100),
                (CLEAR_INVOICE, 100),
            ),
            id="L1 receipt after the invoice",
        ),
        pytest.param(
            "L1",
            item(INVOICE_AFTER_GR, (ORDER, 100), (GOODS_RECEIPT, 100), (CLEAR_INVOICE, 100)),
            id="L1 no invoice",
        ),
        pytest.param(
            "L1",
            item(
                INVOICE_AFTER_GR,
                (ORDER, 100),
                (GOODS_RECEIPT, 100),
                (SERVICE_ENTRY, 100),
                (INVOICE_RECEIPT, 100),
                (CLEAR_INVOICE, 100),
            ),
            id="L1 service item",
        ),
        pytest.param(
            "L2",
            item(
                INVOICE_AFTER_GR,
                (ORDER, 100),
                (GOODS_RECEIPT, 100),
                (INVOICE_RECEIPT, 50),
                (INVOICE_RECEIPT, 50),
                (CLEAR_INVOICE, 100),
            ),
            id="L2 two invoices",
        ),
        pytest.param(
            "L2",
            item(INVOICE_AFTER_GR, (ORDER, 100), (GOODS_RECEIPT, 100), (CLEAR_INVOICE, 100)),
            id="L2 no invoice",
        ),
        pytest.param(
            "L2",
            item(INVOICE_AFTER_GR, (ORDER, 100), (GOODS_RECEIPT, 100), (INVOICE_RECEIPT, 100)),
            id="L2 open",
        ),
        pytest.param(
            "L3",
            item(
                INVOICE_AFTER_GR,
                (ORDER, 100),
                (GOODS_RECEIPT, 50),
                (GOODS_RECEIPT, 50),
                (INVOICE_RECEIPT, 100),
                (CLEAR_INVOICE, 100),
            ),
            id="L3 two receipts",
        ),
        pytest.param(
            "L3",
            item(
                INVOICE_AFTER_GR,
                (ORDER, 1),
                (GOODS_RECEIPT, 1),
                (INVOICE_RECEIPT, 1),
                (CLEAR_INVOICE, 1),
            ),
            id="L3 under 2 EUR",
        ),
        pytest.param(
            "L3",
            item(
                INVOICE_AFTER_GR,
                (ORDER, 100),
                (GOODS_RECEIPT, 100),
                (SERVICE_ENTRY, 100),
                (INVOICE_RECEIPT, 100),
                (CLEAR_INVOICE, 100),
            ),
            id="L3 service item",
        ),
    ],
)
def test_c14_a_kind_does_not_apply_to_the_items_next_to_its_column(
    kind: str, candidate: Item
) -> None:
    assert not KIND[kind].applies(candidate)


def changed(category: str, *events: tuple[str, datetime, float]) -> Item:
    return Item("A_1", category, tuple(Event(*event) for event in events))


@pytest.mark.criterion("C14")
@pytest.mark.parametrize(
    ("kind", "original", "expected"),
    [
        pytest.param(
            "F1",
            item(
                INVOICE_AFTER_GR,
                (ORDER, 100),
                (GOODS_RECEIPT, 60),
                (INVOICE_RECEIPT, 70),
                (GOODS_RECEIPT, 40),
                (INVOICE_RECEIPT, 30),
                (CLEAR_INVOICE, 100),
            ),
            changed(
                INVOICE_AFTER_GR,
                (ORDER, at(1), 100),
                (INVOICE_RECEIPT, at(2, -1), 70),
                (GOODS_RECEIPT, at(2), 60),
                (GOODS_RECEIPT, at(4), 40),
                (INVOICE_RECEIPT, at(5), 30),
                (CLEAR_INVOICE, at(6), 100),
            ),
            id="F1",
        ),
        pytest.param(
            "F2",
            item(
                INVOICE_BEFORE_GR,
                (ORDER, 100),
                (INVOICE_RECEIPT, 100),
                (GOODS_RECEIPT, 100),
                (CANCEL_GOODS_RECEIPT, 100),
                (GOODS_RECEIPT, 100),
                (CLEAR_INVOICE, 100),
            ),
            changed(
                INVOICE_BEFORE_GR,
                (ORDER, at(1), 100),
                (INVOICE_RECEIPT, at(2), 100),
                (CLEAR_INVOICE, at(6), 100),
            ),
            id="F2",
        ),
        pytest.param(
            "F3",
            before_item(),
            changed(
                INVOICE_BEFORE_GR,
                (ORDER, at(1), 100),
                (INVOICE_RECEIPT, at(2), 100),
                (GOODS_RECEIPT, at(3), 100),
                (CANCEL_GOODS_RECEIPT, at(3, 1), 100),
                (CLEAR_INVOICE, at(4), 100),
            ),
            id="F3",
        ),
        pytest.param(
            "F4",
            item(
                TWO_WAY,
                (ORDER, 100),
                (INVOICE_RECEIPT, 100),
                (CANCEL_INVOICE_RECEIPT, 100),
                (INVOICE_RECEIPT, 100),
                (CLEAR_INVOICE, 100),
            ),
            changed(TWO_WAY, (ORDER, at(1), 100), (CLEAR_INVOICE, at(5), 100)),
            id="F4",
        ),
        pytest.param(
            "F5",
            item(CONSIGNMENT, (ORDER, 100), (GOODS_RECEIPT, 100)),
            changed(
                CONSIGNMENT,
                (ORDER, at(1), 100),
                (GOODS_RECEIPT, at(2), 100),
                (INVOICE_RECEIPT, at(2, 1), 100),
            ),
            id="F5",
        ),
        pytest.param(
            "F6",
            item(
                INVOICE_AFTER_GR,
                (ORDER, 3000),
                (GOODS_RECEIPT, 3000),
                (INVOICE_RECEIPT, 1000),
                (INVOICE_RECEIPT, 2005),
                (CLEAR_INVOICE, 3000),
            ),
            changed(
                INVOICE_AFTER_GR,
                (ORDER, at(1), 3000),
                (GOODS_RECEIPT, at(2), 3000),
                (INVOICE_RECEIPT, at(3), 1000),
                (INVOICE_RECEIPT, at(4), 2205),
                (CLEAR_INVOICE, at(5), 3000),
            ),
            id="F6 10 percent",
        ),
        pytest.param(
            "F6",
            goods_item(),
            changed(
                INVOICE_AFTER_GR,
                (ORDER, at(1), 100),
                (GOODS_RECEIPT, at(2), 100),
                (INVOICE_RECEIPT, at(3), 200),
                (CLEAR_INVOICE, at(4), 100),
            ),
            id="F6 at least 100",
        ),
        pytest.param(
            "L1",
            goods_item(),
            changed(
                INVOICE_AFTER_GR,
                (ORDER, at(1), 100),
                (GOODS_RECEIPT, at(2), 100),
                (CANCEL_GOODS_RECEIPT, at(2, 1), 100),
                (GOODS_RECEIPT, at(2, 2), 100),
                (INVOICE_RECEIPT, at(3), 100),
                (CLEAR_INVOICE, at(4), 100),
            ),
            id="L1",
        ),
        pytest.param(
            "L2",
            goods_item(),
            changed(
                INVOICE_AFTER_GR,
                (ORDER, at(1), 100),
                (GOODS_RECEIPT, at(2), 100),
                (INVOICE_RECEIPT, at(3), 100),
                (CANCEL_INVOICE_RECEIPT, at(3, 1), 100),
                (INVOICE_RECEIPT, at(3, 2), 100),
                (CLEAR_INVOICE, at(4), 100),
            ),
            id="L2",
        ),
        pytest.param(
            "L3",
            item(
                INVOICE_AFTER_GR,
                (ORDER, 101),
                (GOODS_RECEIPT, 101),
                (INVOICE_RECEIPT, 101),
                (CLEAR_INVOICE, 101),
            ),
            changed(
                INVOICE_AFTER_GR,
                (ORDER, at(1), 101),
                (GOODS_RECEIPT, at(2), 50),
                (GOODS_RECEIPT, at(2), 50),
                (INVOICE_RECEIPT, at(3), 101),
                (CLEAR_INVOICE, at(4), 101),
            ),
            id="L3",
        ),
    ],
)
def test_c14_a_kind_changes_the_item_as_its_column_says(
    kind: str, original: Item, expected: Item
) -> None:
    assert KIND[kind].change(original) == expected


def log() -> list[Item]:
    """Enough unflagged items for every kind, and flagged ones every after-GR kind applies to
    but for being flagged."""
    flagged_goods = [
        item(
            INVOICE_AFTER_GR,
            (ORDER, 100),
            (GOODS_RECEIPT, 100),
            (INVOICE_RECEIPT, 300),
            (CLEAR_INVOICE, 100),
            item_id=f"X_{n}",
        )
        for n in range(100)
    ]
    return [
        *flagged_goods,
        *(goods_item(f"G_{n}") for n in range(300)),
        *(before_item(f"B_{n}") for n in range(120)),
        *(two_way_item(f"T_{n}") for n in range(60)),
        *(consignment_item(f"C_{n}") for n in range(60)),
    ]


@pytest.mark.criterion("C14")
def test_c14_choose_takes_50_unflagged_items_per_kind_each_once() -> None:
    items = log()
    by_id = {candidate.id: candidate for candidate in items}
    chosen = choose(items, seed=1)
    assert len(chosen) == PER_KIND * len(KINDS)
    for kind in KINDS:
        ids = [item_id for item_id, chosen_kind in chosen.items() if chosen_kind == kind]
        assert len(ids) == PER_KIND
        assert all(kind.applies(by_id[item_id]) for item_id in ids)
    assert not any(flagged(by_id[item_id]) for item_id in chosen)


@pytest.mark.criterion("C14")
def test_c14_the_same_seed_gives_the_same_choice() -> None:
    assert choose(log(), seed=1) == choose(log(), seed=1)
    assert choose(log(), seed=1) != choose(log(), seed=2)


@pytest.mark.criterion("C14")
def test_c14_a_kind_short_of_candidates_raises() -> None:
    items = [*log()[:-60], *(consignment_item(f"C_{n}") for n in range(49))]
    with pytest.raises(ValueError, match="F5"):
        choose(items, seed=1)
