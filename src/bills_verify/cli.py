"""CLI sin dependencias externas.

  bills-verify verify --source intercom --conversations conv.json --billing billing.csv --out informe.html
  bills-verify demo --out demo/
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, billing, engine, report, synth
from .adapters import common, intercom, zendesk
from .rules import RULES, Config


def _load_conversations(args):
    if args.source == "intercom":
        return intercom.load(args.conversations)
    if args.source == "zendesk":
        ids = [x.strip() for x in (args.zendesk_ai_authors or "").split(",") if x.strip()]
        if not ids:
            print("Aviso: sin --zendesk-ai-authors, todos los agentes cuentan como humanos.", file=sys.stderr)
        return zendesk.load(args.conversations, ids)
    return common.load(args.conversations)


def cmd_verify(args) -> int:
    convs = _load_conversations(args)
    lines = billing.load(args.billing)
    cfg = Config(recontact_days=args.recontact_days)
    rules = args.rules.split(",") if args.rules else None
    if rules:
        unknown = [r for r in rules if r not in RULES]
        if unknown:
            print(f"Reglas desconocidas: {', '.join(unknown)}", file=sys.stderr)
            return 2
    result = engine.run(convs, lines, cfg, rules)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report.render(result, source=Path(args.conversations).name), encoding="utf-8")
    if args.json:
        Path(args.json).write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")

    pct = result.disputable_share * 100
    print(f"{len(convs)} conversaciones, {result.billed_lines} líneas facturadas.")
    print(f"Discutible: {report.money(result.disputable_amount, result.currency)} "
          f"({str(round(pct, 1)).replace(".", ",")} % de {report.money(result.billed_amount, result.currency)}) "
          f"en {result.disputable_conversations} conversaciones.")
    print(f"Informe: {out}")
    if args.fail_above is not None and pct > args.fail_above:
        return 1  # útil en CI / GitHub Action
    return 0


def cmd_demo(args) -> int:
    paths = synth.write(args.out, n=args.n, seed=args.seed)
    ns = argparse.Namespace(source="intercom", conversations=str(paths["conversations"]),
                            billing=str(paths["billing"]), out=str(Path(args.out) / "informe.html"),
                            json=str(Path(args.out) / "informe.json"), rules=None,
                            recontact_days=7, fail_above=None, zendesk_ai_authors=None)
    return cmd_verify(ns)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="bills-verify",
                                description="Verifica facturas por resultado de IA en soporte.")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("verify", help="Verifica una exportación contra su facturación")
    v.add_argument("--source", choices=["intercom", "zendesk", "common"], required=True)
    v.add_argument("--conversations", required=True, help="Exportación de conversaciones (JSON o JSONL)")
    v.add_argument("--billing", required=True, help="CSV de facturación en formato común")
    v.add_argument("--out", default="informe.html", help="Ruta del informe HTML")
    v.add_argument("--json", help="Ruta opcional para los hallazgos en JSON")
    v.add_argument("--rules", help=f"Reglas a ejecutar, separadas por comas ({', '.join(RULES)})")
    v.add_argument("--recontact-days", type=int, default=7)
    v.add_argument("--zendesk-ai-authors", help="author_id del agente de IA en Zendesk, separados por comas")
    v.add_argument("--fail-above", type=float, help="Sale con código 1 si el %% discutible lo supera")
    v.set_defaults(func=cmd_verify)

    d = sub.add_parser("demo", help="Genera datos sintéticos y su informe")
    d.add_argument("--out", default="demo")
    d.add_argument("--n", type=int, default=200)
    d.add_argument("--seed", type=int, default=7)
    d.set_defaults(func=cmd_demo)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
