"""La libreria dei PDF: un file per articolo, col nome della sua citazione.

Tre strade per cui un PDF entra in libreria:

  - open access: il link di Unpaywall (o di Semantic Scholar) si scarica da
    qui, senza passare dal browser, quando porta davvero a un PDF;
  - Download: quello che arriva da LibKey passa per il login della biblioteca,
    che sta nel browser e non nell'app. Lo scarica chi legge, come ha sempre
    fatto, e qui lo si riconosce dal DOI o dal PMID scritti nel testo e lo si
    porta in libreria;
  - a mano: un file trascinato sulla scheda dell'articolo.

In tutt'e tre i casi il file prende il nome della citazione,
`Autore Anno - Rivista - Titolo [PMID n].pdf`, cosi' che la cartella si legga
anche fuori dall'app, dal Finder o da un'altra macchina. Il PMID tra
parentesi quadre rende il nome unico e permette di ritrovare l'articolo anche
se il database non c'e' piu'.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

import requests

TIMEOUT = 60
# Oltre questa soglia un "PDF" e' quasi sempre un supplemento con i video, non
# l'articolo: meglio fermarsi che riempire il disco senza dirlo.
MAX_BYTES = 150 * 1024 * 1024
# Quanto indietro si guarda nella cartella Download. Un PDF di tre mesi fa non
# e' quello appena scaricato da LibKey, e guardarli tutti ogni volta vorrebbe
# dire aprire centinaia di file a ogni giro dell'app.
RECENT_DAYS = 30

# Alcuni editori rispondono 403 a un client che non si presenta come browser.
# Non e' un modo di aggirare niente: il link e' open access, e lo stesso file
# si apre da qualunque browser.
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
                   "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                   "Safari/605.1.15 Radiowriter"),
    "Accept": "application/pdf,*/*;q=0.8",
}

TITLE_MAX = 90
NAME_MAX = 180

DOI_RX = re.compile(r"\b(10\.\d{4,9}/[^\s\"'<>\]\[]+)", re.I)
PMID_RX = re.compile(r"\bPMID[:\s]*(\d{5,9})\b", re.I)
# Caratteri che un nome di file non puo' avere su almeno uno dei tre sistemi.
BAD_CHARS = re.compile(r'[\\/*?"<>|\x00-\x1f]')
INITIALS = re.compile(r"^[A-Z]{1,4}$")


class LibraryError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# il nome del file
# ---------------------------------------------------------------------------

def _medline_field(raw: str, tag: str) -> str:
    """Il primo valore di un campo MEDLINE (`TA  - Radiology`)."""
    m = re.search(rf"^{tag}\s*-\s*(.+)$", raw or "", re.M)
    return m.group(1).strip() if m else ""


def first_author(authors: str, raw: str = "") -> str:
    """Il cognome del primo autore.

    `authors` e' "Smith J; Doe A" per i record entrati dall'API; molti record
    storici ce l'hanno vuoto, e li' si legge la prima riga `AU` del blocco
    MEDLINE, che e' nella stessa forma. Le iniziali in fondo si tolgono, un
    cognome in piu' parole resta intero ("van der Berg")."""
    first = (authors or "").split(";")[0].strip() or _medline_field(raw, "AU")
    if not first:
        return "Anonymous"
    words = first.split()
    if len(words) > 1 and INITIALS.match(words[-1]):
        words = words[:-1]
    # un autore collettivo ("American College of Radiology Imaging Network")
    # si accorcia: il nome del file non e' il posto per il nome intero
    return " ".join(words[:4])


def journal_short(raw: str, journal_title: str = "", journal: str = "") -> str:
    """La rivista in forma breve: l'abbreviazione ISO del campo `TA`
    ("J Oral Maxillofac Surg"), che PubMed da' per ogni record. Senza, il
    titolo esteso fino ai due punti del sottotitolo."""
    ta = _medline_field(raw, "TA")
    if ta:
        return ta
    name = (journal_title or journal or "").split(" : ")[0].strip()
    return name or "Unknown journal"


