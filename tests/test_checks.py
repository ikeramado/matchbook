from collections.abc import Callable
from pathlib import Path

import pytest
from test_xes import EventSpec, write_log

from matchbook import checks
from matchbook.checks import Finding, check_c1
from matchbook.xes import Item, read_items

AFTER_GR = "3-way match, invoice after GR"
ORDER = ("Create Purchase Order Item", "2018-01-02T10:00:00.000Z", 100.0)
GR = ("Record Goods Receipt", "2018-01-10T10:00:00.000Z", 100.0)
IR_EARLY = ("Record Invoice Receipt", "2018-01-05T10:00:00.000Z", 100.0)
IR_LATE = ("Record Invoice Receipt", "2018-01-15T10:00:00.000Z", 100.0)


def item(tmp_path: Path, category: str, events: list[EventSpec]) -> Item:
    (only,) = read_items(write_log(tmp_path / "log.xes", [("A_1", category, events)]))
    return only


@pytest.mark.criterion("C1")
def test_c1_flags_an_invoice_before_the_first_goods_receipt(tmp_path: Path) -> None:
    finding = check_c1(item(tmp_path, AFTER_GR, [ORDER, IR_EARLY, GR, IR_LATE]))
    assert finding is not None
    assert (finding.item_id, finding.criterion) == ("A_1", "C1")
    assert [e.activity for e in finding.events] == [
        "Record Invoice Receipt",
        "Record Goods Receipt",
    ]


@pytest.mark.criterion("C1")
def test_c1_counts_only_the_first_goods_receipt(tmp_path: Path) -> None:
    second_gr = ("Record Goods Receipt", "2018-01-20T10:00:00.000Z", 100.0)
    assert check_c1(item(tmp_path, AFTER_GR, [ORDER, GR, IR_LATE, second_gr])) is None


CANCEL = ("Cancel Goods Receipt", "2018-01-12T10:00:00.000Z", 100.0)
GR_AGAIN = ("Record Goods Receipt", "2018-01-20T10:00:00.000Z", 100.0)
IR_LAST = ("Record Invoice Receipt", "2018-01-25T10:00:00.000Z", 100.0)


@pytest.mark.criterion("C1")
def test_c1_flags_an_invoice_after_every_goods_receipt_was_cancelled(tmp_path: Path) -> None:
    finding = check_c1(item(tmp_path, AFTER_GR, [ORDER, GR, CANCEL, IR_LATE, GR_AGAIN]))
    assert finding is not None
    assert [(e.activity, e.timestamp.day) for e in finding.events] == [
        ("Record Goods Receipt", 10),
        ("Cancel Goods Receipt", 12),
        ("Record Invoice Receipt", 15),
        ("Record Goods Receipt", 20),
    ]


@pytest.mark.criterion("C1")
@pytest.mark.parametrize(
    ("category", "events"),
    [
        pytest.param(AFTER_GR, [ORDER, GR, IR_LATE], id="right order"),
        pytest.param(AFTER_GR, [ORDER, GR, CANCEL, GR_AGAIN, IR_LAST], id="received again"),
        pytest.param(AFTER_GR, [ORDER, GR, GR_AGAIN, CANCEL, IR_LAST], id="one of two cancelled"),
        pytest.param("3-way match, invoice before GR", [ORDER, IR_EARLY, GR], id="other category"),
        pytest.param(AFTER_GR, [ORDER, IR_EARLY], id="no goods receipt"),
    ],
)
def test_c1_does_not_flag(tmp_path: Path, category: str, events: list[EventSpec]) -> None:
    assert check_c1(item(tmp_path, category, events)) is None


CLEARED = ("Clear Invoice", "2018-01-30T10:00:00.000Z", 100.0)


@pytest.mark.criterion("C1")
def test_c1_flags_a_cleared_item_invoiced_with_no_goods_receipt(tmp_path: Path) -> None:
    finding = check_c1(item(tmp_path, AFTER_GR, [ORDER, IR_EARLY, CLEARED]))
    assert finding is not None
    assert (finding.item_id, finding.criterion) == ("A_1", "C1")
    assert [e.activity for e in finding.events] == ["Record Invoice Receipt", "Clear Invoice"]


@pytest.mark.criterion("C1")
def test_c1_does_not_flag_a_cleared_item_with_no_invoice_receipt(tmp_path: Path) -> None:
    assert check_c1(item(tmp_path, AFTER_GR, [ORDER, CLEARED])) is None


