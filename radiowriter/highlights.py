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


def _item(page, annot) -> dict | None:
    """Un'annotazione come la vede la lista, o None se non e' del testo
    marcato."""
    import fitz

    kind = KINDS.get(annot.type[1])
    if kind is None:
        return None
    width, height = page.rect.width or 1, page.rect.height or 1
    verts = annot.vertices or []
    quads = [fitz.Quad(verts[i:i + 4]) for i in range(0, len(verts) - 3, 4)]
    if not quads:
        quads = [fitz.Quad(annot.rect)]
    # il testo si legge nello spazio della pagina non ruotata, dove stanno i
    # vertici; la posizione si porta in quello ruotato
    text = _join([page.get_textbox(q.rect) for q in quads])
    shown = [q.rect * page.rotation_matrix for q in quads]
    rects = [[round(r.x0 / width, 5), round(r.y0 / height, 5),
              round(r.x1 / width, 5), round(r.y1 / height, 5)]
             for r in shown]
    note = ((annot.info or {}).get("content") or "").strip()
    if not text and not note:
        return None
    item = {
        "page": page.number + 1,
        "kind": kind,
        "color": _hex((annot.colors or {}).get("stroke")),
        "text": text,
        "note": note,
        "rects": rects,
        "_order": (page.number, round(min(r[1] for r in rects), 2),
                   min(r[0] for r in rects)),
    }
    item["hkey"] = key_of(item)
    return item


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
            for annot in page.annots() or []:
                item = _item(page, annot)
                if item is not None:
                    found.append(item)
    found.sort(key=lambda h: h["_order"])
    for n, h in enumerate(found):
        h.pop("_order")
        h["ord"] = n
    return found


# ---------------------------------------------------------------------------
# scrivere nel PDF, dal lettore dell'app
# ---------------------------------------------------------------------------
#
# Si evidenzia nel lettore della finestra di studio e l'evidenziazione va
# DENTRO il PDF, come annotazione standard: la si vede anche aprendo il file
# con Anteprima, sull'iPad o mandandolo a qualcuno. Poi la si rilegge da li'
# come tutte le altre, quindi c'e' una strada sola per cui un'evidenziazione
# entra nella lista.

def _rgb(color: str) -> tuple[float, float, float]:
    c = (color or "#ffd400").lstrip("#")
    if len(c) != 6:
        c = "ffd400"
    return tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _save(doc, path: Path) -> None:
    """Salva le modifiche nel file stesso.

    Il salvataggio incrementale aggiunge in coda e non riscrive il resto: e'
    veloce e lascia intatto quello che c'era. Non sempre si puo' (un PDF
    riparato all'apertura, certi PDF cifrati): allora si riscrive in un file
    accanto e lo si mette al posto dell'originale, cosi' un errore a meta' non
    lascia un PDF rotto."""
    import os
    import tempfile

    try:
        doc.saveIncr()
        return
    except Exception:
        pass
    fd, tmp = tempfile.mkstemp(dir=Path(path).parent, suffix=".part")
    os.close(fd)
    try:
        doc.save(tmp, garbage=1, deflate=True)
        doc.close()
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def add(path: Path, page_no: int, rects: list[list[float]], color: str,
        kind: str = "highlight") -> None:
    """Un'evidenziazione nuova su una pagina. `rects` sono le righe
    selezionate, in frazioni della pagina come si vede (vedi `extract`)."""
    import fitz

    doc = fitz.open(path)
    try:
        page = doc[int(page_no) - 1]
        w, h = page.rect.width, page.rect.height
        quads = []
        for x0, y0, x1, y1 in rects:
            r = fitz.Rect(x0 * w, y0 * h, x1 * w, y1 * h) * page.derotation_matrix
            r.normalize()
            if r.width > 0.5 and r.height > 0.5:
                quads.append(r.quad)
        if not quads:
            return
        maker = page.add_underline_annot if kind == "underline" else page.add_highlight_annot
        annot = maker(quads=quads)
        annot.set_colors(stroke=_rgb(color))
        annot.update()
        _save(doc, path)
    finally:
        if not doc.is_closed:
            doc.close()


def _change(path: Path, hkey: str, what) -> bool:
    """Trova l'annotazione con quella chiave e le fa `what(page, annot)`."""
    import fitz

    doc = fitz.open(path)
    try:
        for page in doc:
            for annot in page.annots() or []:
                item = _item(page, annot)
                if item is not None and item["hkey"] == hkey:
                    what(page, annot)
                    _save(doc, path)
                    return True
        return False
    finally:
        if not doc.is_closed:
            doc.close()


def remove(path: Path, hkey: str) -> bool:
    """Toglie un'evidenziazione dal PDF."""
    return _change(path, hkey, lambda page, annot: page.delete_annot(annot))


def set_note(path: Path, hkey: str, note: str) -> bool:
    """La nota di un'evidenziazione, scritta nel PDF: e' il campo che
    Anteprima e Acrobat mostrano come commento."""
    def write(page, annot):
        info = annot.info or {}
        info["content"] = note or ""
        annot.set_info(info)
        annot.update()
    return _change(path, hkey, write)


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
