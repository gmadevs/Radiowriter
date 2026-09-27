"""Le metriche delle riviste, dal file SCImago.

Il file e' quello che si scarica da scimagojr.com: punto e virgola come
separatore, virgola come segno decimale, trentaduemila riviste. Sta nella
cartella del progetto e si trova da solo, cosi' l'anno prossimo basta lasciarci
cadere `scimagojr 2026.csv` perche' valga quello.

DUE PAROLE SUL NOME. Questo file NON contiene l'impact factor: l'impact factor
e' di Clarivate e sta nel Journal Citation Reports, che e' un altro prodotto e
si paga. Qui ci sono due numeri, e sono due cose diverse:

- **SJR**: quanto e' prestigiosa la rivista. Non conta le citazioni, le pesa -
  una citazione da Radiology vale piu' di una da un giornale che nessuno legge.
  E' il numero su cui SCImago costruisce i quartili.
- **Citations / Doc. (2 years)**: le citazioni medie per articolo negli ultimi
  due anni. E' calcolato come l'impact factor ed e' la cosa che gli somiglia di
  piu', ma su Scopus invece che su Web of Science, quindi i numeri non sono gli
  stessi.

Il quartile e' il "SJR Best Quartile": una rivista sta in piu' categorie e in
ognuna ha un quartile suo, e questo e' il migliore. `categories` porta il
dettaglio, che per un radiologo dice piu' del riassunto - una rivista puo'
essere Q1 in "Medicine (miscellaneous)" e Q3 in "Radiology".

AGGANCIARLE AGLI ARTICOLI. Per ISSN, non per titolo. Il titolo che restituisce
PubMed e quello che scrive SCImago sono la stessa rivista scritta in due modi
("Medicine" contro "Medicine (United States)"), mentre l'ISSN e' lo stesso
numero per tutti e due. Sull'archivio vero l'ISSN aggancia il 90% degli
articoli; il titolo esatto ne aggiunge una manciata, e il restante 10% sono
riviste che in SCImago non ci sono davvero - Cureus, medRxiv, parecchi giornali
di case report.
"""

from __future__ import annotations

import csv
import gzip
import io
import re
from pathlib import Path

from radiowriter import paths

# I quartili, dal migliore al peggiore. I loro colori stanno in `theme`, uno
# per tema chiaro e uno per scuro.
QUARTILES = ["Q1", "Q2", "Q3", "Q4"]

CATEGORY_QUARTILE = re.compile(r"^(.*?)\s*\((Q[1-4])\)\s*$")


class JournalDataError(RuntimeError):
    pass


def norm_title(text) -> str:
    """Un titolo di rivista ridotto a come si confronta."""
    out = (text or "").lower().replace("&", " and ")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", out).split())


def norm_issn(text) -> str:
    """Un ISSN senza trattini e in maiuscolo: `2296-858X` -> `2296858X`.

    SCImago li scrive gia' cosi', PubMed col trattino. Si ridurrebbero allo
    stesso identificatore anche solo togliendo i non alfanumerici, ma la X di
    controllo puo' arrivare minuscola e due stringhe diverse non si
    incontrerebbero mai."""
    return re.sub(r"[^0-9X]", "", (text or "").upper())


def find_file() -> Path | None:
    """Il file delle metriche da leggere, o None.

    Dove cercarlo lo sa `paths`: il file che ha scaricato l'utente prima di
    tutto, poi quello che il pacchetto porta con se'."""
    return paths.journal_csv()


def _open(path: Path):
    """Il file in lettura, compresso o no.

    Quello dentro il pacchetto e' un `.csv.gz` - undici megabyte di export non
    stanno in una wheel - e quello che scarica l'utente e' il `.csv` come gliel'
    ha dato SCImago. Sotto sono lo stesso formato, e il lettore e' lo stesso:
    cambia solo come si arriva ai byte.

    `utf-8-sig` in tutti e due i casi: l'export ha un BOM davanti, e senza
    saltarlo la prima colonna si chiamerebbe `\ufeffRank` e nessun controllo
    sui nomi delle colonne tornerebbe.
    """
    if path.suffix.lower() == ".gz":
        return io.TextIOWrapper(gzip.open(path, "rb"), encoding="utf-8-sig",
                                newline="")
    return open(path, encoding="utf-8-sig", newline="")


