"""Accesso a pubmed_database.db: schema, migrazioni additive, impostazioni, CRUD.

Il database esiste gia' con migliaia di record: ogni migrazione qui dentro e'
puramente additiva (ALTER TABLE ADD COLUMN / CREATE TABLE IF NOT EXISTS), mai
distruttiva.
"""

from __future__ import annotations

import os
import sqlite3
import time
from datetime import datetime, timezone

from radiowriter import journals as jr
from radiowriter import paths

# Dove sta il file lo decide `paths`: accanto al codice se questa e'
# l'installazione storica, altrimenti nella cartella dei dati che il sistema
# operativo indica. `RADIOPAEDIA_DB` scavalca tutto ed e' quello che usano i
# test - `check_app.py` esegue l'app davvero, e l'app all'avvio fa pulizia
# degli articoli gia' letti: una suite che girasse sull'archivio vero lo
# modificherebbe a ogni lancio.
DB_PATH = paths.db_path()

# Colonne aggiunte dopo la prima versione dell'app (nome -> tipo SQL).
# Vengono create solo se mancanti, cosi' il DB storico resta valido.
EXTRA_ARTICLE_COLUMNS = {
    "authors": "TEXT",
    "year": "TEXT",
    "pub_types": "TEXT",
    "source_query": "TEXT",
    "citation_count": "INTEGER",
    "influential_citations": "INTEGER",
    "citations_per_year": "REAL",
    "s2_paper_id": "TEXT",
    "s2_fetched_at": "TEXT",
    "oa_pdf_url": "TEXT",
    # l'ISSN e' quello che aggancia l'articolo alle metriche della rivista;
    # `journal_title` e' il titolo pulito, che nei record vecchi il campo
    # `journal` non e' (li' c'e' l'abbreviazione incollata al titolo esteso)
    "issn": "TEXT",
    "journal_title": "TEXT",
    "journal_metric_id": "INTEGER",
    # Unpaywall: se il full text e' legalmente libero, e dove
    "oa_status": "TEXT",
    "oa_url": "TEXT",
    "oa_fetched_at": "TEXT",
}

# Il tipo di articolo Radiopaedia della bozza ("disease", "anatomy-bone", ...).
# Si tiene qui e non solo in sessione perche' e' una decisione sull'articolo,
# non sulla scheda aperta: da' la struttura dei titoli e va ritrovata domani.
EXTRA_DRAFT_COLUMNS = {
    "profile": "TEXT",
}

DEFAULT_SETTINGS = {
    "ncbi_email": os.environ.get("NCBI_EMAIL", ""),
    "ncbi_api_key": os.environ.get("NCBI_API_KEY", ""),
    "s2_api_key": os.environ.get("SEMANTIC_SCHOLAR_API_KEY", ""),
    "libkey_library_id": os.environ.get("LIBKEY_LIBRARY_ID", ""),
    "unpaywall_email": os.environ.get("UNPAYWALL_EMAIL", ""),
    "title_font_rem": "1.35",
    "page_size": "10",
}


# ---------------------------------------------------------------------------
# connessione
# ---------------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    # WAL: le scritture vanno in un log persistente invece di creare e cancellare
    # un file -journal a ogni transazione. Meno I/O sulla directory, meno lock.
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.DatabaseError:
        # WAL non c'e' su tutti i filesystem - una share di rete, certi volumi
        # montati - e li' sqlite rifiuta il PRAGMA. Non e' un guasto: si
        # continua col journal classico, che e' piu' lento e funziona sempre.
        pass
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def db_retry(fn, attempts: int = 4, delay: float = 0.15):
    """Riprova un'operazione fallita per errori transitori (I/O, lock).

    Su macOS con disco quasi pieno sqlite puo' restituire 'disk I/O error' in
    modo intermittente: un secondo tentativo di solito va a buon fine.
    """
    if attempts < 1:
        # Senza questo, `attempts=0` non esegue mai il ciclo e la funzione
        # torna None: chi ha chiamato crede che la scrittura sia andata.
        raise ValueError("db_retry needs at least one attempt")
    for i in range(attempts):
        try:
            return fn()
        except sqlite3.OperationalError:
            if i == attempts - 1:
                raise
            time.sleep(delay * (2 ** i))


# ---------------------------------------------------------------------------
# schema
# ---------------------------------------------------------------------------

