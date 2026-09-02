"""Dal markdown della bozza all'HTML che l'editor WYSIWYG di Radiopaedia accetta.

Tre problemi distinti, tenuti separati apposta:

1. L'editor e' WYSIWYG e non capisce il markdown: incollare testo semplice
   perde la formattazione. Quello che accetta e' HTML negli appunti (flavour
   text/html), quindi qui si produce HTML e la copia rich la fa il browser.

2. Le citazioni si scrivono `[@27859258]` - l'identificatore stesso, non un
   numero. Il numero non esiste finche' l'articolo non e' finito: aggiungere
   una fonte a meta' testo rinumera tutto quello che viene dopo. La
   numerazione 1..N si calcola all'export sull'ordine di prima comparsa,
   come in un articolo vero.

3. Il testo della citazione lo produce radiopaedia.work/cite, lo stesso
   worker dello userscript e del linter, cosi' quello che esce di qui e'
   gia' nella forma che quegli strumenti si aspettano.
"""

from __future__ import annotations

import html as html_mod
import json
import re
from datetime import datetime, timezone

import requests
from markdown_it import MarkdownIt

CITE_URL = "https://radiopaedia.work/cite"
CITE_TIMEOUT = 60
CITE_MAX_BYTES = 1024 * 1024

# Radiopaedia scrive 2,3 per una coppia e 2-4 da tre in su. Stessa costante
# dello userscript: cambiarla qui cambia solo questa app.
RANGE_FROM = 3

# I titoli di sezione di un articolo Radiopaedia sono h3, i sottotitoli h4.
# `#` nel markdown della bozza e' quindi h3, non h1.
TOP_HEADING = 3

# Una citazione, o piu' di seguito: `[@27859258]`, `[@10.1002/path.4843]`,
# `[@27859258; 10.1002/path.4843]`, o due token attaccati.
CITE_TOKEN = re.compile(r"\[@\s*([^\]]+?)\s*\]")
CITE_RUN = re.compile(r"\[@\s*[^\]]+?\s*\](?:[ \t]*\[@\s*[^\]]+?\s*\])*")


class CiteError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# identificatori
# ---------------------------------------------------------------------------

def normalise_identifier(raw: str) -> str:
    """Forma canonica di un identificatore: e' sia il token che scrivi nel
    markdown sia la chiave della cache, quindi le due cose non possono
    divergere."""
    s = (raw or "").strip()
    if not s:
        return ""
    # un URL PubMed vale il suo PMID: la stessa fonte non deve finire due
    # volte in bibliografia solo perche' l'hai incollata in due modi
    m = re.search(r"(?:pubmed\.ncbi\.nlm\.nih\.gov/|pubmed/|\bpmid[:\s]*)(\d{4,9})", s, re.I)
    if m:
        return m.group(1)
    if re.fullmatch(r"\d{4,9}", s):
        return s
    m = re.search(r"\b(10\.\d{4,9}/[^\s\"'<>]+)", s)
    if m:
        return m.group(1).rstrip(".,;)").lower()
    m = re.fullmatch(r"(?i)(pmc\d{4,9})", s)
    if m:
        return m.group(1).upper()
    return s


def identifier_kind(ident: str) -> str:
    if re.fullmatch(r"\d{4,9}", ident):
        return "PMID"
    if ident.lower().startswith("10."):
        return "DOI"
    if re.fullmatch(r"(?i)pmc\d{4,9}", ident):
        return "PMCID"
    if re.fullmatch(r"(?i)(978|979)?[\d-]{9,17}[\dx]", ident.replace(" ", "")):
        return "ISBN"
    if ident.lower().startswith(("http://", "https://")):
        return "URL"
    return "search"


# ---------------------------------------------------------------------------
# il worker delle citazioni
# ---------------------------------------------------------------------------

def _deep_find(node, key: str, depth: int = 0):
    """Livewire tagga gli array mentre serializza - `[valore, {"s":"arr"}]` -
    quindi si cerca per chiave invece di scendere un percorso che un
    aggiornamento di versione sposterebbe."""
    if depth > 12:
        return None
    if isinstance(node, dict):
        if key in node:
            return node
        for v in node.values():
            found = _deep_find(v, key, depth + 1)
            if found:
                return found
    elif isinstance(node, list):
        for v in node:
            found = _deep_find(v, key, depth + 1)
            if found:
                return found
    return None


def _snapshot(page: str) -> dict | None:
    m = re.search(r'wire:snapshot="([^"]*)"', page)
    if not m:
        return None
    try:
        return json.loads(html_mod.unescape(m.group(1))).get("data") or {}
    except (json.JSONDecodeError, AttributeError):
        return None


