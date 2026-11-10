"""The criteria of CRITERIA.md, each a check on one item."""

from collections import Counter
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

from matchbook.xes import Event, Item

INVOICE_AFTER_GR = "3-way match, invoice after GR"
INVOICE_BEFORE_GR = "3-way match, invoice before GR"
TWO_WAY = "2-way match"
CONSIGNMENT = "Consignment"
GOODS_RECEIPT = "Record Goods Receipt"
CANCEL_GOODS_RECEIPT = "Cancel Goods Receipt"
INVOICE_RECEIPT = "Record Invoice Receipt"
CANCEL_INVOICE_RECEIPT = "Cancel Invoice Receipt"
CLEAR_INVOICE = "Clear Invoice"
SERVICE_ENTRY = "Record Service Entry Sheet"
# Activities after which a service item's net values follow no known rule (C6).
SERVICE_HISTORY = (
    CANCEL_GOODS_RECEIPT,
    CANCEL_INVOICE_RECEIPT,
    "Change Price",
    "Change Quantity",
    "Record Subsequent Invoice",
    "Cancel Subsequent Invoice",
)
REVERSAL_WINDOW = timedelta(minutes=10)
REVERSAL_NOTE = "cleared within 10 minutes after a Cancel Invoice Receipt: may be the reversal"
# Severity thresholds in EUR at stake (C13), highest first.
SEVERITIES = ((10_000, "high"), (1_000, "medium"), (0, "low"))
# The log's window: 2018 orders and their tail into January 2019 (C7).
WINDOW_START = datetime(2018, 1, 1, tzinfo=UTC)
WINDOW_END = datetime(2019, 2, 1, tzinfo=UTC)


@dataclass(frozen=True)
class Finding:
    """An item that breaks a criterion, with the events that broke it (C11) and the euros
    at stake (C12), None on C7 and "C6 not checked" findings."""

    item_id: str
    criterion: str
    events: tuple[Event, ...]
    note: str = ""
    at_stake: float | None = None


def severity(finding: Finding) -> str:
    """C13: high, medium or low by the euros at stake, one level lower with REVERSAL_NOTE;
    empty for a finding with no euros at stake."""
    if finding.at_stake is None:
        return ""
    level = next(i for i, (floor, _) in enumerate(SEVERITIES) if finding.at_stake >= floor)
    if finding.note == REVERSAL_NOTE:
        level = min(level + 1, len(SEVERITIES) - 1)
    return SEVERITIES[level][1]


def check_c1(item: Item) -> Finding | None:
    """C1: an invoice-after-GR item invoiced while no goods receipt is in force.

    A goods receipt is in force from its Record Goods Receipt until a Cancel Goods Receipt
    undoes it. Order is log order, which on the full log matches timestamp order for every
    item. An item with neither a goods receipt nor a Clear Invoice is an open item, out of
    scope (BRIEF.md); one with a Clear Invoice is closed, as in C2. The evidence is the
    receipts and cancellations before the first such invoice, the invoice, and the next
    Record Goods Receipt after it, or the first Clear Invoice when the item has no goods
    receipt. The euros at stake are the value of that invoice (C12).
    """
    if item.category != INVOICE_AFTER_GR:
        return None
    if not any(event.activity == GOODS_RECEIPT for event in item.events):
        return _invoiced_and_cleared(item)
    in_force = 0
    evidence: list[Event] = []
    invoice: Event | None = None
    for event in item.events:
        if event.activity == GOODS_RECEIPT:
            if invoice:
                return Finding(item.id, "C1", (*evidence, event), at_stake=invoice.net_worth)
            in_force += 1
            evidence.append(event)
        elif event.activity == CANCEL_GOODS_RECEIPT and not invoice:
            in_force = max(in_force - 1, 0)
            evidence.append(event)
        elif event.activity == INVOICE_RECEIPT and in_force == 0 and not invoice:
            invoice = event
            evidence.append(event)
    if invoice is None:
        return None
    return Finding(item.id, "C1", tuple(evidence), at_stake=invoice.net_worth)


def _invoiced_and_cleared(item: Item) -> Finding | None:
    """C1 for an item with no goods receipt: its first invoice receipt and Clear Invoice."""
    invoice = next((e for e in item.events if e.activity == INVOICE_RECEIPT), None)
    clear = next((e for e in item.events if e.activity == CLEAR_INVOICE), None)
    if invoice is None or clear is None:
        return None
    return Finding(item.id, "C1", (invoice, clear), at_stake=invoice.net_worth)


def _cleared_without(item: Item, receipt: str, cancel: str) -> tuple[Event, ...] | None:
    """The receipts and cancellations before the first Clear Invoice that finds no receipt
    in force, and that Clear Invoice; None if every Clear Invoice finds one.

    A receipt is in force from its record until a cancellation undoes it, as in C1.
    """
    in_force = 0
    evidence: list[Event] = []
    for event in item.events:
        if event.activity == receipt:
            in_force += 1
            evidence.append(event)
        elif event.activity == cancel:
            in_force = max(in_force - 1, 0)
            evidence.append(event)
        elif event.activity == CLEAR_INVOICE and in_force == 0:
            return (*evidence, event)
    return None


