from pathlib import Path

import pytest
from test_inject import ORDER, before_item, item, two_way_item

from matchbook import compare as compare_module
from matchbook.checks import (
    CANCEL_GOODS_RECEIPT,
    CANCEL_INVOICE_RECEIPT,
    CLEAR_INVOICE,
    GOODS_RECEIPT,
    INVOICE_AFTER_GR,
    INVOICE_BEFORE_GR,
    INVOICE_RECEIPT,
    SERVICE_ENTRY,
    TWO_WAY,
)
from matchbook.compare import Comparison, compare
from matchbook.xes import Item


def goods(*events: tuple[str, float]) -> Item:
    """A closed invoice-after-GR goods item with the documents given."""
    return item(INVOICE_AFTER_GR, (ORDER, 100), *events, (CLEAR_INVOICE, 100))


LOG = [
    # B6 only: 0.50 EUR apart, within the truncation to whole euros.
    goods((GOODS_RECEIPT, 100), (INVOICE_RECEIPT, 100.5)),
    # B6 only: "C6 not checked" is not C6.
    item(
        INVOICE_AFTER_GR,
        (ORDER, 100),
        (GOODS_RECEIPT, 100),
        (SERVICE_ENTRY, 100),
        (INVOICE_RECEIPT, 120),
        ("Change Price", 120),
        (CLEAR_INVOICE, 120),
    ),
    # C6 only: the totals agree, the cancelled invoice does not.
    goods((GOODS_RECEIPT, 150), (INVOICE_RECEIPT, 150), (CANCEL_INVOICE_RECEIPT, 50)),
    # B6 and C6.
    goods((GOODS_RECEIPT, 100), (INVOICE_RECEIPT, 120)),
    # C2 only: the only goods receipt is cancelled.
    item(
        INVOICE_BEFORE_GR,
        (ORDER, 100),
        (INVOICE_RECEIPT, 100),
        (GOODS_RECEIPT, 100),
        (CANCEL_GOODS_RECEIPT, 100),
        (CLEAR_INVOICE, 100),
    ),
    # B2 and C2.
    item(INVOICE_BEFORE_GR, (ORDER, 100), (INVOICE_RECEIPT, 100), (CLEAR_INVOICE, 100)),
    # C3 only: the only invoice receipt is cancelled.
    item(
        TWO_WAY,
        (ORDER, 100),
        (INVOICE_RECEIPT, 100),
        (CANCEL_INVOICE_RECEIPT, 100),
        (CLEAR_INVOICE, 100),
    ),
    # Flagged by no one.
    before_item(),
    two_way_item(),
]


@pytest.mark.criterion("C17")
def test_c17_compare_counts_rule_only_criterion_only_and_both_per_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(compare_module, "read_items", lambda _path: iter(LOG))
    assert compare(Path("log.xes")) == [
        Comparison("B2", "C2", 0, 1, 1),
        Comparison("B3", "C3", 0, 1, 0),
        Comparison("B4", "C4", 0, 0, 0),
        Comparison("B6", "C6", 2, 1, 1),
    ]


@pytest.mark.criterion("C17")
def test_c17_compare_main_prints_a_header_and_a_line_per_rule(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(compare_module, "read_items", lambda _path: iter(LOG))
    assert compare_module.main(["log.xes"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "rule\tcriterion\trule only\tcriterion only\tboth",
        "B2\tC2\t0\t1\t1",
        "B3\tC3\t0\t1\t0",
        "B4\tC4\t0\t0\t0",
        "B6\tC6\t2\t1\t1",
    ]
