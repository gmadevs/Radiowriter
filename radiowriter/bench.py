"""Il banco dello Screening: una pagina web servita in locale.

Lo Screening e' la scheda in cui si fanno piu' clic - centinaia di spunte per
seduta - e in Streamlit ogni clic costa un giro dello script: mezzo secondo
anche dopo aver isolato la scheda dalle altre. Qui un clic e' una richiesta
piccola e cambia solo l'elemento toccato, come nei banchi di neuropedia
(`casi/serve.py`, `struttura/serve.py`) da cui questo prende la forma: un
server della libreria standard, una pagina HTML sola, SQLite dietro.

L'app Streamlit lo avvia una volta (`start`) e lo mostra dentro la scheda 2 in
un iframe. Le altre schede restano dov'erano.

Niente Streamlit qui dentro: le funzioni si chiamano e si provano da sole, ed
e' quello che fa `check_bench.py`.

CHI PUO' CHIAMARLO. Il server ascolta solo su 127.0.0.1, ma questo non basta:
qualunque pagina aperta nello stesso browser puo' mandare una richiesta a un
indirizzo locale, e qui ci sono richieste che cancellano articoli. Tre cose,
tutte e tre controllate a ogni richiesta:

- un gettone casuale, nuovo a ogni avvio. La pagina lo riceve nell'indirizzo e
  lo rimanda in un'intestazione sua (`X-Radiowriter-Token`). Un'altra pagina
  non lo conosce, e un'intestazione fuori standard non la puo' mandare senza
  un permesso CORS che questo server non da' mai;
- l'intestazione `Host`, che dev'essere 127.0.0.1 o localhost sulla porta
  giusta: un nome qualunque fatto puntare qui (DNS rebinding) viene respinto;
- le scritture passano solo in POST e solo come JSON.
"""

from __future__ import annotations

import html
import json
import secrets
import sqlite3
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import requests

from radiowriter import cards
from radiowriter import db
from radiowriter import highlight
from radiowriter import journals as jr
from radiowriter import library
from radiowriter import paths
from radiowriter import semantic_scholar as s2
from radiowriter import study
from radiowriter import theme
from radiowriter import unpaywall as upw
from radiowriter.cards import clean

PAGE = Path(__file__).with_name("web") / "screening.html"
TOKEN_HEADER = "X-Radiowriter-Token"

SHOW = ["All", "To read", "Read", "Flagged ★"]
PAGE_SIZES = [10, 20, 50, 100]
NO_METRIC = "Not in SCImago"
ORDER_SQL = {
    "Recently added": "a.created_at DESC",
    "Influential citations": "a.influential_citations DESC NULLS LAST, a.created_at DESC",
    "Total citations": "a.citation_count DESC NULLS LAST, a.created_at DESC",
    "Citations per year": "a.citations_per_year DESC NULLS LAST, a.created_at DESC",
    "Year": "a.year DESC NULLS LAST, a.created_at DESC",
    "Journal SJR": "m.sjr DESC NULLS LAST, a.created_at DESC",
}

# La JOIN sulle metriche e' LEFT: un articolo la cui rivista non sta in SCImago
# deve restare nell'elenco, senza quartile, non sparire.
FROM = ("FROM articles a "
        "LEFT JOIN journal_metrics m ON m.id = a.journal_metric_id")


class BenchError(Exception):
    """Un errore da dire a chi sta usando la pagina, con le sue parole."""


# ---------------------------------------------------------------------------
# i filtri e la pagina di articoli
# ---------------------------------------------------------------------------

def filters_from(query: dict) -> dict:
    """I filtri come arrivano dall'indirizzo, ripuliti. Un valore che non e'
    fra quelli previsti torna al suo default: la pagina manda solo quelli, e
    chiunque altro non deve poter scrivere un pezzo di SQL in `sort`."""
    def one(name: str, default: str = "") -> str:
        return (query.get(name) or [default])[0]

    def number(name: str, default: int) -> int:
        try:
            return int(one(name, str(default)))
        except ValueError:
            return default

    show = one("show", SHOW[0])
    sort = one("sort", "Recently added")
    size = number("size", PAGE_SIZES[0])
    wanted = [q for q in one("quartiles").split(",") if q]
    return {
        "show": show if show in SHOW else SHOW[0],
        "list_id": number("list", 0) or None,
        "text": one("q").strip(),
        "quartiles": [q for q in wanted if q in jr.QUARTILES or q == NO_METRIC],
        "sort": sort if sort in ORDER_SQL else "Recently added",
        "page": max(1, number("page", 1)),
        "size": size if size in PAGE_SIZES else PAGE_SIZES[0],
    }


