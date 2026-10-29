from __future__ import annotations

import html
import re
import unicodedata

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_WORD = re.compile(r"[a-z0-9]+")

# Palabras vacías mínimas (es/en) para comparar temas sin ruido.
_STOP = set("""
a al algo como con de del el en es esta este hay la las lo los me mi mis no o para pero por que
se si sin su sus te tengo un una uno y ya yo hola gracias buenos dias tardes favor
the a an and are as at be but by for from have hi hello i in is it my of on or please thanks
that the this to was with you your can help need
""".split())


def strip_html(s: str) -> str:
    return _WS.sub(" ", html.unescape(_TAG.sub(" ", s or ""))).strip()


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def keywords(s: str) -> set[str]:
    return {w for w in _WORD.findall(normalize(s)) if len(w) > 2 and w not in _STOP}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)
