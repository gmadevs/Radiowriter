"""I termini cercati, evidenziati nei titoli e negli abstract.

Chi legge cento abstract per decidere quali tenere non li legge tutti per
intero: cerca dove compare quello che ha chiesto. Evidenziarlo gli dice in un
colpo d'occhio se un lavoro ne parla davvero o lo nomina di passaggio.

I termini si ricavano dalla stessa stringa che si scrive nella ricerca, in
sintassi PubMed, togliendo tutto quello che non e' testo da cercare: i tag di
campo (`[tiab]`, `[MeSH Terms]`), gli operatori, e cio' che sta dopo un NOT -
evidenziare quello che si e' chiesto di escludere direbbe il contrario.

E' un aiuto a leggere, non una ricostruzione di cosa ha trovato PubMed:
PubMed espande i termini (i sinonimi MeSH, l'automatic term mapping), e un
abstract puo' essere stato trovato per una parola che qui non si accende.
"""

from __future__ import annotations

import html
import re

FIELD_TAG = re.compile(r"\[[^\]]*\]")
# dopo un NOT: un gruppo tra parentesi (un livello), una frase tra virgolette,
# o una parola sola
AFTER_NOT = re.compile(r'\bNOT\s+(?:\([^()]*\)|"[^"]*"|\S+)')
PHRASE = re.compile(r'"([^"]+)"')
WORD = re.compile(r"[\w][\w'*-]*")
OPERATORS = {"AND", "OR", "NOT"}


def terms_of(query: str) -> list[str]:
    """Le parole e le frasi da evidenziare, nell'ordine in cui compaiono.

    Un asterisco finale resta: vuol dire "tutto quello che comincia cosi'",
    come in PubMed. Le parole di una lettera sola non contano."""
    query = FIELD_TAG.sub(" ", query or "")
    query = AFTER_NOT.sub(" ", query)
    found: list[str] = []
    for phrase in PHRASE.findall(query):
        found.append(" ".join(phrase.split()))
    for word in WORD.findall(PHRASE.sub(" ", query)):
        if word in OPERATORS or len(word.rstrip("*")) < 2:
            continue
        found.append(word)
    seen: set[str] = set()
    out = []
    for term in found:
        key = term.lower()
        if term and key not in seen:
            seen.add(key)
            out.append(term)
    return out


def pattern(terms: list[str]) -> re.Pattern | None:
    """Una regex sola per tutti i termini, le frasi prima delle parole.

    Il plurale inglese regolare si accende da solo - "abscess" prende anche
    "abscesses" - e dentro una frase uno spazio vale anche un trattino:
    "contrast enhanced" e "contrast-enhanced" sono la stessa cosa scritta da
    due autori diversi."""
    parts = []
    for term in sorted(terms, key=len, reverse=True):
        prefix = term.endswith("*")
        words = term.rstrip("*").split()
        body = r"[\s-]+".join(re.escape(w) for w in words)
        tail = r"\w*" if prefix else r"(?:e?s)?\b"
        parts.append(rf"\b{body}{tail}")
    if not parts:
        return None
    return re.compile("(" + "|".join(parts) + ")", re.IGNORECASE)


def mark(text: str, rx: re.Pattern | None) -> str:
    """Il testo escapato per l'HTML, con i termini dentro `<mark>`.

    Si spezza il testo sulle corrispondenze PRIMA di escaparlo: cercare dopo
    vorrebbe dire cercare anche dentro `&amp;` e `&lt;`."""
    if rx is None:
        return html.escape(text)
    pieces = rx.split(text)
    # con un gruppo nella regex, split alterna: testo, corrispondenza, testo...
    return "".join(f"<mark>{html.escape(p)}</mark>" if i % 2 else html.escape(p)
                   for i, p in enumerate(pieces))