def _number(text) -> float | None:
    """Un numero scritto all'europea: `104,065` fa 104.065.

    Il punto NON e' un separatore di migliaia in questo file - i numeri grandi
    non ce l'hanno - quindi si tocca solo la virgola."""
    text = (text or "").strip()
    if not text or text == "-":
        return None
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def _integer(text) -> int | None:
    value = _number(text)
    return int(value) if value is not None else None


def categories_of(text: str) -> list[tuple[str, str | None]]:
    """`"Hematology (Q1); Oncology (Q3)"` -> [("Hematology", "Q1"), ...]."""
    out: list[tuple[str, str | None]] = []
    for chunk in (text or "").split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        m = CATEGORY_QUARTILE.match(chunk)
        out.append((m.group(1), m.group(2)) if m else (chunk, None))
    return out


def read(path: Path | None = None) -> list[dict]:
    """Le righe del file, gia' con i numeri come numeri.

    Si tengono solo le riviste: SCImago elenca anche atti di convegni e collane
    di libri, che una bibliografia di Radiopaedia non cita e che nella tendina
    dei quartili sarebbero solo rumore.
    """
    path = path or find_file()
    if path is None:
        raise JournalDataError(
            "No journal metrics file at all — not even the one that ships with "
            "the app. The install looks incomplete; reinstalling should fix it.")

    rows: list[dict] = []
    with _open(path) as fh:
        reader = csv.DictReader(fh, delimiter=";")
        missing = {"Title", "Issn", "SJR", "SJR Best Quartile"} - set(reader.fieldnames or ())
        if missing:
            raise JournalDataError(
                f"{path.name} does not look like a SCImago export: "
                f"it has no {', '.join(sorted(missing))} column.")
        for row in reader:
            if (row.get("Type") or "").strip().lower() not in ("journal", ""):
                continue
            title = (row.get("Title") or "").strip()
            if not title:
                continue
            quartile = (row.get("SJR Best Quartile") or "").strip()
            issns = [i for i in (norm_issn(x) for x in (row.get("Issn") or "").split(","))
                     if len(i) == 8]
            rows.append({
                "title": title,
                "norm_title": norm_title(title),
                "issns": issns,
                "sjr": _number(row.get("SJR")),
                "quartile": quartile if quartile in QUARTILES else None,
                "h_index": _integer(row.get("H index")),
                "cites_per_doc": _number(row.get("Citations / Doc. (2years)")),
                "categories": (row.get("Categories") or "").strip(),
                "country": (row.get("Country") or "").strip(),
                "publisher": (row.get("Publisher") or "").strip(),
            })
    if not rows:
        raise JournalDataError(f"{path.name} has no journals in it.")
    return rows


def issns_in_medline(raw_text: str) -> list[str]:
    """Gli ISSN di un blocco MEDLINE (le righe `IS`).

    Serve per l'archivio storico: quei record sono entrati da un import di
    testo, e l'ISSN non era fra i campi che si salvavano - ma il blocco grezzo
    e' li' e ce l'ha dentro."""
    out: list[str] = []
    for value in re.findall(r"^IS\s+-\s*(\S+)", raw_text or "", flags=re.M):
        issn = norm_issn(value)
        if len(issn) == 8 and issn not in out:
            out.append(issn)
    return out


def title_in_medline(raw_text: str) -> str:
    """Il titolo esteso di un blocco MEDLINE (la riga `JT`).

    I record vecchi dell'archivio hanno nel campo `journal` l'abbreviazione
    incollata al titolo - `Eur J Radiol European journal of radiology` - perche'
    li ha scritti una versione dell'app di prima. Il blocco grezzo tiene i due
    campi separati, e questo e' quello buono."""
    m = re.search(r"^JT\s+-\s*(.+)$", raw_text or "", flags=re.M)
    return m.group(1).strip() if m else ""