def init_db() -> None:
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                pmid TEXT PRIMARY KEY,
                title TEXT,
                abstract TEXT,
                journal TEXT,
                pub_date TEXT,
                doi TEXT,
                raw_text TEXT,
                is_read INTEGER DEFAULT 0,
                is_flagged INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Registro dei PMID gia' letti ed eliminati: serve a non re-importarli
        c.execute("""
            CREATE TABLE IF NOT EXISTS screened_pmids (
                pmid TEXT PRIMARY KEY,
                screened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        # Storico delle ricerche, per rilanciare una query senza riscriverla
        c.execute("""
            CREATE TABLE IF NOT EXISTS searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                terms TEXT,
                query TEXT,
                n_found INTEGER,
                n_fetched INTEGER,
                n_saved INTEGER DEFAULT 0,
                run_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # --- metriche delle riviste (SCImago) -----------------------------
        # Il CSV sta fuori dal database e cambia una volta l'anno; qui dentro
        # ci finisce la sua copia, perche' filtrare per quartile dev'essere una
        # JOIN. Farlo in Python vorrebbe dire caricare trentamila righe a ogni
        # rerun e, peggio, non poter piu' paginare in SQL: il conto delle pagine
        # si fa sul totale filtrato, e il totale filtrato lo sa solo il database.
        c.execute("""
            CREATE TABLE IF NOT EXISTS journal_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                norm_title TEXT,
                sjr REAL,
                quartile TEXT,
                h_index INTEGER,
                cites_per_doc REAL,
                categories TEXT,
                country TEXT,
                publisher TEXT
            )
        """)
        # Una rivista ha piu' ISSN (stampa, elettronico, linking) e tutti
        # portano alla stessa riga: e' una tabella a parte, non una colonna.
        c.execute("""
            CREATE TABLE IF NOT EXISTS journal_issns (
                issn TEXT PRIMARY KEY,
                metric_id INTEGER NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_metrics_norm "
                  "ON journal_metrics(norm_title)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_metrics_quartile "
                  "ON journal_metrics(quartile)")

        # --- liste di lettura --------------------------------------------
        # Una lista e' un raccoglitore di articoli deciso da chi cerca: "quelli
        # da leggere per il capitolo sulle complicanze", "quelli buoni della
        # ricerca di ieri". Non e' uno stato dell'articolo come letto o
        # segnalato - quelli sono due soli e uguali per tutti - e un articolo
        # puo' stare in piu' liste insieme.
        c.execute("""
            CREATE TABLE IF NOT EXISTS lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                note TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS list_items (
                list_id INTEGER NOT NULL,
                pmid TEXT NOT NULL,
                note TEXT DEFAULT '',
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (list_id, pmid),
                FOREIGN KEY (list_id) REFERENCES lists(id) ON DELETE CASCADE
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_list_items_pmid ON list_items(pmid)")

        # --- bozze di articoli Radiopaedia -------------------------------
        c.execute("""
            CREATE TABLE IF NOT EXISTS drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                body_md TEXT DEFAULT '',
                top_heading INTEGER DEFAULT 3,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)
        # La bibliografia di UNA bozza. Non c'e' un numero qui dentro: il
        # numero e' l'ordine di prima comparsa nel testo e si calcola
        # all'export, altrimenti aggiungere una fonte a meta' articolo
        # obbligherebbe a riscrivere la tabella.
        c.execute("""
            CREATE TABLE IF NOT EXISTS draft_refs (
                draft_id INTEGER NOT NULL,
                identifier TEXT NOT NULL,
                note TEXT DEFAULT '',
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (draft_id, identifier),
                FOREIGN KEY (draft_id) REFERENCES drafts(id) ON DELETE CASCADE
            )
        """)
        # Le ricerche agganciate a una bozza: da dove viene la bibliografia
        c.execute("""
            CREATE TABLE IF NOT EXISTS draft_searches (
                draft_id INTEGER NOT NULL,
                search_id INTEGER NOT NULL,
                attached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (draft_id, search_id),
                FOREIGN KEY (draft_id) REFERENCES drafts(id) ON DELETE CASCADE
            )
        """)
        # Una citazione risolta vale per sempre: si chiede al worker una volta
        # sola per identificatore, non una volta per bozza.
        c.execute("""
            CREATE TABLE IF NOT EXISTS citation_cache (
                identifier TEXT PRIMARY KEY,
                citation TEXT,
                title TEXT,
                journal TEXT,
                year TEXT,
                pmid TEXT,
                doi TEXT,
                error TEXT,
                fetched_at TIMESTAMP
            )
        """)

        existing = {r["name"] for r in c.execute("PRAGMA table_info(articles)")}
        for col, coltype in EXTRA_ARTICLE_COLUMNS.items():
            if col not in existing:
                c.execute(f"ALTER TABLE articles ADD COLUMN {col} {coltype}")

        in_drafts = {r["name"] for r in c.execute("PRAGMA table_info(drafts)")}
        for col, coltype in EXTRA_DRAFT_COLUMNS.items():
            if col not in in_drafts:
                c.execute(f"ALTER TABLE drafts ADD COLUMN {col} {coltype}")

        # i record importati prima dell'aggiunta della colonna hanno year NULL:
        # lo si ricava da pub_date, altrimenti l'ordinamento per anno li scarta
        c.execute(
            "UPDATE articles SET year = substr(pub_date, 1, 4) "
            "WHERE (year IS NULL OR year = '') "
            "AND pub_date GLOB '[12][0-9][0-9][0-9]*'"
        )

        c.execute("CREATE INDEX IF NOT EXISTS idx_articles_read ON articles(is_read)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_articles_flagged ON articles(is_flagged)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_articles_created ON articles(created_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_articles_metric "
                  "ON articles(journal_metric_id)")
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# impostazioni
# ---------------------------------------------------------------------------

def get_settings() -> dict[str, str]:
    conn = get_connection()
    try:
        stored = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM settings")}
    finally:
        conn.close()
    # i valori salvati vincono; l'ambiente riempie solo i buchi
    return {**DEFAULT_SETTINGS, **{k: v for k, v in stored.items() if v is not None}}


def save_settings(values: dict[str, str]) -> None:
    def _write():
        conn = get_connection()
        try:
            conn.executemany(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                [(k, "" if v is None else str(v)) for k, v in values.items()],
            )
            conn.commit()
        finally:
            conn.close()

    db_retry(_write)


# ---------------------------------------------------------------------------
# articoli
# ---------------------------------------------------------------------------

def set_status(pmid: str, field: str, value: bool) -> None:
    if field not in ("is_read", "is_flagged"):
        raise ValueError(f"Campo non valido: {field}")

    def _write():
        conn = get_connection()
        try:
            conn.execute(f"UPDATE articles SET {field} = ? WHERE pmid = ?", (int(value), pmid))
            conn.commit()
        finally:
            conn.close()

    db_retry(_write)


def cleanup_read_articles() -> int:
    """Elimina gli articoli gia' letti conservandone il PMID in screened_pmids."""

    def _run():
        conn = get_connection()
        try:
            c = conn.cursor()
            # Chi sta in una lista non si tocca. Metterlo in una lista e'
            # una decisione di tenerlo, e spuntarlo come letto e' il modo
            # normale di finire di leggerlo: senza questa eccezione la lista
            # si svuoterebbe da sola proprio mentre la si usa.
            c.execute(
                "INSERT OR IGNORE INTO screened_pmids (pmid) "
                "SELECT pmid FROM articles WHERE is_read = 1 "
                "  AND pmid NOT IN (SELECT pmid FROM list_items)"
            )
            c.execute(
                "DELETE FROM articles WHERE is_read = 1 "
                "  AND pmid NOT IN (SELECT pmid FROM list_items)")
            removed = c.rowcount
            conn.commit()
            return removed
        finally:
            conn.close()

    return db_retry(_run)


ARTICLE_FIELDS = (
    "pmid", "title", "abstract", "journal", "pub_date", "doi", "raw_text",
    "authors", "year", "pub_types", "source_query",
    "citation_count", "influential_citations", "citations_per_year",
    "s2_paper_id", "s2_fetched_at", "oa_pdf_url",
    "issn", "journal_title", "oa_status", "oa_url", "oa_fetched_at",
)


def insert_articles(records: list[dict]) -> tuple[int, int, int]:
    """Inserisce record nuovi. Ritorna (aggiunti, scartati_gia_letti, gia_presenti)."""

    def _run():
        conn = get_connection()
        try:
            c = conn.cursor()
            screened = {r[0] for r in c.execute("SELECT pmid FROM screened_pmids")}
            fresh.clear()
            added = skipped_screened = 0
            considered = 0
            cols = ", ".join(ARTICLE_FIELDS)
            placeholders = ", ".join("?" * len(ARTICLE_FIELDS))
            for rec in records:
                pmid = str(rec.get("pmid") or "").strip()
                if not pmid:
                    continue
                considered += 1
                if pmid in screened:
                    skipped_screened += 1
                    continue
                values = [rec.get(f) for f in ARTICLE_FIELDS]
                values[0] = pmid
                c.execute(
                    f"INSERT OR IGNORE INTO articles ({cols}) VALUES ({placeholders})", values
                )
                if c.rowcount > 0:
                    added += 1
                    fresh.append(pmid)
            conn.commit()
            return added, skipped_screened, considered - added - skipped_screened
        finally:
            conn.close()

    fresh: list[str] = []
    result = db_retry(_run)
    # L'aggancio alla rivista si fa qui e non dal chiamante: gli articoli
    # entrano da tre porte diverse - una ricerca, il salvataggio in una lista,
    # l'import di un export MEDLINE - e ricordarselo in tutte e tre sarebbe un
    # modo di dimenticarsene in una.
    if fresh:
        try:
            match_journals(fresh)
        except sqlite3.Error:
            # senza quartile si vive; senza gli articoli no
            pass
    return result


def classify_pmids(pmids: list[str]) -> tuple[set[str], set[str]]:
    """Ritorna (gia_in_archivio, gia_screenati) per marcare i risultati di ricerca."""
    if not pmids:
        return set(), set()
    conn = get_connection()
    try:
        marks = ", ".join("?" * len(pmids))
        in_db = {r[0] for r in conn.execute(
            f"SELECT pmid FROM articles WHERE pmid IN ({marks})", pmids)}
        screened = {r[0] for r in conn.execute(
            f"SELECT pmid FROM screened_pmids WHERE pmid IN ({marks})", pmids)}
        return in_db, screened
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# storico ricerche
# ---------------------------------------------------------------------------

def log_search(terms: str, query: str, n_found: int, n_fetched: int) -> int:
    def _run():
        conn = get_connection()
        try:
            cur = conn.execute(
                "INSERT INTO searches (terms, query, n_found, n_fetched, run_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (terms, query, n_found, n_fetched,
                 datetime.now(timezone.utc).isoformat(timespec="seconds")),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    return db_retry(_run)


def bump_search_saved(search_id: int | None, n_saved: int) -> None:
    if not search_id or not n_saved:
        return

    def _run():
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE searches SET n_saved = COALESCE(n_saved, 0) + ? WHERE id = ?",
                (n_saved, search_id),
            )
            conn.commit()
        finally:
            conn.close()

    db_retry(_run)


def recent_searches(limit: int = 10) -> list[sqlite3.Row]:
    conn = get_connection()
    try:
        return list(conn.execute(
            "SELECT id, terms, query, n_found, n_fetched, n_saved, run_at "
            "FROM searches ORDER BY id DESC LIMIT ?", (limit,)))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# PMID gia' noti, da escludere dai risultati di ricerca
# ---------------------------------------------------------------------------

# chiave interna -> etichetta mostrata nella UI
EXCLUDE_MODES = {
    "db": "Everything already in the database",
    "decided": "Only those already decided (read, flagged, screened out)",
    "none": "Nothing: show every result",
}


def known_pmids(mode: str = "db") -> set[str]:
    """PMID da nascondere nei risultati di ricerca.

    - 'decided': screenati in passato + letti o segnalati in archivio, cioe' i
      lavori su cui una decisione c'e' gia'
    - 'db': i precedenti piu' tutto il resto dell'archivio; un record gia' in
      coda di screening non e' ricuperabile comunque (insert_articles lo
      ignorerebbe), mostrarlo di nuovo e' solo rumore
    """
    if mode == "none":
        return set()

    conn = get_connection()
    try:
        pmids = {r[0] for r in conn.execute("SELECT pmid FROM screened_pmids")}
        if mode == "decided":
            pmids |= {r[0] for r in conn.execute(
                "SELECT pmid FROM articles WHERE is_read = 1 OR is_flagged = 1")}
        else:
            pmids |= {r[0] for r in conn.execute("SELECT pmid FROM articles")}
        return pmids
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# open access (Unpaywall)
# ---------------------------------------------------------------------------

def store_oa(found: dict[str, dict], by_doi: dict[str, str]) -> int:
    """Scrive quello che Unpaywall ha detto. `by_doi` porta dal DOI al PMID,
    perche' Unpaywall risponde per DOI e l'archivio e' indicizzato per PMID."""
    def _run():
        conn = get_connection()
        try:
            written = 0
            for doi, rec in found.items():
                pmid = by_doi.get(doi)
                if not pmid:
                    continue
                conn.execute(
                    "UPDATE articles SET oa_status = ?, oa_url = ?, oa_fetched_at = ? "
                    "WHERE pmid = ?",
                    (rec.get("oa_status"), rec.get("oa_url"),
                     rec.get("oa_fetched_at"), pmid))
                written += 1
            conn.commit()
            return written
        finally:
            conn.close()

    return db_retry(_run)


def articles_for_export(scope: str = "all", list_id: int | None = None) -> list[sqlite3.Row]:
    """I record grezzi da mandare in un file MEDLINE, nell'ordine in cui sono
    entrati. `scope`: 'all', 'flagged', 'unread', 'read' o 'list'."""
    where, params = "", []
    if scope == "flagged":
        where = " WHERE is_flagged = 1"
    elif scope == "unread":
        where = " WHERE is_read = 0"
    elif scope == "read":
        where = " WHERE is_read = 1"
    elif scope == "list" and list_id is not None:
        where = " WHERE pmid IN (SELECT pmid FROM list_items WHERE list_id = ?)"
        params.append(list_id)
    conn = get_connection()
    try:
        return list(conn.execute(
            f"SELECT pmid, raw_text FROM articles{where} ORDER BY created_at, pmid",
            params))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# metriche delle riviste
# ---------------------------------------------------------------------------

def import_journal_metrics(rows: list[dict]) -> int:
    """Rifa' da capo la copia locale del file SCImago.

    Si svuota e si riscrive invece di aggiornare riga per riga: il file nuovo
    e' la verita' intera, e una rivista sparita dall'edizione di quest'anno
    deve sparire anche di qui - se restasse, mostrerebbe per sempre il quartile
    di un anno che non c'e' piu'. Gli articoli non si toccano: il loro aggancio
    si rifa' subito dopo con `match_journals`."""
    def _run():
        conn = get_connection()
        try:
            c = conn.cursor()
            c.execute("DELETE FROM journal_issns")
            c.execute("DELETE FROM journal_metrics")
            for row in rows:
                c.execute(
                    "INSERT INTO journal_metrics (title, norm_title, sjr, quartile, "
                    "  h_index, cites_per_doc, categories, country, publisher) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (row["title"], row["norm_title"], row["sjr"], row["quartile"],
                     row["h_index"], row["cites_per_doc"], row["categories"],
                     row["country"], row["publisher"]))
                metric_id = c.lastrowid
                for issn in row["issns"]:
                    # Un ISSN in due riviste non dovrebbe esistere; se il file
                    # ne ha uno, vince la prima, che e' quella meglio piazzata
                    # in classifica.
                    c.execute("INSERT OR IGNORE INTO journal_issns (issn, metric_id) "
                              "VALUES (?, ?)", (issn, metric_id))
            conn.commit()
            return len(rows)
        finally:
            conn.close()

    return db_retry(_run)


def journal_metrics_status() -> dict:
    """Quante riviste ci sono e quanti articoli sono agganciati."""
    conn = get_connection()
    try:
        return {
            "journals": conn.execute(
                "SELECT COUNT(*) FROM journal_metrics").fetchone()[0],
            "articles": conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0],
            "matched": conn.execute(
                "SELECT COUNT(*) FROM articles "
                "WHERE journal_metric_id IS NOT NULL").fetchone()[0],
        }
    finally:
        conn.close()


def match_journals(pmids: list[str] | None = None) -> tuple[int, int]:
    """Aggancia gli articoli alle riviste. Ritorna (agganciati, esaminati).

    `pmids` limita il lavoro a quelli appena inseriti; senza, si rifa' tutto -
    ed e' quello che serve dopo aver caricato un file SCImago nuovo.

    Per gli articoli vecchi l'ISSN e il titolo pulito non sono nelle loro
    colonne, perche' quelle colonne non esistevano quando sono entrati: si
    ricavano dal blocco MEDLINE grezzo, che l'app ha sempre salvato per intero.
    E' anche l'occasione per riempirle una volta per tutte.
    """
    def _run():
        conn = get_connection()
        try:
            c = conn.cursor()
            by_issn = {r[0]: r[1] for r in c.execute(
                "SELECT issn, metric_id FROM journal_issns")}
            by_title = {r[0]: r[1] for r in c.execute(
                "SELECT norm_title, id FROM journal_metrics WHERE norm_title <> ''")}
            if not by_issn and not by_title:
                return 0, 0

            if pmids:
                marks = ", ".join("?" * len(pmids))
                rows = c.execute(
                    f"SELECT pmid, journal, journal_title, issn, raw_text "
                    f"FROM articles WHERE pmid IN ({marks})", pmids).fetchall()
            else:
                rows = c.execute(
                    "SELECT pmid, journal, journal_title, issn, raw_text "
                    "FROM articles").fetchall()

            updates = []
            matched = 0
            for row in rows:
                issns = [i for i in (row["issn"] or "").split("; ") if i]
                title = row["journal_title"] or ""
                if not issns or not title:
                    raw = row["raw_text"] or ""
                    issns = issns or jr.issns_in_medline(raw)
                    title = title or jr.title_in_medline(raw) or (row["journal"] or "")

                metric_id = next((by_issn[i] for i in issns if i in by_issn), None)
                if metric_id is None:
                    metric_id = by_title.get(jr.norm_title(title))
                if metric_id is not None:
                    matched += 1
                updates.append(("; ".join(issns), title, metric_id, row["pmid"]))

            c.executemany(
                "UPDATE articles SET issn = ?, journal_title = ?, journal_metric_id = ? "
                "WHERE pmid = ?", updates)
            conn.commit()
            return matched, len(rows)
        finally:
            conn.close()

    return db_retry(_run)


def journal_metric(metric_id: int | None) -> sqlite3.Row | None:
    if metric_id is None:
        return None
    conn = get_connection()
    try:
        return conn.execute("SELECT * FROM journal_metrics WHERE id = ?",
                            (metric_id,)).fetchone()
    finally:
        conn.close()


def metrics_for(issns: list[str], titles: list[str]) -> tuple[dict, dict]:
    """(per ISSN, per titolo normalizzato) per un pugno di riviste.

    Serve ai risultati di una ricerca, che non sono ancora in archivio e quindi
    non hanno un aggancio salvato: si chiedono in blocco le poche riviste che
    compaiono in quella pagina, non le trentamila del file."""
    issns = [i for i in issns if i]
    titles = [t for t in titles if t]
    if not issns and not titles:
        return {}, {}
    conn = get_connection()
    try:
        by_issn: dict[str, sqlite3.Row] = {}
        by_title: dict[str, sqlite3.Row] = {}
        if issns:
            marks = ", ".join("?" * len(issns))
            for row in conn.execute(
                    f"SELECT i.issn AS k, m.* FROM journal_issns i "
                    f"JOIN journal_metrics m ON m.id = i.metric_id "
                    f"WHERE i.issn IN ({marks})", issns):
                by_issn[row["k"]] = row
        if titles:
            marks = ", ".join("?" * len(titles))
            for row in conn.execute(
                    f"SELECT * FROM journal_metrics WHERE norm_title IN ({marks})",
                    titles):
                by_title.setdefault(row["norm_title"], row)
        return by_issn, by_title
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# liste di lettura
# ---------------------------------------------------------------------------

def list_lists() -> list[sqlite3.Row]:
    """Le liste, con quanti articoli hanno dentro e quanti ne restano da leggere.

    Il conto dei non letti si fa con una JOIN su `articles` e non con un
    COUNT(*) su `list_items`: un articolo puo' essere in lista senza essere in
    archivio - se e' stato tolto dall'archivio prima che la lista lo
    proteggesse - e contarlo fra i "da leggere" prometterebbe una scheda che
    non c'e' piu'.
    """
    conn = get_connection()
    try:
        return list(conn.execute(
            "SELECT l.id, l.name, l.note, l.created_at, l.updated_at, "
            "  (SELECT COUNT(*) FROM list_items i WHERE i.list_id = l.id) AS n_items, "
            "  (SELECT COUNT(*) FROM list_items i JOIN articles a ON a.pmid = i.pmid "
            "     WHERE i.list_id = l.id AND a.is_read = 0) AS n_unread "
            "FROM lists l ORDER BY COALESCE(l.updated_at, l.created_at) DESC"))
    finally:
        conn.close()


def get_list(list_id: int) -> sqlite3.Row | None:
    conn = get_connection()
    try:
        return conn.execute("SELECT * FROM lists WHERE id = ?", (list_id,)).fetchone()
    finally:
        conn.close()


def create_list(name: str, note: str = "") -> int | None:
    """La lista nuova, o None se un'altra ha gia' quel nome.

    None e non un'eccezione: due liste con lo stesso nome sono
    indistinguibili in un menu a tendina, e chi chiama deve dirlo a chi
    scrive, non andare in errore."""
    name = " ".join((name or "").split())
    if not name:
        return None

    def _run():
        conn = get_connection()
        try:
            cur = conn.execute(
                "INSERT OR IGNORE INTO lists (name, note, updated_at) VALUES (?, ?, ?)",
                (name, note or "", _now()))
            conn.commit()
            return cur.lastrowid if cur.rowcount else None
        finally:
            conn.close()

    return db_retry(_run)


def rename_list(list_id: int, *, name: str | None = None,
                note: str | None = None) -> bool:
    """False se il nome nuovo e' gia' di un'altra lista."""
    sets, vals = [], []
    if name is not None:
        clean_name = " ".join(name.split())
        if not clean_name:
            return False
        sets.append("name = ?"); vals.append(clean_name)
    if note is not None:
        sets.append("note = ?"); vals.append(note)
    if not sets:
        return True
    sets.append("updated_at = ?"); vals.append(_now())
    vals.append(list_id)

    def _run():
        conn = get_connection()
        try:
            conn.execute(f"UPDATE lists SET {', '.join(sets)} WHERE id = ?", vals)
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    return db_retry(_run)


def delete_list(list_id: int) -> None:
    """Butta via la lista. Gli articoli restano in archivio: la lista era un
    modo di guardarli, non il posto in cui stavano."""
    def _run():
        conn = get_connection()
        try:
            conn.execute("DELETE FROM list_items WHERE list_id = ?", (list_id,))
            conn.execute("DELETE FROM lists WHERE id = ?", (list_id,))
            conn.commit()
        finally:
            conn.close()

    db_retry(_run)


def add_to_list(list_id: int, pmids: list[str], note: str = "") -> int:
    """Quanti ne sono entrati davvero: chi c'era gia' non conta."""
    def _run():
        conn = get_connection()
        try:
            added = 0
            for pmid in pmids:
                pmid = str(pmid or "").strip()
                if not pmid:
                    continue
                cur = conn.execute(
                    "INSERT OR IGNORE INTO list_items (list_id, pmid, note, added_at) "
                    "VALUES (?, ?, ?, ?)", (list_id, pmid, note or "", _now()))
                added += cur.rowcount
            conn.execute("UPDATE lists SET updated_at = ? WHERE id = ?", (_now(), list_id))
            conn.commit()
            return added
        finally:
            conn.close()

    return db_retry(_run)


def remove_from_list(list_id: int, pmid: str) -> None:
    def _run():
        conn = get_connection()
        try:
            conn.execute("DELETE FROM list_items WHERE list_id = ? AND pmid = ?",
                         (list_id, pmid))
            conn.execute("UPDATE lists SET updated_at = ? WHERE id = ?", (_now(), list_id))
            conn.commit()
        finally:
            conn.close()

    db_retry(_run)


def list_pmids(list_id: int) -> list[str]:
    conn = get_connection()
    try:
        return [r[0] for r in conn.execute(
            "SELECT pmid FROM list_items WHERE list_id = ? ORDER BY added_at, pmid",
            (list_id,))]
    finally:
        conn.close()


def lists_for(pmids: list[str]) -> dict[str, list[tuple[int, str]]]:
    """PMID -> [(id lista, nome lista)]. Una query sola per tutta la pagina:
    chiederlo scheda per scheda vorrebbe dire una query per articolo."""
    if not pmids:
        return {}
    conn = get_connection()
    try:
        marks = ", ".join("?" * len(pmids))
        out: dict[str, list[tuple[int, str]]] = {}
        for row in conn.execute(
                f"SELECT i.pmid, l.id, l.name FROM list_items i "
                f"JOIN lists l ON l.id = i.list_id "
                f"WHERE i.pmid IN ({marks}) ORDER BY l.name", pmids):
            out.setdefault(row[0], []).append((row[1], row[2]))
        return out
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# bozze di articoli
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def list_drafts() -> list[sqlite3.Row]:
    conn = get_connection()
    try:
        return list(conn.execute(
            "SELECT d.id, d.title, d.body_md, d.top_heading, d.profile, d.created_at, d.updated_at, "
            "  (SELECT COUNT(*) FROM draft_refs r WHERE r.draft_id = d.id) AS n_refs, "
            "  (SELECT COUNT(*) FROM draft_searches s WHERE s.draft_id = d.id) AS n_searches "
            "FROM drafts d ORDER BY COALESCE(d.updated_at, d.created_at) DESC"))
    finally:
        conn.close()


def get_draft(draft_id: int) -> sqlite3.Row | None:
    conn = get_connection()
    try:
        return conn.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
    finally:
        conn.close()


def create_draft(title: str, *, body_md: str = "", top_heading: int = 3,
                 profile: str | None = None) -> int:
    """Una bozza nuova. Gli argomenti dopo il titolo servono all'import, che
    arriva con la bozza gia' scritta: crearla vuota e poi salvarci sopra
    lascerebbe per un istante una bozza senza niente dentro, e se il salvataggio
    fallisse resterebbe cosi'."""
    def _run():
        conn = get_connection()
        try:
            cur = conn.execute(
                "INSERT INTO drafts (title, body_md, top_heading, profile, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (title.strip() or "Untitled article", body_md or "",
                 int(top_heading or 3), profile, _now()))
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    return db_retry(_run)


