"""Adaptador para tickets exportados de Zendesk (JSON con comentarios).

SUPUESTO A VERIFICAR (semana 1): cada ticket sigue el objeto Ticket de la API
de Zendesk con sus comentarios embebidos (el export CSV no los incluye):

  {"tickets": [{
     "id": 42, "requester_id": 1001, "created_at": "2026-10-01T10:00:00Z",
     "tags": ["facturacion"], "via": {"channel": "web"},
     "satisfaction_rating": {"score": "good" | "bad" | "offered" | "unoffered"},
     "comments": [{"author_id": 1001, "plain_body": "...", "created_at": "..."}]
  }]}

También acepta JSON Lines (un ticket por línea), que es el formato del export
completo de Zendesk.

Cómo se distingue al agente de IA de un agente humano en los comentarios está
por confirmar. Mientras tanto se pasan los author_id del agente de IA
(ai_author_ids); cualquier otro autor distinto del solicitante cuenta como humano.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from ..model import Conversation, Message
from ..textutil import strip_html
from ..timeutil import parse_ts

_CSAT = {"good": 5, "bad": 1}


def from_dict(d: dict, ai_author_ids: Iterable[str] = ()) -> Conversation:
    ai_ids = {str(x) for x in ai_author_ids}
    requester = str(d.get("requester_id", ""))
    msgs: list[Message] = []
    for c in d.get("comments", []) or []:
        author_id = str(c.get("author_id", ""))
        if author_id == requester:
            author = "customer"
        elif author_id in ai_ids:
            author = "ai"
        else:
            author = "human"
        text = c.get("plain_body") or strip_html(c.get("html_body") or c.get("body") or "")
        msgs.append(Message(author=author, text=text, at=parse_ts(c["created_at"])))
    msgs.sort(key=lambda m: m.at)
    score = (d.get("satisfaction_rating") or {}).get("score")
    tags = d.get("tags") or []
    return Conversation(
        id=str(d["id"]),
        customer_id=requester,
        created_at=parse_ts(d["created_at"]),
        messages=msgs,
        channel=((d.get("via") or {}).get("channel")) or "web",
        csat=_CSAT.get(score),
        topic=tags[0] if tags else None,
        source="zendesk",
    )


def _iter_tickets(path: Path):
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return
    if raw[0] == "[" or raw.startswith('{"tickets"'):
        data = json.loads(raw)
        yield from (data["tickets"] if isinstance(data, dict) else data)
    else:  # JSON Lines
        for line in raw.splitlines():
            if line.strip():
                yield json.loads(line)


def load(path: str | Path, ai_author_ids: Iterable[str] = ()) -> list[Conversation]:
    return [from_dict(d, ai_author_ids) for d in _iter_tickets(Path(path))]