def fetch_citation(identifier: str, session: requests.Session | None = None) -> dict:
    """Interroga radiopaedia.work/cite. Ritorna sempre un dict: `citation` e'
    None quando il worker non ha saputo rispondere, e in quel caso `error`
    dice perche'."""
    session = session or requests.Session()
    try:
        resp = session.get(
            CITE_URL, params={"search": identifier}, timeout=CITE_TIMEOUT,
            headers={"User-Agent": "radiopaedia-draft-editor/1.0"},
        )
    except requests.RequestException as exc:
        raise CiteError(f"The citation tool could not be reached: {exc}") from exc

    if resp.status_code >= 400:
        raise CiteError(f"The citation tool answered {resp.status_code}.")
    if len(resp.content) > CITE_MAX_BYTES:
        raise CiteError("That answer was not a page.")

    data = _snapshot(resp.text)
    if data is None:
        raise CiteError("The citation tool answered with a page this app could not read.")

    meta = _deep_find(data.get("result"), "title") or {}
    citation = data.get("citation")
    citation = citation.strip() if isinstance(citation, str) and citation.strip() else None

    # Il nodo `meta` del worker e' intermittente: la stessa richiesta a
    # distanza di un'ora torna una volta piena e una volta vuota, mentre la
    # citazione arriva sempre. Siccome DOI e PMID stanno DENTRO la citazione,
    # nei suoi link, si leggono di li' e `meta` resta un di piu'. Da questi
    # due identificatori dipende l'accorpamento delle reference doppie, che
    # non puo' funzionare a intermittenza.
    from_text = identifiers_in(citation or "")

    return {
        "identifier": identifier,
        "citation": citation,
        "error": (data.get("error") or "").strip() or None,
        "title": (meta.get("title") or "").strip() or None,
        "journal": (meta.get("journal") or "").strip() or None,
        "year": (str(meta["year"]) if meta.get("year") is not None
                 else from_text.get("year")),
        "pmid": (str(meta["pmid"]) if meta.get("pmid") is not None
                 else from_text.get("pmid")),
        "doi": ((meta.get("doi") or "").lower() or None) or from_text.get("doi"),
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


# Gli identificatori come compaiono nel testo di una citazione gia' formattata.
# Stessi pattern dello userscript, che li legge dalle reference dell'articolo.
CITATION_IDS = {
    "pmid": re.compile(r"(?:pubmed\.ncbi\.nlm\.nih\.gov/|pubmed/|\bpmid[:\s]*)(\d{4,9})", re.I),
    "pmcid": re.compile(r"\b(pmc\d{4,9})\b", re.I),
    "doi": re.compile(r"\b(10\.\d{4,9}/[^\s\"'<>)]+)"),
    # Vancouver: "… J Pathol. 2017;241(2):294-309."
    "year": re.compile(r"\b((?:19|20)\d{2})\s*[;:]"),
}


def identifiers_in(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for kind, pattern in CITATION_IDS.items():
        hit = pattern.search(text or "")
        if not hit:
            continue
        val = hit.group(1)
        out[kind] = val.rstrip(".,;)").lower() if kind == "doi" else val
    return out


# ---------------------------------------------------------------------------
# numerazione
# ---------------------------------------------------------------------------

def cited_identifiers(md: str) -> list[str]:
    """Gli identificatori citati nel testo, nell'ordine di prima comparsa.
    Questo ordine E' la numerazione dell'articolo."""
    seen: list[str] = []
    known: set[str] = set()
    for token in CITE_TOKEN.finditer(md or ""):
        for part in re.split(r"[;\n]", token.group(1)):
            ident = normalise_identifier(part.lstrip("@"))
            if ident and ident not in known:
                known.add(ident)
                seen.append(ident)
    return seen


# Ordine di preferenza fra identificatori che indicano la stessa opera: la
# strada PubMed produce la citazione piu' ricca (doi + link Pubmed), che e'
# la forma in cui Radiopaedia scrive le sue reference.
KIND_RANK = {"PMID": 0, "PMCID": 1, "DOI": 2, "ISBN": 3, "URL": 4, "search": 5}


def work_key(ident: str, citations: dict[str, dict] | None = None) -> str:
    """Che OPERA e' questa, al di la' di come e' stata scritta.

    Lo stesso lavoro citato una volta col PMID e una col DOI sono due token
    diversi ma una reference sola: numerarli separatamente metterebbe due
    volte lo stesso paper in bibliografia, con due numeri, ed e' un errore
    che in un articolo si nota. Appena il worker ha risposto sappiamo il DOI
    e il PMID di entrambi, e da li' si accorpano."""
    rec = (citations or {}).get(ident) or {}
    if rec.get("doi"):
        return "doi:" + str(rec["doi"]).lower()
    if rec.get("pmid"):
        return "pmid:" + str(rec["pmid"])
    return "id:" + ident


def numbering(md: str, citations: dict[str, dict] | None = None) -> dict[str, int]:
    """identificatore -> numero di reference, per ordine di prima comparsa.
    Identificatori che indicano la stessa opera condividono il numero."""
    numbers: dict[str, int] = {}
    by_work: dict[str, int] = {}
    for ident in cited_identifiers(md):
        key = work_key(ident, citations)
        if key not in by_work:
            by_work[key] = len(by_work) + 1
        numbers[ident] = by_work[key]
    return numbers


def merged_groups(numbers: dict[str, int]) -> dict[int, list[str]]:
    """I numeri a cui corrisponde piu' di un identificatore: da mostrare, cosi'
    chi scrive sa che i due token che ha usato sono finiti sulla stessa riga."""
    groups: dict[int, list[str]] = {}
    for ident, n in numbers.items():
        groups.setdefault(n, []).append(ident)
    return {n: sorted(v) for n, v in groups.items() if len(v) > 1}


def marker_text(numbers: list[int]) -> str:
    """I numeri, ordinati, deduplicati, con le sequenze consecutive chiuse in
    intervalli. Unico posto in cui si scrive il testo di un marker."""
    nums = sorted({n for n in numbers if isinstance(n, int) and n > 0})
    parts: list[str] = []
    i = 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        if j - i + 1 >= RANGE_FROM:
            parts.append(f"{nums[i]}-{nums[j]}")
        else:
            parts.extend(str(nums[k]) for k in range(i, j + 1))
        i = j + 1
    return ",".join(parts)


def _run_numbers(run: str, numbers: dict[str, int]) -> tuple[list[int], list[str]]:
    nums, unknown = [], []
    for token in CITE_TOKEN.finditer(run):
        for part in re.split(r"[;\n]", token.group(1)):
            ident = normalise_identifier(part.lstrip("@"))
            if not ident:
                continue
            if ident in numbers:
                nums.append(numbers[ident])
            else:
                unknown.append(ident)
    return nums, unknown


def substitute_markers(md: str, numbers: dict[str, int]) -> str:
    """Sostituisce i token con `<sup>N</sup>` nel sorgente markdown.

    Due regole di stile, entrambe facili da sbagliare a mano e quindi non
    lasciate alla mano (sono le stesse dello userscript):
      - uno spazio davanti al marker, quando non ce n'e' gia' uno;
      - il marker sta DENTRO la frase, prima del punto. Un token scritto dopo
        il punto viene riportato prima.
    """
    out: list[str] = []
    last = 0
    for run in CITE_RUN.finditer(md or ""):
        nums, _ = _run_numbers(run.group(0), numbers)
        if not nums:
            continue
        head = md[last:run.start()]

        # il marker scavalca la punteggiatura di fine frase che lo precede
        hop = re.search(r"([.?!])([ \t]*)$", head)
        tail_punct = ""
        if hop:
            head = head[:hop.start()]
            tail_punct = hop.group(1)

        out.append(head)
        if head and not head[-1].isspace():
            out.append(" ")
        out.append(f"<sup>{marker_text(nums)}</sup>")
        out.append(tail_punct)
        last = run.end()
    out.append(md[last:])
    return "".join(out)


def unknown_identifiers(md: str, known: set[str]) -> list[str]:
    """Identificatori citati nel testo per cui la bozza non ha una reference."""
    return [i for i in cited_identifiers(md) if i not in known]


# ---------------------------------------------------------------------------
# markdown -> HTML
# ---------------------------------------------------------------------------

def _renderer(top_heading: int = TOP_HEADING) -> MarkdownIt:
    md = MarkdownIt("commonmark", {"html": True, "typographer": False})
    md.enable("table")
    shift = top_heading - 1

    def heading_open(self, tokens, idx, options, env):
        level = min(6, int(tokens[idx].tag[1]) + shift)
        return f"<h{level}>"

    def heading_close(self, tokens, idx, options, env):
        level = min(6, int(tokens[idx].tag[1]) + shift)
        return f"</h{level}>"

    md.add_render_rule("heading_open", heading_open)
    md.add_render_rule("heading_close", heading_close)
    return md


def to_html(md_text: str, numbers: dict[str, int] | None = None,
            top_heading: int = TOP_HEADING) -> str:
    """HTML dell'articolo, marker inclusi. E' questo che finisce negli appunti."""
    source = substitute_markers(md_text or "", numbers or {})
    return _renderer(top_heading).render(source).strip()


def reference_lines(numbers: dict[str, int], citations: dict[str, dict]) -> list[str]:
    """La bibliografia: una riga per box dell'editor, `N. <citazione>`.

    Le fonti non ancora risolte restano in elenco con l'identificatore al posto
    del testo, cosi' la numerazione dell'articolo non si sposta mentre le
    completi."""
    by_number: dict[int, list[str]] = {}
    for ident, n in numbers.items():
        by_number.setdefault(n, []).append(ident)

    lines = []
    for n in sorted(by_number):
        # fra gli identificatori della stessa opera vince quello che ha dato
        # la citazione piu' completa, non quello scritto per primo
        idents = sorted(by_number[n],
                        key=lambda i: (not (citations.get(i) or {}).get("citation"),
                                       KIND_RANK.get(identifier_kind(i), 9), i))
        best = idents[0]
        rec = citations.get(best) or {}
        text = rec.get("citation") or f"[{identifier_kind(best)} {best} — not resolved yet]"
        lines.append(f"{n}. {text}")
    return lines