def save_draft(draft_id: int, *, title: str | None = None, body_md: str | None = None,
               top_heading: int | None = None, profile: str | None = None) -> None:
    sets, vals = [], []
    if title is not None:
        sets.append("title = ?"); vals.append(title.strip() or "Untitled article")
    if body_md is not None:
        sets.append("body_md = ?"); vals.append(body_md)
    if top_heading is not None:
        sets.append("top_heading = ?"); vals.append(int(top_heading))
    if profile is not None:
        sets.append("profile = ?"); vals.append(profile)
    if not sets:
        return
    sets.append("updated_at = ?"); vals.append(_now())
    vals.append(draft_id)

    def _run():
        conn = get_connection()
        try:
            conn.execute(f"UPDATE drafts SET {', '.join(sets)} WHERE id = ?", vals)
            conn.commit()
        finally:
            conn.close()

    db_retry(_run)


def delete_draft(draft_id: int) -> None:
    def _run():
        conn = get_connection()
        try:
            # niente ON DELETE CASCADE senza PRAGMA foreign_keys: si puliscono
            # le tabelle figlie a mano, cosi' vale su qualsiasi connessione
            conn.execute("DELETE FROM draft_refs WHERE draft_id = ?", (draft_id,))
            conn.execute("DELETE FROM draft_searches WHERE draft_id = ?", (draft_id,))
            conn.execute("DELETE FROM drafts WHERE id = ?", (draft_id,))
            conn.commit()
        finally:
            conn.close()

    db_retry(_run)


