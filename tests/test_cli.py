import subprocess
import sys
from pathlib import Path

import pytest
from test_xes import ItemSpec, write_log

AFTER_GR = "3-way match, invoice after GR"


def flagged(item_id: str) -> ItemSpec:
    return (
        item_id,
        AFTER_GR,
        [
            ("Create Purchase Order Item", "2018-01-02T10:00:00.000Z", 100.0),
            ("Record Invoice Receipt", "2018-01-05T10:00:00.000Z", 120.5),
            ("Record Goods Receipt", "2018-01-10T10:00:00.000Z", 100.0),
        ],
    )


def clean(item_id: str) -> ItemSpec:
    return (
        item_id,
        AFTER_GR,
        [
            ("Record Goods Receipt", "2018-02-01T10:00:00.000Z", 50.0),
            ("Record Invoice Receipt", "2018-02-03T10:00:00.000Z", 50.0),
        ],
    )


ITEMS = [flagged("4500000001_00010"), clean("4500000002_00010")]


def run(log: Path) -> subprocess.CompletedProcess[str]:
    # No PYTHONPATH: the command must work as the README writes it, from the installed package.
    return subprocess.run(
        [sys.executable, "-m", "matchbook", str(log)],
        capture_output=True,
        text=True,
        check=True,
        cwd=log.parent,
    )


@pytest.mark.criterion("C11")
def test_output_names_the_item_the_criterion_and_the_events(tmp_path: Path) -> None:
    result = run(write_log(tmp_path / "log.xes", ITEMS))
    assert result.returncode == 0
    assert result.stdout.splitlines() == [
        "4500000001_00010\tC1\t120.50\tlow\t"
        "Record Invoice Receipt 2018-01-05T10:00:00+00:00 120.5 EUR; "
        "Record Goods Receipt 2018-01-10T10:00:00+00:00 100.0 EUR"
    ]


@pytest.mark.criterion("C9")
def test_two_runs_print_identical_output_in_log_order(tmp_path: Path) -> None:
    ids = [f"45000000{n:02d}_00010" for n in (7, 3, 9, 1, 5)]
    log = write_log(tmp_path / "log.xes", [spec for i in ids for spec in (flagged(i), clean(i))])
    first, second = run(log).stdout, run(log).stdout
    assert [line.split("\t")[0] for line in first.splitlines()] == ids
    assert first == second


@pytest.mark.criterion("C10")
def test_a_run_leaves_the_log_directory_unchanged(tmp_path: Path) -> None:
    log = write_log(tmp_path / "log.xes", ITEMS)

    def snapshot() -> list[tuple[str, int, int]]:
        return sorted((p.name, p.stat().st_size, p.stat().st_mtime_ns) for p in tmp_path.iterdir())

    before = snapshot()
    run(log)
    assert snapshot() == before


@pytest.mark.criterion("C2")
def test_output_lists_an_items_findings_in_criterion_order(tmp_path: Path) -> None:
    both = (
        "4500000003_00010",
        AFTER_GR,
        [
            ("Record Invoice Receipt", "2018-03-01T10:00:00.000Z", 70.0),
            ("Clear Invoice", "2018-03-05T10:00:00.000Z", 70.0),
            ("Record Goods Receipt", "2018-03-09T10:00:00.000Z", 70.0),
        ],
    )
    result = run(write_log(tmp_path / "log.xes", [both]))
    assert result.stdout.splitlines() == [
        "4500000003_00010\tC1\t70.00\tlow\t"
        "Record Invoice Receipt 2018-03-01T10:00:00+00:00 70.0 EUR; "
        "Record Goods Receipt 2018-03-09T10:00:00+00:00 70.0 EUR",
        "4500000003_00010\tC2\t70.00\tlow\tClear Invoice 2018-03-05T10:00:00+00:00 70.0 EUR",
    ]


@pytest.mark.criterion("C3")
def test_output_prints_the_note_as_a_last_column(tmp_path: Path) -> None:
    reversed_invoice = (
        "4500000004_00010",
        "2-way match",
        [
            ("Record Invoice Receipt", "2018-04-01T10:00:00.000Z", 80.0),
            ("Cancel Invoice Receipt", "2018-04-03T10:00:00.000Z", 80.0),
            ("Clear Invoice", "2018-04-03T10:01:00.000Z", 80.0),
        ],
    )
    result = run(write_log(tmp_path / "log.xes", [reversed_invoice]))
    (line,) = result.stdout.splitlines()
    assert line.split("\t")[1] == "C3"
    assert line.split("\t")[-1] == (
        "cleared within 10 minutes after a Cancel Invoice Receipt: may be the reversal"
    )


