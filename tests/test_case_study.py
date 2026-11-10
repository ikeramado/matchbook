import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from test_readme import README, section

from matchbook.xes import read_items

LOG = os.environ.get("MATCHBOOK_LOG")
HEADING = "## Case study"
PARTS = ["**Situation.**", "**What I did.**", "**Result.**", "**What this means for you.**"]
UPWORK = "[Upwork profile](https://www.upwork.com/freelancers/~018a26d02cfcd93639)"
CODE = re.compile(r"\b[CFL][0-9]+\b")


def text(lines: list[str]) -> str:
    """The lines joined into one string, each run of whitespace as one space."""
    return " ".join(" ".join(lines).split())


def table(report: list[str], heading: str) -> list[list[str]]:
    """The body rows of the first table after the report's ## heading, as cells."""
    start = report.index(heading)
    first = next(i for i in range(start, len(report)) if report[i].startswith("|"))
    rows = []
    for line in report[first + 2 :]:
        if not line.startswith("|"):
            break
        rows.append([cell.strip() for cell in line.strip("|").split("|")])
    return rows


def number(cell: str) -> float:
    return float(cell.replace(",", "")) if cell else 0.0


@pytest.fixture(scope="module")
def report(tmp_path_factory: pytest.TempPathFactory) -> list[str]:
    assert LOG is not None
    out = tmp_path_factory.mktemp("report") / "report.md"
    subprocess.run(
        [sys.executable, "-m", "matchbook", "report", str(Path(LOG).expanduser()), str(out)],
        capture_output=True,
        check=True,
        timeout=600,
    )
    return out.read_text().splitlines()


@pytest.mark.criterion("C22")
def test_c22_the_first_section_is_the_case_study_in_four_parts_ending_with_upwork() -> None:
    lines = section()
    assert lines[0] == HEADING
    body = text(lines)
    places = [body.find(part) for part in PARTS]
    assert -1 not in places, places
    assert places == sorted(places)
    assert body.rstrip().endswith(UPWORK)


@pytest.mark.criterion("C22")
@pytest.mark.skipif(not LOG, reason="set MATCHBOOK_LOG to the full log to run this test")
def test_c22_the_case_study_numbers_are_those_of_a_run_of_the_report(report: list[str]) -> None:
    assert LOG is not None
    body = text(section())
    items = sum(1 for _ in read_items(Path(LOG).expanduser()))
    severity = {row[0]: row for row in table(report, "## Findings by severity")}
    findings = sum(int(number(row[1])) for row in severity.values())
    euros = sum(number(row[2]) for row in severity.values())
    injected = table(report, "## Injected log, seed 1")
    faults = [row for row in injected if row[0].startswith("F")]
    lookalikes = [row for row in injected if row[0].startswith("L")]
    planted = sum(int(number(row[2])) for row in faults)
    detected = sum(int(number(row[3])) for row in faults)
    alarms = sum(int(number(row[4])) for row in injected)
    baseline_detected = sum(int(number(row[5])) for row in faults)
    baseline_alarms = sum(int(number(row[6])) for row in injected)

    assert f"across its {items:,} order lines" in body
    assert f"{findings:,} exceptions worth {euros / 1e6:.1f} M EUR" in body
    assert f"{int(number(severity['high'][1])):,} of them high severity" in body
    planted_lookalikes = sum(int(number(row[2])) for row in lookalikes)
    assert f"planted {planted} known errors and {planted_lookalikes} legitimate" in body
    assert (detected, alarms) == (planted, 0)
    assert f"All {planted} planted errors caught with no false alarms" in body
    assert f"missed {planted - baseline_detected} and raised {baseline_alarms} false alarms" in body


@pytest.mark.criterion("C23")
def test_c23_the_first_section_names_no_code() -> None:
    assert CODE.findall(text(section())) == []


@pytest.mark.criterion("C23")
def test_c23_every_code_in_the_readme_has_its_name_in_the_table_of_codes() -> None:
    lines = README.read_text().splitlines()
    start = lines.index("| Code | Name |")
    names = {}
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        code, name = (cell.strip() for cell in line.strip("|").split("|"))
        names[code] = name
    assert all(names.values())
    assert set(CODE.findall("\n".join(lines))) <= set(names)


@pytest.mark.criterion("C24")
def test_c24_limitations_states_the_three_points() -> None:
    body = text(section("## Limitations"))
    assert "public data from 2018" in body
    assert "an amount to review, not a confirmed loss" in body
    assert "each check catches its kind, not how many real faults the log holds" in body
