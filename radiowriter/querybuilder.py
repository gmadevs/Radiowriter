"""Una ricerca fatta di piu' concetti, invece che di una riga sola.

Una ricerca seria non e' una stringa: e' due o tre CONCETTI - la malattia, la
modalita', il tipo di studio - ognuno scritto in tutti i modi in cui gli autori
lo scrivono, e messi in AND fra loro. Dentro un concetto i sinonimi vanno in
OR, fra un concetto e l'altro si va in AND. E' il modo in cui le costruiscono
gli information specialist, ed e' anche l'unico che rende le parentesi
prevedibili: ogni blocco ne ha un paio, e non ci sono altri livelli.

    Blocco 1:  "Joubert syndrome"[tiab] OR "molar tooth sign"[tiab]
    Blocco 2:  MRI[tiab] OR "magnetic resonance"[tiab]
    ------------------------------------------------------------
    ("Joubert syndrome"[tiab] OR "molar tooth sign"[tiab]) AND (MRI[tiab] OR ...)

PubMed valuta gli operatori da sinistra a destra, senza dare all'AND
precedenza sull'OR: e' esattamente l'ordine in cui i blocchi si leggono qui,
quindi quello che si vede e' quello che PubMed fa.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# chiave -> (etichetta nella UI, tag PubMed)
FIELDS: dict[str, tuple[str, str]] = {
    "all": ("All fields", ""),
    "tiab": ("Title/Abstract", "[tiab]"),
    "ti": ("Title", "[ti]"),
    "tw": ("Text word", "[tw]"),
    "mh": ("MeSH terms", "[mh]"),
    "majr": ("MeSH major topic", "[majr]"),
    "mh_noexp": ("MeSH, no explosion", "[mh:noexp]"),
    "sh": ("MeSH subheading", "[sh]"),
    "pt": ("Publication type", "[pt]"),
    "au": ("Author", "[au]"),
    "ta": ("Journal", "[ta]"),
    "raw": ("Already written in PubMed syntax", ""),
}

FIELD_LABELS = {key: label for key, (label, _) in FIELDS.items()}

OPERATORS = ("AND", "OR", "NOT")

# Un termine gia' scritto in sintassi PubMed: ha un tag di campo, oppure un
# operatore booleano scritto in maiuscolo fra due parole. In tutti e due i casi
# non e' una parola da etichettare, e' un pezzo di query da lasciare stare.
TAGGED = re.compile(r"\[[A-Za-z][A-Za-z0-9 :/,._-]*\]")
BOOLEAN = re.compile(r"(?<!\S)(AND|OR|NOT)(?!\S)")


@dataclass
class Term:
    """Un modo di scrivere una cosa. `field` e' una chiave di FIELDS."""
    text: str = ""
    field: str = "tiab"


@dataclass
class Block:
    """Un concetto: i suoi sinonimi, e come si lega al concetto precedente."""
    label: str = ""
    terms: list[Term] = field(default_factory=list)
    inner: str = "OR"     # come si uniscono i termini qui dentro
    join: str = "AND"     # come questo blocco si unisce al precedente
    enabled: bool = True


def is_wrapped(text: str) -> bool:
    """Vero se TUTTA la stringa sta dentro un'unica coppia di parentesi.

    Non basta guardare il primo e l'ultimo carattere: `(A) OR (B)` comincia con
    una parentesi e finisce con una parentesi, ma le due non sono la stessa, e
    trattarlo come gia' racchiuso lascerebbe l'OR libero di mangiarsi il primo
    filtro che gli viene messo accanto in AND.
    """
    text = text.strip()
    if not (text.startswith("(") and text.endswith(")")):
        return False
    depth = 0
    for i, ch in enumerate(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i == len(text) - 1
    return False


def _atomic(text: str) -> bool:
    """Un pezzo che non ha bisogno di parentesi attorno: nessun booleano fuori
    da una coppia di parentesi sua."""
    if is_wrapped(text):
        return True
    depth = 0
    for m in re.finditer(r"[()]|(?<!\S)(?:AND|OR|NOT)(?!\S)", text):
        token = m.group(0)
        if token == "(":
            depth += 1
        elif token == ")":
            depth -= 1
        elif depth == 0:
            return False
    return True


def _needs_quotes(text: str) -> bool:
    if not re.search(r"\s", text):
        return False
    if text.startswith('"') and text.endswith('"'):
        return False
    return True


def render_term(text: str, field_key: str = "tiab") -> str:
    """Un termine come lo scrive PubMed.

    Quello che l'utente ha gia' etichettato ([tiab], [Mesh]...) o ha gia'
    composto con AND/OR non si tocca: si presume che sappia quello che scrive,
    e appiccicargli un altro tag lo romperebbe. Si aggiungono solo le
    parentesi, se dentro c'e' un booleano.
    """
    text = " ".join((text or "").split())
    if not text:
        return ""
    if TAGGED.search(text) or BOOLEAN.search(text) or field_key == "raw":
        return text if _atomic(text) else f"({text})"
    suffix = FIELDS.get(field_key, FIELDS["all"])[1]
    if not suffix:
        return text if _atomic(text) else f"({text})"
    body = f'"{text}"' if _needs_quotes(text) else text
    return f"{body}{suffix}"


def render_block(block: Block) -> str:
    """Un blocco come pezzo di query, parentesi comprese. '' se e' vuoto."""
    parts = [render_term(t.text, t.field) for t in block.terms]
    parts = [p for p in parts if p]
    if not parts:
        return ""
    inner = block.inner if block.inner in OPERATORS else "OR"
    joined = f" {inner} ".join(parts)
    return joined if len(parts) == 1 and _atomic(joined) else f"({joined})"


def compose(blocks: list[Block]) -> str:
    """La query intera. I blocchi spenti o vuoti non ci sono."""
    out = ""
    for block in blocks:
        if not block.enabled:
            continue
        chunk = render_block(block)
        if not chunk:
            continue
        if not out:
            out = chunk
            continue
        join = block.join if block.join in OPERATORS else "AND"
        out = f"{out} {join} {chunk}"
    return out


def problems(blocks: list[Block]) -> list[str]:
    """Quello che non va, detto in inglese come il resto della UI.

    Non e' una validazione della sintassi PubMed - quella la fa PubMed, e la
    fa meglio - sono i due o tre sbagli che si fanno davvero e che PubMed non
    segnala perche' per lui sono query legittime che vogliono dire un'altra
    cosa.
    """
    msgs: list[str] = []
    live = [b for b in blocks if b.enabled and render_block(b)]
    if not live:
        return ["No terms yet — write at least one."]

    first = next(b for b in blocks if b.enabled and render_block(b))
    if first.join == "NOT":
        msgs.append("The first block cannot start with NOT: it is the thing "
                    "you are looking for, and its operator is ignored.")

    for n, block in enumerate(live, 1):
        for term in block.terms:
            text = (term.text or "").strip()
            if not text:
                continue
            if text.count('"') % 2:
                msgs.append(f'Block {n}: unbalanced quotation mark in “{text}”.')
            if text.count("(") != text.count(")"):
                msgs.append(f"Block {n}: unbalanced brackets in “{text}”.")
    return msgs
