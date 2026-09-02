#!/usr/bin/env python3
"""Le metriche delle riviste, l'aggancio agli articoli e Unpaywall.

    python3 check_journals.py

Senza rete. Quello che si prova qui e' come si legge il file SCImago, come si
aggancia un articolo alla sua rivista e come si legge la risposta di Unpaywall -
non se i due servizi sono su, che e' affare loro.
"""

from __future__ import annotations

import os
import sys
import tempfile

_TMP_DB = os.path.join(tempfile.mkdtemp(prefix="radiopaedia-journals-"), "test.db")
os.environ["RADIOPAEDIA_DB"] = _TMP_DB

from radiowriter import db                     # noqa: E402
from radiowriter import journals as jr         # noqa: E402
from radiowriter import pubmed                 # noqa: E402
from radiowriter import unpaywall as upw       # noqa: E402

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


# ---------------------------------------------------------------------------
# leggere il file SCImago
# ---------------------------------------------------------------------------

print("\n--- il file ---")

is_("il numero all'europea diventa un numero", jr._number("104,065"), 104.065)
is_("il trattino vuol dire niente", jr._number("-"), None)
is_("e cosi' la cella vuota", jr._number(""), None)
is_("l'indice h e' intero", jr._integer("236"), 236)

is_("il titolo si riduce a come si confronta",
    jr.norm_title("Ca-A Cancer Journal for Clinicians"),
    "ca a cancer journal for clinicians")
is_("la e commerciale diventa 'and'",
    jr.norm_title("Head & Neck"), "head and neck")
is_("la punteggiatura di PubMed non conta",
    jr.norm_title("American journal of medical genetics. Part A"),
    jr.norm_title("American Journal of Medical Genetics, Part A"))
is_("l'ISSN perde il trattino e alza la X", jr.norm_issn("2296-858x"), "2296858X")

is_("le categorie si spacchettano col loro quartile",
    jr.categories_of("Hematology (Q1); Oncology (Q3)"),
    "[('Hematology', 'Q1'), ('Oncology', 'Q3')]")
is_("una categoria senza quartile non fa saltare niente",
    jr.categories_of("Radiology"), "[('Radiology', None)]")

is_("gli ISSN di un blocco MEDLINE si ritrovano",
    jr.issns_in_medline("IS  - 2296-858X (Print)\nIS  - 1664-2295 (Electronic)\n"),
    "['2296858X', '16642295']")
is_("...senza doppioni",
    jr.issns_in_medline("IS  - 2296-858X (Print)\nIS  - 2296-858X (Linking)\n"),
    "['2296858X']")
is_("il titolo esteso si ritrova nella riga JT",
    jr.title_in_medline("TA  - Eur J Radiol\nJT  - European journal of radiology\n"),
    "European journal of radiology")

path = jr.find_file()
if path is None:
    print("\n!!  nessun file scimagojr*.csv: il resto del controllo si salta")
    print(f"\n{checked} controlli, {failed} falliti")
    sys.exit(1 if failed else 0)

print(f"\n--- {path.name} ---")
rows = jr.read(path)
is_("il file si legge", len(rows) > 10000, "True")
is_("ogni riga ha un titolo normalizzato",
    all(r["norm_title"] for r in rows), "True")
is_("i quartili sono solo quelli che esistono",
    sorted({r["quartile"] for r in rows if r["quartile"]}), "['Q1', 'Q2', 'Q3', 'Q4']")
is_("gli ISSN sono tutti di otto caratteri",
    all(len(i) == 8 for r in rows for i in r["issns"]), "True")
is_("gli SJR sono numeri o niente",
    all(r["sjr"] is None or isinstance(r["sjr"], float) for r in rows), "True")


# ---------------------------------------------------------------------------
# l'aggancio
# ---------------------------------------------------------------------------

print("\n--- l'aggancio ---")

db.import_journal_metrics(rows)
status = db.journal_metrics_status()
is_("le riviste finiscono nel database", status["journals"], len(rows))

