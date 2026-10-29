"""Formato común (JSON propio del verificador).

{
  "conversations": [
    {"id": "c1", "customer_id": "u1", "created_at": "2026-10-01T10:00:00Z",
     "channel": "chat", "csat": 4, "topic": "facturación",
     "messages": [{"author": "customer|ai|human", "text": "...", "at": "..."}]}
  ]
}
"""
from __future__ import annotations

import json
from pathlib import Path

from ..model import Conversation, Message
from ..timeutil import parse_ts


def from_dict(d: dict, source: str = "common") -> Conversation:
    msgs = [Message(author=m["author"], text=m.get("text", ""), at=parse_ts(m["at"]))
            for m in d.get("messages", [])]
    msgs.sort(key=lambda m: m.at)
    return Conversation(
        id=str(d["id"]),
        customer_id=str(d.get("customer_id", "")),
        created_at=parse_ts(d["created_at"]),
        messages=msgs,
        channel=d.get("channel", "chat"),
        csat=d.get("csat"),
        topic=d.get("topic"),
        source=source,
    )


def load(path: str | Path) -> list[Conversation]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = data["conversations"] if isinstance(data, dict) else data
    return [from_dict(d) for d in items]