# ---------------------------------------------------------------------------
# bibliografia di una bozza
# ---------------------------------------------------------------------------

def draft_identifiers(draft_id: int) -> list[str]:
    conn = get_connection()
    try:
        return [r[0] for r in conn.execute(
            "SELECT identifier FROM draft_refs WHERE draft_id = ? ORDER BY added_at, identifier",
            (draft_id,))]
    finally:
        conn.close()


def draft_ref_rows(draft_id: int) -> list[sqlite3.Row]:
    """La bibliografia con le note, che e' quello che l'export deve portarsi
    via: `draft_identifiers` da' i soli identificatori e perderebbe da dove
    ognuno e' arrivato."""
    conn = get_connection()
    try:
        return list(conn.execute(
            "SELECT identifier, note FROM draft_refs WHERE draft_id = ? "
            "ORDER BY added_at, identifier", (draft_id,)))
    finally:
        conn.close()


def add_draft_refs(draft_id: int, identifiers: list[str], note: str = "") -> int:
    def _run():
        conn = get_connection()
        try:
            added = 0
            for ident in identifiers:
                ident = (ident or "").strip()
                if not ident:
                    continue
                cur = conn.execute(
                    "INSERT OR IGNORE INTO draft_refs (draft_id, identifier, note, added_at) "
                    "VALUES (?, ?, ?, ?)", (draft_id, ident, note, _now()))
                added += cur.rowcount
            conn.commit()
            return added
        finally:
            conn.close()

    return db_retry(_run)


