"""Portare via l'archivio, e rimetterlo su un altro computer.

Due formati, e sono due cose diverse.

**`.nbib` (MEDLINE)** e' l'esportazione di PubMed, la stessa che si scarica dal
loro sito. Contiene gli articoli e nient'altro: la rilegge questa app, la
rileggono Zotero, EndNote, Mendeley e chiunque altro. E' il formato da usare
per portarsi via la bibliografia, o per darla a qualcun altro.

Non contiene pero' niente di quello che hai fatto TU sopra quegli articoli:
letto, segnalato, in quale lista, in quale bozza. Quei campi in MEDLINE non
esistono, e inventarseli vorrebbe dire scrivere un file che si chiama MEDLINE
senza esserlo.

**`.json` (backup)** e' tutto il resto: gli articoli con il loro stato, le
liste, le bozze con la loro bibliografia, lo storico delle ricerche, le
citazioni gia' risolte. Serve a rimettere in piedi lo stesso archivio altrove.

Quello che NON ci finisce sono le impostazioni - email, chiave NCBI,
identificativo della biblioteca. Un file di backup gira: finisce in un
Dropbox, in una chiavetta, allegato a un messaggio. Le credenziali dentro
sarebbero una fuga in attesa di succedere, e riscriverle e' un minuto.

Le metriche delle riviste non ci sono per un'altra ragione: si rifanno dal file
SCImago in un secondo, e portarsi dietro trentamila righe che si rigenerano
sarebbe solo peso.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from radiowriter import db

FORMAT = "radiopaedia-screener-backup"
VERSION = 1


class BackupError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# MEDLINE
# ---------------------------------------------------------------------------

def to_medline(rows) -> str:
    """I blocchi MEDLINE degli articoli, uno dietro l'altro.

    Il blocco grezzo si salva da quando l'app esiste, quindi non c'e' niente da
    ricostruire: e' esattamente il testo che PubMed aveva mandato. I record
    entrati dall'API hanno un blocco equivalente, scritto da `pubmed._as_medline`.

    Righe vuote fra un record e l'altro, che e' come li separa PubMed e come il
    lettore se li aspetta.
    """
    blocks = []
    for row in rows:
        text = (row["raw_text"] or "").strip()
        if text:
            blocks.append(text.replace("\r\n", "\n"))
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def medline_filename(what: str = "archive") -> str:
    stamp = datetime.now().strftime("%Y%m%d")
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in what).strip("-")
    return f"pubmed-{safe or 'archive'}-{stamp}.nbib"


# ---------------------------------------------------------------------------
# backup completo
# ---------------------------------------------------------------------------

def bundle() -> dict:
    """Tutto l'archivio come dizionario, pronto per `json.dumps`."""
    conn = db.get_connection()
    try:
        def rows(sql, *params):
            return [dict(r) for r in conn.execute(sql, params)]

        lists = rows("SELECT id, name, note, created_at, updated_at FROM lists")
        for lst in lists:
            lst["items"] = rows(
                "SELECT pmid, note, added_at FROM list_items WHERE list_id = ? "
                "ORDER BY added_at", lst["id"])
            lst.pop("id")

        drafts = rows("SELECT id, title, body_md, top_heading, profile, "
                      "created_at, updated_at FROM drafts")
        for draft in drafts:
            draft["references"] = rows(
                "SELECT identifier, note, added_at FROM draft_refs "
                "WHERE draft_id = ? ORDER BY added_at", draft["id"])
            draft.pop("id")

        return {
            "format": FORMAT,
            "version": VERSION,
            "exported": _now(),
            # Le impostazioni NON ci sono: vedi il commento in cima al modulo.
            "articles": rows("SELECT * FROM articles"),
            "screened_pmids": [r["pmid"] for r in
                               rows("SELECT pmid FROM screened_pmids")],
            "lists": lists,
            "drafts": drafts,
            "searches": rows("SELECT terms, query, n_found, n_fetched, n_saved, "
                             "run_at FROM searches"),
            "citations": rows("SELECT * FROM citation_cache"),
        }
    finally:
        conn.close()


