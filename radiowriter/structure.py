"""La struttura che Radiopaedia raccomanda per ogni tipo di articolo.

Radiopaedia non ha una struttura, ne ha ventitre. La sua pagina "standard
article structure" da' l'ordine fisso delle sezioni - Terminology,
Epidemiology, Clinical presentation, Pathology, Radiographic features,
Treatment and prognosis, History and etymology, Differential diagnosis - e poi
dice che vale "in most instances, except for the following specific special
purpose articles", e ne elenca diciotto. Un articolo di anatomia vuole `Gross
anatomy` e `Variant anatomy` e non ha nessun motivo di sentirsi chiedere
`Epidemiology`.

Sono tutte in `data/article-structure.json`: 327 titoli, ognuno col livello a
cui sta e il titolo sotto cui sta, gli 84 modi in cui quei titoli si trovano
scritti negli articoli veri (`etiology`, `plain film`, `CT scan`), e quali
ognuno dei tipi di articolo e' tenuto ad avere. Sono raccomandazioni LORO, non
nostre, trascritte il 2026-08-04: quando cambiano le loro, questa e' una
trascrizione vecchia finche' qualcuno non la rifa'.

Due cose vanno dette chiare, perche' sembrano dettagli e non lo sono:

- Il genitore fa parte dell'identita' di un titolo. `Complications` sotto
  `Clinical presentation` sono le complicanze della malattia; sotto `Treatment
  and prognosis` sono quelle della terapia. Due righe del canone, e un articolo
  puo' volerle tutt'e due.
- Una modalita' basta. Sotto `Radiographic features` non servono tutte, ne
  serve una.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import regex

CANON_FILE = Path(__file__).with_name("data") / "article-structure.json"

# I caratteri invisibili che si trovano dentro i titoli veri, e i marcatori di
# grassetto: nessuno dei due fa parte del nome.
HEADING_NOISE = regex.compile(r"[​‌‍﻿*_`]+")
MD_HEADING = regex.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


class StructureError(RuntimeError):
    pass


@dataclass(frozen=True)
class Row:
    """Una riga del canone: un titolo, il livello a cui sta, sotto cosa sta."""
    entry: str          # "Pathology/Genetics", che e' l'identita' completa
    title: str          # "Genetics"
    level: int          # 1, 2 o 3
    parent: str | None
    order: int          # dove sta nel canone, che e' quello che decide dove va
    required: bool = False


@dataclass
class Canon:
    canons: dict[str, list[dict]]
    index: dict[str, dict[str, list[dict]]]
    profiles: dict[str, dict]
    synonyms: dict[str, str]
    rules: list[tuple[str, object]]
    not_pathology_only: frozenset[str]
    disease_veto: object
    anatomy_types: list[tuple[str, object]]
    by_article_type: dict[str, str]
    fallback: str
    modality_entry: str
    modality_title: str
    transcribed: str


def normalise(text) -> str:
    """Un titolo ridotto a come si confronta."""
    out = HEADING_NOISE.sub("", str(text or ""))
    out = " ".join(out.split()).strip(": ").strip()
    return out.lower()


@lru_cache(maxsize=1)
def canon() -> Canon:
    if not CANON_FILE.exists():
        raise StructureError(
            f"Manca {CANON_FILE.name}: la struttura degli articoli non si puo' leggere.")
    raw = json.loads(CANON_FILE.read_text(encoding="utf-8"))

    index: dict[str, dict[str, list[dict]]] = {}
    for name, rows in (raw.get("canons") or {}).items():
        by_text: dict[str, list[dict]] = {}
        for row in rows:
            by_text.setdefault(normalise(row["t"]), []).append(row)
        index[name] = by_text

    return Canon(
        canons=raw.get("canons") or {},
        index=index,
        profiles=raw.get("profiles") or {},
        synonyms=raw.get("synonyms") or {},
        rules=[(p, regex.compile(r, regex.I)) for p, r in (raw.get("rules") or [])],
        not_pathology_only=frozenset(raw.get("notPathologyOnly") or ()),
        disease_veto=regex.compile(raw.get("diseaseVeto") or "(?!)", regex.I),
        anatomy_types=[(p, regex.compile(r, regex.I)) for p, r in (raw.get("anatomyTypes") or [])],
        by_article_type=raw.get("byArticleType") or {},
        fallback=raw.get("fallbackProfile") or "disease",
        modality_entry=raw.get("modalityEntry") or "",
        modality_title=raw.get("modalityTitle") or "",
        transcribed=raw.get("transcribed") or "",
    )


def profile_labels() -> dict[str, str]:
    """Nome interno -> etichetta da mostrare, nell'ordine del file."""
    return {name: (spec.get("label") or name) for name, spec in canon().profiles.items()}


