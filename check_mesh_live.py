#!/usr/bin/env python3
"""Ogni termine di vocabolario controllato di `strategies.py`, chiesto a PubMed.

    python3 check_mesh_live.py

Questo e' l'unico controllo della suite che usa la rete, ed e' per questo che
sta a parte: gli altri girano sempre, questo si lancia quando si toccano le
strategie o quando il MeSH cambia (una volta l'anno, a gennaio).

Serve perche' un descrittore inventato non da' zero risultati: PubMed lo mette
in errorlist. Un `"Clinical Relevanace"[Mesh]` scritto male passerebbe ogni
controllo offline e poi non troverebbe mai niente, in silenzio.

Ci vuole circa un minuto senza chiave NCBI, una ventina di secondi con.
"""

from __future__ import annotations

import sys
import time

import requests

from radiowriter import db
from radiowriter import strategies as stg

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"


def main() -> int:
    settings = db.get_settings()
    email = (settings.get("ncbi_email") or "").strip()
    api_key = (settings.get("ncbi_api_key") or "").strip()
    if not email:
        print("Manca l'email NCBI nelle impostazioni: le E-utilities la vogliono.")
        return 1

    terms: list[str] = []
    for entry in stg.STRATEGIES.values():
        for term in entry["mesh"]:
            if term not in terms:
                terms.append(term)
    print(f"{len(terms)} termini di vocabolario controllato da verificare.\n")

    session = requests.Session()
    pause = 0.11 if api_key else 0.35
    bad: list[str] = []

    for i, term in enumerate(terms, 1):
        params = {"db": "pubmed", "term": term, "retmax": 0, "retmode": "json",
                  "tool": "radiopaedia-lit-screener", "email": email}
        if api_key:
            params["api_key"] = api_key
        try:
            resp = session.get(ESEARCH, params=params, timeout=45)
            resp.raise_for_status()
            result = resp.json().get("esearchresult", {})
        except (requests.RequestException, ValueError) as exc:
            bad.append(term)
            print(f"  ERR {term}: {exc}")
        else:
            errors = result.get("errorlist") or {}
            count = int(result.get("count", 0))
            # count == 0 basta come sospetto: un descrittore vero, per raro che
            # sia, in MEDLINE qualcosa lo trova sempre.
            if count == 0 or errors.get("phrasesnotfound") or errors.get("fieldsnotfound"):
                bad.append(term)
                print(f"  NO  {term}   count={count} errorlist={errors}")
        if i % 25 == 0:
            print(f"  ...{i}/{len(terms)}")
        time.sleep(pause)

    print(f"\n{len(terms) - len(bad)} ok, {len(bad)} da sistemare")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
