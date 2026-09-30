#!/usr/bin/env python3
"""La libreria dei PDF e l'elenco degli articoli Radiopaedia.

    python3 check_library.py

Senza rete e senza finestre. Si prova il nome dato ai file, come un PDF si
riconosce dal suo testo, come entra in libreria, che la pulizia all'avvio non
lo tocchi, e come si cerca nell'export di Radiopaedia - non se la finestra di
studio si apre, che dipende dallo schermo.
"""

from __future__ import annotations

import gzip
import os
import sys
import tempfile
import time
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="radiowriter-library-")
os.environ["RADIOPAEDIA_DB"] = os.path.join(_TMP, "test.db")
os.environ["RADIOWRITER_HOME"] = _TMP

import fitz                                    # noqa: E402

from radiowriter import db                     # noqa: E402
from radiowriter import library                # noqa: E402
from radiowriter import paths                  # noqa: E402
from radiowriter import study                  # noqa: E402

db.init_db()

checked = 0
failed = 0


def is_(what: str, got, want) -> None:
    global checked, failed
    checked += 1
    if str(got) == str(want):
        print(f"OK  {what}")
        return
    failed += 1
    print(f"NO  {what}\n      ottenuto {got!r}\n      atteso   {want!r}")


def make_pdf(path: Path, text: str) -> Path:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(fitz.Rect(50, 50, 550, 800), text, fontsize=10)
    doc.save(path)
    doc.close()
    return path


RAW = """PMID- 12345678
TI  - Hidden in Plain Sight: Diagnostic Challenges.
AU  - van der Berg AB
AU  - Rossi M
TA  - Niger Med J
JT  - Nigerian medical journal : journal of the Nigeria Medical Association
"""

# ---------------------------------------------------------------------------
# il nome del file
# ---------------------------------------------------------------------------

print("\n--- il nome ---")

rec = {"pmid": "12345678", "title": "Hidden in Plain Sight: Diagnostic Challenges.",
       "authors": "", "year": "2026", "raw_text": RAW,
       "journal_title": "Nigerian medical journal : journal of the Nigeria Medical Association"}
is_("autore, anno, rivista abbreviata, titolo, PMID",
    library.filename_for(rec),
    "van der Berg 2026 - Niger Med J - Hidden in Plain Sight - Diagnostic "
    "Challenges [PMID 12345678].pdf")
is_("il campo authors vince sul MEDLINE",
    library.first_author("Smith J; Doe A", RAW), "Smith")
is_("senza autori", library.first_author("", ""), "Anonymous")
is_("senza TA si taglia il titolo esteso al sottotitolo",
    library.journal_short("", rec["journal_title"]), "Nigerian medical journal")

long_rec = dict(rec, title="Word " * 60, raw_text=RAW)
name = library.filename_for(long_rec)
is_("un titolo lungo si accorcia", len(name) <= library.NAME_MAX, True)
is_("...e il PMID resta in fondo", name.endswith("[PMID 12345678].pdf"), True)

odd = dict(rec, title='[Vestibulocochlear infarct: a/b "test"?]', year="", pub_date="")
is_("quadre, barre, virgolette e anno mancante",
    library.filename_for(odd),
    "van der Berg n.d. - Niger Med J - Vestibulocochlear infarct - a b test "
    "[PMID 12345678].pdf")

# ---------------------------------------------------------------------------
# riconoscere un PDF
# ---------------------------------------------------------------------------

print("\n--- riconoscere ---")

pdf = make_pdf(Path(_TMP) / "download.pdf",
               "Radiology 2021. https://doi.org/10.1148/RADIOL.2021204567. "
               "PMID: 33400000\nHidden in plain sight: diagnostic challenges")
info = library.identify(pdf)
is_("il DOI si legge e va in minuscolo", info["dois"], ["10.1148/radiol.2021204567"])
is_("il PMID pure", info["pmids"], ["33400000"])
is_("un titolo lungo che compare una volta aggancia",
    library.match_title(info["text"], {"1": "Hidden in plain sight: diagnostic challenges",
                                       "2": "Something else entirely, long enough"}), "1")
is_("un titolo corto non aggancia",
    library.match_title(info["text"], {"1": "Radiology"}), None)

broken = Path(_TMP) / "broken.pdf"
broken.write_bytes(b"not a pdf at all")
is_("un file rotto non fa saltare niente", "error" in library.identify(broken), True)
try:
    library.store(broken, paths.pdf_folder(), "x.pdf", move=False)
    is_("un non-PDF viene rifiutato", "accettato", "rifiutato")
except library.LibraryError:
    is_("un non-PDF viene rifiutato", "rifiutato", "rifiutato")

# ---------------------------------------------------------------------------
# entrare in libreria
# ---------------------------------------------------------------------------

