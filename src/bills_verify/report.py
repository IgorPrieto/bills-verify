"""Informe HTML autocontenido (sin dependencias ni recursos externos)."""
from __future__ import annotations

import html
from datetime import datetime, timezone

from . import __version__
from .engine import Result
from .rules import RULE_LABELS

_SYMBOL = {"USD": "$", "EUR": "€", "GBP": "£"}
_SEV = {"alta": "Alta", "media": "Media", "baja": "Baja"}


def money(x: float, cur: str) -> str:
    s = f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    sym = _SYMBOL.get(cur)
    return f"{s} {sym}" if sym else f"{s} {cur}"


def _e(s) -> str:
    return html.escape(str(s), quote=True)


CSS = """
:root{--bg:#fbfaf8;--panel:#fff;--ink:#1d1c1a;--muted:#6b6862;--line:#e6e3dd;--accent:#b4532a;--accent-soft:#f6e6dd;
--alta:#b42318;--media:#b54708;--baja:#6b6862;--bar:#d9d5cd}
@media (prefers-color-scheme:dark){:root{--bg:#161513;--panel:#1f1e1b;--ink:#f1efea;--muted:#a19d95;--line:#34322e;
--accent:#e08a5e;--accent-soft:#3a271d;--alta:#f97066;--media:#fdb022;--baja:#a19d95;--bar:#3d3a35}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.5 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:980px;margin:0 auto;padding:40px 16px 64px}
header{display:flex;justify-content:space-between;align-items:baseline;gap:16px;flex-wrap:wrap;border-bottom:1px solid var(--line);padding-bottom:16px}
.brand{font-weight:700;letter-spacing:-.01em}.meta{color:var(--muted);font-size:13px}
h1{font-size:28px;line-height:1.2;letter-spacing:-.02em;margin:32px 0 8px}
.lead{color:var(--muted);margin:0 0 28px;max-width:62ch}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:36px}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px}
.kpi .v{font-size:26px;font-weight:700;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.kpi .l{color:var(--muted);font-size:13px}
.kpi.hero{background:var(--accent-soft);border-color:var(--accent)}.kpi.hero .v{color:var(--accent)}
h2{font-size:18px;margin:36px 0 12px}
table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden}
th,td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);font-weight:600}
tr:last-child td{border-bottom:0}td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.bar{height:8px;border-radius:4px;background:var(--bar);min-width:2px}
.sev{font-size:12px;font-weight:600;white-space:nowrap}.sev.alta{color:var(--alta)}.sev.media{color:var(--media)}.sev.baja{color:var(--baja)}
code{font:13px ui-monospace,SFMono-Regular,Menlo,monospace}
.wrap{overflow-x:auto}
.cta{margin-top:36px;padding:20px;border:1px solid var(--accent);border-radius:10px;background:var(--accent-soft)}
.cta strong{display:block;margin-bottom:4px}
@media (max-width:640px){.barcol{display:none}}
footer{margin-top:40px;color:var(--muted);font-size:12.5px;border-top:1px solid var(--line);padding-top:16px}
"""


def render(result: Result, source: str = "", brand: str = "bills-verify",
           generated_at: datetime | None = None, max_rows: int = 500) -> str:
    cur = result.currency
    when = (generated_at or datetime.now(timezone.utc)).strftime("%d/%m/%Y %H:%M UTC")
    share = f"{result.disputable_share * 100:.1f}".replace(".", ",") + " %"

    # Resumen por regla: nº de conversaciones e importe (importe = líneas afectadas).
    rule_rows = []
    counts = result.by_rule
    top = max(counts.values()) if counts else 1
    amounts: dict[str, float] = {}
    for f in result.findings:
        amounts[f.rule] = amounts.get(f.rule, 0.0) + f.amount
    for rule, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        width = max(2, int(100 * n / top))
        rule_rows.append(
            f"<tr><td>{_e(RULE_LABELS.get(rule, rule))}</td>"
            f"<td class='barcol' style='width:38%'><div class='bar' style='width:{width}%'></div></td>"
            f"<td class='num'>{n}</td><td class='num'>{_e(money(amounts[rule], cur))}</td></tr>")

    finding_rows = []
    for f in result.findings[:max_rows]:
        finding_rows.append(
            f"<tr><td><code>{_e(f.conversation_id)}</code></td>"
            f"<td>{_e(RULE_LABELS.get(f.rule, f.rule))}</td>"
            f"<td><span class='sev {f.severity}'>{_SEV[f.severity]}</span></td>"
            f"<td>{_e(f.evidence)}</td><td class='num'>{_e(money(f.amount, cur))}</td></tr>")
    more = len(result.findings) - max_rows
    more_note = f"<p class='meta'>Y {more} hallazgos más en la exportación JSON.</p>" if more > 0 else ""

    unverifiable = ""
    if result.unverifiable_amount:
        unverifiable = (f"<div class='kpi'><div class='v'>{_e(money(result.unverifiable_amount, cur))}</div>"
                        f"<div class='l'>facturado sin conversación en la exportación</div></div>")

    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Informe de verificación</title><style>{CSS}</style></head>
<body><main>
<header><div class="brand">{_e(brand)}</div><div class="meta">Generado el {when}{' · ' + _e(source) if source else ''}</div></header>
<h1>{_e(money(result.disputable_amount, cur))} facturados son discutibles</h1>
<p class="lead">De {_e(money(result.billed_amount, cur))} facturados en {result.billed_conversations} conversaciones,
{result.disputable_conversations} tienen al menos una señal de que la resolución no fue real o se cobró de más.</p>
<section class="kpis">
<div class="kpi hero"><div class="v">{_e(share)}</div><div class="l">del importe facturado es discutible</div></div>
<div class="kpi"><div class="v">{_e(money(result.billed_amount, cur))}</div><div class="l">facturado en el periodo · {result.billed_lines} líneas</div></div>
<div class="kpi"><div class="v">{result.disputable_conversations}</div><div class="l">conversaciones discutibles</div></div>
{unverifiable}
</section>
<h2>Por regla</h2>
<div class="wrap"><table><thead><tr><th>Regla</th><th class='barcol'></th><th class="num">Conversaciones</th><th class="num">Importe</th></tr></thead>
<tbody>{''.join(rule_rows) or "<tr><td colspan='4'>Sin hallazgos.</td></tr>"}</tbody></table></div>
<h2>Hallazgos</h2>
<div class="wrap"><table><thead><tr><th>Conversación</th><th>Regla</th><th>Severidad</th><th>Evidencia</th><th class="num">Importe</th></tr></thead>
<tbody>{''.join(finding_rows) or "<tr><td colspan='5'>Sin hallazgos.</td></tr>"}</tbody></table></div>
{more_note}
<div class="cta"><strong>¿Quieres reclamarlo?</strong>El paquete de disputa añade la revisión con IA de cada respuesta y
genera un PDF y un JSON listos para enviar a tu proveedor.</div>
<footer>Procesado en tu equipo: ningún dato ha salido de él. Este informe es información técnica basada en reglas
automáticas; no es asesoramiento legal ni garantiza ningún reembolso. Versión {__version__}.</footer>
</main></body></html>"""