def _where(f: dict) -> tuple[str, list]:
    where, params = " WHERE 1=1", []
    if f["show"] == "To read":
        where += " AND a.is_read = 0"
    elif f["show"] == "Read":
        where += " AND a.is_read = 1"
    elif f["show"] == "Flagged ★":
        where += " AND a.is_flagged = 1"
    if f["text"]:
        where += " AND (a.title LIKE ? OR a.abstract LIKE ? OR a.pmid LIKE ?)"
        params.extend([f"%{f['text']}%"] * 3)
    if f["list_id"] is not None:
        where += " AND a.pmid IN (SELECT pmid FROM list_items WHERE list_id = ?)"
        params.append(f["list_id"])
    if f["quartiles"]:
        picked = [q for q in f["quartiles"] if q in jr.QUARTILES]
        bits = []
        if picked:
            bits.append(f"m.quartile IN ({', '.join('?' * len(picked))})")
            params.extend(picked)
        if NO_METRIC in f["quartiles"]:
            # senza aggancio, oppure agganciata a una rivista che nel file non
            # ha un quartile: per chi guarda sono la stessa cosa
            bits.append("(a.journal_metric_id IS NULL OR m.quartile IS NULL)")
        where += " AND (" + " OR ".join(bits) + ")"
    return where, params


def _safe_url(url: str) -> str:
    """Un indirizzo da mettere in un `href`, o niente. Gli indirizzi del full
    text arrivano da Unpaywall e da Semantic Scholar, cioe' da fuori: uno che
    non comincia per http non si mette in un link (`javascript:` e' un
    indirizzo anche lui)."""
    url = clean(url)
    return url if url.lower().startswith(("http://", "https://")) else ""


def _card(row: sqlite3.Row, rx, in_lists: list, pdf, folder: Path, libkey: str) -> dict:
    """Una riga dell'archivio come la pagina la disegna. I campi che finiscono
    in `_html` sono gia' escapati da `cards` e da `highlight`; tutti gli altri
    sono testo, e la pagina li scrive come testo."""
    pmid = str(row["pmid"])
    # Il nome della rivista: quello di SCImago se l'aggancio c'e', altrimenti
    # il titolo pulito, altrimenti quello che c'e' in archivio - che nei record
    # vecchi e' l'abbreviazione incollata al titolo esteso.
    journal = (clean(row["journal_scimago"]) or clean(row["journal_title"])
               or clean(row["journal"]))
    meta = [b for b in (clean(row["authors"]), journal,
                        clean(row["pub_date"]) or clean(row["year"]),
                        f"PMID {pmid}") if b]

    # il quartile per primo: e' quello che si cerca con l'occhio
    badges = cards.journal_badges(row)
    oa = cards.oa_badge(clean(row["oa_status"]))
    if oa:
        badges.append(oa)
    badges.extend(f"<span>{html.escape(t)}</span>" for t in cards.useful_types(row["pub_types"]))
    cites = cards.citation_badge(row["citation_count"], row["influential_citations"],
                                 row["citations_per_year"])
    if cites:
        badges.append(cites)

    links = [["PubMed", f"https://pubmed.ncbi.nlm.nih.gov/{urllib.parse.quote(pmid)}/"]]
    if libkey:
        links.append(["🔓 LibKey full text",
                      f"https://libkey.io/libraries/{urllib.parse.quote(libkey)}/"
                      f"{urllib.parse.quote(pmid)}"])
    doi = clean(row["doi"])
    if doi:
        links.append(["DOI", "https://doi.org/" + urllib.parse.quote(doi, safe="/")])
    # Unpaywall prima di Semantic Scholar: e' il servizio che fa solo questo,
    # e quando i due dissentono ha ragione lui
    free = _safe_url(row["oa_url"]) or _safe_url(row["oa_pdf_url"])
    if free:
        links.append(["Free full text", free])

    pdf_state, pdf_name = "", ""
    if pdf is not None:
        pdf_name = pdf["filename"]
        pdf_state = "here" if (folder / pdf_name).exists() else "missing"

    return {
        "pmid": pmid,
        "read": bool(row["is_read"]),
        "flagged": bool(row["is_flagged"]),
        "title_html": highlight.mark(clean(row["title"]) or "No title available", rx),
        "meta": " · ".join(meta),
        "badges_html": "".join(badges),
        # Il quartile del badge e' il migliore che la rivista ha in una
        # qualsiasi delle sue categorie. Qui c'e' il dettaglio.
        "categories": clean(row["categories"]),
        "links": links,
        "lists": [list_id for list_id, _ in in_lists],
        "pdf": pdf_state,
        "pdf_name": pdf_name,
        "free_url": free if pdf is None else "",
        "abstract_html": cards.abstract_html(row["abstract"], rx),
    }


