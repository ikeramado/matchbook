import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

LOG = os.environ.get("MATCHBOOK_LOG")
README = Path(__file__).resolve().parents[1] / "README.md"
HEADING = "## The report on the full log"
ITEM = "4507032353_00020"

pytestmark = [
    pytest.mark.criterion("C20"),
    pytest.mark.skipif(not LOG, reason="set MATCHBOOK_LOG to the full log to run this test"),
]


def section(heading: str | None = None) -> list[str]:
    """The lines of the README's ## section with this heading, or its first, heading included."""
    lines = README.read_text().splitlines()
    start = next(
        i for i, line in enumerate(lines) if line.startswith("## ") and heading in (None, line)
    )
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return lines[start:end]


def copied_blocks(section: list[str]) -> list[list[str]]:
    """The runs of lines between <!-- from the report --> and <!-- end -->."""
    blocks: list[list[str]] = []
    block: list[str] | None = None
    for line in section:
        if line == "<!-- from the report -->":
            block = []
        elif line == "<!-- end -->" and block is not None:
            blocks.append(block)
            block = None
        elif block is not None:
            block.append(line)
    return blocks


def event_table(section: list[str]) -> list[list[str]]:
    """The rows of the table with the header Activity | Timestamp | EUR."""
    start = section.index("| Activity | Timestamp | EUR |")
    rows = []
    for line in section[start + 2 :]:
        if not line.startswith("|"):
            break
        rows.append([cell.strip() for cell in line.strip("|").split("|")])
    return rows


def run_matchbook(*args: str) -> str:
    assert LOG is not None
    return subprocess.run(
        [sys.executable, "-m", "matchbook", *args],
        capture_output=True,
        text=True,
        check=True,
        timeout=600,
    ).stdout


@pytest.fixture(scope="module")
def report(tmp_path_factory: pytest.TempPathFactory) -> list[str]:
    assert LOG is not None
    out = tmp_path_factory.mktemp("report") / "report.md"
    run_matchbook("report", str(Path(LOG).expanduser()), str(out))
    return out.read_text().splitlines()


@pytest.fixture(scope="module")
def finding() -> list[str]:
    """The fields of the C2 line of ITEM printed by python -m matchbook on the log."""
    assert LOG is not None
    lines = run_matchbook(str(Path(LOG).expanduser())).splitlines()
    return next(f for line in lines if (f := line.split("\t"))[:2] == [ITEM, "C2"])


def test_c20_the_readme_has_the_section_the_report_on_the_full_log() -> None:
    assert HEADING in README.read_text().splitlines()


def test_c20_each_copied_block_is_a_run_of_lines_of_the_report(report: list[str]) -> None:
    blocks = copied_blocks(section(HEADING))
    assert len(blocks) == 4
    for block in blocks:
        assert block, "empty block"
        starts = [i for i, line in enumerate(report) if line == block[0]]
        assert any(report[i : i + len(block)] == block for i in starts), block


def test_c20_the_told_finding_matches_its_line_of_matchbook(finding: list[str]) -> None:
    lines = section(HEADING)
    events = [
        list(re.fullmatch(r"(.+) (\S+) (\S+) EUR", event).groups())  # type: ignore[union-attr]
        for event in finding[4].split("; ")
    ]
    assert event_table(lines) == events
    told = f"`{ITEM}` breaks C2 with {float(finding[2]):,.2f} EUR at stake, severity {finding[3]}"
    assert told in " ".join(lines)
