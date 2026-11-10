from datetime import UTC, datetime

import pytest

from matchbook.baseline import rule_b2, rule_b3, rule_b4, rule_b6
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
from matchbook.xes import Event, Item

ORDER = "Create Purchase Order Item"


def item(category: str, *events: tuple[str, float]) -> Item:
    """An item whose events are a day apart, in the order given."""
    return Item(
        "A_1",
        category,
        tuple(
            Event(activity, datetime(2018, 1, day + 1, tzinfo=UTC), net_worth)
            for day, (activity, net_worth) in enumerate(events)
        ),
    )


@pytest.mark.criterion("C16")
@pytest.mark.parametrize("category", [INVOICE_AFTER_GR, INVOICE_BEFORE_GR])
def test_c16_b2_flags_a_closed_3_way_item_with_no_goods_receipt(category: str) -> None:
    assert rule_b2(item(category, (ORDER, 100), (INVOICE_RECEIPT, 100), (CLEAR_INVOICE, 100)))


@pytest.mark.criterion("C16")
@pytest.mark.parametrize(
    "candidate",
    [
        pytest.param(
            item(
                INVOICE_AFTER_GR,
                (ORDER, 100),
                (GOODS_RECEIPT, 100),
                (CANCEL_GOODS_RECEIPT, 100),
                (INVOICE_RECEIPT, 100),
                (CLEAR_INVOICE, 100),
            ),
            id="only receipt cancelled",
        ),
        pytest.param(item(INVOICE_AFTER_GR, (ORDER, 100), (INVOICE_RECEIPT, 100)), id="open"),
        pytest.param(
            item(TWO_WAY, (ORDER, 100), (INVOICE_RECEIPT, 100), (CLEAR_INVOICE, 100)),
            id="2-way match",
        ),
    ],
)
def test_c16_b2_does_not_flag(candidate: Item) -> None:
    assert not rule_b2(candidate)


@pytest.mark.criterion("C16")
def test_c16_b3_flags_a_closed_2_way_item_with_no_invoice_receipt() -> None:
    assert rule_b3(item(TWO_WAY, (ORDER, 100), (CLEAR_INVOICE, 100)))


@pytest.mark.criterion("C16")
@pytest.mark.parametrize(
    "candidate",
    [
        pytest.param(
            item(
                TWO_WAY,
                (ORDER, 100),
                (INVOICE_RECEIPT, 100),
                (CANCEL_INVOICE_RECEIPT, 100),
                (CLEAR_INVOICE, 100),
            ),
            id="only invoice cancelled",
        ),
        pytest.param(item(TWO_WAY, (ORDER, 100)), id="open"),
        pytest.param(item(INVOICE_AFTER_GR, (ORDER, 100), (CLEAR_INVOICE, 100)), id="3-way"),
    ],
)
def test_c16_b3_does_not_flag(candidate: Item) -> None:
    assert not rule_b3(candidate)


@pytest.mark.criterion("C16")
@pytest.mark.parametrize(
    "candidate",
    [
        pytest.param(item(CONSIGNMENT, (ORDER, 100), (INVOICE_RECEIPT, 100)), id="invoice"),
        pytest.param(
            item(CONSIGNMENT, (ORDER, 100), (INVOICE_RECEIPT, 100), (CANCEL_INVOICE_RECEIPT, 100)),
            id="invoice cancelled",
        ),
        pytest.param(item(CONSIGNMENT, (ORDER, 100), (CLEAR_INVOICE, 100)), id="clear"),
    ],
)
def test_c16_b4_flags_a_consignment_item_invoiced_or_cleared(candidate: Item) -> None:
    assert rule_b4(candidate)


@pytest.mark.criterion("C16")
@pytest.mark.parametrize(
    "candidate",
    [
        pytest.param(item(CONSIGNMENT, (ORDER, 100), (GOODS_RECEIPT, 100)), id="received only"),
        pytest.param(item(TWO_WAY, (ORDER, 100), (INVOICE_RECEIPT, 100)), id="2-way match"),
    ],
)
def test_c16_b4_does_not_flag(candidate: Item) -> None:
    assert not rule_b4(candidate)


CLOSED_GOODS = ((ORDER, 100), (GOODS_RECEIPT, 60), (GOODS_RECEIPT, 40.01))


@pytest.mark.criterion("C16")
@pytest.mark.parametrize(
    "candidate",
    [
        pytest.param(
            item(INVOICE_AFTER_GR, *CLOSED_GOODS, (INVOICE_RECEIPT, 100), (CLEAR_INVOICE, 100)),
            id="goods off by a cent",
        ),
        pytest.param(
            item(
                INVOICE_AFTER_GR,
                (ORDER, 100),
                (GOODS_RECEIPT, 100),
                (SERVICE_ENTRY, 90),
                (INVOICE_RECEIPT, 100),
                (CLEAR_INVOICE, 100),
            ),
            id="service against its entry sheets",
        ),
        pytest.param(
            item(
                INVOICE_AFTER_GR,
                (ORDER, 100),
                (GOODS_RECEIPT, 100),
                (INVOICE_RECEIPT, 100),
                (CANCEL_INVOICE_RECEIPT, 100),
                (INVOICE_RECEIPT, 100),
                (CLEAR_INVOICE, 100),
            ),
            id="cancellation ignored",
        ),
    ],
)
def test_c16_b6_flags_totals_that_differ(candidate: Item) -> None:
    assert rule_b6(candidate)


@pytest.mark.criterion("C16")
@pytest.mark.parametrize(
    "candidate",
    [
        pytest.param(
            item(INVOICE_AFTER_GR, *CLOSED_GOODS, (INVOICE_RECEIPT, 100.01), (CLEAR_INVOICE, 1)),
            id="agree to the cent",
        ),
        pytest.param(
            item(
                INVOICE_AFTER_GR,
                (ORDER, 100),
                (GOODS_RECEIPT, 50),
                (SERVICE_ENTRY, 100),
                (INVOICE_RECEIPT, 100),
                (CLEAR_INVOICE, 100),
            ),
            id="service agrees with its entry sheets",
        ),
        pytest.param(item(INVOICE_AFTER_GR, *CLOSED_GOODS, (INVOICE_RECEIPT, 1)), id="open"),
        pytest.param(
            item(INVOICE_AFTER_GR, *CLOSED_GOODS, (CLEAR_INVOICE, 1)), id="no invoice receipt"
        ),
        pytest.param(
            item(INVOICE_BEFORE_GR, *CLOSED_GOODS, (INVOICE_RECEIPT, 1), (CLEAR_INVOICE, 1)),
            id="invoice before GR",
        ),
    ],
)
def test_c16_b6_does_not_flag(candidate: Item) -> None:
    assert not rule_b6(candidate)
