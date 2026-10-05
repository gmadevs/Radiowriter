#!/usr/bin/env python3
"""Il banco dello Screening: il server e quello che risponde.

    python3 check_bench.py

Lo Screening non e' piu' una scheda Streamlit ma una pagina web servita da
`radiowriter/bench.py`, e `check_app.py` non la vede: guida Streamlit, non un
browser. Qui si prova il server com'e', con richieste vere su una porta vera,
contro un archivio usa e getta. Niente rete oltre 127.0.0.1.

Quello che NON si prova e' il JavaScript della pagina: i clic, il disegno delle
schede. Quello lo esercita `scripts/shots.py`, che apre un browser.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import urllib.error
import urllib.request

_TMP = tempfile.mkdtemp(prefix="radiowriter-bench-")
os.environ["RADIOPAEDIA_DB"] = os.path.join(_TMP, "test.db")
os.environ["RADIOWRITER_HOME"] = _TMP

from radiowriter import bench                   # noqa: E402
from radiowriter import db                      # noqa: E402
from radiowriter import journals as jr          # noqa: E402

db.init_db()
db.save_settings({"ncbi_email": "prova@esempio.it", "libkey_library_id": "77"})

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


server = bench.start()
BASE = f"http://127.0.0.1:{server.port}"


def call(path: str, body: dict | None = None, *, token: str | None = "ok",
         host: str | None = None, kind: str = "application/json",
         raw: bytes | None = None) -> tuple[int, dict | str]:
    """Una richiesta al banco. `token="ok"` manda quello giusto, None nessuno."""
    headers = {}
    if token is not None:
        headers[bench.TOKEN_HEADER] = server.token if token == "ok" else token
    if host:
        headers["Host"] = host
    data = None
    if body is not None or raw is not None:
        data = raw if raw is not None else json.dumps(body).encode()
        headers["Content-Type"] = kind
    req = urllib.request.Request(BASE + path, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            text, code, got = r.read().decode(), r.status, r.headers
    except urllib.error.HTTPError as exc:
        text, code, got = exc.read().decode(), exc.code, exc.headers
    call.headers = got
    try:
        return code, json.loads(text)
    except ValueError:
        return code, text


# ---------------------------------------------------------------------------
# chi puo' chiamarlo
# ---------------------------------------------------------------------------

print("\n--- chi puo' chiamarlo ---")

is_("il server ascolta solo su 127.0.0.1", server.server.server_address[0], "127.0.0.1")
is_("la pagina senza gettone non si apre", call("/", token=None)[0], 403)
is_("...e nemmeno con uno sbagliato", call("/?t=sbagliato", token=None)[0], 403)
code, page = call("/?t=" + server.token, token=None)
is_("col gettone si'", code, 200)
is_("...ed e' la pagina dello Screening", "Radiowriter - Screening" in page, "True")
is_("...che non carica niente da fuori",
    "default-src 'none'" in call.headers.get("Content-Security-Policy", ""), "True")
is_("...e si lascia mettere solo in una pagina locale",
    "frame-ancestors http://localhost:* http://127.0.0.1:*"
    in call.headers.get("Content-Security-Policy", ""), "True")
is_("un'API senza gettone e' rifiutata", call("/api/state", token=None)[0], 403)
is_("...e con uno sbagliato", call("/api/state", token="x" * 43)[0], 403)
is_("il gettone nell'indirizzo non vale per le API",
    call("/api/state?t=" + server.token, token=None)[0], 403)
is_("un Host che non e' questa macchina e' rifiutato (DNS rebinding)",
    call("/api/state", host="evil.example:%d" % server.port)[0], 403)
is_("...anche per la pagina",
    call("/?t=" + server.token, token=None, host="evil.example")[0], 403)
is_("localhost invece va bene",
    call("/api/state", host="localhost:%d" % server.port)[0], 200)
is_("una scrittura senza gettone e' rifiutata",
    call("/api/delete", {"pmids": ["1"]}, token=None)[0], 403)
is_("...e se non e' JSON anche (un form di un'altra pagina non passa)",
    call("/api/delete", raw=b"pmids=1", kind="application/x-www-form-urlencoded")[0], 415)
is_("un corpo che non e' un oggetto e' rifiutato", call("/api/delete", raw=b"[1]")[0], 400)
is_("un indirizzo che non esiste dice 404", call("/api/niente")[0], 404)
is_("un'azione che non esiste lo dice", call("/api/niente", {})[1],
    {"error": "Unknown action."})
is_("il gettone cambia a ogni avvio ed e' lungo", len(server.token) >= 40, "True")
is_("avviarlo due volte ritorna lo stesso server", bench.start() is server, "True")

# ---------------------------------------------------------------------------
# la pagina di articoli
# ---------------------------------------------------------------------------

print("\n--- gli articoli ---")

db.import_journal_metrics([{
    "title": "European Journal of Radiology",
    "norm_title": jr.norm_title("European Journal of Radiology"),
    "issns": ["0720048X"], "sjr": 1.075, "quartile": "Q1", "h_index": 140,
    "cites_per_doc": 4.0, "categories": "Radiology (Q1)", "country": "Netherlands",
    "publisher": "Elsevier",
}])
db.insert_articles([
    {"pmid": "9201", "title": "Con quartile e <script>alert(1)</script>",
     "abstract": "BACKGROUND: un ascesso <b>grande</b>. RESULTS: guarito.",
     "journal": "European journal of radiology",
     "journal_title": "European journal of radiology", "issn": "0720048X",
     "doi": "10.1000/abc<>", "authors": "Rossi M; Bianchi <i>L</i>", "year": "2024",
     "pub_types": "Review; Journal Article"},
    {"pmid": "9202", "title": "Senza quartile", "abstract": "parla di ascessi",
     "journal": "Cureus", "journal_title": "Cureus", "issn": "20408090",
     "year": "2020"},
    {"pmid": "9203", "title": "Terzo", "abstract": "altro", "year": "2022"},
])
db.match_journals()

code, st = call("/api/state")
is_("lo stato dice come si puo' filtrare", st["show"],
    "['All', 'To read', 'Read', 'Flagged ★']")
is_("...con i quartili e chi non ne ha", st["quartiles"][-1], "Not in SCImago")
is_("...e la misura di pagina salvata", st["page_size"], 10)

code, got = call("/api/articles")
is_("senza filtri ci sono tutti", (code, got["total"], len(got["rows"])), "(200, 3, 3)")
by_pmid = {r["pmid"]: r for r in got["rows"]}
first = by_pmid["9201"]
is_("il titolo arriva escapato: un tag scritto nel titolo resta testo",
    first["title_html"], "Con quartile e &lt;script&gt;alert(1)&lt;/script&gt;")
is_("...e cosi' l'abstract", "&lt;b&gt;grande&lt;/b&gt;" in first["abstract_html"], "True")
is_("...diviso nelle sue sezioni",
    first["abstract_html"].count('<span class="lbl">'), 2)
is_("il quartile si vede, col suo colore", 'class="q1"' in first["badges_html"], "True")
is_("...e porta lo SJR con se'", "Q1 · SJR 1.07" in first["badges_html"], "True")
is_("i tipi che non dicono niente non fanno un badge",
    "Journal Article" in first["badges_html"], "False")
is_("...quelli utili si'", "<span>Review</span>" in first["badges_html"], "True")
is_("una rivista senza metrica non stampa 'nan'",
    "nan" in json.dumps(by_pmid["9202"]).lower(), "False")
is_("...e non ha badge di quartile", by_pmid["9202"]["badges_html"], "")
is_("gli autori sono testo, non HTML: lo scrive la pagina",
    "Bianchi <i>L</i>" in first["meta"], "True")
is_("il link al DOI e' codificato",
    dict(first["links"])["DOI"], "https://doi.org/10.1000/abc%3C%3E")
is_("...e LibKey c'e' se la biblioteca e' impostata",
    dict(first["links"])["🔓 LibKey full text"], "https://libkey.io/libraries/77/9201")
is_("senza DOI non si offre di chiedere a Unpaywall",
    sorted(got["missing_oa"]), "['9201']")
is_("le citazioni mancano a tutti", sorted(got["missing_citations"]),
    "['9201', '9202', '9203']")

code, got = call("/api/articles?quartiles=Q1")
is_("il filtro per quartile restringe, e il conto con lui",
    (got["total"], [r["pmid"] for r in got["rows"]]), "(1, ['9201'])")
code, got = call("/api/articles?quartiles=Not+in+SCImago")
is_("...e sa chiedere quelli che SCImago non ha",
    sorted(r["pmid"] for r in got["rows"]), "['9202', '9203']")
code, got = call("/api/articles?q=ascess")
is_("la casella cerca nel titolo e nell'abstract",
    sorted(r["pmid"] for r in got["rows"]), "['9201', '9202']")
code, got = call("/api/articles?q=ascesso")
is_("...ed evidenzia quello che si cerca",
    "<mark>ascesso</mark>" in got["rows"][0]["abstract_html"], "True")
code, got = call("/api/articles?q=9203")
is_("un PMID si cerca ma non si evidenzia",
    (got["total"], "<mark>" in json.dumps(got)), "(1, False)")
code, got = call("/api/articles?sort=Year")
is_("si ordina per anno", [r["pmid"] for r in got["rows"]], "['9201', '9203', '9202']")
code, got = call("/api/articles?sort=a.pmid;DROP+TABLE+articles")
is_("un ordinamento che non esiste torna a quello di default",
    (code, got["total"]), "(200, 3)")
code, got = call("/api/articles?size=7&page=abc&list=x")
is_("valori senza senso tornano ai default", (code, got["page"], got["total"]),
    "(200, 1, 3)")

db.insert_articles([{"pmid": str(9300 + i), "title": f"Riempitivo {i}",
                     "abstract": "x"} for i in range(22)])
code, got = call("/api/articles?size=10&page=3")
is_("la paginazione conta le pagine", (got["total"], got["n_pages"], got["page"],
                                      len(got["rows"])), "(25, 3, 3, 5)")
code, got = call("/api/articles?size=10&page=99")
is_("una pagina oltre l'ultima e' l'ultima", got["page"], 3)
code, got = call("/api/pmids?q=Riempitivo")
is_("Select all prende tutte le pagine", len(got["pmids"]), 22)

# ---------------------------------------------------------------------------
# le azioni
# ---------------------------------------------------------------------------

print("\n--- le azioni ---")

is_("spuntare Read scrive subito",
    (call("/api/status", {"pmid": "9202", "field": "is_read", "value": True})[0],
     db.article_row("9202")["is_read"]), "(200, 1)")
code, got = call("/api/articles?show=Read")
is_("...e il filtro Read lo trova", [r["pmid"] for r in got["rows"]], "['9202']")
is_("un campo che non esiste non si scrive",
    call("/api/status", {"pmid": "9202", "field": "title", "value": "x"})[1],
    {"error": "Unknown field."})
call("/api/status", {"pmid": "9203", "field": "is_flagged", "value": True})
code, got = call("/api/articles?show=Flagged+%E2%98%85")
is_("Flagged funziona allo stesso modo", [r["pmid"] for r in got["rows"]], "['9203']")

is_("una lista si crea", call("/api/list/create", {"name": "  Da  leggere ", "note": "n"})[0], 200)
lists = {r["name"]: r for r in db.list_lists()}
is_("...col nome ripulito", list(lists), "['Da leggere']")
lid = lists["Da leggere"]["id"]
is_("due liste non possono avere lo stesso nome",
    call("/api/list/create", {"name": "Da leggere"})[1],
    {"error": "“Da leggere” is already the name of a list."})
is_("una lista senza nome non nasce",
    call("/api/list/create", {"name": "   "})[1], {"error": "A list needs a name."})
call("/api/membership", {"pmid": "9201", "list_id": lid, "value": True})
call("/api/membership", {"pmid": "9202", "list_id": lid, "value": True})
is_("spuntare la lista sulla scheda ce lo mette davvero",
    sorted(db.list_pmids(lid)), "['9201', '9202']")
code, got = call(f"/api/articles?list={lid}")
is_("...e il filtro In list li trova", sorted(r["pmid"] for r in got["rows"]),
    "['9201', '9202']")
is_("...con la lista scritta sulla scheda", got["rows"][0]["lists"], [lid])
call("/api/membership", {"pmid": "9202", "list_id": lid, "value": False})
is_("e toglierla lo toglie", db.list_pmids(lid), "['9201']")
is_("una lista che non c'e' piu' lo dice",
    call("/api/membership", {"pmid": "9201", "list_id": 9999, "value": True})[0], 400)
call("/api/list/update", {"id": lid, "name": "Ottimi"})
call("/api/list/update", {"id": lid, "note": "per il capitolo"})
row = db.get_list(lid)
is_("la lista si rinomina, e la nota a parte", (row["name"], row["note"]),
    "('Ottimi', 'per il capitolo')")
code, st = call("/api/state")
is_("lo stato conta gli articoli della lista e i non letti",
    (st["lists"][0]["n_items"], st["lists"][0]["n_unread"]), "(1, 1)")

is_("le preferenze si salvano",
    (call("/api/prefs", {"abstracts_open": True, "page_size": 50})[0],
     db.get_settings()["abstracts_open"], db.get_settings()["page_size"]),
    "(200, '1', '50')")
call("/api/prefs", {"page_size": 37})
is_("una misura di pagina che non esiste non si salva",
    db.get_settings()["page_size"], "50")
is_("...e lo stato le rilegge", call("/api/state")[1]["abstracts_open"], "True")

# eliminare: anche chi sta in una lista, non chi ha un PDF
db.save_pdf("9203", "terzo.pdf", "0" * 64, 10, "added")
code, got = call("/api/articles?q=Terzo")
is_("un PDF registrato ma sparito dalla cartella si dice",
    (got["rows"][0]["pdf"], got["rows"][0]["pdf_name"]), "('missing', 'terzo.pdf')")
code, got = call("/api/delete", {"pmids": ["9201", "9203", "non-esiste"]})
is_("eliminare toglie chi sta in una lista e lascia chi ha un PDF", got,
    {"deleted": 1, "kept": 1})
is_("...lo toglie dalla lista", db.list_pmids(lid), "[]")
is_("...e ne ricorda il PMID", "9201" in db.classify_pmids(["9201"])[1], "True")
is_("...l'articolo col PDF e' ancora li'", db.article_row("9203") is not None, "True")
is_("senza articoli non si elimina niente", call("/api/delete", {"pmids": "9202"})[0], 400)

is_("aprire un PDF che non c'e' lo dice",
    call("/api/pdf/open", {"pmid": "9202"})[1], {"error": "This article has no PDF."})
is_("salvare un PDF senza copia libera lo dice",
    call("/api/pdf/save", {"pmid": "9202"})[1],
    {"error": "No free copy is known for this article."})
conn = db.get_connection()
conn.execute("UPDATE articles SET oa_url = 'javascript:alert(1)' WHERE pmid = '9202'")
conn.commit()
conn.close()
code, got = call("/api/articles?q=Senza")
is_("un indirizzo che non e' http non diventa un link",
    [label for label, _ in got["rows"][0]["links"]], "['PubMed', '🔓 LibKey full text']")
is_("...e non si offre di scaricarlo", got["rows"][0]["free_url"], "")

db.save_settings({"ncbi_email": "", "unpaywall_email": ""})
is_("Unpaywall senza email lo dice invece di chiamare",
    "Unpaywall requires one" in call("/api/open-access", {"pmids": ["9202"]})[1]["error"],
    "True")

is_("cancellare la lista non cancella gli articoli",
    (call("/api/list/delete", {"id": lid})[0], db.list_lists(),
     db.article_row("9202") is not None), "(200, [], True)")

# ---------------------------------------------------------------------------
# la pagina
# ---------------------------------------------------------------------------

print("\n--- la pagina ---")

html_page = bench.render_page("dark")
is_("il tema chiesto e' scritto nella pagina", 'data-theme="dark"' in html_page, "True")
is_("un tema che non esiste diventa 'auto'",
    'data-theme="auto"' in bench.render_page('"><script>'), "True")
is_("i colori sono quelli dell'app", "--bg: #15181c" in html_page, "True")
is_("...e il CSS delle schede e' lo stesso dei risultati di ricerca",
    ".art-title" in html_page and ".abstract" in html_page, "True")
db.save_settings({"reading_font_rem": "1.4"})
is_("la misura del testo scelta nelle impostazioni arriva",
    "font-size: 1.4rem" in bench.render_page(), "True")
is_("niente segnaposto rimasti", "%THEME%" in html_page or "/*STYLE*/" in html_page,
    "False")
is_("la pagina non carica script ne' fogli da fuori",
    "src=" in html_page or "<link" in html_page, "False")
is_("l'indirizzo per l'iframe porta gettone e tema",
    server.url("light", "abc").startswith(
        f"http://127.0.0.1:{server.port}/?t={server.token}&theme=light"), "True")

print(f"\n{checked} controlli, {failed} falliti")
sys.exit(1 if failed else 0)
