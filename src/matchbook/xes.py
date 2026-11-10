"""Streaming reader of an XES event log: one purchase order item at a time."""

import xml.etree.ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ACTIVITY = "concept:name"
TIMESTAMP = "time:timestamp"
NET_WORTH = "Cumulative net worth (EUR)"
ITEM_ID = "concept:name"
# The XES file stores the key without the "(case) " prefix that CSV exports of the log add.
CATEGORY = "Item Category"


@dataclass(frozen=True)
class Event:
    activity: str
    timestamp: datetime
    net_worth: float


@dataclass(frozen=True)
class Item:
    id: str
    category: str
    events: tuple[Event, ...]


def _attributes(element: ET.Element) -> dict[str, str]:
    """The key and value of each attribute directly under an element."""
    return {
        child.attrib["key"]: child.attrib["value"]
        for child in element
        if child.tag != "event" and "key" in child.attrib
    }


def _require(attributes: dict[str, str], key: str, where: str) -> str:
    try:
        return attributes[key]
    except KeyError:
        raise ValueError(f"{where}: missing attribute {key!r}") from None


def _event(element: ET.Element, item_id: str) -> Event:
    attributes = _attributes(element)
    where = f"item {item_id}"
    return Event(
        activity=_require(attributes, ACTIVITY, where),
        timestamp=datetime.fromisoformat(_require(attributes, TIMESTAMP, where)),
        net_worth=float(_require(attributes, NET_WORTH, where)),
    )


def read_items(path: Path) -> Iterator[Item]:
    """Yield each item of the log in log order, with its events in log order.

    Each trace is cleared once read, so memory stays flat on the full log.
    """
    root: ET.Element | None = None
    for action, element in ET.iterparse(path, events=("start", "end")):
        if root is None:
            root = element
        if action != "end" or element.tag != "trace":
            continue
        attributes = _attributes(element)
        item_id = _require(attributes, ITEM_ID, "trace")
        yield Item(
            id=item_id,
            category=_require(attributes, CATEGORY, f"item {item_id}"),
            events=tuple(_event(child, item_id) for child in element.iter("event")),
        )
        root.clear()