print("\n--- la libreria ---")

db.insert_articles([{"pmid": "33400000", "title": "Hidden in plain sight: diagnostic challenges",
                     "doi": "10.1148/radiol.2021204567", "year": "2021",
                     "raw_text": RAW.replace("12345678", "33400000")}])
is_("il DOI del PDF porta all'articolo",
    db.articles_by_ids(info["dois"], []), {"10.1148/radiol.2021204567": "33400000"})

folder = paths.pdf_folder()
is_("la cartella sta nella cartella dei dati", folder, Path(_TMP) / "PDFs")
target = library.filename_for(db.article_row("33400000"))
stored, digest, size = library.store(pdf, folder, target, move=True)
db.save_pdf("33400000", stored, digest, size, "downloads")
is_("il file e' in libreria col suo nome", (folder / target).exists(), True)
is_("...e non e' piu' in Download", pdf.exists(), False)
is_("l'impronta lo ritrova", db.pdf_by_sha(digest)["pmid"], "33400000")
is_("la pagina dello screening lo vede", list(db.pdfs_for(["33400000", "1"])), ["33400000"])
is_("il riepilogo lo conta", db.archive_summary()["pdfs"], 1)
is_("la libreria lo trova per titolo", len(db.library_rows("plain sight")), 1)
is_("...e non per altro", len(db.library_rows("pneumothorax")), 0)

draft = db.create_draft("Test")
db.add_draft_refs(draft, ["10.1148/RADIOL.2021204567"], note="")
is_("una bozza che lo cita per DOI lo trova",
    [r["pmid"] for r in db.library_rows(draft_id=draft)], ["33400000"])

db.set_status("33400000", "is_read", True)
db.cleanup_read_articles()
is_("letto ma con PDF: la pulizia non lo tocca",
    db.article_row("33400000") is not None, True)

db.forget_pdf("33400000")
db.cleanup_read_articles()
is_("senza PDF invece se ne va", db.article_row("33400000"), None)

# ---------------------------------------------------------------------------
# l'elenco Radiopaedia
# ---------------------------------------------------------------------------

print("\n--- l'elenco Radiopaedia ---")

csv_text = (
    "Title,URL,Systems,Sections,Date of Last Edit (Newest)\n"
    "Pneumothorax,https://radiopaedia.org/articles/pneumothorax,Chest,\"\",\"September 1, 2026\"\n"
    "Tension pneumothorax,https://radiopaedia.org/articles/tension-pneumothorax,"
    "\"Chest,Trauma\",\"\",\"August 1, 2026\"\n"
    "Deep sulcus sign (chest radiograph),https://radiopaedia.org/articles/deep-sulcus-sign,"
    "Chest,Signs,\"July 1, 2026\"\n"
    "Broken row,http://example.org/x,Chest,\"\",\"\"\n")
index_file = Path(_TMP) / "radiopaedia-articles-2026-09-29.csv.gz"
index_file.write_bytes(gzip.compress(csv_text.encode()))
is_("l'export si trova nella cartella dei dati", paths.radiopaedia_index(), index_file)
index = study.read_index(index_file)
is_("le righe fuori da radiopaedia.org si scartano", len(index), 3)
is_("la data si legge qualunque sia l'ordinamento", index[0]["edited"], "September 1, 2026")
is_("i sistemi restano come sono", index[1]["systems"], "Chest,Trauma")
is_("chi comincia con la ricerca viene prima",
    [r["title"] for r in study.find(index, "pneumo")],
    ["Pneumothorax", "Tension pneumothorax"])
is_("tutte le parole devono esserci",
    [r["title"] for r in study.find(index, "sulcus chest")],
    ["Deep sulcus sign (chest radiograph)"])
is_("la ricerca vuota non trova niente", study.find(index, "  "), [])
is_("l'URL della loro ricerca",
    study.search_url("cerebral abscess"),
    "https://radiopaedia.org/search?scope=articles&q=cerebral+abscess")

old = Path(_TMP) / "PDFs" / "old.pdf"
make_pdf(old, "x")
os.utime(old, (time.time() - 90 * 86400,) * 2)
fresh_one = make_pdf(Path(_TMP) / "PDFs" / "new.pdf", "y")
is_("in Download si guardano solo i PDF recenti",
    [p.name for p in library.recent_pdfs(Path(_TMP) / "PDFs")
     if p.name in ("old.pdf", "new.pdf")], ["new.pdf"])

# ---------------------------------------------------------------------------
# le evidenziazioni
# ---------------------------------------------------------------------------

print("\n--- le evidenziazioni ---")

from radiowriter import highlights as hl       # noqa: E402

TEXT = ("Vestibular schwannomas are benign tumours of the eighth nerve. They "
        "enhance avidly after gadolinium. Most are unilateral.")