def _year(rec) -> str:
    year = str(rec.get("year") or "").strip()
    if not re.fullmatch(r"\d{4}", year):
        m = re.match(r"\d{4}", str(rec.get("pub_date") or ""))
        year = m.group(0) if m else ""
    return year or "n.d."


def _clean(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "")
    # un titolo tradotto da PubMed sta fra parentesi quadre: nel nome del file
    # le quadre sono riservate al PMID
    text = text.replace("[", "").replace("]", "")
    text = text.replace(":", " -")
    text = BAD_CHARS.sub(" ", text)
    return " ".join(text.split()).strip(" .")


def _cut(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;-")
    return cut + "..."


def filename_for(rec) -> str:
    """`Autore Anno - Rivista - Titolo [PMID n].pdf` per un record d'archivio.

    `rec` e' una riga di `articles` (o un dizionario con gli stessi campi)."""
    rec = dict(rec)
    raw = rec.get("raw_text") or ""
    author = _clean(first_author(rec.get("authors") or "", raw))
    journal = _clean(journal_short(raw, rec.get("journal_title") or "",
                                   rec.get("journal") or ""))
    title = _clean(rec.get("title") or "") or "Untitled"
    tail = f" [PMID {rec.get('pmid')}].pdf"
    head = f"{author} {_year(rec)} - {journal} - "
    room = max(20, min(TITLE_MAX, NAME_MAX - len(head) - len(tail)))
    return head + _cut(title, room) + tail


# ---------------------------------------------------------------------------
# file
# ---------------------------------------------------------------------------

def is_pdf(head: bytes) -> bool:
    """Un PDF comincia con `%PDF-`, a volte dopo qualche byte di spazzatura
    che i lettori tollerano: si guarda il primo kilobyte."""
    return b"%PDF-" in head[:1024]


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def store(src: Path, folder: Path, name: str, *, move: bool) -> tuple[str, str, int]:
    """Porta `src` in `folder` col nome `name`. Ritorna (nome, sha256, byte).

    Si scrive prima un file temporaneo nella stessa cartella e poi lo si
    rinomina: se il disco si riempie a meta', in libreria non resta un PDF
    tronco col nome giusto."""
    src = Path(src)
    with open(src, "rb") as fh:
        if not is_pdf(fh.read(1024)):
            raise LibraryError(f"{src.name} is not a PDF.")
    digest = sha256_of(src)
    size = src.stat().st_size
    dest = folder / name
    fd, tmp = tempfile.mkstemp(dir=folder, suffix=".part")
    os.close(fd)
    try:
        shutil.copyfile(src, tmp)
        os.replace(tmp, dest)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    if move and src.resolve() != dest.resolve():
        # Tolto da Download solo dopo che la copia e' al suo posto.
        src.unlink(missing_ok=True)
    return name, digest, size


def store_bytes(data: bytes, folder: Path, name: str) -> tuple[str, str, int]:
    if not is_pdf(data[:1024]):
        raise LibraryError("The file is not a PDF.")
    fd, tmp = tempfile.mkstemp(dir=folder, suffix=".part")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, folder / name)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return name, hashlib.sha256(data).hexdigest(), len(data)


def download(url: str, session: requests.Session | None = None) -> bytes:
    """Il PDF dietro un link open access.

    Molti link di Unpaywall portano alla pagina dell'articolo, non al file:
    allora si dice cosi', e il PDF lo scarica chi legge dal browser - poi lo
    si raccoglie dalla cartella Download come quelli di LibKey."""
    http = session or requests
    try:
        resp = http.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True,
                        allow_redirects=True)
    except requests.RequestException as exc:
        raise LibraryError(f"Could not reach the free full text: {exc}") from exc
    with resp:
        if resp.status_code >= 400:
            raise LibraryError(
                f"The publisher answered {resp.status_code}. Open the link in "
                "the browser and download the PDF there; it will be picked up "
                "from Downloads.")
        chunks, total, checked = [], 0, False
        for chunk in resp.iter_content(1 << 16):
            chunks.append(chunk)
            total += len(chunk)
            # si guarda il primo kilobyte appena c'e', per non scaricare tutta
            # una pagina HTML prima di dire che non e' un PDF
            if not checked and total >= 1024:
                checked = True
                if not is_pdf(b"".join(chunks)):
                    raise LibraryError(
                        "The free link leads to a web page, not to a PDF. Open "
                        "it, download the PDF from there, and it will be "
                        "picked up from Downloads.")
            if total > MAX_BYTES:
                raise LibraryError("The file is larger than 150 MB; not saved.")
    data = b"".join(chunks)
    if not is_pdf(data[:1024]):
        raise LibraryError("The free link did not return a PDF.")
    return data


