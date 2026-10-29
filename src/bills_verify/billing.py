"""Carga de líneas de facturación en formato común (CSV).

Columnas: conversation_id, outcome_type, billed_at, amount, currency

SUPUESTO A VERIFICAR (semana 1): Intercom y Zendesk exponen el detalle de uso
facturado en formatos propios; aquí se añadirán sus mapeos cuando conozcamos
los campos reales. Hasta entonces, el cliente (o el CLI) convierte a este CSV.
"""
from __future__ import annotations

import csv
from pathlib import Path

from .model import BillingLine
from .timeutil import parse_ts

REQUIRED = ("conversation_id", "outcome_type", "billed_at", "amount")


def load(path: str | Path) -> list[BillingLine]:
    with Path(path).open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"Faltan columnas en la facturación: {', '.join(missing)}")
        return [
            BillingLine(
                conversation_id=str(r["conversation_id"]).strip(),
                outcome_type=r["outcome_type"].strip(),
                billed_at=parse_ts(r["billed_at"]),
                amount=float(r["amount"]),
                currency=(r.get("currency") or "USD").strip() or "USD",
            )
            for r in reader
        ]