BEFORE_GR = "3-way match, invoice before GR"
TWO_WAY = "2-way match"
CONSIGNMENT = "Consignment"
CLEAR_EARLY = ("Clear Invoice", "2018-01-08T10:00:00.000Z", 100.0)
CLEAR_LATE = ("Clear Invoice", "2018-01-30T10:00:00.000Z", 100.0)
IR = ("Record Invoice Receipt", "2018-01-05T10:00:00.000Z", 100.0)
CANCEL_IR = ("Cancel Invoice Receipt", "2018-01-07T10:00:00.000Z", 100.0)
IR_AGAIN = ("Record Invoice Receipt", "2018-01-20T10:00:00.000Z", 100.0)


@pytest.mark.criterion("C2")
@pytest.mark.parametrize("category", [AFTER_GR, BEFORE_GR])
def test_c2_flags_a_clearing_before_any_goods_receipt(tmp_path: Path, category: str) -> None:
    finding = checks.check_c2(item(tmp_path, category, [ORDER, IR, CLEAR_EARLY, GR]))
    assert finding is not None
    assert (finding.item_id, finding.criterion) == ("A_1", "C2")
    assert [e.activity for e in finding.events] == ["Clear Invoice"]


@pytest.mark.criterion("C2")
def test_c2_flags_a_clearing_after_every_goods_receipt_was_cancelled(tmp_path: Path) -> None:
    finding = checks.check_c2(item(tmp_path, BEFORE_GR, [ORDER, GR, CANCEL, CLEAR_LATE]))
    assert finding is not None
    assert [(e.activity, e.timestamp.day) for e in finding.events] == [
        ("Record Goods Receipt", 10),
        ("Cancel Goods Receipt", 12),
        ("Clear Invoice", 30),
    ]


@pytest.mark.criterion("C2")
def test_c2_flags_a_cleared_item_with_no_goods_receipt(tmp_path: Path) -> None:
    assert checks.check_c2(item(tmp_path, AFTER_GR, [ORDER, IR, CLEAR_LATE])) is not None


@pytest.mark.criterion("C2")
@pytest.mark.parametrize(
    ("category", "events"),
    [
        pytest.param(BEFORE_GR, [ORDER, IR, GR, CLEAR_LATE], id="goods received"),
        pytest.param(AFTER_GR, [ORDER, GR, CANCEL, GR_AGAIN, CLEAR_LATE], id="received again"),
        pytest.param(BEFORE_GR, [ORDER, IR], id="not cleared"),
        pytest.param(TWO_WAY, [ORDER, IR, CLEAR_LATE], id="other category"),
    ],
)
def test_c2_does_not_flag(tmp_path: Path, category: str, events: list[EventSpec]) -> None:
    assert checks.check_c2(item(tmp_path, category, events)) is None


@pytest.mark.criterion("C3")
def test_c3_flags_a_clearing_before_any_invoice_receipt(tmp_path: Path) -> None:
    finding = checks.check_c3(item(tmp_path, TWO_WAY, [ORDER, CLEAR_EARLY, IR_AGAIN]))
    assert finding is not None
    assert (finding.item_id, finding.criterion) == ("A_1", "C3")
    assert [e.activity for e in finding.events] == ["Clear Invoice"]


@pytest.mark.criterion("C3")
def test_c3_flags_a_clearing_after_every_invoice_receipt_was_cancelled(tmp_path: Path) -> None:
    finding = checks.check_c3(item(tmp_path, TWO_WAY, [ORDER, IR, CANCEL_IR, CLEAR_EARLY]))
    assert finding is not None
    assert [e.activity for e in finding.events] == [
        "Record Invoice Receipt",
        "Cancel Invoice Receipt",
        "Clear Invoice",
    ]


@pytest.mark.criterion("C3")
@pytest.mark.parametrize(
    ("category", "events"),
    [
        pytest.param(TWO_WAY, [ORDER, IR, CLEAR_LATE], id="invoice received"),
        pytest.param(TWO_WAY, [ORDER, IR, CANCEL_IR, IR_AGAIN, CLEAR_LATE], id="received again"),
        pytest.param(BEFORE_GR, [ORDER, CLEAR_EARLY], id="other category"),
    ],
)
def test_c3_does_not_flag(tmp_path: Path, category: str, events: list[EventSpec]) -> None:
    assert checks.check_c3(item(tmp_path, category, events)) is None


@pytest.mark.criterion("C4")
@pytest.mark.parametrize(
    "events",
    [
        pytest.param([ORDER, GR, IR], id="invoice receipt"),
        pytest.param([ORDER, GR, IR, CANCEL_IR, IR_AGAIN], id="invoiced again"),
        pytest.param([ORDER, GR, CLEAR_LATE], id="clearing"),
    ],
)
def test_c4_flags_an_invoiced_consignment_item(tmp_path: Path, events: list[EventSpec]) -> None:
    finding = checks.check_c4(item(tmp_path, CONSIGNMENT, events))
    assert finding is not None
    assert (finding.item_id, finding.criterion) == ("A_1", "C4")
    assert "Record Goods Receipt" not in [e.activity for e in finding.events]


