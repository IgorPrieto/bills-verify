"""Generador de datos sintéticos con problemas plantados y verdad conocida.

Produce:
  - conversaciones con la forma de la API de Intercom (intercom.json)
  - facturación en formato común (billing.csv)
  - la verdad conocida: qué conversación tiene qué problema (truth.json)

Sirve para tests y para la demo del informe mientras no haya datos reales.
"""
from __future__ import annotations

import csv
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

PRICE = 0.99

TOPICS = {
    "facturacion": (
        ["No me ha llegado la factura de octubre", "Necesito descargar la factura del pedido",
         "La factura tiene mal el NIF de mi empresa"],
        "Puedes descargar todas tus facturas desde Ajustes > Facturación > Historial.",
    ),
    "envio": (
        ["Mi pedido no ha llegado todavía", "El paquete aparece como entregado pero no lo tengo",
         "Cuándo llega mi pedido del lunes"],
        "Tu pedido está en reparto y llegará mañana antes de las 14:00. Te he enviado el enlace de seguimiento.",
    ),
    "acceso": (
        ["No puedo entrar en mi cuenta", "He olvidado la contraseña de acceso",
         "Me dice que la contraseña es incorrecta"],
        "Te he enviado un enlace para restablecer la contraseña a tu correo. Caduca en 30 minutos.",
    ),
    "devolucion": (
        ["Quiero devolver unas zapatillas", "Cómo hago una devolución de un producto defectuoso",
         "Me ha llegado la talla equivocada y quiero cambiarla"],
        "He generado la etiqueta de devolución; la tienes en tu correo. El reembolso tarda 5 días.",
    ),
    "suscripcion": (
        ["Quiero cancelar mi suscripción", "Cómo cambio mi plan a anual",
         "Me habéis cobrado dos veces la suscripción"],
        "He actualizado tu plan; verás el cambio en la próxima renovación.",
    ),
}

CATEGORIES = [
    ("limpia", 0.58),
    ("recontacto", 0.08),
    ("escalado_posterior", 0.06),
    ("silencio_negativo", 0.06),
    ("pregunta_final", 0.05),
    ("evasiva", 0.04),
    ("ruido", 0.04),
    ("duplicado", 0.05),
    ("sin_conversacion", 0.04),
]


def _ts(dt: datetime) -> int:
    return int(dt.timestamp())


def _conv(cid: str, user: str, start: datetime, parts: list[tuple[str, str, int]],
          rating: int | None, topic: str | None) -> dict:
    """parts = [(author_type, body, segundos desde el inicio)]; el primero es el source."""
    first = parts[0]
    return {
        "id": cid,
        "created_at": _ts(start),
        "source": {"body": f"<p>{first[1]}</p>", "author": {"type": first[0], "id": user},
                   "delivered_as": "customer_initiated"},
        "contacts": {"contacts": [{"id": user}]},
        "conversation_rating": {"rating": rating} if rating is not None else None,
        "tags": {"tags": [{"name": topic}]} if topic else {"tags": []},
        "conversation_parts": {"conversation_parts": [
            {"part_type": "comment", "body": f"<p>{body}</p>", "author": {"type": a},
             "created_at": _ts(start + timedelta(seconds=s))}
            for a, body, s in parts[1:]
        ]},
    }


def generate(n: int = 200, seed: int = 7, start: datetime | None = None):
    rng = random.Random(seed)
    base = start or datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
    names = [c for c, _ in CATEGORIES]
    weights = [w for _, w in CATEGORIES]
    convs: list[dict] = []
    billing: list[dict] = []
    truth: dict[str, str] = {}

    for i in range(n):
        cat = rng.choices(names, weights)[0]
        cid = f"ic_{i:04d}"
        user = f"user_{i:04d}"  # un cliente por conversación: la limpia nunca da recontacto
        topic = rng.choice(list(TOPICS))
        asks, answer = TOPICS[topic]
        ask = rng.choice(asks)
        start = base + timedelta(hours=rng.randint(0, 24 * 20), minutes=rng.randint(0, 59))
        rating = rng.choice([None, None, 4, 5])
        parts = [("user", ask, 0), ("bot", answer, 40)]

        if cat == "recontacto":
            convs.append(_conv(cid, user, start, parts, None, topic))
            again = start + timedelta(hours=rng.randint(6, 120))
            follow = _conv(f"{cid}_r", user, again,
                           [("user", ask + " otra vez, sigue sin funcionar", 0), ("admin", "Lo reviso ahora mismo.", 300)],
                           None, topic)
            convs.append(follow)
            truth[f"{cid}_r"] = "seguimiento_no_facturado"
        elif cat == "escalado_posterior":
            parts += [("user", "Eso no me sirve, quiero hablar con una persona", 120),
                      ("admin", "Hola, soy Marta del equipo de soporte. Lo reviso.", 600)]
            convs.append(_conv(cid, user, start, parts, rating, topic))
        elif cat == "silencio_negativo":
            convs.append(_conv(cid, user, start, parts, rng.choice([1, 2]), topic))
        elif cat == "pregunta_final":
            parts[-1] = ("bot", "¿Podrías indicarme el número de pedido?", 40)
            convs.append(_conv(cid, user, start, parts, None, topic))
        elif cat == "evasiva":
            parts[-1] = ("bot", "Lo siento, no tengo información sobre eso. Contacta con el equipo de soporte.", 40)
            convs.append(_conv(cid, user, start, parts, None, topic))
        elif cat == "ruido":
            parts = [("user", rng.choice(["test", "prueba", "ok"]), 0), ("bot", "¡Hola! Estoy aquí para lo que necesites.", 20)]
            convs.append(_conv(cid, user, start, parts, None, None))
        elif cat == "sin_conversacion":
            pass  # se factura pero no se exporta
        else:  # limpia y duplicado
            convs.append(_conv(cid, user, start, parts, rating, topic))

        billed_at = start + timedelta(hours=24)
        billing.append({"conversation_id": cid, "outcome_type": "resolution",
                        "billed_at": billed_at.isoformat(), "amount": PRICE, "currency": "USD"})
        if cat == "duplicado":
            billing.append({"conversation_id": cid, "outcome_type": "resolution",
                            "billed_at": (billed_at + timedelta(minutes=5)).isoformat(),
                            "amount": PRICE, "currency": "USD"})
        truth[cid] = cat

    return {"conversations": convs}, billing, truth


EXPECTED_RULE = {
    "recontacto": "recontacto",
    "escalado_posterior": "escalado_posterior",
    "silencio_negativo": "silencio_negativo",
    "pregunta_final": "respuesta_no_resolutiva",
    "evasiva": "respuesta_no_resolutiva",
    "ruido": "ruido",
    "duplicado": "duplicado",
    "sin_conversacion": "sin_conversacion",
}


def write(outdir: str | Path, n: int = 200, seed: int = 7) -> dict[str, Path]:
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    convs, billing, truth = generate(n, seed)
    paths = {"conversations": out / "intercom.json", "billing": out / "billing.csv", "truth": out / "truth.json"}
    paths["conversations"].write_text(json.dumps(convs, ensure_ascii=False, indent=1), encoding="utf-8")
    with paths["billing"].open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["conversation_id", "outcome_type", "billed_at", "amount", "currency"])
        w.writeheader()
        w.writerows(billing)
    paths["truth"].write_text(json.dumps(truth, ensure_ascii=False, indent=1), encoding="utf-8")
    return paths