def _cleared_finding(item: Item, criterion: str, evidence: tuple[Event, ...]) -> Finding:
    """A C2 or C3 finding, noted when its Clear Invoice may clear an invoice's reversal; the
    euros at stake are the value of that Clear Invoice (C12)."""
    clear = evidence[-1]
    reversal = any(
        event.activity == CANCEL_INVOICE_RECEIPT
        and timedelta(0) <= clear.timestamp - event.timestamp <= REVERSAL_WINDOW
        for event in item.events
    )
    note = REVERSAL_NOTE if reversal else ""
    return Finding(item.id, criterion, evidence, note, at_stake=clear.net_worth)


def check_c2(item: Item) -> Finding | None:
    """C2: a 3-way match item whose invoice is cleared while no goods receipt is in force.

    An item with a Clear Invoice is closed, so one with no goods receipt at all is flagged.
    """
    if item.category not in (INVOICE_AFTER_GR, INVOICE_BEFORE_GR):
        return None
    evidence = _cleared_without(item, GOODS_RECEIPT, CANCEL_GOODS_RECEIPT)
    return _cleared_finding(item, "C2", evidence) if evidence else None


def check_c3(item: Item) -> Finding | None:
    """C3: a 2-way match item whose invoice is cleared while no invoice receipt is in force."""
    if item.category != TWO_WAY:
        return None
    evidence = _cleared_without(item, INVOICE_RECEIPT, CANCEL_INVOICE_RECEIPT)
    return _cleared_finding(item, "C3", evidence) if evidence else None


def check_c4(item: Item) -> Finding | None:
    """C4: a consignment item with a Clear Invoice, or an invoice receipt not cancelled.

    The evidence is every invoice receipt, cancellation and Clear Invoice of the item; the
    euros at stake are the value of its first event (C12).
    """
    if item.category != CONSIGNMENT:
        return None
    in_force = 0
    cleared = False
    evidence: list[Event] = []
    for event in item.events:
        if event.activity == INVOICE_RECEIPT:
            in_force += 1
        elif event.activity == CANCEL_INVOICE_RECEIPT:
            in_force = max(in_force - 1, 0)
        elif event.activity == CLEAR_INVOICE:
            cleared = True
        else:
            continue
        evidence.append(event)
    if not (in_force or cleared):
        return None
    return Finding(item.id, "C4", tuple(evidence), at_stake=evidence[0].net_worth)


DOCUMENT_CHECKS = (check_c1, check_c2, check_c3, check_c4)


def check_c6(item: Item) -> Finding | None:
    """C6: a closed invoice-after-GR item whose net invoiced and net received values differ.

    Net invoiced is the invoice receipts minus their cancellations; net received is the
    service entry sheets in a service item, else the goods receipts minus their
    cancellations. Each stored value v is a whole euro truncated from an amount in
    [v, v + 1), so with i invoices, c invoice cancellations, r receipts and g receipt
    cancellations the stored difference d is a finding when d >= r + c or d <= -(i + g).
    The evidence is those documents; the euros at stake are the absolute difference as
    printed, to the cent (C12). A service item with any SERVICE_HISTORY activity is
    returned as "C6 not checked", its evidence those activities. Open items (no Clear
    Invoice) and items with no invoice receipt are not checked.
    """
    activities = {event.activity for event in item.events}
    if (
        item.category != INVOICE_AFTER_GR
        or CLEAR_INVOICE not in activities
        or INVOICE_RECEIPT not in activities
    ):
        return None
    if SERVICE_ENTRY in activities:
        history = tuple(e for e in item.events if e.activity in SERVICE_HISTORY)
        if history:
            return Finding(
                item.id, "C6 not checked", history, "service item with cancellations or changes"
            )
        received, received_back = SERVICE_ENTRY, ""
    else:
        received, received_back = GOODS_RECEIPT, CANCEL_GOODS_RECEIPT
    signs = {INVOICE_RECEIPT: 1, CANCEL_INVOICE_RECEIPT: -1, received: -1, received_back: 1}
    evidence = tuple(e for e in item.events if e.activity in signs)
    difference = sum(signs[e.activity] * e.net_worth for e in evidence)
    count = Counter(e.activity for e in evidence)
    upper = count[received] + count[CANCEL_INVOICE_RECEIPT]
    lower = -(count[INVOICE_RECEIPT] + count[received_back])
    if lower < difference < upper:
        return None
    return Finding(
        item.id,
        "C6",
        evidence,
        f"net invoiced minus net received: {difference:.2f} EUR",
        at_stake=round(abs(difference), 2),
    )


def _outside_window(event: Event) -> bool:
    return not WINDOW_START <= event.timestamp < WINDOW_END


def within_window(item: Item) -> Item:
    """The item without its events outside the log's window, for the document checks (C7)."""
    return replace(item, events=tuple(e for e in item.events if not _outside_window(e)))


def check_c7(item: Item) -> Finding | None:
    """C7: an item with events before 2018-01-01 or after 2019-01-31; they are the evidence."""
    outside = tuple(event for event in item.events if _outside_window(event))
    return Finding(item.id, "C7", outside) if outside else None


def findings(item: Item) -> list[Finding]:
    """The findings python -m matchbook prints for the item, in its order: C1 to C4 on the
    item within the window, then C6 (or "C6 not checked") and C7 on the whole item."""
    checked = within_window(item)
    found = [check(checked) for check in DOCUMENT_CHECKS] + [check_c6(item), check_c7(item)]
    return [finding for finding in found if finding is not None]
