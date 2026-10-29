"""Adaptador para conversaciones exportadas de Intercom.

SUPUESTO A VERIFICAR (semana 1): la forma sigue el objeto Conversation de la
API REST de Intercom:

  {"conversations": [{
     "id": "123", "created_at": 1730000000,
     "source": {"body": "<p>...</p>", "author": {"type": "user", "id": "u1"}},
     "contacts": {"contacts": [{"id": "u1"}]},
     "conversation_rating": {"rating": 4} | null,
     "tags": {"tags": [{"name": "facturación"}]},
     "conversation_parts": {"conversation_parts": [
        {"part_type": "comment", "body": "...", "author": {"type": "bot"}, "created_at": 1730000060}
     ]}
  }]}

Mapeo de autor: user/lead/contact -> customer · bot -> ai (Fin) · admin -> human.
Cuando tengamos una cuenta de prueba, ajustar aquí cualquier campo que difiera.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..model import Conversation, Message
from ..textutil import strip_html
from ..timeutil import parse_ts

_AUTHOR_MAP = {"user": "customer", "lead": "customer", "contact": "customer",
               "bot": "ai", "admin": "human", "team": "human"}


def _author(part: dict) -> str | None:
    t = (part.get("author") or {}).get("type")
    return _AUTHOR_MAP.get(t)


def from_dict(d: dict) -> Conversation:
    msgs: list[Message] = []
    src = d.get("source") or {}
    if src.get("body"):
        a = _author(src) or "customer"
        msgs.append(Message(author=a, text=strip_html(src["body"]), at=parse_ts(d["created_at"])))
    parts = ((d.get("conversation_parts") or {}).get("conversation_parts")) or []
    for p in parts:
        body = p.get("body")
        a = _author(p)
        if not body or a is None:
            continue  # asignaciones, cierres y demás eventos sin texto
        msgs.append(Message(author=a, text=strip_html(body), at=parse_ts(p["created_at"])))
    msgs.sort(key=lambda m: m.at)

    contacts = ((d.get("contacts") or {}).get("contacts")) or []
    customer_id = str(contacts[0]["id"]) if contacts else str((src.get("author") or {}).get("id", ""))
    rating = (d.get("conversation_rating") or {}).get("rating")
    tags = ((d.get("tags") or {}).get("tags")) or []

    return Conversation(
        id=str(d["id"]),
        customer_id=customer_id,
        created_at=parse_ts(d["created_at"]),
        messages=msgs,
        channel=src.get("delivered_as", "chat") or "chat",
        csat=int(rating) if rating is not None else None,
        topic=tags[0]["name"] if tags else None,
        source="intercom",
    )


def load(path: str | Path) -> list[Conversation]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = data["conversations"] if isinstance(data, dict) else data
    return [from_dict(d) for d in items]