# ---------------------------------------------------------------------------
# riconoscere un PDF
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def identify(path: Path) -> dict:
    """Quello che un PDF dice di se': DOI, PMID e il testo della prima pagina.

    Si guardano i metadati e le prime due pagine, dove stanno intestazione e
    piede con il DOI. Un PDF scansionato senza testo non dice niente, e si
    aggancia a mano."""
    import fitz  # PyMuPDF: importato qui perche' serve solo a questo

    out = {"dois": [], "pmids": [], "text": ""}
    try:
        with fitz.open(path) as doc:
            meta = " ".join(str(v) for v in (doc.metadata or {}).values() if v)
            pages = [doc[i].get_text() for i in range(min(2, doc.page_count))]
    except Exception as exc:  # un PDF rotto non deve fermare gli altri
        out["error"] = str(exc)
        return out
    text = meta + "\n" + "\n".join(pages)
    dois = []
    for m in DOI_RX.findall(text):
        doi = m.rstrip(".,;:)").lower()
        if doi not in dois:
            dois.append(doi)
    out["dois"] = dois
    out["pmids"] = list(dict.fromkeys(PMID_RX.findall(text)))
    out["text"] = _norm(pages[0] if pages else "")
    return out


def match_title(page_text: str, titles: dict[str, str]) -> str | None:
    """PMID dell'articolo il cui titolo compare nella prima pagina.

    Ultima risorsa, per i PDF senza DOI stampato. Vale solo un titolo lungo
    abbastanza da non comparire per caso, e solo se ne compare uno: due
    candidati vogliono dire che non si sa."""
    if not page_text:
        return None
    hits = [pmid for pmid, title in titles.items()
            if len(t := _norm(title)) >= 30 and t in page_text]
    return hits[0] if len(hits) == 1 else None


def recent_pdfs(folder: Path, days: int = RECENT_DAYS) -> list[Path]:
    """I PDF della cartella Download degli ultimi `days` giorni, i piu'
    nuovi prima. Non si scende nelle sottocartelle."""
    cutoff = time.time() - days * 86400
    try:
        found = [p for p in folder.iterdir()
                 if p.is_file() and p.suffix.lower() == ".pdf"
                 and p.stat().st_mtime >= cutoff]
    except OSError:
        return []
    return sorted(found, key=lambda p: p.stat().st_mtime, reverse=True)


# ---------------------------------------------------------------------------
# aprire
# ---------------------------------------------------------------------------

def open_file(path: Path) -> None:
    """Apre il file col programma di sistema (Anteprima su macOS).

    L'app gira su questo computer e il server ascolta solo qui: aprire un
    file locale e' la stessa cosa che fare doppio clic nel Finder."""
    _launch(path, reveal=False)


def reveal(path: Path) -> None:
    """Mostra il file nella sua cartella (Finder, Esplora risorse)."""
    _launch(path, reveal=True)


def _launch(path: Path, *, reveal: bool) -> None:
    path = Path(path)
    if sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)] if reveal else ["open", str(path)])
    elif os.name == "nt":
        if reveal:
            subprocess.Popen(["explorer", "/select,", str(path)])
        else:
            os.startfile(str(path))  # noqa: S606 - e' un file nostro
    else:
        subprocess.Popen(["xdg-open", str(path.parent if reveal else path)])
