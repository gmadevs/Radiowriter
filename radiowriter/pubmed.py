"""Ricerca su PubMed via E-utilities (esearch + efetch).

I filtri riproducono quelli della schermata PubMed:
    ultimi N anni, Full text, Books and Documents, Clinical Trial Phase IV,
    Consensus Statement, Evidence Synthesis, Guideline, Meta-Analysis,
    Multicenter Study, Network Meta-Analysis, Practice Guideline, Review,
    Scoping Review, Systematic Review, English, Humans.

Le etichette dei tipi sono state verificate contro l'API: si traducono tutte
senza finire in "phrases not found".
"""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from datetime import date

import requests

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
ESEARCH_URL = f"{EUTILS}/esearch.fcgi"
EFETCH_URL = f"{EUTILS}/efetch.fcgi"

TOOL_NAME = "radiopaedia-lit-screener"

# NCBI: 3 richieste/sec senza api key, 10 con api key
PAUSE_NO_KEY = 0.34
PAUSE_WITH_KEY = 0.11

# (etichetta mostrata, frammento di query) - l'ordine e' quello della schermata PubMed
ARTICLE_TYPES: list[tuple[str, str]] = [
    ("Books and Documents", "booksdocs[Filter]"),
    ("Clinical Trial, Phase IV", '"Clinical Trial, Phase IV"[pt]'),
    ("Consensus Statement", '"Consensus Statement"[pt]'),
    ("Evidence Synthesis", '"Evidence Synthesis"[pt]'),
    ("Guideline", '"Guideline"[pt]'),
    ("Meta-Analysis", '"Meta-Analysis"[pt]'),
    ("Multicenter Study", '"Multicenter Study"[pt]'),
    ("Network Meta-Analysis", '"Network Meta-Analysis"[pt]'),
    ("Practice Guideline", '"Practice Guideline"[pt]'),
    ("Review", '"Review"[pt]'),
    ("Scoping Review", '"Scoping Review"[pt]'),
    ("Systematic Review", '"Systematic Review"[pt]'),
]

DEFAULT_TYPE_LABELS = [label for label, _ in ARTICLE_TYPES]

FULLTEXT_CLAUSE = "fft[Filter]"
ENGLISH_CLAUSE = "english[la]"
HUMANS_CLAUSE = '"humans"[MeSH Terms]'


class PubMedError(RuntimeError):
    pass


def ncbi_params(email: str, api_key: str = "") -> dict:
    params = {"tool": TOOL_NAME}
    if email:
        params["email"] = email
    if api_key:
        params["api_key"] = api_key
    return params


def pause(api_key: str = "") -> float:
    return PAUSE_WITH_KEY if api_key else PAUSE_NO_KEY