@pytest.mark.criterion("C4")
@pytest.mark.parametrize(
    ("category", "events"),
    [
        pytest.param(CONSIGNMENT, [ORDER, GR], id="no invoice"),
        pytest.param(CONSIGNMENT, [ORDER, GR, IR, CANCEL_IR], id="invoice cancelled"),
        pytest.param(TWO_WAY, [ORDER, IR, CLEAR_LATE], id="other category"),
    ],
)
def test_c4_does_not_flag(tmp_path: Path, category: str, events: list[EventSpec]) -> None:
    assert checks.check_c4(item(tmp_path, category, events)) is None


CANCEL_IR_AT_10 = ("Cancel Invoice Receipt", "2018-02-01T10:00:00.000Z", 100.0)
CLEAR_AT_10_10 = ("Clear Invoice", "2018-02-01T10:10:00.000Z", 100.0)
CLEAR_AT_10_11 = ("Clear Invoice", "2018-02-01T10:11:00.000Z", 100.0)


@pytest.mark.criterion("C3")
def test_c3_notes_a_clearing_right_after_an_invoice_cancellation(tmp_path: Path) -> None:
    finding = checks.check_c3(item(tmp_path, TWO_WAY, [ORDER, IR, CANCEL_IR_AT_10, CLEAR_AT_10_10]))
    assert finding is not None
    assert finding.note == checks.REVERSAL_NOTE


@pytest.mark.criterion("C3")
def test_c3_does_not_note_a_clearing_eleven_minutes_later(tmp_path: Path) -> None:
    finding = checks.check_c3(item(tmp_path, TWO_WAY, [ORDER, IR, CANCEL_IR_AT_10, CLEAR_AT_10_11]))
    assert finding is not None
    assert finding.note == ""


@pytest.mark.criterion("C2")
def test_c2_notes_a_clearing_right_after_an_invoice_cancellation(tmp_path: Path) -> None:
    events = [ORDER, IR, CANCEL_IR_AT_10, CLEAR_AT_10_10]
    finding = checks.check_c2(item(tmp_path, BEFORE_GR, events))
    assert finding is not None
    assert finding.note == checks.REVERSAL_NOTE
    no_note = checks.check_c2(item(tmp_path, BEFORE_GR, [ORDER, IR, CLEAR_LATE]))
    assert no_note is not None
    assert no_note.note == ""


@pytest.mark.criterion("C3")
def test_c3_does_not_note_a_cancellation_after_the_clearing(tmp_path: Path) -> None:
    cancel_after = ("Cancel Invoice Receipt", "2018-02-01T10:15:00.000Z", 100.0)
    finding = checks.check_c3(item(tmp_path, TWO_WAY, [ORDER, CLEAR_AT_10_10, cancel_after]))
    assert finding is not None
    assert finding.note == ""


@pytest.mark.criterion("C2")
def test_c2_does_not_note_a_clearing_eleven_minutes_later(tmp_path: Path) -> None:
    events = [ORDER, IR, CANCEL_IR_AT_10, CLEAR_AT_10_11]
    finding = checks.check_c2(item(tmp_path, BEFORE_GR, events))
    assert finding is not None
    assert finding.note == ""


BEFORE_WINDOW = "2017-12-31T23:59:59.000Z"
AFTER_WINDOW = "2019-02-01T00:00:00.000Z"
WINDOW_FIRST = ("Vendor creates invoice", "2018-01-01T00:00:00.000Z", 100.0)
WINDOW_LAST = ("Clear Invoice", "2019-01-31T23:59:59.000Z", 100.0)


@pytest.mark.criterion("C7")
@pytest.mark.parametrize("timestamp", [BEFORE_WINDOW, AFTER_WINDOW])
def test_c7_flags_an_event_outside_the_window(tmp_path: Path, timestamp: str) -> None:
    outside = ("Vendor creates invoice", timestamp, 100.0)
    finding = checks.check_c7(item(tmp_path, AFTER_GR, [WINDOW_FIRST, outside, GR, WINDOW_LAST]))
    assert finding is not None
    assert (finding.item_id, finding.criterion) == ("A_1", "C7")
    assert [e.timestamp.isoformat() for e in finding.events] == [
        timestamp.replace(".000Z", "+00:00")
    ]