def remove_draft_ref(draft_id: int, identifier: str) -> None:
    def _run():
        conn = get_connection()
        try:
            conn.execute("DELETE FROM draft_refs WHERE draft_id = ? AND identifier = ?",
                         (draft_id, identifier))
            conn.commit()
        finally:
            conn.close()

    db_retry(_run)


def flagged_articles() -> list[sqlite3.Row]:
    conn = get_connection()
    try:
        return list(conn.execute(
            "SELECT pmid, title FROM articles WHERE is_flagged = 1 "
            "ORDER BY created_at DESC"))
    finally:
        conn.close()


def list_articles(list_id: int) -> list[sqlite3.Row]:
    """Gli articoli di una lista, con il titolo. Solo quelli ancora in
    archivio: di uno tolto di li' non resterebbe che il PMID."""
    conn = get_connection()
    try:
        return list(conn.execute(
            "SELECT a.pmid, a.title FROM list_items i "
            "JOIN articles a ON a.pmid = i.pmid "
            "WHERE i.list_id = ? ORDER BY i.added_at, a.pmid", (list_id,)))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# ricerche agganciate
# ---------------------------------------------------------------------------

def attach_search(draft_id: int, search_id: int) -> None:
    def _run():
        conn = get_connection()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO draft_searches (draft_id, search_id, attached_at) "
                "VALUES (?, ?, ?)", (draft_id, search_id, _now()))
            conn.commit()
        finally:
            conn.close()

    db_retry(_run)


