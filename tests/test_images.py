import os
import subprocess
import sys
from pathlib import Path

import pytest
from test_readme import HEADING, section
from test_report import COMPARISONS, FOUND, SCORES

from matchbook.images import draw
from matchbook.report import render

LOG = os.environ.get("MATCHBOOK_LOG")
IMAGES = Path(__file__).resolve().parents[1] / "docs" / "images"
NAMES = ["controls.svg", "injected.svg", "baseline.svg"]

pytestmark = pytest.mark.criterion("C21")


def run_matchbook(*args: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "matchbook", *args], capture_output=True, check=True, timeout=600
    )


def test_c21_images_writes_the_three_files_and_the_same_bytes_twice(tmp_path: Path) -> None:
    report = tmp_path / "report.md"
    report.write_text(render(FOUND, SCORES, COMPARISONS, seed=1))
    run_matchbook("images", str(report), str(tmp_path / "one"))
    draw(report.read_text(), tmp_path / "two")
    for name in NAMES:
        one = (tmp_path / "one" / name).read_bytes()
        assert one.startswith(b"<?xml"), name
        assert one == (tmp_path / "two" / name).read_bytes(), name


def test_c21_the_report_section_shows_the_three_images() -> None:
    text = "\n".join(section(HEADING))
    for name in NAMES:
        assert f"](docs/images/{name})" in text, name


@pytest.mark.skipif(not LOG, reason="set MATCHBOOK_LOG to the full log to run this test")
def test_c21_the_committed_images_are_drawn_from_a_run_of_the_report(tmp_path: Path) -> None:
    assert LOG is not None
    report = tmp_path / "report.md"
    run_matchbook("report", str(Path(LOG).expanduser()), str(report))
    run_matchbook("images", str(report), str(tmp_path))
    for name in NAMES:
        assert (IMAGES / name).read_bytes() == (tmp_path / name).read_bytes(), name