# Un articolo come lo scrive PubMed oggi: ISSN nella sua colonna.
db.insert_articles([{
    "pmid": "9101", "title": "Con ISSN", "journal": "European journal of radiology",
    "journal_title": "European journal of radiology", "issn": "0720048X",
}])
conn = db.get_connection()
got = conn.execute(
    "SELECT m.title, m.quartile FROM articles a JOIN journal_metrics m "
    "ON m.id = a.journal_metric_id WHERE a.pmid = '9101'").fetchone()
conn.close()
is_("l'ISSN aggancia la rivista giusta", got["title"], "European Journal of Radiology")
is_("...col suo quartile", got["quartile"], "Q1")

# Un articolo dell'archivio storico: niente ISSN in colonna, e nel campo
# `journal` l'abbreviazione incollata al titolo. L'ISSN sta nel blocco grezzo.
db.insert_articles([{
    "pmid": "9102", "title": "Vecchio stile",
    "journal": "Eur J Radiol European journal of radiology",
    "raw_text": ("PMID- 9102\nIS  - 0720-048X (Print)\n"
                 "TA  - Eur J Radiol\nJT  - European journal of radiology\n"),
}])
conn = db.get_connection()
old_row = conn.execute(
    "SELECT a.issn, a.journal_title, m.quartile FROM articles a "
    "LEFT JOIN journal_metrics m ON m.id = a.journal_metric_id "
    "WHERE a.pmid = '9102'").fetchone()
conn.close()
is_("un record vecchio si aggancia dal blocco MEDLINE", old_row["quartile"], "Q1")
is_("...e l'ISSN gli viene riempito", old_row["issn"], "0720048X")
is_("...e cosi' il titolo pulito", old_row["journal_title"],
    "European journal of radiology")

# Una rivista che in SCImago non c'e' non deve prendersi il quartile di
# un'altra: e' il caso in cui uno sbaglio non si vedrebbe.
db.insert_articles([{"pmid": "9103", "title": "Cureus", "journal": "Cureus",
                     "journal_title": "Cureus", "issn": "20408090"}])
conn = db.get_connection()
none_row = conn.execute(
    "SELECT journal_metric_id FROM articles WHERE pmid = '9103'").fetchone()
conn.close()
is_("una rivista non in SCImago resta senza metrica",
    none_row["journal_metric_id"], None)

status = db.journal_metrics_status()
is_("il conteggio degli agganciati e' giusto", status["matched"], 2)

by_issn, by_title = db.metrics_for(["0720048X"], [])
is_("le metriche si chiedono anche per un pugno di ISSN",
    by_issn["0720048X"]["quartile"], "Q1")
by_issn, by_title = db.metrics_for([], [jr.norm_title("European Journal of Radiology")])
is_("...e per titolo normalizzato",
    by_title[jr.norm_title("European Journal of Radiology")]["quartile"], "Q1")
is_("senza niente da chiedere non si chiede niente", db.metrics_for([], []), "({}, {})")

# ricaricare il file rifa' tutto senza perdere gli agganci
db.import_journal_metrics(rows)
matched, seen = db.match_journals()
is_("ricaricare il file e riagganciare ritrova gli stessi", matched, 2)


# ---------------------------------------------------------------------------
# l'ISSN che arriva da PubMed
# ---------------------------------------------------------------------------

print("\n--- pubmed ---")

parsed = pubmed.parse_medline_text(
    "PMID- 555\nTI  - Titolo\nIS  - 2296-858X (Print)\n"
    "IS  - 2296-858X (Electronic)\nTA  - Front Med (Lausanne)\n"
    "JT  - Frontiers in medicine\nDP  - 2026 Jan\n")[0]
is_("l'import MEDLINE tiene l'ISSN", parsed["issn"], "2296858X")
is_("...senza ripeterlo per ogni riga IS", parsed["issn"].count(";"), 0)
is_("...e il titolo e' quello esteso, non l'abbreviazione",
    parsed["journal"], "Frontiers in medicine")

packed = pubmed._pack("1", "T", "A", "J", "2026", "2026", "", [], [],
                      ["0720-048x", "0720-048X", "corto"])
is_("gli ISSN si normalizzano e non si ripetono", packed["issn"], "0720048X")


# ---------------------------------------------------------------------------
# unpaywall
# ---------------------------------------------------------------------------

print("\n--- unpaywall ---")


