"""Una bozza che esce dal programma e una che ci rientra.

Il database e' un file su questo computer, e va benissimo finche' il computer
e' questo. Quello che manca a una bozza tenuta solo li' e' un modo per
portarsela dietro, mandarla a qualcuno, tenersene una copia prima di riscrivere
mezza sezione, o ritrovarla fra due anni quando questo programma non ci sara'
piu'.

Si scrivono due file, e sono due cose diverse:

    .json   la bozza intera: testo, tipo di articolo, bibliografia con le note,
            e le citazioni gia' risolte. E' questo che l'import rilegge, e
            torna dentro esattamente com'e' uscito.

    .md     da leggere. Il markdown della bozza con davanti quello che serve a
            capire cos'e', e la bibliografia in fondo. Si apre con qualunque
            cosa, anche fra dieci anni.

L'import legge SOLO il json, ed e' apposta: il markdown non ha dentro ne' il
tipo di articolo ne' le note della bibliografia ne' le citazioni risolte, quindi
rileggerlo perderebbe tutte e tre le cose senza dirlo. Perdere qualcosa in
silenzio e' l'unica cosa che una copia di sicurezza non deve fare mai.

Un file che arriva da fuori e' un dato, non un'istruzione: si legge, se ne
controlla la forma, e quello che ne esce finisce in una bozza NUOVA. Non
sovrascrive mai quella aperta.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from radiowriter import db
from radiowriter import radiopaedia as rp

FORMAT = "radiopaedia-draft"
VERSION = 1
MAX_BYTES = 8 * 1024 * 1024        # un articolo; piu' grande di cosi' non lo e'
MAX_REFS = 500


class DraftIOError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# fuori
# ---------------------------------------------------------------------------

def bundle(draft_id: int) -> dict:
    """Tutto quello che serve per rimettere in piedi una bozza altrove."""
    draft = db.get_draft(draft_id)
    if draft is None:
        raise DraftIOError("Questa bozza non esiste piu'.")

    refs = [{"identifier": r["identifier"], "note": r["note"] or ""}
            for r in db.draft_ref_rows(draft_id)]
    # Le citazioni gia' risolte viaggiano con la bozza: chi la riapre altrove
    # non deve richiederle una per una a radiopaedia.work, e una bozza aperta
    # senza rete resta leggibile.
    citations = db.cached_citations([r["identifier"] for r in refs])

    return {
        "format": FORMAT,
        "version": VERSION,
        "exported": _now(),
        "title": draft["title"],
        "body_md": draft["body_md"] or "",
        "top_heading": draft["top_heading"] or rp.TOP_HEADING,
        "profile": draft["profile"],
        "created_at": str(draft["created_at"] or ""),
        "updated_at": str(draft["updated_at"] or ""),
        "references": refs,
        "citations": {k: {kk: vv for kk, vv in v.items() if kk != "fetched_at"}
                      for k, v in citations.items()},
    }


def to_json(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


def to_markdown(data: dict) -> str:
    """La meta' da leggere. Intestazione, testo, bibliografia numerata."""
    numbers = rp.numbering(data["body_md"], data.get("citations") or {})
    lines = rp.reference_lines(numbers, data.get("citations") or {})

    head = [
        f"# {data['title']}",
        "",
        f"> Bozza Radiopaedia · esportata il {data['exported']}"
        + (f" · tipo: {data['profile']}" if data.get("profile") else ""),
        ">",
        # Le parentesi dicono che il pezzo unico e' voluto: in una lista di
        # stringhe, due righe accostate senza virgola sono indistinguibili da
        # una virgola dimenticata.
        ("> Questa copia e' da leggere. Il `.json` accanto e' quello da"
         " reimportare: ha dentro il tipo di articolo, le note della"
         " bibliografia e le citazioni gia' risolte, che qui non ci sono."),
        "",
        "---",
        "",
    ]
    body = [data["body_md"].rstrip(), ""]
    tail = ["", "## References", ""] + [f"{line}" for line in lines] if lines else []
    return "\n".join(head + body + tail).rstrip() + "\n"


def filename(data: dict, suffix: str) -> str:
    stem = "".join(c if c.isalnum() or c in "-_" else "-" for c in data["title"]).strip("-")
    return f"{(stem or 'draft')[:60]}-{data['exported'][:10]}{suffix}"


# ---------------------------------------------------------------------------
# dentro
# ---------------------------------------------------------------------------

def read_bundle(raw: bytes | str) -> dict:
    """Il file, controllato. Solleva se non e' una bozza di questo programma."""
    if isinstance(raw, bytes):
        if len(raw) > MAX_BYTES:
            raise DraftIOError("Il file e' troppo grande per essere una bozza.")
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DraftIOError("Il file non e' testo UTF-8.") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DraftIOError(
            "Non e' un JSON valido. L'import vuole il file .json, non il .md accanto."
        ) from exc

    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise DraftIOError(
            "Non e' una bozza esportata da questo programma. "
            "L'import vuole il file .json, non il .md accanto.")
    if not isinstance(data.get("body_md"), str):
        raise DraftIOError("La bozza non ha un testo dentro.")

    refs = []
    for item in (data.get("references") or [])[:MAX_REFS]:
        if isinstance(item, str):
            ident = rp.normalise_identifier(item)
            note = ""
        elif isinstance(item, dict):
            ident = rp.normalise_identifier(item.get("identifier", ""))
            note = str(item.get("note") or "")
        else:
            continue
        if ident:
            refs.append({"identifier": ident, "note": note})

    citations = {}
    for ident, rec in (data.get("citations") or {}).items():
        if isinstance(rec, dict) and isinstance(ident, str):
            citations[ident] = rec

    top = data.get("top_heading")
    return {
        "title": " ".join(str(data.get("title") or "Untitled article").split())[:200],
        "body_md": data["body_md"],
        "top_heading": int(top) if isinstance(top, int) and 1 <= top <= 6 else rp.TOP_HEADING,
        "profile": data.get("profile") if isinstance(data.get("profile"), str) else None,
        "exported": str(data.get("exported") or ""),
        "references": refs,
        "citations": citations,
    }


def create_from(data: dict, *, title: str | None = None) -> int:
    """La bozza letta, messa in archivio come bozza NUOVA.

    Nuova sempre: sovrascrivere quella aperta sarebbe la cosa piu' facile da
    fare per sbaglio e la piu' difficile da disfare."""
    draft_id = db.create_draft(
        title or data["title"],
        body_md=data["body_md"],
        top_heading=data["top_heading"],
        profile=data["profile"],
    )
    for ref in data["references"]:
        db.add_draft_refs(draft_id, [ref["identifier"]], note=ref["note"] or "imported")

    # Le citazioni che il file si portava dietro: si mettono in cache solo se
    # non c'e' gia' una risposta nostra, che e' piu' recente per definizione.
    known = db.cached_citations([r["identifier"] for r in data["references"]])
    for ident, rec in data["citations"].items():
        if known.get(ident, {}).get("citation"):
            continue
        db.store_citation({"identifier": ident, "fetched_at": _now(),
                           **{k: rec.get(k) for k in
                              ("citation", "title", "journal", "year", "pmid", "doi", "error")}})
    return draft_id