def highlighted(path: Path, rotate: int = 0, extra: bool = False) -> Path:
    doc = fitz.open()
    for n in range(2):
        page = doc.new_page()
        page.insert_textbox(fitz.Rect(50, 50, 550, 800), TEXT, fontsize=12)
        a = page.add_highlight_annot(page.search_for("benign tumours of the eighth"))
        a.set_info(content="for the introduction")
        a.update()
        if n == 1:
            page.add_underline_annot(page.search_for("enhance avidly"))
            page.set_rotation(rotate)
        if extra and n == 0:
            page.add_squiggly_annot(page.search_for("Most are unilateral"))
        page.add_text_annot((300, 300), "a sticky note, not a highlight")
    doc.save(path)
    doc.close()
    return path


marked = highlighted(Path(_TMP) / "marked.pdf", rotate=90)
items = hl.extract(marked)
is_("tre evidenziazioni, la nota a margine no", len(items), 3)
is_("il testo sotto l'evidenziazione", items[0]["text"], "benign tumours of the eighth")
is_("la nota dell'evidenziazione", items[0]["note"], "for the introduction")
is_("il tipo", [h["kind"] for h in items], ["highlight", "highlight", "underline"])
is_("in ordine di pagina", [h["page"] for h in items], [1, 1 + 1, 2])
is_("il colore dell'evidenziatore", items[0]["color"], "#ffff00")
is_("la posizione in frazioni della pagina",
    all(0 <= v <= 1 for h in items for r in h["rects"] for v in r), True)
is_("sulla pagina ruotata la riga diventa verticale",
    (lambda r: (r[2] - r[0]) < (r[3] - r[1]))(items[1]["rects"][0]), True)
is_("le chiavi sono tutte diverse", len({h["hkey"] for h in items}), 3)
is_("una parola spezzata a fine riga si riattacca",
    hl._join(["benign tu-", "mours of the"]), "benign tumours of the")

db.insert_articles([{"pmid": "40000001", "title": "Vestibular schwannoma review",
                     "year": "2024", "raw_text": RAW.replace("12345678", "40000001")}])
lib = paths.pdf_folder()
name = library.filename_for(db.article_row("40000001"))
stored, digest, size = library.store(marked, lib, name, move=False)
db.save_pdf("40000001", stored, digest, size, "by hand")
path = lib / stored

is_("la prima lettura legge", hl.sync("40000001", path), True)
is_("la seconda no: il file non e' cambiato", hl.sync("40000001", path), False)
marks = db.highlights_for("40000001")
is_("nel database ci sono tutte", len(marks), 3)
db.set_highlight_done(marks[0]["id"], True)
is_("la spunta si conta", db.highlight_counts(["40000001"]), {"40000001": (3, 1)})

# si evidenzia ancora, e si risalva: la spunta di prima resta
highlighted(path, rotate=90, extra=True)
os.utime(path, (time.time() + 5,) * 2)
is_("il file cambiato si rilegge", hl.sync("40000001", path), True)
marks = db.highlights_for("40000001")
is_("ora sono quattro", len(marks), 4)
is_("...e quella gia' fatta e' ancora fatta",
    [m["text"] for m in marks if m["done"]], ["benign tumours of the eighth"])

# se ne toglie una dal file: sparisce anche dalla lista
highlighted(path, rotate=90)
os.utime(path, (time.time() + 10,) * 2)
hl.sync("40000001", path)
is_("quella tolta dal file se ne va", len(db.highlights_for("40000001")), 3)

# un file illeggibile non cancella le spunte
good = path.read_bytes()
path.write_bytes(b"%PDF-1.7 broken")
os.utime(path, (time.time() + 15,) * 2)
is_("un PDF rotto non si rilegge", hl.sync("40000001", path), False)
is_("...e le spunte restano", db.highlight_counts(["40000001"]), {"40000001": (3, 1)})
path.write_bytes(good)

api = study.ReaderApi("40000001", path, Path(_TMP) / "open.pdf", "Test")
state = api.reread()
is_("il lettore riceve titolo ed evidenziazioni",
    (state["title"], len(state["highlights"])), ("Test", 3))
is_("...con le posizioni gia' decodificate", type(state["highlights"][0]["rects"]).__name__,
    "list")
api.set_done(state["highlights"][1]["id"], True)
is_("la spunta dal lettore arriva nel database",
    db.highlight_counts(["40000001"]), {"40000001": (3, 2)})
is_("il lettore viaggia col pacchetto", (study.WEB / "viewer.html").is_file(), True)

db.forget_pdf("40000001")
is_("togliere il PDF toglie le sue evidenziazioni", db.highlights_for("40000001"), [])

print(f"\n{checked} controlli, {failed} falliti")
sys.exit(1 if failed else 0)
