import subprocess
import sys
from pathlib import Path

import pytest
from test_cli import ITEMS
from test_inject import log as injectable
from test_xes import write_log

from matchbook.checks import REVERSAL_NOTE, Finding
from matchbook.compare import Comparison
from matchbook.inject import KINDS
from matchbook.report import decides, render, status
from matchbook.score import Score


def finding(item_id: str, criterion: str, at_stake: float, note: str = "") -> Finding:
    return Finding(item_id, criterion, (), note, at_stake)


# C2 FAIL: its finding with the most euros is medium by the reversal note.
C2 = [
    finding("4500000001_00010", "C2", 500.0),
    finding("4500000002_00010", "C2", 358_488.0, REVERSAL_NOTE),
    finding("4500000003_00010", "C2", 58_815.0),
    finding("4500000004_00010", "C2", 12_000.0),
]
# C3 HOLD: medium and low findings only.
C3 = [finding("4500000005_00010", "C3", 2_000.0), finding("4500000006_00010", "C3", 15.5)]
# Not controls: left out of every table.
OTHERS = [
    Finding("4500000007_00010", "C7", ()),
    Finding("4500000008_00010", "C6 not checked", (), "service item with cancellations or changes"),
]
FOUND = [*C2, *C3, *OTHERS]
SCORES = [
    Score(KINDS[0], 50, 49, 1, 0, 0),
    Score(KINDS[-1], 50, None, 2, None, 50),
]
COMPARISONS = [Comparison("B2", "C2", 0, 169, 566)]


def section(text: str, title: str) -> list[str]:
    """The lines of the section with the title, up to the next one."""
    lines = text.splitlines()
    start = lines.index(f"## {title}") + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return [line for line in lines[start:end] if line]


@pytest.mark.criterion("C18")
def test_c18_status_is_pass_hold_or_fail_by_the_findings() -> None:
    assert status([]) == "PASS"
    assert status(C3) == "HOLD"
    assert status(C2) == "FAIL"
    # A high euro amount lowered to medium by the reversal note does not make a FAIL.
    assert status([C2[1]]) == "HOLD"


@pytest.mark.criterion("C18")
def test_c18_decides_names_the_high_finding_for_fail_and_the_largest_for_hold() -> None:
    assert decides([]) is None
    assert decides(C2) == C2[2]
    assert decides([C2[1]]) == C2[1]
    assert decides(C3) == C3[0]


@pytest.mark.criterion("C18")
def test_c18_decides_takes_the_first_in_log_order_on_a_tie() -> None:
    tied = [finding("4500000009_00010", "C3", 2_000.0), C3[0]]
    assert decides(tied) == tied[0]


@pytest.mark.criterion("C18")
def test_c18_report_gives_status_and_plan_per_control() -> None:
    text = render(FOUND, SCORES, COMPARISONS, 1)
    assert section(text, "Controls")[2:] == [
        "| C1 | PASS | 0 | 0.00 |",
        "| C2 | FAIL | 4 | 429,803.00 |",
        "| C3 | HOLD | 2 | 2,015.50 |",
        "| C4 | PASS | 0 | 0.00 |",
        "| C6 | PASS | 0 | 0.00 |",
    ]
    assert section(text, "Plan") == [
        "- C1: keep.",
        "- C2: replace, decided by 4500000003_00010 at 58,815.00 EUR, high.",
        "- C3: fix, decided by 4500000005_00010 at 2,000.00 EUR, medium.",
        "- C4: keep.",
        "- C6: keep.",
    ]


@pytest.mark.criterion("C19")
def test_c19_report_holds_the_six_sections_in_order() -> None:
    text = render(FOUND, SCORES, COMPARISONS, 7)
    titles = [line for line in text.splitlines() if line.startswith("## ")]
    assert titles == [
        "## Controls",
        "## Plan",
        "## Findings by severity",
        "## Findings by criterion",
        "## Injected log, seed 7",
        "## Baseline on the real log",
    ]


