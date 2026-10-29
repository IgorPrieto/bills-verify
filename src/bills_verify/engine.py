"""Ejecuta las reglas y calcula los totales del informe."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .model import BillingLine, Conversation, Finding
from .rules import RULES, Config, Context

UNVERIFIABLE = {"sin_conversacion"}


@dataclass
class Result:
    findings: list[Finding]
    billed_conversations: int
    billed_lines: int
    billed_amount: float
    disputable_conversations: int
    disputable_amount: float
    unverifiable_amount: float
    currency: str
    by_rule: dict[str, int] = field(default_factory=dict)

    @property
    def disputable_share(self) -> float:
        return self.disputable_amount / self.billed_amount if self.billed_amount else 0.0

    def to_dict(self) -> dict:
        return {
            "billed_conversations": self.billed_conversations,
            "billed_lines": self.billed_lines,
            "billed_amount": round(self.billed_amount, 2),
            "disputable_conversations": self.disputable_conversations,
            "disputable_amount": round(self.disputable_amount, 2),
            "disputable_share": round(self.disputable_share, 4),
            "unverifiable_amount": round(self.unverifiable_amount, 2),
            "currency": self.currency,
            "by_rule": self.by_rule,
            "findings": [f.to_dict() for f in self.findings],
        }


def run(convs: list[Conversation], lines: list[BillingLine], cfg: Config | None = None,
        rules: list[str] | None = None) -> Result:
    ctx = Context.build(convs, lines, cfg)
    selected = rules or list(RULES)
    findings: list[Finding] = []
    for name in selected:
        findings.extend(RULES[name](ctx))

    currencies = Counter(b.currency for b in lines)
    currency = currencies.most_common(1)[0][0] if currencies else "USD"

    # Importe discutible sin doble conteo: si una conversación tiene algún hallazgo
    # distinto de "duplicado", es discutible todo lo facturado en ella; si solo es
    # duplicado, solo lo que sobra.
    per_conv: dict[str, set[str]] = defaultdict(set)
    for f in findings:
        per_conv[f.conversation_id].add(f.rule)
    disputable = 0.0
    unverifiable = 0.0
    disputable_convs = 0
    for cid, rules_hit in per_conv.items():
        conv_lines = ctx.billing.get(cid, [])
        total = sum(b.amount for b in conv_lines)
        if rules_hit & UNVERIFIABLE:
            unverifiable += total
            continue
        disputable_convs += 1
        if rules_hit - {"duplicado"}:
            disputable += total
        else:
            disputable += sum(b.amount for b in conv_lines[1:])

    findings.sort(key=lambda f: ({"alta": 0, "media": 1, "baja": 2}[f.severity], f.conversation_id, f.rule))
    return Result(
        findings=findings,
        billed_conversations=len(ctx.billing),
        billed_lines=len(lines),
        billed_amount=sum(b.amount for b in lines),
        disputable_conversations=disputable_convs,
        disputable_amount=disputable,
        unverifiable_amount=unverifiable,
        currency=currency,
        by_rule=dict(Counter(f.rule for f in findings)),
    )
