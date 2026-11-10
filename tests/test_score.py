from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from test_inject import KIND, ORDER, before_item, goods_item, item, log

from matchbook import score as score_module
from matchbook.checks import (
    CLEAR_INVOICE,
    GOODS_RECEIPT,
    INVOICE_AFTER_GR,
    INVOICE_RECEIPT,
    SERVICE_ENTRY,
)
from matchbook.inject import KINDS, PER_KIND
from matchbook.score import Score, count, criteria, score
from matchbook.xes import Event, Item


def outside(original: Item) -> Item:
    """The item with an event before the window, so C7 flags it."""
    early = Event(ORDER, datetime(2017, 12, 1, tzinfo=UTC), 100)
    return replace(original, events=(early, *original.events))


def unchecked_service_item() -> Item:
    """A closed service item with a price change: "C6 not checked" and nothing else."""
    return item(
        INVOICE_AFTER_GR,
        (ORDER, 100),
        (GOODS_RECEIPT, 100),
        (SERVICE_ENTRY, 100),
        (INVOICE_RECEIPT, 100),
        ("Change Price", 100),
        (CLEAR_INVOICE, 100),
    )


@pytest.mark.criterion("C15")
def test_c15_criteria_are_those_of_the_findings() -> None:
    assert criteria(goods_item()) == set()
    assert criteria(KIND["F1"].change(goods_item())) == {"C1"}
    assert criteria(outside(KIND["F1"].change(goods_item()))) == {"C1", "C7"}
    assert criteria(unchecked_service_item()) == {"C6 not checked"}


@pytest.mark.criterion("C15")
def test_c15_a_fault_flagged_by_its_criterion_is_detected() -> None:
    f1 = KIND["F1"]
    assert count(f1, [f1.change(goods_item())]) == Score(f1, 1, 1, 0, 0, 0)


@pytest.mark.criterion("C15")
@pytest.mark.parametrize(
    ("kind", "flagged"),
    [
        pytest.param("F1", outside(goods_item()), id="C7"),
        pytest.param("F6", unchecked_service_item(), id="C6 not checked"),
        pytest.param("F2", KIND["F1"].change(goods_item()), id="another document check"),
    ],
)
def test_c15_a_fault_flagged_by_another_criterion_is_a_false_alarm(
    kind: str, flagged: Item
) -> None:
    assert count(KIND[kind], [flagged]) == Score(KIND[kind], 1, 0, 1, 0, 0)


@pytest.mark.criterion("C15")
def test_c15_a_fault_flagged_by_both_counts_in_both() -> None:
    f1 = KIND["F1"]
    assert count(f1, [outside(f1.change(goods_item()))]) == Score(f1, 1, 1, 1, 0, 0)


@pytest.mark.criterion("C15")
def test_c15_a_look_alike_flagged_by_any_criterion_is_a_false_alarm() -> None:
    l1 = KIND["L1"]
    clean = l1.change(goods_item())
    assert count(l1, [clean]) == Score(l1, 1, None, 0, None, 1)
    assert count(l1, [clean, outside(clean)]) == Score(l1, 2, None, 1, None, 2)


@pytest.mark.criterion("C15")
def test_c15_score_counts_50_items_per_kind_the_same_for_the_same_seed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(score_module, "read_items", lambda _path: iter(log()))
    first = score(Path("log.xes"), seed=1)
    assert [row.kind for row in first] == list(KINDS)
    assert all(row.items == PER_KIND for row in first)
    assert all(row.false_alarms == 0 for row in first)
    assert all(row.detected == PER_KIND for row in first if row.kind.criterion)
    assert score(Path("log.xes"), seed=1) == first


@pytest.mark.criterion("C15")
def test_c15_main_prints_a_header_and_a_line_per_kind(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(score_module, "read_items", lambda _path: iter(log()))
    assert score_module.main(["log.xes", "--seed", "1"]) == 0
    lines = [line.split("\t")[:5] for line in capsys.readouterr().out.splitlines()]
    assert lines[0] == ["kind", "criterion", "items", "detected", "false alarms"]
    assert lines[1] == ["F1", "C1", "50", "50", "0"]
    assert lines[-1] == ["L3", "", "50", "", "0"]
    assert len(lines) == 1 + len(KINDS)


def mismatched_goods_item() -> Item:
    """A closed goods item invoiced 20 EUR over its receipt: B6 flags it."""
    return item(
        INVOICE_AFTER_GR,
        (ORDER, 100),
        (GOODS_RECEIPT, 100),
        (INVOICE_RECEIPT, 120),
        (CLEAR_INVOICE, 120),
    )


def baseline(row: Score) -> tuple[int | None, int]:
    return row.baseline_detected, row.baseline_false_alarms


@pytest.mark.criterion("C17")
def test_c17_a_fault_flagged_by_its_rule_is_baseline_detected() -> None:
    f2 = KIND["F2"]
    assert baseline(count(f2, [f2.change(before_item())])) == (1, 0)


@pytest.mark.criterion("C17")
def test_c17_a_fault_flagged_by_another_rule_is_a_baseline_false_alarm() -> None:
    assert baseline(count(KIND["F4"], [mismatched_goods_item()])) == (0, 1)


@pytest.mark.criterion("C17")
def test_c17_a_fault_flagged_by_its_rule_and_another_counts_in_both() -> None:
    no_receipt = item(INVOICE_AFTER_GR, (ORDER, 100), (INVOICE_RECEIPT, 100), (CLEAR_INVOICE, 100))
    assert baseline(count(KIND["F2"], [no_receipt])) == (1, 1)


@pytest.mark.criterion("C17")
def test_c17_an_f1_item_is_missed_by_the_baseline_even_when_a_rule_flags_it() -> None:
    f1 = KIND["F1"]
    assert baseline(count(f1, [f1.change(goods_item())])) == (0, 0)
    assert baseline(count(f1, [f1.change(mismatched_goods_item())])) == (0, 1)


@pytest.mark.criterion("C17")
def test_c17_a_look_alike_flagged_by_any_rule_is_a_baseline_false_alarm() -> None:
    l3 = KIND["L3"]
    assert baseline(count(l3, [goods_item()])) == (None, 0)
    assert baseline(count(l3, [goods_item(), l3.change(goods_item())])) == (None, 1)


@pytest.mark.criterion("C17")
def test_c17_score_counts_the_baseline_per_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(score_module, "read_items", lambda _path: iter(log()))
    rows = {row.kind.name: baseline(row) for row in score(Path("log.xes"), seed=1)}
    assert rows == {
        "F1": (0, 0),
        "F2": (50, 0),
        "F3": (0, 0),
        "F4": (50, 0),
        "F5": (50, 0),
        "F6": (50, 0),
        "L1": (None, 50),
        "L2": (None, 50),
        "L3": (None, 50),
    }


@pytest.mark.criterion("C17")
def test_c17_main_prints_the_baseline_columns_at_the_end(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(score_module, "read_items", lambda _path: iter(log()))
    assert score_module.main(["log.xes", "--seed", "1"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == (
        "kind\tcriterion\titems\tdetected\tfalse alarms\tbaseline detected\tbaseline false alarms"
    )
    assert lines[1] == "F1\tC1\t50\t50\t0\t0\t0"
    assert lines[2] == "F2\tC2\t50\t50\t0\t50\t0"
    assert lines[-1] == "L3\t\t50\t\t0\t\t50"