class FakeResponse:
    def __init__(self, payload, code=200):
        self._payload = payload
        self.status_code = code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError("non doveva arrivare qui")

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, payload, code=200):
        self.payload = payload
        self.code = code
        self.calls: list[dict] = []

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params})
        return FakeResponse(self.payload, self.code)


session = FakeSession({
    "is_oa": True, "oa_status": "green",
    "best_oa_location": {"url_for_pdf": "https://example.org/x.pdf",
                         "url": "https://example.org/x"},
})
got = upw.lookup("10.1000/ABC", "chi@esempio.it", session)
is_("il DOI si abbassa di maiuscole", got["doi"], "10.1000/abc")
is_("si prende il PDF quando c'e'", got["oa_url"], "https://example.org/x.pdf")
is_("lo stato e' quello che dice Unpaywall", got["oa_status"], "green")
is_("l'email va nella richiesta", session.calls[0]["params"]["email"], "chi@esempio.it")

session = FakeSession({"is_oa": True, "oa_status": "",
                       "best_oa_location": {"url": "https://example.org/x"}})
got = upw.lookup("10.1000/abc", "chi@esempio.it", session)
is_("senza PDF si ripiega sulla pagina", got["oa_url"], "https://example.org/x")
is_("senza stato ma aperto, si chiama gold", got["oa_status"], "gold")

session = FakeSession({"is_oa": False}, 200)
is_("chiuso e' chiuso", upw.lookup("10.1000/abc", "x@y.it", session)["oa_status"],
    "closed")

session = FakeSession({}, 404)
got = upw.lookup("10.1000/mai-visto", "x@y.it", session)
is_("un DOI che non conosce non e' un errore", got["oa_status"], "unknown")
is_("...e non promette un link", got["oa_url"], "")

try:
    upw.lookup("10.1000/abc", "", None)
    is_("senza email si rifiuta di chiamare", "chiamato", "rifiutato")
except upw.UnpaywallError:
    is_("senza email si rifiuta di chiamare", "rifiutato", "rifiutato")

try:
    upw.lookup("", "x@y.it", None)
    is_("senza DOI si rifiuta di chiamare", "chiamato", "rifiutato")
except upw.UnpaywallError:
    is_("senza DOI si rifiuta di chiamare", "rifiutato", "rifiutato")


class BoomSession:
    """Una chiamata che salta in aria non deve fermare le altre."""
    def __init__(self):
        self.n = 0

    def get(self, url, params=None, timeout=None):
        self.n += 1
        if self.n == 1:
            raise ValueError("risposta illeggibile")
        return FakeResponse({"is_oa": True, "oa_status": "gold",
                             "best_oa_location": {"url": "https://example.org/y"}})


upw.PAUSE = 0
found = upw.enrich(["10.1/uno", "10.1/due"], "x@y.it", BoomSession())
is_("un DOI che fallisce non porta giu' gli altri", list(found), "['10.1/due']")

is_("l'etichetta dello stato e' quella giusta", upw.label("gold"), "🔓 gold OA")
is_("uno stato sconosciuto non ha etichetta", upw.label("boh"), "")

db.store_oa({"10.1/uno": {"oa_status": "gold", "oa_url": "https://e.org/a",
                          "oa_fetched_at": "2026-09-02T00:00:00+00:00"}},
            {"10.1/uno": "9101"})
conn = db.get_connection()
saved = conn.execute("SELECT oa_status, oa_url FROM articles WHERE pmid='9101'").fetchone()
conn.close()
is_("quello che dice Unpaywall si salva", saved["oa_status"], "gold")
is_("...con il link", saved["oa_url"], "https://e.org/a")


# ---------------------------------------------------------------------------
# portare via l'archivio e rimetterlo
# ---------------------------------------------------------------------------

print("\n--- export e backup ---")

from radiowriter import backup                # noqa: E402

MEDLINE = """PMID- 7001
OWN - NLM
IS  - 0720-048X (Print)
TI  - Un articolo da esportare.
AB  - Con il suo abstract.
TA  - Eur J Radiol
JT  - European journal of radiology
DP  - 2024 Mar
AU  - Rossi M
PT  - Review
"""

