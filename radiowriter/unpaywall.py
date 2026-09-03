"""Unpaywall: il full text legalmente libero, quando c'e'.

Si interroga per DOI e risponde se di quel lavoro esiste una copia aperta e
dove sta. Non e' la stessa cosa di LibKey, che porta al PDF attraverso
l'abbonamento della biblioteca: qui si parla di copie che chiunque puo' aprire,
anche da casa e anche fra dieci anni.

`oa_status` e' la parola di Unpaywall, e le parole significano cose diverse:

    gold    la rivista e' tutta aperta, l'articolo nasce libero
    hybrid  rivista a pagamento, ma questo articolo e' stato liberato (pagando)
    green   il PDF sta in un archivio istituzionale o in PubMed Central
    bronze  leggibile sul sito dell'editore ma senza licenza: oggi si', domani
            forse no
    closed  niente

L'email non e' un'autenticazione, e' cortesia obbligatoria: senza, l'API
risponde 422. Non ci sono chiavi e non c'e' registrazione.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import requests

API = "https://api.unpaywall.org/v2/"
TIMEOUT = 30

# Unpaywall dichiara 100.000 chiamate al giorno e non pubblica un limite al
# secondo. Dieci al secondo e' quello che si tiene un client educato.
PAUSE = 0.1

STATUS_LABELS = {
    "gold": "🔓 gold OA",
    "hybrid": "🔓 hybrid OA",
    "green": "🔓 green OA",
    "bronze": "🔓 bronze OA",
    "closed": "🔒 closed",
}


class UnpaywallError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def lookup(doi: str, email: str, session: requests.Session | None = None) -> dict:
    """Cosa sa Unpaywall di un DOI.

    Un DOI che non conosce non e' un errore: e' un lavoro senza copia aperta
    conosciuta, e va registrato come tale - altrimenti glielo si richiederebbe
    a ogni giro.
    """
    doi = (doi or "").strip().lower()
    if not doi:
        raise UnpaywallError("No DOI given.")
    if not (email or "").strip():
        raise UnpaywallError(
            "Unpaywall needs an email address in the query. Set one in the "
            "sidebar settings.")

    http = session or requests
    resp = http.get(f"{API}{doi}", params={"email": email.strip()}, timeout=TIMEOUT)
    if resp.status_code == 404:
        return {"doi": doi, "oa_status": "unknown", "oa_url": "",
                "oa_fetched_at": _now()}
    if resp.status_code == 422:
        raise UnpaywallError(
            "Unpaywall refused the email address. It has to be a real one.")
    resp.raise_for_status()

    data = resp.json() or {}
    best = data.get("best_oa_location") or {}
    status = (data.get("oa_status") or "").strip().lower()
    if not status:
        status = "gold" if data.get("is_oa") else "closed"
    return {
        "doi": doi,
        # il PDF se c'e', altrimenti la pagina: una pagina che si apre vale
        # piu' di un PDF che non esiste
        "oa_url": (best.get("url_for_pdf") or best.get("url") or "").strip(),
        "oa_status": status,
        "oa_fetched_at": _now(),
    }


def enrich(dois: list[str], email: str, session: requests.Session | None = None,
           progress=None) -> dict[str, dict]:
    """DOI -> quello che Unpaywall ne dice. Uno per volta: l'API non ha un
    endpoint a lotti, e ci si mette in coda educatamente.

    Un DOI che fa saltare la chiamata non ferma gli altri: si va avanti e a
    quello si ritenta la prossima volta.
    """
    http = session or requests.Session()
    out: dict[str, dict] = {}
    unique = [d for d in dict.fromkeys((d or "").strip().lower() for d in dois) if d]
    for i, doi in enumerate(unique, 1):
        try:
            out[doi] = lookup(doi, email, http)
        except (UnpaywallError, requests.RequestException, ValueError):
            # Questo DOI non si sa, gli altri si': si tira dritto. Chi non ha
            # risposto resta senza `oa_fetched_at`, quindi la prossima volta
            # rientra da solo fra quelli da chiedere.
            pass
        if progress:
            progress(i, len(unique))
        if i < len(unique):
            time.sleep(PAUSE)
    return out


def label(status: str) -> str:
    status = (status or "").strip().lower()
    return STATUS_LABELS.get(status, "")