def guess_profile(title: str) -> str:
    """Che tipo di articolo e', dal titolo.

    Lo userscript ha una scorciatoia che qui non c'e': `article_type`, che
    arriva dentro la risposta del linter ed e' la classificazione che
    Radiopaedia da' del proprio articolo. Su una bozza quell'articolo non
    esiste ancora, quindi resta l'elenco ordinato di regole sul titolo, primo
    che becca vince: un mnemonic prima di una malattia, perche' "Tuberous
    sclerosis mnemonic" e' un mnemonic; una classificazione prima di una
    misura, perche' "Bern score" e' una classificazione.

    Sbaglia, ed e' fatto apposta: il menu nell'interfaccia e' la risposta a
    quello."""
    c = canon()
    text = " ".join(str(title or "").split())
    if not text:
        return c.fallback
    for profile, pattern in c.rules:
        if not pattern.search(text):
            continue
        # Tre regole sono trattenute da un titolo che nomina una malattia:
        # "Iodinated contrast induced thyrotoxicosis" non e' un mezzo di
        # contrasto, e' la tireotossicosi che ne viene.
        if profile in c.not_pathology_only and c.disease_veto.search(text):
            continue
        if profile == "anatomy":
            for kind, anatomy in c.anatomy_types:
                if anatomy.search(text):
                    return kind
        return profile

    # Nessuna regola sul titolo dice "anatomia": nello userscript quel dato
    # arriva da `article_type`, che qui non c'e' perche' l'articolo non e'
    # ancora pubblicato. Restano le stesse espressioni che laggiu' scelgono
    # FRA i tipi di anatomia, usate qui anche per decidere SE lo e' - trattenute
    # da un titolo che nomina una malattia, altrimenti "median nerve injury"
    # diventerebbe un articolo di anatomia sul nervo mediano.
    if not c.disease_veto.search(text):
        for kind, anatomy in c.anatomy_types:
            if anatomy.search(text):
                return kind
    return c.fallback


def canonical(title: str, canon_name: str) -> str | None:
    """Il titolo del canone che questo titolo scritto a mano vuol dire, se c'e'."""
    c = canon()
    key = normalise(title)
    by_text = c.index.get(canon_name) or c.index.get("standard") or {}
    if key in by_text:
        return by_text[key][0]["t"]
    target = c.synonyms.get(key)
    if target and normalise(target) in by_text:
        return target
    return None


def rows_for(profile_name: str) -> list[Row]:
    """Tutte le righe del canone di un tipo di articolo, in ordine, con
    segnato quali sono obbligatorie."""
    c = canon()
    spec = c.profiles.get(profile_name) or c.profiles.get(c.fallback) or {}
    required = set(spec.get("required") or ())
    rows = c.canons.get(spec.get("canon") or "standard") or []
    return [
        Row(entry=row["v"], title=row["t"], level=row["l"], parent=row.get("p"),
            order=i, required=row["v"] in required or row["t"] in required)
        for i, row in enumerate(rows)
    ]


# ---------------------------------------------------------------------------
# i titoli che la bozza ha gia'
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Heading:
    line: int           # riga del markdown, da 1
    level: int          # 1, 2 o 3, come il canone li conta
    title: str
    parent: str | None


def headings_in(body_md: str) -> list[Heading]:
    """I titoli di una bozza, ognuno con il titolo sotto cui sta."""
    out: list[Heading] = []
    stack: list[tuple[int, str]] = []
    for n, line in enumerate(str(body_md or "").splitlines(), start=1):
        m = MD_HEADING.match(line)
        if not m:
            continue
        level, title = len(m.group(1)), " ".join(m.group(2).split())
        if not title:
            continue
        while stack and stack[-1][0] >= level:
            stack.pop()
        parent = stack[-1][1] if stack else None
        stack.append((level, title))
        out.append(Heading(line=n, level=level, title=title, parent=parent))
    return out


def present_entries(body_md: str, canon_name: str) -> dict[str, Heading]:
    """Quali righe del canone la bozza ha gia', per identita' completa.

    Il genitore fa parte dell'identita', quindi un `Complications` sotto
    `Pathology` non conta come il `Complications` sotto `Treatment and
    prognosis`: sono due righe diverse e un articolo puo' volerle tutt'e due."""
    found: dict[str, Heading] = {}
    for heading in headings_in(body_md):
        title = canonical(heading.title, canon_name)
        if not title:
            continue
        parent = canonical(heading.parent, canon_name) if heading.parent else None
        entry = f"{parent}/{title}" if parent else title
        found.setdefault(entry, heading)
        # Un titolo di primo livello e' anche se stesso senza genitore: il
        # canone scrive `Radiographic features` e non `qualcosa/Radiographic
        # features`.
        if heading.level == 1:
            found.setdefault(title, heading)
    return found


# ---------------------------------------------------------------------------
# metterceli
# ---------------------------------------------------------------------------

# Quello che va sotto un titolo appena messo. `content pending` e' la parola di
# Radiopaedia per una sezione che c'e' ed e' vuota, e il linter ha una regola
# che le ritrova - quindi mettercelo non e' sporcare la bozza, e' lasciarsi un
# promemoria che una macchina sa rileggere.
PENDING = "content pending"


