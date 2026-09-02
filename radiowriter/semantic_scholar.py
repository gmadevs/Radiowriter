"""Arricchimento dei record PubMed con i dati di citazione di Semantic Scholar.

Endpoint usato: POST /graph/v1/paper/batch, che accetta fino a 500 id per
richiesta nella forma "PMID:12345678".

Limiti: senza API key la quota condivisa e' bassa (di fatto ~1 richiesta/sec),
quindi si va a lotti con pausa e backoff sul 429. Con una API key gratuita
(https://www.semanticscholar.org/product/api) il ritmo puo' salire.
"""

from __future__ import annotations

import time
from datetime import date, datetime, timezone

import requests

BATCH_URL = "https://api.semanticscholar.org/graph/v1/paper/batch"

FIELDS = "paperId,title,year,venue,citationCount,influentialCitationCount,externalIds,openAccessPdf"

BATCH_SIZE_NO_KEY = 100
BATCH_SIZE_WITH_KEY = 500
PAUSE_NO_KEY = 1.3
PAUSE_WITH_KEY = 0.15
MAX_RETRIES = 4


class SemanticScholarError(RuntimeError):
    pass


def citations_per_year(citation_count: int | None, year: str | int | None,
                       today: date | None = None) -> float | None:
    """Citazioni annue: normalizza il vantaggio dei lavori piu' vecchi."""
    if citation_count is None:
        return None
    try:
        y = int(str(year)[:4])
    except (TypeError, ValueError):
        return None
    age = max(1, (today or date.today()).year - y + 1)
    return round(citation_count / age, 2)


def enrich(
    pmids: list[str],
    api_key: str = "",
    session: requests.Session | None = None,
    progress=None,
) -> dict[str, dict]:
    """Ritorna una voce per OGNI pmid richiesto.

    Per i lavori non indicizzati da S2 (tipicamente i piu' recenti) i valori
    sono None ma `s2_fetched_at` e' valorizzato: cosi' il tentativo resta
    registrato e non lo si ripete a ogni apertura della pagina.
    """
    if not pmids:
        return {}

    session = session or requests.Session()
    headers = {"x-api-key": api_key} if api_key else {}
    size = BATCH_SIZE_WITH_KEY if api_key else BATCH_SIZE_NO_KEY
    pause = PAUSE_WITH_KEY if api_key else PAUSE_NO_KEY

    out: dict[str, dict] = {}
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for i in range(0, len(pmids), size):
        chunk = pmids[i : i + size]
        data = _post_batch(chunk, session, headers, pause)
        data = list(data) + [None] * (len(chunk) - len(data))
        # la risposta e' posizionale: stesso ordine degli id inviati, None se ignoto
        for pmid, item in zip(chunk, data):
            item = item or {}
            cc = item.get("citationCount")
            out[pmid] = {
                "s2_paper_id": item.get("paperId"),
                "citation_count": cc,
                "influential_citations": item.get("influentialCitationCount"),
                "citations_per_year": citations_per_year(cc, item.get("year")),
                "oa_pdf_url": (item.get("openAccessPdf") or {}).get("url"),
                "s2_fetched_at": now,
            }
        if progress:
            progress(min(i + size, len(pmids)), len(pmids))
        if i + size < len(pmids):
            time.sleep(pause)
    return out


def _post_batch(ids: list[str], session, headers: dict, pause: float) -> list:
    body = {"ids": [f"PMID:{p}" for p in ids]}
    delay = pause
    last_error = ""
    for attempt in range(MAX_RETRIES):
        try:
            resp = session.post(BATCH_URL, params={"fields": FIELDS}, json=body,
                                headers=headers, timeout=90)
        except requests.RequestException as exc:
            last_error = str(exc)
        else:
            if resp.status_code == 200:
                payload = resp.json()
                return payload if isinstance(payload, list) else []
            if resp.status_code == 400 and "no valid paper ids" in resp.text.lower():
                # nessun id del lotto e' noto a S2: non e' un errore, e'
                # semplicemente letteratura non ancora indicizzata
                return []
            if resp.status_code in (429, 503, 504):
                last_error = f"HTTP {resp.status_code} (rate limited)"
            else:
                # 400 = di solito un id malformato: inutile insistere
                raise SemanticScholarError(
                    f"Semantic Scholar HTTP {resp.status_code}: {resp.text[:200]}")
        if attempt < MAX_RETRIES - 1:
            delay *= 2
            time.sleep(delay)
    raise SemanticScholarError(f"Semantic Scholar is unreachable: {last_error}")
