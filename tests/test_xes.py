from datetime import UTC, datetime
from pathlib import Path
from xml.sax.saxutils import quoteattr

import pytest

from matchbook.xes import Event, Item, read_items

EventSpec = tuple[str, str, float]
ItemSpec = tuple[str, str, list[EventSpec]]


def write_log(path: Path, items: list[ItemSpec]) -> Path:
    """Write a small XES log shaped like the BPI Challenge 2019 file."""
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?><log xes.version="1849.2016">',
        '<global scope="event"><string key="concept:name" value="UNKNOWN"></string></global>',
        '<string key="concept:name" value="test log"></string>',
    ]
    for item_id, category, events in items:
        parts.append(
            f'<trace><string key="Item Category" value={quoteattr(category)}></string>'
            f'<string key="concept:name" value={quoteattr(item_id)}></string>'
        )
        for activity, timestamp, net_worth in events:
            parts.append(
                f'<event><string key="concept:name" value={quoteattr(activity)}></string>'
                f'<float key="Cumulative net worth (EUR)" value="{net_worth}"></float>'
                f'<date key="time:timestamp" value="{timestamp}"></date></event>'
            )
        parts.append("</trace>")
    parts.append("</log>")
    path.write_text("".join(parts), encoding="utf-8")
    return path


def test_reader_yields_every_item_with_its_events_in_log_order(tmp_path: Path) -> None:
    log = write_log(
        tmp_path / "log.xes",
        [
            (
                "4500000001_00010",
                "3-way match, invoice after GR",
                [
                    ("Create Purchase Order Item", "2018-01-02T13:53:00.000Z", 298.0),
                    ("Record Goods Receipt", "2018-03-06T06:44:00.000Z", 298.0),
                ],
            ),
            ("4500000002_00010", "Consignment & more", []),
        ],
    )
    assert list(read_items(log)) == [
        Item(
            id="4500000001_00010",
            category="3-way match, invoice after GR",
            events=(
                Event(
                    "Create Purchase Order Item", datetime(2018, 1, 2, 13, 53, tzinfo=UTC), 298.0
                ),
                Event("Record Goods Receipt", datetime(2018, 3, 6, 6, 44, tzinfo=UTC), 298.0),
            ),
        ),
        Item(id="4500000002_00010", category="Consignment & more", events=()),
    ]


def test_reader_reads_whole_traces_from_a_log_larger_than_one_parse_chunk(tmp_path: Path) -> None:
    # A small log is parsed in one go, so a trace already looks complete at its start tag.
    # A log of a few megabytes makes the reader prove it waits for each trace's end tag.
    events: list[EventSpec] = [("Record Goods Receipt", "2018-01-10T10:00:00.000Z", 1.0)] * 5
    log = write_log(tmp_path / "log.xes", [(f"A_{i}", "2-way match", events) for i in range(2000)])
    items = list(read_items(log))
    assert [item.id for item in items] == [f"A_{i}" for i in range(2000)]
    assert all(len(item.events) == 5 for item in items)


def test_reader_names_the_item_when_an_event_lacks_an_attribute(tmp_path: Path) -> None:
    log = tmp_path / "log.xes"
    log.write_text(
        '<log><trace><string key="concept:name" value="A_1"></string>'
        '<string key="Item Category" value="2-way match"></string>'
        '<event><string key="concept:name" value="Clear Invoice"></string></event>'
        "</trace></log>",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="item A_1: missing attribute 'time:timestamp'"):
        list(read_items(log))
