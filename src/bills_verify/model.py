"""Modelo común: conversaciones, líneas de facturación y hallazgos.

Todos los adaptadores (Intercom, Zendesk, formato común) convierten sus datos
a estas clases. Las reglas solo trabajan sobre este modelo.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Literal, Optional

Author = Literal["customer", "ai", "human"]


@dataclass
class Message:
    author: Author
    text: str
    at: datetime


@dataclass
class Conversation:
    id: str
    customer_id: str
    created_at: datetime
    messages: list[Message] = field(default_factory=list)
    channel: str = "chat"
    csat: Optional[int] = None  # 1-5; None si no hay valoración
    topic: Optional[str] = None  # etiqueta o tema, si el proveedor lo da
    source: str = "common"

    @property
    def ended_at(self) -> datetime:
        return self.messages[-1].at if self.messages else self.created_at

    def first_customer_text(self) -> str:
        for m in self.messages:
            if m.author == "customer" and m.text.strip():
                return m.text
        return ""

    def last_message(self) -> Optional[Message]:
        return self.messages[-1] if self.messages else None


@dataclass
class BillingLine:
    conversation_id: str
    outcome_type: str  # p. ej. "resolution", "procedure_handoff", "verified"
    billed_at: datetime
    amount: float
    currency: str = "USD"


@dataclass
class Finding:
    conversation_id: str
    rule: str
    severity: Literal["alta", "media", "baja"]
    evidence: str
    amount: float
    currency: str

    def to_dict(self) -> dict:
        return asdict(self)
