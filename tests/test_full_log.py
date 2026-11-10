import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

LOG = os.environ.get("MATCHBOOK_LOG")


@pytest.mark.criterion("C8")
@pytest.mark.skipif(not LOG, reason="set MATCHBOOK_LOG to the full log to run this test")
def test_the_full_log_is_processed_in_under_ten_minutes() -> None:
    assert LOG is not None
    start = time.monotonic()
    result = subprocess.run(
        [sys.executable, "-m", "matchbook", str(Path(LOG).expanduser())],
        capture_output=True,
        text=True,
        check=True,
        timeout=600,
    )
    elapsed = time.monotonic() - start
    flagged = len(result.stdout.splitlines())
    print(f"full log: {elapsed:.0f} s, {flagged} items flagged")
    assert elapsed < 600