@pytest.mark.criterion("C7")
def test_c7_does_not_flag_events_on_the_window_edges(tmp_path: Path) -> None:
    assert checks.check_c7(item(tmp_path, AFTER_GR, [WINDOW_FIRST, GR, WINDOW_LAST])) is None


@pytest.mark.criterion("C7")
def test_c7_leaves_a_clearing_outside_the_window_out_of_c2(tmp_path: Path) -> None:
    clear_outside = ("Clear Invoice", BEFORE_WINDOW, 100.0)
    cleared = item(tmp_path, BEFORE_GR, [ORDER, IR, clear_outside, GR])
    assert checks.check_c2(cleared) is not None
    assert checks.check_c2(checks.within_window(cleared)) is None


@pytest.mark.criterion("C7")
def test_c7_leaves_an_invoice_receipt_outside_the_window_out_of_c3(tmp_path: Path) -> None:
    ir_outside = ("Record Invoice Receipt", AFTER_WINDOW, 100.0)
    invoiced = item(tmp_path, TWO_WAY, [ORDER, ir_outside, CLEAR_LATE])
    assert checks.check_c3(invoiced) is None
    finding = checks.check_c3(checks.within_window(invoiced))
    assert finding is not None
    assert [e.activity for e in finding.events] == ["Clear Invoice"]


def at(activity: str, day: int, value: float) -> EventSpec:
    return (activity, f"2018-02-{day:02d}T10:00:00.000Z", value)


C6_CLEAR = at("Clear Invoice", 28, 0.0)


def c6_goods(invoiced: float) -> list[EventSpec]:
    return [ORDER, at("Record Goods Receipt", 2, 100.0), at("Record Invoice Receipt", 3, invoiced)]


def c6_services(invoiced: float) -> list[EventSpec]:
    return [
        ORDER,
        at("Record Service Entry Sheet", 2, 50.0),
        at("Record Goods Receipt", 3, 7.0),
        at("Record Service Entry Sheet", 4, 50.0),
        at("Record Invoice Receipt", 5, invoiced),
    ]


@pytest.mark.criterion("C6")
@pytest.mark.parametrize(
    ("events", "difference"),
    [
        pytest.param(c6_goods(101.0), 1.0, id="goods, one euro above one receipt"),
        pytest.param(c6_goods(99.0), -1.0, id="goods, one euro below one invoice"),
        pytest.param(c6_services(102.0), 2.0, id="services, two euros above two sheets"),
        pytest.param(c6_services(98.0), -2.0, id="services, two euros below"),
    ],
)
def test_c6_flags_a_difference_beyond_the_truncation(
    tmp_path: Path, events: list[EventSpec], difference: float
) -> None:
    finding = checks.check_c6(item(tmp_path, AFTER_GR, [*events, C6_CLEAR]))
    assert finding is not None
    assert (finding.item_id, finding.criterion) == ("A_1", "C6")
    assert finding.note == f"net invoiced minus net received: {difference:.2f} EUR"


@pytest.mark.criterion("C6")
def test_c6_evidence_is_the_counted_documents(tmp_path: Path) -> None:
    finding = checks.check_c6(item(tmp_path, AFTER_GR, [*c6_services(110.0), C6_CLEAR]))
    assert finding is not None
    assert [e.activity for e in finding.events] == [
        "Record Service Entry Sheet",
        "Record Service Entry Sheet",
        "Record Invoice Receipt",
    ]


@pytest.mark.criterion("C6")
@pytest.mark.parametrize(
    ("category", "events"),
    [
        pytest.param(AFTER_GR, [*c6_goods(100.0), C6_CLEAR], id="goods, equal"),
        pytest.param(AFTER_GR, [*c6_goods(100.5), C6_CLEAR], id="goods, within the truncation"),
        pytest.param(AFTER_GR, [*c6_services(101.0), C6_CLEAR], id="services, within"),
        pytest.param(
            AFTER_GR,
            [
                *c6_goods(100.0),
                at("Cancel Goods Receipt", 6, 100.0),
                at("Record Goods Receipt", 7, 100.0),
                C6_CLEAR,
            ],
            id="goods, a receipt cancelled and recorded again",
        ),
        pytest.param(
            AFTER_GR,
            [
                *c6_goods(100.0),
                at("Cancel Invoice Receipt", 6, 100.0),
                at("Record Invoice Receipt", 7, 100.0),
                C6_CLEAR,
            ],
            id="goods, an invoice cancelled and recorded again",
        ),
        pytest.param(AFTER_GR, c6_goods(200.0), id="open item"),
        pytest.param(BEFORE_GR, [*c6_goods(200.0), C6_CLEAR], id="other category"),
    ],
)
def test_c6_does_not_flag(tmp_path: Path, category: str, events: list[EventSpec]) -> None:
    assert checks.check_c6(item(tmp_path, category, events)) is None