def page(f: dict) -> dict:
    """Una pagina dell'archivio per questi filtri.

    Si carica una pagina sola: i filtri li applica la query, cosi' il totale e
    il numero di pagine contano solo quello che corrisponde."""
    settings = db.get_settings()
    where, params = _where(f)
    conn = db.get_connection()
    try:
        total = conn.execute(f"SELECT COUNT(*) {FROM}{where}", params).fetchone()[0]
        n_pages = max(1, -(-total // f["size"]))
        number = min(f["page"], n_pages)
        rows = conn.execute(
            "SELECT a.pmid, a.title, a.abstract, a.journal, a.journal_title, "
            "a.pub_date, a.year, a.doi, a.authors, a.pub_types, a.citation_count, "
            "a.influential_citations, a.citations_per_year, a.oa_pdf_url, "
            "a.s2_fetched_at, a.is_read, a.is_flagged, "
            "a.oa_status, a.oa_url, a.oa_fetched_at, "
            "m.quartile, m.sjr, m.cites_per_doc, m.categories, "
            "m.title AS journal_scimago "
            f"{FROM}{where} ORDER BY {ORDER_SQL[f['sort']]} LIMIT ? OFFSET ?",
            params + [f["size"], (number - 1) * f["size"]]).fetchall()
    finally:
        conn.close()

    pmids = [str(r["pmid"]) for r in rows]
    # In quali liste stanno gli articoli di QUESTA pagina, in una query sola:
    # chiederlo scheda per scheda sarebbe una query per articolo.
    membership = db.lists_for(pmids)
    pdfs = db.pdfs_for(pmids)
    folder = paths.pdf_folder(settings.get("pdf_folder") or "")
    libkey = (settings.get("libkey_library_id") or "").strip()
    # Si evidenzia quello che si cerca nella casella. Un PMID non e' un
    # termine: cercarne uno non accende niente.
    rx = (None if f["text"].isdigit() else
          highlight.pattern(highlight.terms_of(f["text"])))
    return {
        "total": total,
        "n_pages": n_pages,
        "page": number,
        "rows": [_card(r, rx, membership.get(str(r["pmid"]), []),
                       pdfs.get(str(r["pmid"])), folder, libkey) for r in rows],
        # si guarda s2_fetched_at, non citation_count: un lavoro troppo recente
        # per essere indicizzato da S2 resterebbe "da recuperare" per sempre
        "missing_citations": [str(r["pmid"]) for r in rows if not r["s2_fetched_at"]],
        # Unpaywall risponde per DOI: senza DOI non c'e' niente da chiedere
        "missing_oa": [str(r["pmid"]) for r in rows
                       if clean(r["doi"]) and not r["oa_fetched_at"]],
    }


def all_pmids(f: dict) -> list[str]:
    """Tutti i PMID che i filtri trovano, su tutte le pagine: per "Select all"."""
    where, params = _where(f)
    conn = db.get_connection()
    try:
        return [str(r[0]) for r in conn.execute(f"SELECT a.pmid {FROM}{where}", params)]
    finally:
        conn.close()


def state() -> dict:
    """Quello che la pagina deve sapere prima di chiedere gli articoli."""
    settings = db.get_settings()
    try:
        size = int(settings.get("page_size") or PAGE_SIZES[0])
    except ValueError:
        size = PAGE_SIZES[0]
    return {
        "lists": [{"id": r["id"], "name": r["name"], "note": r["note"] or "",
                   "n_items": r["n_items"], "n_unread": r["n_unread"],
                   "updated": str(r["updated_at"] or "")[:10]}
                  for r in db.list_lists()],
        "abstracts_open": settings.get("abstracts_open") == "1",
        "page_size": size if size in PAGE_SIZES else PAGE_SIZES[0],
        "show": SHOW, "sorts": list(ORDER_SQL), "page_sizes": PAGE_SIZES,
        "quartiles": jr.QUARTILES + [NO_METRIC],
    }


# ---------------------------------------------------------------------------
# le azioni
# ---------------------------------------------------------------------------

def attach_pdf(pmid: str, folder: Path, *, path: Path | None = None,
               data: bytes | None = None, source: str, move: bool = False) -> str | None:
    """Mette un PDF in libreria col nome della citazione. Ritorna l'errore da
    mostrare, o None se e' andata.

    Se l'articolo aveva gia' un PDF con un altro nome, il vecchio file si
    toglie: un articolo ha un PDF solo, e due copie nella cartella direbbero il
    contrario."""
    rec = db.article_row(pmid)
    if rec is None:
        return f"PMID {pmid} is not in the archive."
    name = library.filename_for(rec)
    old = db.pdfs_for([pmid]).get(str(pmid))
    try:
        if data is not None:
            name, digest, size = library.store_bytes(data, folder, name)
        else:
            name, digest, size = library.store(path, folder, name, move=move)
    except (library.LibraryError, OSError) as exc:
        return str(exc)
    if old and old["filename"] != name:
        (folder / old["filename"]).unlink(missing_ok=True)
    db.save_pdf(pmid, name, digest, size, source)
    return None


def _pmids(body: dict) -> list[str]:
    raw = body.get("pmids")
    if not isinstance(raw, list):
        raise BenchError("No articles given.")
    return [str(p).strip() for p in raw if str(p or "").strip()]


def act(action: str, body: dict) -> dict:
    """Una scrittura. Ogni azione ritorna quello che la pagina deve mostrare;
    quello che non va si dice con `BenchError`."""
    settings = db.get_settings()
    pmid = str(body.get("pmid") or "").strip()

    if action == "status":
        if body.get("field") not in ("is_read", "is_flagged"):
            raise BenchError("Unknown field.")
        db.set_status(pmid, body["field"], bool(body.get("value")))
        return {}

    if action == "membership":
        list_id = int(body.get("list_id") or 0)
        if db.get_list(list_id) is None:
            raise BenchError("That list does not exist any more.")
        if body.get("value"):
            db.add_to_list(list_id, [pmid], note="from screening")
        else:
            db.remove_from_list(list_id, pmid)
        return {}

    if action == "list/create":
        name = " ".join(str(body.get("name") or "").split())
        if not name:
            raise BenchError("A list needs a name.")
        if db.create_list(name, str(body.get("note") or "")) is None:
            raise BenchError(f"“{name}” is already the name of a list.")
        return {}

    if action == "list/update":
        list_id = int(body.get("id") or 0)
        if "name" in body:
            name = " ".join(str(body["name"] or "").split())
            if not name:
                raise BenchError("A list needs a name.")
            if not db.rename_list(list_id, name=name):
                raise BenchError(f"“{name}” is already the name of another list.")
        if "note" in body:
            db.rename_list(list_id, note=str(body["note"] or ""))
        return {}

    if action == "list/delete":
        db.delete_list(int(body.get("id") or 0))
        return {}

    if action == "delete":
        deleted, kept = db.delete_articles(_pmids(body))
        return {"deleted": deleted, "kept": kept}

    if action == "citations":
        pmids = _pmids(body)
        try:
            found = s2.enrich(pmids, api_key=(settings.get("s2_api_key") or "").strip())
        except s2.SemanticScholarError as exc:
            raise BenchError(f"Semantic Scholar unavailable: {exc}") from exc
        db.store_citations(found)
        return {"queried": len(found),
                "found": sum(1 for v in found.values() if v.get("s2_paper_id"))}

    if action == "open-access":
        email = ((settings.get("unpaywall_email") or "").strip()
                 or (settings.get("ncbi_email") or "").strip())
        if not email:
            raise BenchError("Set an email in the sidebar first (⚙️ Settings): "
                             "Unpaywall requires one in every request.")
        by_doi = {}
        for wanted in _pmids(body):
            row = db.article_row(wanted)
            if row is not None and clean(row["doi"]):
                by_doi[clean(row["doi"]).lower()] = wanted
        found = upw.enrich(list(by_doi), email, requests.Session())
        written = db.store_oa(found, by_doi)
        return {"checked": written,
                "free": sum(1 for r in found.values()
                            if r.get("oa_status") not in ("closed", "unknown"))}

    if action == "pdf/open":
        pdf = db.pdfs_for([pmid]).get(pmid)
        if pdf is None:
            raise BenchError("This article has no PDF.")
        missing = study.available()
        if missing:
            raise BenchError(missing)
        folder = paths.pdf_folder(settings.get("pdf_folder") or "")
        study.launch(None, folder / pdf["filename"],
                     settings.get("study_layout") or "lr", pmid=pmid)
        return {"message": "The reader opens in a separate window."}

    if action == "pdf/save":
        row = db.article_row(pmid)
        if row is None:
            raise BenchError(f"PMID {pmid} is not in the archive.")
        url = _safe_url(row["oa_url"]) or _safe_url(row["oa_pdf_url"])
        if not url:
            raise BenchError("No free copy is known for this article.")
        try:
            got = library.download(url, requests.Session())
        except library.LibraryError as exc:
            raise BenchError(str(exc)) from exc
        problem = attach_pdf(pmid, paths.pdf_folder(settings.get("pdf_folder") or ""),
                             data=got, source="open access")
        if problem:
            raise BenchError(problem)
        return {}

    if action == "prefs":
        values = {}
        if "abstracts_open" in body:
            values["abstracts_open"] = "1" if body["abstracts_open"] else "0"
        if body.get("page_size") in PAGE_SIZES:
            values["page_size"] = str(body["page_size"])
        if values:
            db.save_settings(values)
        return {}

    raise BenchError("Unknown action.")


# ---------------------------------------------------------------------------
# la pagina
# ---------------------------------------------------------------------------

def _palette(p: dict) -> str:
    return "".join(f"--{k}: {v};" for k, v in p.items())


def render_page(theme_name: str = "auto") -> str:
    """La pagina, coi colori dell'app e le misure scelte nelle impostazioni.
    `theme_name`: "light", "dark", o "auto" per seguire il sistema."""
    settings = db.get_settings()

    def size(key: str, default: float) -> float:
        try:
            return float(settings.get(key) or default)
        except ValueError:
            return default

    title_rem = size("title_font_rem", 1.35)
    reading_font = theme.READING_FONTS.get(settings.get("reading_font") or "serif",
                                           theme.READING_FONTS["serif"])
    style = (
        f":root {{ {_palette(theme.LIGHT)} --primary: {theme.PRIMARY}; "
        f"--ui-font: {theme.UI_FONT}; --summary-rem: {max(0.95, title_rem - 0.3):.2f}rem; }}\n"
        # `color-scheme` e' per i controlli che disegna il browser: senza, le
        # caselle e i menu restano bianchi sul fondo scuro
        f":root[data-theme=dark] {{ {_palette(theme.DARK)} color-scheme: dark; }}\n"
        f"@media (prefers-color-scheme: dark) {{ :root[data-theme=auto] "
        f"{{ {_palette(theme.DARK)} color-scheme: dark; }} }}\n"
        + cards.css(title_rem, size("reading_font_rem", 1.05), reading_font))
    if theme_name not in ("light", "dark"):
        theme_name = "auto"
    return (PAGE.read_text(encoding="utf-8")
            .replace("/*STYLE*/", style)
            .replace("%THEME%", theme_name))


# ---------------------------------------------------------------------------
# il server
# ---------------------------------------------------------------------------

class Bench:
    """Il server avviato: la porta che ha preso e il gettone di questo avvio."""

    def __init__(self, server: ThreadingHTTPServer, token: str):
        self.server = server
        self.token = token
        self.port = server.server_address[1]

    def url(self, theme_name: str = "auto", stamp: str = "") -> str:
        """L'indirizzo da mettere nell'iframe. `stamp` non lo legge nessuno:
        cambia quando cambiano le impostazioni che la pagina riceve solo
        all'apertura, cosi' l'iframe si ricarica."""
        query = urllib.parse.urlencode(
            {"t": self.token, "theme": theme_name, "v": stamp})
        return f"http://127.0.0.1:{self.port}/?{query}"

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def _handler(token: str):
    class Handler(BaseHTTPRequestHandler):
        server_version = "RadiowriterBench"

        def log_message(self, *args) -> None:   # niente righe nel terminale
            pass

        def _hosts(self) -> tuple[str, str]:
            port = self.server.server_address[1]
            return (f"127.0.0.1:{port}", f"localhost:{port}")

        def _refuse(self, code: int) -> None:
            self.send_response(code)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _send(self, code: int, body: bytes, kind: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            if kind.startswith("text/html"):
                # la pagina sta in un iframe dell'app e in nessun altro posto,
                # e non carica niente da fuori
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'none'; script-src 'unsafe-inline'; "
                    "style-src 'unsafe-inline'; connect-src 'self'; "
                    "frame-ancestors http://localhost:* http://127.0.0.1:*")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, data: dict, code: int = 200) -> None:
            self._send(code, json.dumps(data, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")

        def do_GET(self) -> None:
            if self.headers.get("Host") not in self._hosts():
                return self._refuse(403)
            url = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(url.query)
            if url.path == "/":
                given = (query.get("t") or [""])[0]
                if not secrets.compare_digest(given, token):
                    return self._refuse(403)
                return self._send(
                    200, render_page((query.get("theme") or ["auto"])[0]).encode("utf-8"),
                    "text/html; charset=utf-8")
            if not secrets.compare_digest(self.headers.get(TOKEN_HEADER) or "", token):
                return self._refuse(403)
            try:
                if url.path == "/api/state":
                    return self._json(state())
                if url.path == "/api/articles":
                    return self._json(page(filters_from(query)))
                if url.path == "/api/pmids":
                    return self._json({"pmids": all_pmids(filters_from(query))})
            except sqlite3.Error as exc:
                return self._json({"error": f"The archive could not be read: {exc}"}, 500)
            self._refuse(404)

        def do_POST(self) -> None:
            if self.headers.get("Host") not in self._hosts():
                return self._refuse(403)
            if not secrets.compare_digest(self.headers.get(TOKEN_HEADER) or "", token):
                return self._refuse(403)
            url = urllib.parse.urlparse(self.path)
            if not url.path.startswith("/api/"):
                return self._refuse(404)
            if (self.headers.get("Content-Type") or "").split(";")[0] != "application/json":
                return self._refuse(415)
            try:
                length = int(self.headers.get("Content-Length") or 0)
                if length > 4 * 1024 * 1024:
                    return self._refuse(413)
                body = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(body, dict):
                    raise ValueError
            except ValueError:
                return self._refuse(400)
            try:
                return self._json(act(url.path[len("/api/"):], body))
            except BenchError as exc:
                return self._json({"error": str(exc)}, 400)
            except (sqlite3.Error, ValueError, TypeError) as exc:
                return self._json({"error": f"Could not save the change: {exc}"}, 500)

    return Handler


_lock = threading.Lock()
_running: Bench | None = None


def start() -> Bench:
    """Avvia il server, o ritorna quello gia' avviato in questo processo.

    La porta la sceglie il sistema (porta 0): l'app si puo' lanciare due volte,
    su due porte, e i due banchi non devono contendersene una fissa."""
    global _running
    with _lock:
        if _running is None:
            token = secrets.token_urlsafe(32)
            server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(token))
            server.daemon_threads = True
            threading.Thread(target=server.serve_forever, daemon=True,
                             name="radiowriter-bench").start()
            _running = Bench(server, token)
        return _running
