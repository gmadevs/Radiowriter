"""La finestra di studio: la pagina Radiopaedia da una parte, il PDF dall'altra.

Radiopaedia non si puo' aprire dentro la pagina dell'app: un sito con login
non si lascia incorniciare da una pagina altrui, e anche se lo facesse non
avrebbe i cookie della sessione, quindi non si potrebbe modificare niente.
Qui si aprono due finestre vere con pywebview (su macOS lo stesso motore di
Safari), che tengono il login da una volta all'altra in una cartella propria
dentro la cartella dei dati.

Si lancia dall'app, col pulsante "Open study window", come processo a parte:
pywebview vuole il filo principale del processo, e in quello dell'app c'e'
gia' Streamlit. Si puo' anche lanciare a mano:

    python -m radiowriter.study --page URL [--pdf FILE] [--layout lr|tb]

Qui dentro c'e' anche l'elenco degli articoli Radiopaedia (l'export della loro
ricerca), che l'app usa per scegliere la pagina senza importare pywebview.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path

from radiowriter import paths

WEB = Path(__file__).resolve().parent / "web"
SEARCH_URL = "https://radiopaedia.org/search?scope=articles&q="
HOME_URL = "https://radiopaedia.org/"


# ---------------------------------------------------------------------------
# l'elenco degli articoli
# ---------------------------------------------------------------------------

def read_index(path: Path) -> list[dict]:
    """Le righe dell'export: titolo, URL, sistemi, sezioni, ultima modifica.

    Le colonne si cercano per nome, e il nome della data cambia con
    l'ordinamento scelto nella loro ricerca ("Date of Last Edit (Newest)"):
    si prende quella che comincia per "Date"."""
    raw = path.read_bytes()
    if path.suffix == ".gz":
        raw = gzip.decompress(raw)
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    date_col = next((c for c in reader.fieldnames or [] if c.startswith("Date")), "")
    out = []
    for row in reader:
        url = (row.get("URL") or "").strip()
        title = (row.get("Title") or "").strip()
        if not url.startswith("https://radiopaedia.org/") or not title:
            continue
        out.append({
            "title": title,
            "url": url,
            "systems": (row.get("Systems") or "").strip(),
            "sections": (row.get("Sections") or "").strip(),
            "edited": (row.get(date_col) or "").strip() if date_col else "",
        })
    return out


def find(index: list[dict], text: str, limit: int = 40) -> list[dict]:
    """Gli articoli il cui titolo contiene tutte le parole cercate.

    Prima quelli che cominciano con quello che si e' scritto, poi quelli in
    cui una parola comincia cosi', poi il resto; a parita', il titolo piu'
    corto, che e' di solito l'articolo principale e non un caso particolare."""
    words = text.lower().split()
    if not words:
        return []
    q = " ".join(words)
    hits = []
    for rec in index:
        t = rec["title"].lower()
        if all(w in t for w in words):
            rank = 0 if t.startswith(q) else 1 if f" {q}" in f" {t}" else 2
            hits.append((rank, len(t), rec))
    hits.sort(key=lambda h: (h[0], h[1]))
    return [h[2] for h in hits[:limit]]


def search_url(text: str) -> str:
    return SEARCH_URL + urllib.parse.quote_plus(text.strip())


# ---------------------------------------------------------------------------
# lanciare la finestra
# ---------------------------------------------------------------------------

def available() -> str:
    """Stringa vuota se pywebview c'e', altrimenti cosa manca."""
    try:
        import webview  # noqa: F401
    except ImportError as exc:
        return (f"pywebview is not installed ({exc}). On Linux it also needs "
                "GTK or Qt: see https://pywebview.flowrl.com/guide/installation.html")
    return ""


def launch(page: str, pdf: Path | None = None, layout: str = "lr",
           pmid: str | None = None) -> subprocess.Popen:
    """Apre la finestra di studio in un processo a parte e torna subito.

    Col PMID, a destra si apre il lettore con le evidenziazioni; senza, il
    PDF cosi' com'e'."""
    cmd = [sys.executable, "-m", "radiowriter.study", "--page", page,
           "--layout", layout]
    if pdf is not None:
        cmd += ["--pdf", str(pdf)]
    if pmid:
        cmd += ["--pmid", str(pmid)]
    # una sessione sua: chiudere il terminale dell'app non chiude la finestra
    # a meta' lavoro, e chiudere la finestra non tocca l'app
    return subprocess.Popen(cmd, start_new_session=True,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _serve_as(pdf: Path, link: Path) -> None:
    """Il PDF sotto un nome semplice, per il server di pywebview (vedi `main`)."""
    link.unlink(missing_ok=True)
    try:
        link.symlink_to(pdf.resolve())
    except OSError:
        # Windows senza privilegi non crea collegamenti simbolici
        shutil.copyfile(pdf, link)


def copy_text(text: str) -> None:
    """Negli appunti del sistema. Il lettore gira in una pagina servita da
    pywebview, dove l'API degli appunti del browser non e' garantita: si passa
    da Python, che qui e' sempre a disposizione."""
    if sys.platform == "darwin":
        subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=False)
    elif sys.platform == "win32":
        subprocess.run(["clip"], input=text.encode("utf-16le"), check=False)
    else:
        for cmd in (["wl-copy"], ["xclip", "-selection", "clipboard"]):
            try:
                subprocess.run(cmd, input=text.encode("utf-8"), check=False)
                return
            except FileNotFoundError:
                continue