@pytest.mark.criterion("C6")
@pytest.mark.parametrize("invoiced", [100.0, 300.0])
def test_c6_reports_a_service_item_with_changes_as_not_checked(
    tmp_path: Path, invoiced: float
) -> None:
    change = at("Change Price", 6, 80.0)
    finding = checks.check_c6(item(tmp_path, AFTER_GR, [*c6_services(invoiced), change, C6_CLEAR]))
    assert finding is not None
    assert finding.criterion == "C6 not checked"
    assert [e.activity for e in finding.events] == ["Change Price"]


@pytest.mark.criterion("C6")
def test_c6_checks_a_goods_item_with_changes(tmp_path: Path) -> None:
    change = at("Change Price", 6, 80.0)
    finding = checks.check_c6(item(tmp_path, AFTER_GR, [*c6_goods(300.0), change, C6_CLEAR]))
    assert finding is not None
    assert finding.criterion == "C6"


GR_50 = ("Record Goods Receipt", "2018-01-10T10:00:00.000Z", 50.0)
IR_70 = ("Record Invoice Receipt", "2018-01-05T10:00:00.000Z", 70.0)
CLEAR_90 = ("Clear Invoice", "2018-01-08T10:00:00.000Z", 90.0)


@pytest.mark.criterion("C12")
@pytest.mark.parametrize(
    ("check", "category", "events", "at_stake"),
    [
        pytest.param(check_c1, AFTER_GR, [ORDER, IR_70, GR_50], 70.0, id="C1, the invoice"),
        pytest.param(
            check_c1, AFTER_GR, [ORDER, IR_70, CLEAR_90], 70.0, id="C1 with no receipt, the invoice"
        ),
        pytest.param(
            checks.check_c2, BEFORE_GR, [ORDER, IR_70, CLEAR_90, GR_50], 90.0, id="C2, the clearing"
        ),
        pytest.param(
            checks.check_c3, TWO_WAY, [ORDER, GR_50, CLEAR_90], 90.0, id="C3, the clearing"
        ),
        pytest.param(
            checks.check_c4, CONSIGNMENT, [ORDER, GR_50, IR_70, CLEAR_90], 70.0, id="C4, first"
        ),
        pytest.param(
            checks.check_c6, AFTER_GR, [*c6_goods(99.0), C6_CLEAR], 1.0, id="C6, absolute"
        ),
    ],
)
def test_c12_euros_at_stake_per_criterion(
    tmp_path: Path,
    check: Callable[[Item], Finding | None],
    category: str,
    events: list[EventSpec],
    at_stake: float,
) -> None:
    finding = check(item(tmp_path, category, events))
    assert finding is not None
    assert finding.at_stake == at_stake


@pytest.mark.criterion("C12")
def test_c12_no_euros_on_c7_and_c6_not_checked(tmp_path: Path) -> None:
    outside = ("Record Goods Receipt", BEFORE_WINDOW, 100.0)
    c7 = checks.check_c7(item(tmp_path, AFTER_GR, [ORDER, outside]))
    change = at("Change Price", 6, 80.0)
    not_checked = checks.check_c6(item(tmp_path, AFTER_GR, [*c6_services(100.0), change, C6_CLEAR]))
    assert c7 is not None and not_checked is not None
    assert (c7.at_stake, not_checked.at_stake) == (None, None)


def finding_of(at_stake: float | None, note: str = "") -> Finding:
    return Finding("A_1", "C2", (), note, at_stake)


@pytest.mark.criterion("C13")
@pytest.mark.parametrize(
    ("at_stake", "level"),
    [(0.0, "low"), (999.99, "low"), (1_000.0, "medium"), (9_999.99, "medium"), (10_000.0, "high")],
)
def test_c13_severity_at_the_boundaries(at_stake: float, level: str) -> None:
    assert checks.severity(finding_of(at_stake)) == level


@pytest.mark.criterion("C13")
@pytest.mark.parametrize(
    ("at_stake", "level"), [(10_000.0, "medium"), (1_000.0, "low"), (999.99, "low")]
)
def test_c13_reversal_note_lowers_severity_one_level(at_stake: float, level: str) -> None:
    assert checks.severity(finding_of(at_stake, checks.REVERSAL_NOTE)) == level


@pytest.mark.criterion("C13")
def test_c13_no_severity_without_euros_at_stake() -> None:
    assert checks.severity(finding_of(None)) == ""