def _marker(row: Row) -> str:
    return "#" * min(row.level, 6) + " " + row.title


def _place(lines: list[str], row: Row, present: dict[str, Heading],
           canon_name: str) -> int:
    """Su quale riga va messo, come indice da 0.

    Il canone e' un ordine, quindi la risposta e': sopra la prima sezione che
    il canone mette DOPO questa e che la bozza ha davvero. Quella regola sola
    piazza anche i sottotitoli, ed e' per questo che e' una regola e non due -
    il canone li alterna, quindi la prima riga dopo `Epidemiology/Risk factors`
    che la bozza ha puo' benissimo essere `Clinical presentation`, e andare
    sopra quella e' esattamente "in fondo a Epidemiology".

    Su una bozza le cui sezioni sono in disordine va sopra TUTTE quelle che
    precede, non sopra la prima che il canone nomina: sono due risposte diverse
    e la seconda sbaglia."""
    rows = canon().canons.get(canon_name) or []
    best: int | None = None
    for j in range(int(row.order) + 1, len(rows)):
        hit = present.get(rows[j]["v"])
        if hit is None:
            continue
        if best is None or hit.line < best:
            best = hit.line
    return (best - 1) if best is not None else len(lines)


def _insert(lines: list[str], at: int, row: Row, pending: bool) -> None:
    block = [_marker(row), ""]
    if pending:
        block += [PENDING, ""]
    if at >= len(lines):
        # in fondo: una riga vuota di stacco, ma non due
        while lines and not lines[-1].strip():
            lines.pop()
        if lines:
            lines.append("")
        lines.extend(block)
    else:
        lines[at:at] = block


def insert_rows(body_md: str, rows: list[Row], canon_name: str, *,
                pending: bool = False) -> tuple[str, list[str]]:
    """I titoli scelti, nell'ordine del canone, uno alla volta.

    Nell'ordine del canone perche' si piazzano a vicenda: `Epidemiology/Risk
    factors` va in fondo a `Epidemiology`, e su una bozza che non ha ne' l'uno
    ne' l'altro l'unico modo perche' sia vero e' che `Epidemiology` sia entrato
    prima. E uno alla volta perche' ogni inserimento cambia la risposta a "cosa
    ha questa bozza", quindi si rilegge fra uno e l'altro."""
    lines = str(body_md or "").splitlines()
    added: list[str] = []
    for row in sorted(rows, key=lambda r: r.order):
        present = present_entries("\n".join(lines), canon_name)
        if row.entry in present:
            continue                      # e' entrato come genitore di un altro
        _insert(lines, _place(lines, row, present, canon_name), row, pending)
        added.append(row.title)
    return "\n".join(lines), added


@dataclass
class Placement:
    """Dove finirebbe un titolo, e se il posto chiesto e' quello giusto."""
    line: int                   # la riga chiesta, da 1
    canon_line: int             # dove lo metterebbe la struttura, da 1
    inside: str | None          # in che sezione cade la riga chiesta
    conflict: str | None        # cosa non torna, se non torna


def check_one(body_md: str, row: Row, at_line: int, canon_name: str) -> Placement:
    """Un titolo, dove dice l'utente - e cosa fare se non e' dove va.

    E' l'unico dei tre modi che puo' andare storto, e la gerarchia e' come:
    `Microscopic appearance` lasciato cadere in mezzo a `Radiographic features`
    e' il sottotitolo della cosa sbagliata, e sembra tale e quale a uno finito
    al posto giusto. Quindi la riga chiesta si confronta con la sezione in cui
    cade davvero, e dove le due non vanno d'accordo si dice. Non si rifiuta:
    chi lo intende puo' comunque dire "qui"."""
    lines = str(body_md or "").splitlines()
    at_line = max(1, min(int(at_line or 1), len(lines) + 1))
    present = present_entries(body_md, canon_name)
    canon_line = _place(lines, row, present, canon_name) + 1

    # In che sezione cade la riga chiesta: il titolo di primo livello piu'
    # vicino sopra di essa.
    inside = None
    for heading in headings_in(body_md):
        if heading.line >= at_line:
            break
        if heading.level == 1:
            inside = heading.title

    conflict = None
    if row.parent:
        under = canonical(inside, canon_name) if inside else None
        if under != row.parent:
            where = f'dentro "{inside}"' if inside else "sopra ogni sezione"
            conflict = (f'"{row.title}" va sotto "{row.parent}", '
                        f"e la riga {at_line} e' {where}.")
    return Placement(line=at_line, canon_line=canon_line, inside=inside, conflict=conflict)


def insert_at(body_md: str, row: Row, at_line: int, *, pending: bool = False) -> str:
    """Un titolo, sulla riga chiesta, senza discutere."""
    lines = str(body_md or "").splitlines()
    at = max(0, min(int(at_line or 1) - 1, len(lines)))
    _insert(lines, at, row, pending)
    return "\n".join(lines)