parsed = pubmed.parse_medline_text(MEDLINE)
db.insert_articles(parsed)
db.set_status("7001", "is_flagged", True)
lid = db.create_list("Da portare via", "una nota")
db.add_to_list(lid, ["7001"])
draft_id = db.create_draft("Bozza da portare via", body_md="# Epidemiology\n")
db.add_draft_refs(draft_id, ["7001"], note="a mano")

rows = db.articles_for_export("all")
text = backup.to_medline(rows)
is_("l'export MEDLINE contiene il record", "PMID- 7001" in text, "True")
# non `[0]`: nell'archivio di prova ci sono anche i record delle prove di
# sopra, e il primo del file non e' quello appena inserito
reread = {r["pmid"]: r for r in pubmed.parse_medline_text(text)}
is_("...e si rilegge da solo", reread["7001"]["title"], "Un articolo da esportare.")
is_("...con il suo ISSN", reread["7001"]["issn"], "0720048X")
is_("l'export filtrato per segnalati prende solo quelli",
    [r["pmid"] for r in db.articles_for_export("flagged")], "['7001']")
is_("...e quello per lista pure",
    [r["pmid"] for r in db.articles_for_export("list", lid)], "['7001']")
is_("il nome del file dice cosa contiene",
    backup.medline_filename("Da portare via").startswith("pubmed-Da-portare-via-"),
    "True")

data = backup.bundle()
is_("il backup conta quello che c'e'", backup.counts(data)["articles"] >= 1, "True")
is_("...comprese le liste", backup.counts(data)["lists"], 1)
is_("...e le bozze", backup.counts(data)["drafts"] >= 1, "True")
is_("la lista si porta dietro i suoi articoli",
    [i["pmid"] for i in data["lists"][0]["items"]], "['7001']")
is_("la bozza si porta dietro la bibliografia",
    any(d["references"] for d in data["drafts"]), "True")

# Le impostazioni non devono uscire: un file di backup gira.
db.save_settings({"ncbi_email": "segreto@esempio.it", "ncbi_api_key": "CHIAVE123"})
blob = backup.to_json(backup.bundle())
is_("l'email non finisce nel backup", "segreto@esempio.it" in blob, "False")
is_("...e nemmeno la chiave API", "CHIAVE123" in blob, "False")

try:
    backup.read_bundle('{"hello": "world"}')
    is_("un file estraneo viene rifiutato", "accettato", "rifiutato")
except backup.BackupError:
    is_("un file estraneo viene rifiutato", "rifiutato", "rifiutato")

try:
    backup.read_bundle('{"format": "radiopaedia-screener-backup", "version": 99}')
    is_("un backup di una versione futura viene rifiutato", "accettato", "rifiutato")
except backup.BackupError:
    is_("un backup di una versione futura viene rifiutato", "rifiutato", "rifiutato")

# Il ripristino e' additivo: quello che c'e' non si tocca.
saved = backup.read_bundle(blob)
report = backup.restore(saved)
is_("rimettere un backup su se stesso non duplica gli articoli",
    report["articles"], 0)
is_("...ne' le liste", report["lists"], 0)
is_("...ne' le bozze", report["drafts"], 0)
is_("e la lista ha ancora un articolo solo", db.list_pmids(lid), "['7001']")

# Su un archivio vuoto invece rimette tutto.
import os as _os, tempfile as _tf                      # noqa: E402
_os.environ["RADIOPAEDIA_DB"] = _os.path.join(
    _tf.mkdtemp(prefix="radiopaedia-restore-"), "vuoto.db")
import importlib                                        # noqa: E402
importlib.reload(db)
importlib.reload(backup)
db.init_db()
report = backup.restore(saved)
is_("su un archivio vuoto il ripristino rimette gli articoli",
    report["articles"] >= 1, "True")
is_("...le liste", report["lists"], 1)
is_("...con dentro i loro articoli", report["list_items"], 1)
is_("...e le bozze con la bibliografia", report["draft_refs"] >= 1, "True")
is_("l'articolo ripristinato e' quello giusto",
    db.get_connection().execute(
        "SELECT title FROM articles WHERE pmid='7001'").fetchone()[0],
    "Un articolo da esportare.")

print(f"\n{checked} controlli, {failed} falliti")
sys.exit(1 if failed else 0)