def detach_search(draft_id: int, search_id: int) -> None:
    def _run():
        conn = get_connection()
        try:
            conn.execute("DELETE FROM draft_searches WHERE draft_id = ? AND search_id = ?",
                         (draft_id, search_id))
            conn.commit()
        finally:
            conn.close()

    db_retry(_run)


def draft_search_list(draft_id: int) -> list[sqlite3.Row]:
    conn = get_connection()
    try:
        return list(conn.execute(
            "SELECT s.id, s.terms, s.query, s.n_found, s.n_fetched, s.n_saved, s.run_at "
            "FROM draft_searches ds JOIN searches s ON s.id = ds.search_id "
            "WHERE ds.draft_id = ? ORDER BY ds.attached_at DESC", (draft_id,)))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# cache delle citazioni
# ---------------------------------------------------------------------------

def cached_citations(identifiers: list[str]) -> dict[str, dict]:
    if not identifiers:
        return {}
    conn = get_connection()
    try:
        marks = ", ".join("?" * len(identifiers))
        return {r["identifier"]: dict(r) for r in conn.execute(
            f"SELECT * FROM citation_cache WHERE identifier IN ({marks})", identifiers)}
    finally:
        conn.close()


def store_citation(rec: dict) -> None:
    def _run():
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO citation_cache "
                "(identifier, citation, title, journal, year, pmid, doi, error, fetched_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(identifier) DO UPDATE SET "
                "  citation=excluded.citation, title=excluded.title, journal=excluded.journal, "
                "  year=excluded.year, pmid=excluded.pmid, doi=excluded.doi, "
                "  error=excluded.error, fetched_at=excluded.fetched_at",
                (rec["identifier"], rec.get("citation"), rec.get("title"), rec.get("journal"),
                 rec.get("year"), rec.get("pmid"), rec.get("doi"), rec.get("error"),
                 rec.get("fetched_at")))
            conn.commit()
        finally:
            conn.close()

    db_retry(_run)