@pytest.mark.criterion("C7")
def test_output_leaves_out_and_lists_events_outside_the_window(tmp_path: Path) -> None:
    dated_1948 = (
        "4500000005_00010",
        AFTER_GR,
        [
            ("Record Goods Receipt", "1948-01-26T23:00:00.000Z", 60.0),
            ("Record Invoice Receipt", "2018-05-01T10:00:00.000Z", 60.0),
            ("Record Goods Receipt", "2018-05-09T10:00:00.000Z", 60.0),
        ],
    )
    result = run(write_log(tmp_path / "log.xes", [dated_1948]))
    assert result.stdout.splitlines() == [
        "4500000005_00010\tC1\t60.00\tlow\t"
        "Record Invoice Receipt 2018-05-01T10:00:00+00:00 60.0 EUR; "
        "Record Goods Receipt 2018-05-09T10:00:00+00:00 60.0 EUR",
        "4500000005_00010\tC7\t\t\tRecord Goods Receipt 1948-01-26T23:00:00+00:00 60.0 EUR",
    ]


@pytest.mark.criterion("C6")
def test_output_reports_a_c6_service_item_with_changes_as_not_checked(tmp_path: Path) -> None:
    changed = (
        "4500000006_00010",
        AFTER_GR,
        [
            ("Record Service Entry Sheet", "2018-06-01T10:00:00.000Z", 50.0),
            ("Record Goods Receipt", "2018-06-02T10:00:00.000Z", 50.0),
            ("Record Invoice Receipt", "2018-06-05T10:00:00.000Z", 50.0),
            ("Change Price", "2018-06-06T10:00:00.000Z", 60.0),
            ("Clear Invoice", "2018-06-09T10:00:00.000Z", 60.0),
        ],
    )
    result = run(write_log(tmp_path / "log.xes", [changed]))
    assert result.stdout.splitlines() == [
        "4500000006_00010\tC6 not checked\t\t\t"
        "Change Price 2018-06-06T10:00:00+00:00 60.0 EUR\t"
        "service item with cancellations or changes"
    ]


@pytest.mark.criterion("C6")
def test_output_prints_a_c6_line_with_the_difference(tmp_path: Path) -> None:
    over_invoiced = (
        "4500000007_00010",
        AFTER_GR,
        [
            ("Record Goods Receipt", "2018-07-01T10:00:00.000Z", 100.0),
            ("Record Invoice Receipt", "2018-07-05T10:00:00.000Z", 110.0),
            ("Clear Invoice", "2018-07-09T10:00:00.000Z", 110.0),
        ],
    )
    result = run(write_log(tmp_path / "log.xes", [over_invoiced]))
    assert result.stdout.splitlines() == [
        "4500000007_00010\tC6\t10.00\tlow\t"
        "Record Goods Receipt 2018-07-01T10:00:00+00:00 100.0 EUR; "
        "Record Invoice Receipt 2018-07-05T10:00:00+00:00 110.0 EUR\t"
        "net invoiced minus net received: 10.00 EUR"
    ]


@pytest.mark.criterion("C13")
def test_output_prints_euros_and_severity_after_the_criterion(tmp_path: Path) -> None:
    reversed_invoice = (
        "4500000008_00010",
        "2-way match",
        [
            ("Record Invoice Receipt", "2018-08-01T10:00:00.000Z", 12500.0),
            ("Cancel Invoice Receipt", "2018-08-03T10:00:00.000Z", 12500.0),
            ("Clear Invoice", "2018-08-03T10:01:00.000Z", 12500.0),
        ],
    )
    result = run(write_log(tmp_path / "log.xes", [reversed_invoice]))
    (line,) = result.stdout.splitlines()
    assert line.split("\t")[1:4] == ["C3", "12500.00", "medium"]


@pytest.mark.criterion("C13")
def test_output_leaves_euros_and_severity_empty_on_c7_and_c6_not_checked(
    tmp_path: Path,
) -> None:
    both = (
        "4500000009_00010",
        AFTER_GR,
        [
            ("Record Service Entry Sheet", "2017-12-01T10:00:00.000Z", 50.0),
            ("Record Invoice Receipt", "2018-06-05T10:00:00.000Z", 50.0),
            ("Change Price", "2018-06-06T10:00:00.000Z", 60.0),
            ("Record Goods Receipt", "2018-06-07T10:00:00.000Z", 60.0),
            ("Clear Invoice", "2018-06-09T10:00:00.000Z", 60.0),
        ],
    )
    result = run(write_log(tmp_path / "log.xes", [both]))
    fields = [line.split("\t") for line in result.stdout.splitlines()]
    assert [f[1:4] for f in fields if f[1] in ("C6 not checked", "C7")] == [
        ["C6 not checked", "", ""],
        ["C7", "", ""],
    ]
