# bills-verify

Verificador independiente de facturas por resultado de IA en soporte (Intercom Fin, Zendesk).

Tu proveedor cobra cada "resolución" de su IA y además decide qué cuenta como resolución.
`bills-verify` revisa tu exportación de conversaciones contra lo facturado y te dice qué
importe es discutible y por qué. **Todo se procesa en tu equipo: ningún dato sale de él.**

## Uso rápido

```bash
pip install -e .
bills-verify demo --out demo        # datos sintéticos + informe de ejemplo
bills-verify verify --source intercom \
  --conversations conversaciones.json \
  --billing facturacion.csv \
  --out informe.html --json hallazgos.json
```

Zendesk: indica qué `author_id` corresponden al agente de IA:

```bash
bills-verify verify --source zendesk --conversations tickets.jsonl \
  --billing facturacion.csv --zendesk-ai-authors 123,456
```

En CI, `--fail-above 5` devuelve código 1 si más del 5 % de lo facturado es discutible.

## Reglas (v1, deterministas)

| Regla | Qué marca |
| --- | --- |
| `duplicado` | Más de un resultado facturado en la misma conversación (solo cuenta lo que sobra) |
| `recontacto` | El cliente vuelve a escribir sobre el mismo tema en los 7 días siguientes |
| `escalado_posterior` | Una persona interviene después de la IA en una conversación facturada como resuelta |
| `silencio_negativo` | Resolución asumida por silencio con CSAT ≤ 2 |
| `respuesta_no_resolutiva` | La última respuesta de la IA es una pregunta o una evasiva |
| `ruido` | Conversaciones vacías, de prueba o con mensajes de 1-2 caracteres |
| `sin_conversacion` | Facturada pero ausente de la exportación (no verificable; no suma como discutible) |

El importe discutible no cuenta dos veces una conversación que dispara varias reglas.

## Formatos de entrada

- **Facturación** (CSV): `conversation_id, outcome_type, billed_at, amount, currency`.
- **Intercom**: objeto Conversation de la API REST (`source`, `conversation_parts`, `contacts`, `conversation_rating`, `tags`).
- **Zendesk**: tickets con comentarios embebidos, en JSON o JSON Lines.
- **Común**: JSON propio documentado en `src/bills_verify/adapters/common.py`.

> **Pendiente de verificar con cuentas reales:** los campos exactos de las exportaciones de
> Intercom y Zendesk y sus ficheros de uso facturado. Los adaptadores marcan cada supuesto.

## Desarrollo

```bash
pip install -e ".[dev]"
pytest
```

Sin dependencias en tiempo de ejecución, para que el mismo motor corra en el navegador con Pyodide.

## Aviso

El informe es información técnica basada en reglas automáticas. No es asesoramiento legal
ni garantiza ningún reembolso. No afiliado a Intercom ni a Zendesk.