def to_json(data: dict) -> str:
    return json.dumps(data, indent=1, ensure_ascii=False)


def json_filename() -> str:
    return f"screener-backup-{datetime.now():%Y%m%d}.json"


def counts(data: dict) -> dict:
    return {
        "articles": len(data.get("articles") or []),
        "lists": len(data.get("lists") or []),
        "drafts": len(data.get("drafts") or []),
        "searches": len(data.get("searches") or []),
        "citations": len(data.get("citations") or []),
    }


def read_bundle(raw: bytes | str) -> dict:
    try:
        data = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackupError(f"This is not a readable JSON file: {exc}") from exc
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise BackupError(
            "This file is not a backup of this app. A backup has "
            f"\"format\": \"{FORMAT}\" as its first field.")
    if int(data.get("version") or 0) > VERSION:
        raise BackupError(
            f"The file was written by a newer version of the app "
            f"(format {data['version']}, this one reads up to {VERSION}).")
    return data


def restore(data: dict) -> dict:
    """Rimette dentro quello che nel database non c'e' gia'.

    Additivo, mai distruttivo: un archivio con dentro del lavoro non deve
    perderlo perche' qualcuno ha aperto un backup vecchio. Un articolo, una
    lista o una bozza che gia' esistono si saltano, e il conto lo dice.

    Gli articoli passano da `db.insert_articles`, cosi' si portano dietro anche
    l'aggancio alla rivista senza doverlo rifare a mano.
    """
    report = {"articles": 0, "lists": 0, "list_items": 0, "drafts": 0,
              "draft_refs": 0, "citations": 0, "screened": 0}

    articles = data.get("articles") or []
    if articles:
        added, _, _ = db.insert_articles(articles)
        report["articles"] = added

    conn = db.get_connection()
    try:
        c = conn.cursor()
        for pmid in data.get("screened_pmids") or []:
            c.execute("INSERT OR IGNORE INTO screened_pmids (pmid) VALUES (?)", (pmid,))
            report["screened"] += c.rowcount

        for record in data.get("citations") or []:
            fields = ("identifier", "citation", "title", "journal", "year",
                      "pmid", "doi", "error", "fetched_at")
            c.execute(
                f"INSERT OR IGNORE INTO citation_cache ({', '.join(fields)}) "
                f"VALUES ({', '.join('?' * len(fields))})",
                [record.get(f) for f in fields])
            report["citations"] += c.rowcount

        for entry in data.get("searches") or []:
            c.execute(
                "INSERT INTO searches (terms, query, n_found, n_fetched, n_saved, run_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [entry.get(k) for k in
                 ("terms", "query", "n_found", "n_fetched", "n_saved", "run_at")])
        conn.commit()
    finally:
        conn.close()

    for lst in data.get("lists") or []:
        list_id = db.create_list(lst.get("name") or "", lst.get("note") or "")
        if list_id is None:
            # una lista con quel nome c'e' gia': ci si aggiunge dentro, non si
            # crea un doppione dal nome indistinguibile
            existing = next((r for r in db.list_lists()
                             if r["name"] == (lst.get("name") or "").strip()), None)
            if existing is None:
                continue
            list_id = existing["id"]
        else:
            report["lists"] += 1
        pmids = [item.get("pmid") for item in (lst.get("items") or [])]
        report["list_items"] += db.add_to_list(list_id, pmids, note="from a backup")

    existing_titles = {r["title"] for r in db.list_drafts()}
    for draft in data.get("drafts") or []:
        title = (draft.get("title") or "Untitled article").strip()
        if title in existing_titles:
            continue
        draft_id = db.create_draft(
            title, body_md=draft.get("body_md") or "",
            top_heading=int(draft.get("top_heading") or 3),
            profile=draft.get("profile"))
        report["drafts"] += 1
        for ref in draft.get("references") or []:
            report["draft_refs"] += db.add_draft_refs(
                draft_id, [ref.get("identifier")], note=ref.get("note") or "")

    return report