class ReaderApi:
    """Quello che il lettore (web/viewer.html) chiede a Python.

    pywebview espone al JavaScript i metodi pubblici di questo oggetto come
    `window.pywebview.api.<nome>`; gli attributi cominciano con `_` perche'
    non vanno esposti."""

    def __init__(self, pmid: str, pdf: Path, link: Path, title: str):
        self._pmid, self._pdf, self._link, self._title = pmid, pdf, link, title
        self._mtime = None

    def _state(self, force: bool = False) -> dict:
        from radiowriter import db
        from radiowriter import highlights as hl

        hl.sync(self._pmid, self._pdf, force=force)
        try:
            mtime = self._pdf.stat().st_mtime
        except OSError:
            mtime = None
        if mtime != self._mtime and not self._link.is_symlink():
            # una copia (Windows): va rifatta quando il PDF vero cambia
            _serve_as(self._pdf, self._link)
        self._mtime = mtime
        return {"title": self._title, "mtime": mtime,
                "highlights": db.highlights_for(self._pmid)}

    def state(self) -> dict:
        return self._state()

    def reread(self) -> dict:
        return self._state(force=True)

    def set_done(self, highlight_id: int, done: bool) -> bool:
        from radiowriter import db

        db.set_highlight_done(int(highlight_id), bool(done))
        return True

    def copy(self, text: str) -> bool:
        copy_text(text or "")
        return True

    def open_external(self) -> bool:
        from radiowriter import library

        library.open_file(self._pdf)
        return True


def _geometry(layout: str) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    """(x, y, larghezza, altezza) delle due finestre sullo schermo principale."""
    import webview

    try:
        screen = webview.screens[0]
        width, height = int(screen.width), int(screen.height)
    except Exception:
        width, height = 1440, 900
    # un margine in alto per la barra dei menu di macOS, uno in basso per il Dock
    top, usable = 30, height - 30 - 60
    if layout == "tb":
        half = usable // 2
        return (0, top, width, half), (0, top + half, width, usable - half)
    half = width // 2
    return (0, top, half, usable), (half, top, width - half, usable)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="radiowriter.study")
    parser.add_argument("--page", default=HOME_URL, help="Radiopaedia URL to open")
    parser.add_argument("--pdf", help="PDF to open next to it")
    parser.add_argument("--pmid", help="its article, to read and tick its highlights")
    parser.add_argument("--layout", choices=("lr", "tb"), default="lr",
                        help="lr = side by side, tb = one above the other")
    args = parser.parse_args(argv)

    import webview

    left, right = _geometry(args.layout)
    webview.create_window(
        "Radiopaedia", args.page, x=left[0], y=left[1],
        width=left[2], height=left[3], text_select=True)
    storage = paths.home() / "study-browser"
    storage.mkdir(parents=True, exist_ok=True)
    if args.pdf:
        pdf = Path(args.pdf)
        # Un percorso locale, non un URL file://: pywebview lo serve lui da un
        # piccolo server su questo computer. Ma quel server non regge i nomi
        # della libreria - spazi, quadre, lettere accentate - e mostra una
        # pagina bianca: gli si passa un collegamento con un nome semplice.
        link = storage / "open.pdf"
        _serve_as(pdf, link)
        if args.pmid:
            # il lettore sta accanto al PDF, cosi' lo trova come `open.pdf`
            viewer = storage / "viewer.html"
            shutil.copyfile(WEB / "viewer.html", viewer)
            webview.create_window(
                pdf.stem, str(viewer), x=right[0], y=right[1],
                width=right[2], height=right[3], text_select=True,
                js_api=ReaderApi(args.pmid, pdf, link, pdf.stem))
        else:
            webview.create_window(
                pdf.stem, str(link), x=right[0], y=right[1],
                width=right[2], height=right[3], text_select=True)
    # private_mode=False e una cartella nostra: il login a Radiopaedia resta
    # fra una volta e l'altra, e non si mescola con quello del browser di tutti
    # i giorni.
    webview.start(private_mode=False, storage_path=str(storage))
    return 0


if __name__ == "__main__":
    sys.exit(main())
