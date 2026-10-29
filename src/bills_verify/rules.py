"""Reglas deterministas de verificación (v1).

Cada regla recibe el contexto ya indexado y devuelve hallazgos. No llaman a
ningún servicio externo: corren igual en CLI, navegador (Pyodide) y servidor.
La evaluación con LLM de respuestas no resolutivas irá en el plan de pago;
aquí hay una versión heurística.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Callable

from .model import BillingLine, Conversation, Finding
from .textutil import jaccard, keywords, normalize

# Tipos de resultado que afirman que la IA resolvió el caso por sí sola.
RESOLUTION_TYPES = {"resolution", "assumed_resolution", "confirmed_resolution", "verified", "automated_resolution"}


@dataclass
class Config:
    recontact_days: int = 7
    recontact_similarity: float = 0.25
    negative_csat_max: int = 2
    min_customer_chars: int = 3
    test_markers: tuple[str, ...] = ("test", "prueba", "testing", "asdf", "hola test")
    evasive_patterns: tuple[str, ...] = (
        r"\bno (lo )?se\b", r"no tengo (esa )?informacion", r"no puedo ayudarte",
        r"contacta(r)? con (el )?(equipo|soporte|atencion)", r"ponte en contacto",
        r"i (do not|don't) know", r"i'?m not sure", r"i can'?t help",
        r"contact (our )?support", r"reach out to",
    )


@dataclass
class Context:
    conversations: dict[str, Conversation]
    by_customer: dict[str, list[Conversation]]
    billing: dict[str, list[BillingLine]]
    cfg: Config = field(default_factory=Config)

    @classmethod
    def build(cls, convs: list[Conversation], lines: list[BillingLine], cfg: Config | None = None) -> "Context":
        by_id = {c.id: c for c in convs}
        by_customer: dict[str, list[Conversation]] = {}
        for c in convs:
            by_customer.setdefault(c.customer_id, []).append(c)
        for lst in by_customer.values():
            lst.sort(key=lambda c: c.created_at)
        billing: dict[str, list[BillingLine]] = {}
        for b in lines:
            billing.setdefault(b.conversation_id, []).append(b)
        return cls(by_id, by_customer, billing, cfg or Config())

    def billed_resolutions(self):
        """(conversación, primera línea de tipo resolución) para cada conversación facturada que existe."""
        for cid, lines in self.billing.items():
            conv = self.conversations.get(cid)
            if conv is None:
                continue
            res = [b for b in lines if b.outcome_type in RESOLUTION_TYPES]
            if res:
                yield conv, res[0]


def _f(line: BillingLine, rule: str, severity: str, evidence: str, amount: float | None = None) -> Finding:
    return Finding(line.conversation_id, rule, severity, evidence,
                   line.amount if amount is None else amount, line.currency)


def rule_duplicado(ctx: Context) -> list[Finding]:
    out = []
    for cid, lines in ctx.billing.items():
        if len(lines) > 1:
            extra = sum(b.amount for b in lines[1:])
            out.append(_f(lines[0], "duplicado", "alta",
                          f"{len(lines)} resultados facturados en la misma conversación", extra))
    return out


def rule_sin_conversacion(ctx: Context) -> list[Finding]:
    return [
        _f(lines[0], "sin_conversacion", "baja",
           "Facturada pero no aparece en la exportación: no se puede verificar",
           sum(b.amount for b in lines))
        for cid, lines in ctx.billing.items() if cid not in ctx.conversations
    ]


def rule_recontacto(ctx: Context) -> list[Finding]:
    out = []
    window = timedelta(days=ctx.cfg.recontact_days)
    for conv, line in ctx.billed_resolutions():
        base_kw = keywords(conv.first_customer_text())
        for other in ctx.by_customer.get(conv.customer_id, []):
            if other.id == conv.id or not conv.ended_at < other.created_at <= conv.ended_at + window:
                continue
            same_topic = conv.topic is not None and conv.topic == other.topic
            sim = jaccard(base_kw, keywords(other.first_customer_text()))
            if same_topic or sim >= ctx.cfg.recontact_similarity:
                hours = (other.created_at - conv.ended_at).total_seconds() / 3600
                why = "mismo tema" if same_topic else f"similitud {sim:.2f}"
                out.append(_f(line, "recontacto", "alta",
                              f"El cliente volvió a escribir {hours:.0f} h después (conversación {other.id}, {why})"))
                break
    return out


def rule_escalado_posterior(ctx: Context) -> list[Finding]:
    out = []
    for conv, line in ctx.billed_resolutions():
        seen_ai = False
        for m in conv.messages:
            if m.author == "ai":
                seen_ai = True
            elif m.author == "human" and seen_ai:
                out.append(_f(line, "escalado_posterior", "alta",
                              "Una persona intervino después de la IA en una conversación facturada como resuelta"))
                break
    return out


def rule_silencio_negativo(ctx: Context) -> list[Finding]:
    out = []
    for conv, line in ctx.billed_resolutions():
        last = conv.last_message()
        if last and last.author == "ai" and conv.csat is not None and conv.csat <= ctx.cfg.negative_csat_max:
            out.append(_f(line, "silencio_negativo", "alta",
                          f"Resolución por silencio con valoración negativa (CSAT {conv.csat})"))
    return out


def rule_respuesta_no_resolutiva(ctx: Context) -> list[Finding]:
    out = []
    patterns = [re.compile(p) for p in ctx.cfg.evasive_patterns]
    for conv, line in ctx.billed_resolutions():
        last = conv.last_message()
        if not last or last.author != "ai":
            continue
        text = last.text.strip()
        if text.endswith("?"):
            out.append(_f(line, "respuesta_no_resolutiva", "media",
                          f"La última respuesta de la IA es una pregunta: «{text[-80:]}»"))
            continue
        norm = normalize(text)
        if any(p.search(norm) for p in patterns):
            out.append(_f(line, "respuesta_no_resolutiva", "media",
                          f"La última respuesta de la IA no resuelve: «{text[:80]}»"))
    return out


def rule_ruido(ctx: Context) -> list[Finding]:
    out = []
    for conv, line in ctx.billed_resolutions():
        texts = [m.text.strip() for m in conv.messages if m.author == "customer" and m.text.strip()]
        joined = normalize(" ".join(texts))
        if not texts:
            why = "El cliente no escribió nada"
        elif len(joined) < ctx.cfg.min_customer_chars:
            why = f"Mensaje del cliente demasiado corto: «{joined}»"
        elif joined in ctx.cfg.test_markers or joined.startswith("test "):
            why = f"Parece una conversación de prueba: «{joined[:40]}»"
        else:
            continue
        out.append(_f(line, "ruido", "media", why))
    return out


RULES: dict[str, Callable[[Context], list[Finding]]] = {
    "duplicado": rule_duplicado,
    "recontacto": rule_recontacto,
    "escalado_posterior": rule_escalado_posterior,
    "silencio_negativo": rule_silencio_negativo,
    "respuesta_no_resolutiva": rule_respuesta_no_resolutiva,
    "ruido": rule_ruido,
    "sin_conversacion": rule_sin_conversacion,
}

RULE_LABELS = {
    "duplicado": "Duplicado",
    "recontacto": "Recontacto",
    "escalado_posterior": "Escalado posterior",
    "silencio_negativo": "Silencio con señal negativa",
    "respuesta_no_resolutiva": "Respuesta no resolutiva",
    "ruido": "Ruido o prueba",
    "sin_conversacion": "Sin conversación en la exportación",
}
