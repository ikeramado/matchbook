import tomllib

import pytest
from test_readme import README

ROOT = README.parent
WORKFLOW = ROOT / ".github" / "workflows" / "check.yml"
ACTIONS = "https://github.com/ikeramado/matchbook/actions/workflows/check.yml"


@pytest.mark.criterion("C26")
def test_the_license_is_mit_naming_the_author_and_pyproject_declares_it() -> None:
    text = (ROOT / "LICENSE").read_text()
    assert text.startswith("MIT License\n")
    assert "Copyright (c) 2026 Iker Amado" in text
    assert "Permission is hereby granted, free of charge" in text
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    assert project["license"] == "MIT"
    assert project["license-files"] == ["LICENSE"]


@pytest.mark.criterion("C27")
def test_the_workflow_runs_the_python_gates_on_push_and_pull_request() -> None:
    lines = [line.strip() for line in WORKFLOW.read_text().splitlines()]
    on = lines.index("on:")
    assert lines[on + 1 : on + 3] == ["push:", "pull_request:"]
    for gate in ["ruff format --check .", "ruff check .", "mypy", "pytest"]:
        assert f"- run: uv run {gate}" in lines


@pytest.mark.criterion("C27")
def test_the_readme_shows_the_workflow_badge() -> None:
    assert f"[![check]({ACTIONS}/badge.svg)]({ACTIONS})" in README.read_text()
