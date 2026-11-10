import re
import subprocess
from pathlib import Path

import pytest
from test_readme import README

SECTIONS = [
    "Development",
    "The check",
    "Template",
    "Git hooks",
    "How it is built",
    "Sessions and state",
    "Merge tiers",
]
VERSION = re.compile(r"\bv[0-9]+\.[0-9]+\.[0-9]+\b")

pytestmark = pytest.mark.criterion("C25")


def headings(path: Path) -> list[str]:
    """The text of each Markdown heading in the file, without the leading #s."""
    return [
        line.lstrip("#").strip() for line in path.read_text().splitlines() if line.startswith("#")
    ]


def named(heading: str, section: str) -> bool:
    """Whether the heading is the section's, allowing a trailing note such as (`src/`)."""
    return heading == section or heading.startswith(section + " (")


def test_the_readme_has_no_workflow_section_and_no_link_to_one() -> None:
    found = [h for h in headings(README) for s in SECTIONS if named(h, s)]
    assert found == []
    assert "/workflow.md" not in README.read_text()


def test_every_status_line_in_the_readme_names_the_latest_tag() -> None:
    tags = subprocess.run(
        ["git", "tag", "--sort=-v:refname"],
        cwd=README.parent,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    if not tags:
        pytest.skip("no tags in this clone")
    lines = README.read_text().splitlines()
    status = [i for i, line in enumerate(lines) if "**Status:**" in line]
    for i in status:
        # A status line may wrap: read it up to the end of its blockquote or paragraph.
        end = next(
            (j for j in range(i + 1, len(lines)) if not lines[j].startswith(">")), len(lines)
        )
        text = " ".join(lines[i:end])
        assert VERSION.findall(text) == [tags[0]], text