@pytest.mark.criterion("C19")
def test_c19_counts_and_euros_per_severity_and_criterion_add_up() -> None:
    text = render(FOUND, SCORES, COMPARISONS, 1)
    assert section(text, "Findings by severity")[2:] == [
        "| high | 2 | 70,815.00 |",
        "| medium | 2 | 360,488.00 |",
        "| low | 2 | 515.50 |",
    ]
    assert section(text, "Findings by criterion")[2:] == [
        "| C1 | 0 | 0.00 | 0 | 0 | 0 |",
        "| C2 | 4 | 429,803.00 | 2 | 1 | 1 |",
        "| C3 | 2 | 2,015.50 | 0 | 1 | 1 |",
        "| C4 | 0 | 0.00 | 0 | 0 | 0 |",
        "| C6 | 0 | 0.00 | 0 | 0 | 0 |",
    ]


@pytest.mark.criterion("C19")
def test_c19_report_holds_the_tables_of_score_and_compare() -> None:
    text = render(FOUND, SCORES, COMPARISONS, 1)
    assert section(text, "Injected log, seed 1") == [
        "| Kind | Criterion | Items | Detected | False alarms"
        " | Baseline detected | Baseline false alarms |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
        "| F1 | C1 | 50 | 49 | 1 | 0 | 0 |",
        "| L3 |  | 50 |  | 2 |  | 50 |",
    ]
    assert section(text, "Baseline on the real log") == [
        "| Rule | Criterion | Rule only | Criterion only | Both |",
        "| --- | --- | ---: | ---: | ---: |",
        "| B2 | C2 | 0 | 169 | 566 |",
    ]


def data_log(tmp_path: Path) -> Path:
    """A log with the items of the command line tests and enough items to inject every kind,
    in a directory of its own, so the report can go next to it."""
    (tmp_path / "data").mkdir()
    specs = [
        (
            item.id,
            item.category,
            [(e.activity, e.timestamp.isoformat(), e.net_worth) for e in item.events],
        )
        for item in injectable()
    ]
    return write_log(tmp_path / "data" / "log.xes", [*ITEMS, *specs])


def run(log: Path, output: Path) -> subprocess.CompletedProcess[str]:
    # No PYTHONPATH: the command must work as the README writes it, from the installed package.
    return subprocess.run(
        [sys.executable, "-m", "matchbook", "report", str(log), str(output)],
        capture_output=True,
        text=True,
        check=False,
        cwd=log.parent,
    )


@pytest.mark.criterion("C18", "C19")
def test_c18_c19_command_writes_the_report_of_a_small_log(tmp_path: Path) -> None:
    log = data_log(tmp_path)
    output = tmp_path / "report.md"
    result = run(log, output)
    assert result.returncode == 0, result.stderr
    text = output.read_text(encoding="utf-8")
    assert "| C1 | HOLD | 1 | 120.50 |" in text
    assert "- C1: fix, decided by 4500000001_00010 at 120.50 EUR, low." in text
    assert "| F1 | C1 | 50 | 50 | 0 | 0 | 0 |" in section(text, "Injected log, seed 1")


@pytest.mark.criterion("C10")
def test_c10_report_inside_the_log_directory_is_refused(tmp_path: Path) -> None:
    log = write_log(tmp_path / "log.xes", ITEMS)
    before = sorted(p.name for p in tmp_path.iterdir())
    result = run(log, tmp_path / "sub" / "report.md")
    assert result.returncode == 2
    assert "inside the directory of the log" in result.stderr
    assert sorted(p.name for p in tmp_path.iterdir()) == before


@pytest.mark.criterion("C9")
def test_c9_two_runs_write_the_same_report(tmp_path: Path) -> None:
    log = data_log(tmp_path)
    first, second = tmp_path / "first.md", tmp_path / "second.md"
    assert run(log, first).returncode == 0
    assert run(log, second).returncode == 0
    assert first.read_bytes() == second.read_bytes()