def wrapped(text: str) -> bool:
    """Vero se TUTTA la stringa sta dentro un'unica coppia di parentesi.

    Guardare solo il primo e l'ultimo carattere non basta: `(A) OR (B)`
    comincia con una parentesi e finisce con una parentesi, ma le due non sono
    la stessa. Lasciarlo senza parentesi proprie significa che il primo filtro
    aggiunto in AND si lega al solo `(B)` - e la ricerca diventa un'altra,
    senza che niente lo segnali.
    """
    text = text.strip()
    if not (text.startswith("(") and text.endswith(")")):
        return False
    depth = 0
    for i, ch in enumerate(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i == len(text) - 1
    return False


def build_query(
    terms: str,
    *,
    type_labels: list[str] | None = None,
    years: int = 10,
    full_text: bool = True,
    english: bool = True,
    humans: bool = True,
    filters: list[str] | None = None,
    today: date | None = None,
) -> str:
    """Compone la query completa. `terms` accetta la sintassi PubMed nativa.

    `filters` sono clausole gia' scritte da mettere in AND - i filtri ISSG per
    linee guida e revisioni sistematiche arrivano di li'."""
    terms = (terms or "").strip()
    if not terms:
        raise PubMedError("No search terms given.")

    # se l'utente non ha gia' messo parentesi/operatori suoi, incapsuliamo
    clauses = [terms if wrapped(terms) else f"({terms})"]

    labels = DEFAULT_TYPE_LABELS if type_labels is None else type_labels
    fragments = [frag for label, frag in ARTICLE_TYPES if label in labels]
    if fragments:
        clauses.append("(" + " OR ".join(fragments) + ")")

    for extra in filters or []:
        extra = (extra or "").strip()
        if extra:
            clauses.append(extra if wrapped(extra) else f"({extra})")

    if full_text:
        clauses.append(FULLTEXT_CLAUSE)
    if english:
        clauses.append(ENGLISH_CLAUSE)
    if humans:
        clauses.append(HUMANS_CLAUSE)

    if years and years > 0:
        ref = today or date.today()
        try:
            start = ref.replace(year=ref.year - years)
        except ValueError:  # 29 febbraio
            start = ref.replace(month=2, day=28, year=ref.year - years)
        clauses.append(
            f'("{start:%Y/%m/%d}"[Date - Publication] : "3000"[Date - Publication])'
        )

    return " AND ".join(clauses)


def esearch(
    query: str,
    session: requests.Session,
    params: dict,
    max_results: int = 500,
    batch_size: int = 500,
    exclude: set[str] | None = None,
    progress=None,
    warn=None,
) -> tuple[int, list[str], int]:
    """Ritorna (totale su PubMed, PMID da scaricare, quanti esclusi).

    `exclude` sono i PMID gia' noti al database: si scartano QUI, prima di
    efetch e di Semantic Scholar, cosi' il budget di `max_results` va tutto su
    record effettivamente nuovi e non si spendono chiamate a vuoto.

    esearch tronca silenziosamente a retmax: per query ampie bisogna paginare
    con retstart, altrimenti si perdono risultati senza accorgersene.

    `warn` riceve le frasi che nell'indice PubMed non trovano niente. NON sono
    un errore, ed e' importante non trattarle come tale: PubMed le segnala solo
    quando il totale e' zero, e una qualunque delle stringhe pubblicate dell'ISSG
    ne contiene - `chemotreatment*` non ha corrispondenze in tutto MEDLINE.
    Sollevare li' vorrebbe dire che ogni ricerca a zero risultati fatta con un
    filtro per linee guida diventa un errore rosso, e la ragione vera - non c'e'
    niente su quell'argomento - resterebbe nascosta dietro un messaggio che
    parla di sintassi. Un campo inesistente invece e' davvero una query rotta,
    e quello continua a sollevare.
    """
    exclude = exclude or set()
    kept: list[str] = []
    seen: set[str] = set()
    excluded = 0
    total: int | None = None
    retstart = 0

    while True:
        resp = session.get(
            ESEARCH_URL,
            params={
                "db": "pubmed",
                "term": query,
                "retmax": batch_size,
                "retstart": retstart,
                "retmode": "json",
                "sort": "date",
                **{k: v for k, v in params.items() if not k.startswith("_")},
            },
            timeout=45,
        )
        resp.raise_for_status()
        result = resp.json().get("esearchresult", {})
        errors = result.get("errorlist") or {}
        if errors.get("fieldsnotfound"):
            raise PubMedError(
                "PubMed does not know these search fields: "
                + ", ".join(errors["fieldsnotfound"]))
        if errors.get("phrasesnotfound") and warn:
            warn(list(errors["phrasesnotfound"]))
        if total is None:
            total = int(result.get("count", 0))

        chunk = result.get("idlist", []) or []
        for pmid in chunk:
            if pmid in seen:
                continue
            seen.add(pmid)
            if pmid in exclude:
                excluded += 1
            elif len(kept) < max_results:
                kept.append(pmid)

        if progress:
            progress(len(kept), excluded, len(seen), total)

        retstart += batch_size
        if not chunk or len(kept) >= max_results or retstart >= total:
            break
        time.sleep(params.get("_pause", PAUSE_NO_KEY))

    return total or 0, kept, excluded


def efetch(
    pmids: list[str],
    session: requests.Session,
    params: dict,
    batch_size: int = 200,
    progress=None,
) -> list[dict]:
    records: list[dict] = []
    for i in range(0, len(pmids), batch_size):
        records.extend(_efetch_batch(pmids[i : i + batch_size], session, params))
        if progress:
            progress(min(i + batch_size, len(pmids)), len(pmids))
        if i + batch_size < len(pmids):
            time.sleep(params.get("_pause", PAUSE_NO_KEY))
    return records


def _text(el) -> str:
    return "".join(el.itertext()).strip() if el is not None else ""


def _efetch_batch(pmids: list[str], session: requests.Session, params: dict) -> list[dict]:
    if not pmids:
        return []
    payload = {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml",
               **{k: v for k, v in params.items() if not k.startswith("_")}}
    resp = session.post(EFETCH_URL, data=payload, timeout=120)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    records = []
    # PubmedArticle = articoli di rivista; PubmedBookArticle = voci "Books and Documents"
    for node in root.findall(".//PubmedArticle") + root.findall(".//PubmedBookArticle"):
        rec = _parse_article(node) if node.tag == "PubmedArticle" else _parse_book(node)
        if rec:
            records.append(rec)
    return records


def _authors_from(node, path: str) -> list[str]:
    authors = []
    for author in node.findall(path):
        last = author.find("LastName")
        initials = author.find("Initials")
        collective = author.find("CollectiveName")
        if last is not None and last.text:
            name = last.text
            if initials is not None and initials.text:
                name = f"{name} {initials.text}"
            authors.append(name)
        elif collective is not None and collective.text:
            authors.append(collective.text)
    return authors


def _abstract_from(node, path: str) -> str:
    parts = []
    for ab in node.findall(path):
        label = ab.attrib.get("Label")
        body = _text(ab)
        if not body:
            continue
        parts.append(f"{label}: {body}" if label else body)
    return "\n\n".join(parts)


def _parse_article(node) -> dict | None:
    pmid = _text(node.find(".//MedlineCitation/PMID"))
    if not pmid:
        return None

    title = _text(node.find(".//Article/ArticleTitle"))
    abstract = _abstract_from(node, ".//Article/Abstract/AbstractText")

    journal = _text(node.find(".//Article/Journal/Title")) or _text(
        node.find(".//Article/Journal/ISOAbbreviation"))

    year, pub_date = "", ""
    pd_node = node.find(".//Article/Journal/JournalIssue/PubDate")
    if pd_node is not None:
        year = _text(pd_node.find("Year"))
        month = _text(pd_node.find("Month"))
        if not year:
            medline = _text(pd_node.find("MedlineDate"))
            year = medline[:4]
            pub_date = medline
        else:
            pub_date = f"{year} {month}".strip()

    authors = _authors_from(node, ".//Article/AuthorList/Author")
    pub_types = [t for t in (_text(pt) for pt in
                 node.findall(".//Article/PublicationTypeList/PublicationType")) if t]

    # L'ISSN e' quello che aggancia l'articolo alle metriche della rivista: il
    # titolo che scrive PubMed e quello che scrive SCImago sono spesso la stessa
    # rivista scritta in due modi, l'ISSN e' lo stesso numero per entrambi.
    # `ISSNLinking` per primo: e' quello che NLM usa per tenere insieme la
    # versione a stampa e quella elettronica, cioe' proprio il caso in cui
    # altrimenti si mancherebbe la corrispondenza.
    issns = [_text(el) for el in
             node.findall(".//MedlineJournalInfo/ISSNLinking")
             + node.findall(".//Article/Journal/ISSN")]

    doi = ""
    for eloc in node.findall(".//Article/ELocationID"):
        if eloc.attrib.get("EIdType") == "doi":
            doi = _text(eloc)
            break
    if not doi:
        for aid in node.findall(".//PubmedData/ArticleIdList/ArticleId"):
            if aid.attrib.get("IdType") == "doi":
                doi = _text(aid)
                break

    return _pack(pmid, title, abstract, journal, pub_date, year, doi, authors,
                 pub_types, issns)


def _parse_book(node) -> dict | None:
    pmid = _text(node.find(".//BookDocument/PMID"))
    if not pmid:
        return None
    title = _text(node.find(".//BookDocument/ArticleTitle")) or _text(
        node.find(".//BookDocument/Book/BookTitle"))
    abstract = _abstract_from(node, ".//BookDocument/Abstract/AbstractText")
    journal = _text(node.find(".//BookDocument/Book/BookTitle"))
    year = _text(node.find(".//BookDocument/Book/PubDate/Year"))
    authors = _authors_from(node, ".//BookDocument/AuthorList/Author")
    pub_types = [t for t in (_text(pt) for pt in
                 node.findall(".//BookDocument/PublicationType")) if t] or ["Book/Document"]
    doi = ""
    for aid in node.findall(".//BookDocument/ArticleIdList/ArticleId"):
        if aid.attrib.get("IdType") == "doi":
            doi = _text(aid)
            break
    return _pack(pmid, title, abstract, journal, year, year, doi, authors,
                 pub_types, [])


def _pack(pmid, title, abstract, journal, pub_date, year, doi, authors, pub_types,
          issns=()) -> dict:
    seen: list[str] = []
    for raw in issns:
        issn = re.sub(r"[^0-9X]", "", (raw or "").upper())
        if len(issn) == 8 and issn not in seen:
            seen.append(issn)
    rec = {
        "pmid": pmid,
        "title": title or "No title available",
        "abstract": abstract or "No abstract available.",
        "journal": journal,
        "pub_date": pub_date or year,
        "year": year,
        "doi": (doi or "").strip(),
        "authors": "; ".join(authors),
        "pub_types": "; ".join(pub_types),
        "issn": "; ".join(seen),
        "journal_title": journal,
    }
    rec["raw_text"] = _as_medline(rec)
    return rec


def _as_medline(rec: dict) -> str:
    """Blocco in stile MEDLINE, per uniformita' con i record importati da file."""
    lines = [f"PMID- {rec['pmid']}", f"TI  - {rec['title']}"]
    if rec["abstract"]:
        lines.append(f"AB  - {rec['abstract']}")
    if rec["journal"]:
        lines.append(f"JT  - {rec['journal']}")
    if rec["pub_date"]:
        lines.append(f"DP  - {rec['pub_date']}")
    for a in (rec["authors"] or "").split("; "):
        if a:
            lines.append(f"AU  - {a}")
    for t in (rec["pub_types"] or "").split("; "):
        if t:
            lines.append(f"PT  - {t}")
    for issn in (rec.get("issn") or "").split("; "):
        if issn:
            lines.append(f"IS  - {issn}")
    if rec["doi"]:
        lines.append(f"LID - {rec['doi']} [doi]")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# parser dell'export MEDLINE incollato a mano (percorso di import gia' esistente)
# ---------------------------------------------------------------------------

def parse_medline_text(text: str) -> list[dict]:
    records = []
    for block in re.split(r"\n(?=PMID-\s*)", (text or "").strip()):
        if not block.strip():
            continue
        fields: dict[str, list[str]] = {}
        current = None
        for line in block.splitlines():
            m = re.match(r"^([A-Z]{2,4})\s*-\s*(.*)", line)
            if m:
                current = m.group(1)
                fields.setdefault(current, []).append(m.group(2).strip())
            elif current:
                fields[current][-1] += " " + line.strip()

        pmid = (fields.get("PMID") or [""])[0].strip()
        if not pmid:
            continue

        doi = ""
        for tag in ("LID", "AID"):
            for val in fields.get(tag, []):
                if "[doi]" in val and not doi:
                    doi = val.replace("[doi]", "").strip()

        journal = (fields.get("JT") or fields.get("TA") or fields.get("SO") or [""])[0]
        pub_date = (fields.get("DP") or [""])[0]
        # `IS  - 2296-858X (Print)`: si tiene il numero, non l'etichetta
        issns: list[str] = []
        for value in fields.get("IS", []):
            issn = re.sub(r"[^0-9X]", "", value.split()[0].upper() if value.split() else "")
            if len(issn) == 8 and issn not in issns:
                issns.append(issn)
        rec = {
            "pmid": pmid,
            "title": " ".join(fields.get("TI", [])) or "No title available",
            "abstract": " ".join(fields.get("AB", [])) or "No abstract available.",
            "journal": journal,
            "pub_date": pub_date,
            "year": pub_date[:4],
            "doi": doi,
            "authors": "; ".join(fields.get("AU", [])),
            "pub_types": "; ".join(fields.get("PT", [])),
            "issn": "; ".join(issns),
            "journal_title": journal,
            "raw_text": block,
        }
        records.append(rec)
    return records
