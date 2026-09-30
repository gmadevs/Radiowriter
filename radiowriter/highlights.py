"""Le evidenziazioni di un PDF, una per riquadro, da spuntare man mano.

Si evidenzia dove si legge meglio - Anteprima, Acrobat, l'iPad - e le
annotazioni restano dentro il PDF come oggetti standard. Qui si leggono: il
testo sotto ogni evidenziazione, la pagina, il colore, la nota se c'e', e la
posizione, cosi' il lettore della finestra di studio ci puo' saltare sopra.

Le spunte "fatto" stanno nel database, non nel PDF: il file resta quello che
si e' scaricato, e riaprirlo con un altro programma non cambia niente.

Il PDF puo' cambiare dopo: si evidenzia ancora, si toglie un'evidenziazione
sbagliata. Ogni evidenziazione ha allora una chiave ricavata da pagina e
posizione, e rileggendo il file quelle che c'erano gia' tengono la loro spunta;
quelle sparite dal file spariscono anche dalla lista.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

# Evidenziatore, sottolineato, ondulato, barrato: i quattro modi di marcare
# del testo. Le note a margine e i disegni non hanno testo sotto e non entrano.
KINDS = {
    "Highlight": "highlight",
    "Underline": "underline",
    "Squiggly": "squiggly",
    "StrikeOut": "strikeout",
}


def _hex(rgb) -> str:
    if not rgb or len(rgb) < 3:
        return "#f5d547"
    return "#" + "".join(f"{max(0, min(255, round(c * 255))):02x}" for c in rgb[:3])


def _join(pieces: list[str]) -> str:
    """Le righe di un'evidenziazione in un testo solo. Una parola spezzata a
    fine riga ("tu-" "mours") si riattacca."""
    out = ""
    for piece in pieces:
        piece = " ".join(piece.split())
        if not piece:
            continue
        if out.endswith("-") and piece[:1].islower():
            out = out[:-1] + piece
        else:
            out = f"{out} {piece}" if out else piece
    return out


def extract(path: Path) -> list[dict]:
    """Le evidenziazioni del PDF, nell'ordine di lettura.

    `rects` e' la posizione di ogni riga evidenziata come frazioni della
    pagina cosi' come si vede (ruotata se il PDF lo chiede): il lettore la
    moltiplica per la dimensione a cui disegna la pagina, qualunque sia lo
    zoom."""
    import fitz

    found: list[dict] = []
    with fitz.open(path) as doc:
        for page in doc:
            width, height = page.rect.width or 1, page.rect.height or 1
            for annot in page.annots() or []:
                kind = KINDS.get(annot.type[1])
                if kind is None:
                    continue
                verts = annot.vertices or []
                quads = [fitz.Quad(verts[i:i + 4]) for i in range(0, len(verts) - 3, 4)]
                if not quads:
                    quads = [fitz.Quad(annot.rect)]
                # il testo si legge nello spazio della pagina non ruotata, dove
                # stanno i vertici; la posizione si porta in quello ruotato
                text = _join([page.get_textbox(q.rect) for q in quads])
                shown = [q.rect * page.rotation_matrix for q in quads]
                rects = [[round(r.x0 / width, 5), round(r.y0 / height, 5),
                          round(r.x1 / width, 5), round(r.y1 / height, 5)]
                         for r in shown]
                note = ((annot.info or {}).get("content") or "").strip()
                if not text and not note:
                    continue
                top = min(r[1] for r in rects)
                left = min(r[0] for r in rects)
                found.append({
                    "page": page.number + 1,
                    "kind": kind,
                    "color": _hex((annot.colors or {}).get("stroke")),
                    "text": text,
                    "note": note,
                    "rects": rects,
                    "_order": (page.number, round(top, 2), left),
                })
    found.sort(key=lambda h: h["_order"])
    for n, h in enumerate(found):
        h.pop("_order")
        h["ord"] = n
        h["hkey"] = key_of(h)
    return found


def key_of(h: dict) -> str:
    """Pagina e posizione arrotondata: la stessa evidenziazione riletta dopo
    un salvataggio ha la stessa chiave, anche se il programma che ha salvato
    ha spostato i vertici di un decimo di punto."""
    where = [[round(v, 3) for v in r] for r in h["rects"]]
    raw = json.dumps([h["page"], h["kind"], where])
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def sync(pmid: str, path: Path, *, force: bool = False) -> bool:
    """Rilegge le evidenziazioni se il file e' cambiato dall'ultima volta.
    Ritorna True se le ha rilette.

    Si guarda la data del file: aprire un PDF di duecento pagine a ogni giro
    dell'app costerebbe, e quasi sempre non e' cambiato niente."""
    from radiowriter import db

    try:
        mtime = Path(path).stat().st_mtime
    except OSError:
        return False
    if not force and db.highlights_mtime(pmid) == mtime:
        return False
    try:
        items = extract(Path(path))
    except Exception:
        # Un PDF che PyMuPDF non apre - magari lo si sta salvando proprio ora
        # da Anteprima. Non si tocca niente: scrivere una lista vuota
        # cancellerebbe le spunte gia' messe.
        return False
    db.sync_highlights(pmid, items, mtime)
    return True
