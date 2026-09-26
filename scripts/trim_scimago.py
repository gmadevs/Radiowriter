#!/usr/bin/env python3
"""Riduce l'export SCImago al sottoinsieme che il pacchetto porta con se'.

L'export che si scarica da scimagojr.com ha venticinque colonne e undici
megabyte; l'app ne legge nove e le serve solo per le riviste. Questo script
taglia il resto, cosi' il file che finisce dentro la wheel pesa un ottavo.

NON si cambiano i nomi delle colonne. Sono quelli di SCImago, e restano quelli
perche' `journals.read()` deve saper leggere allo stesso modo questo file e
quello che l'utente scarica da se' l'anno prossimo: due formati vorrebbero due
percorsi di lettura, e il secondo non lo proverebbe mai nessuno.

    python3 scripts/trim_scimago.py "scimagojr 2026.csv"

Scrive `radiowriter/data/scimagojr-<anno>.csv.gz` e il `.about.txt` che gli sta
accanto e dice da dove viene.
"""

from __future__ import annotations

import csv
import gzip
import re
import sys
from datetime import date
from pathlib import Path

# Le colonne che `journals.read()` legge davvero, nell'ordine dell'export.
# `Type` resta perche' il lettore ci si appoggia per scartare atti di convegni
# e collane di libri, e perche' una riga deve continuare a dire cosa e'.
KEEP = [
    "Title",
    "Type",
    "Issn",
    "SJR",
    "SJR Best Quartile",
    "H index",
    "Citations / Doc. (2years)",
    "Categories",
    "Country",
    "Publisher",
]

ABOUT = """\
scimagojr-{year}.csv.gz - da dove viene e cosa gli e' stato fatto
================================================================

LORO. I dati sono di SCImago Journal & Country Rank
(https://www.scimagojr.com/), ricavati dal database Scopus di Elsevier.
Licenza CC BY-NC. Non sono nostri, non li abbiamo calcolati noi e non li
abbiamo corretti.

Scaricato il {downloaded} da https://www.scimagojr.com/journalrank.php
(il link "Download data" in alto a destra della tabella).
Anno dei dati: {year}.

NOSTRO. Solo il taglio, fatto da `scripts/trim_scimago.py`:

- delle 25 colonne dell'export ne restano {kept}, quelle che l'app legge:
  {columns}
- delle {rows_in:,} righe restano le {rows_out:,} di tipo "journal": atti di
  convegni e collane di libri non finiscono in una bibliografia di Radiopaedia
- il file e' compresso con gzip

Niente altro e' stato toccato: valori, nomi delle colonne, separatore (punto e
virgola) e virgola decimale sono quelli di SCImago.

L'ANNO PROSSIMO. Non serve rifare niente per far valere un file nuovo: basta
lasciare `scimagojr 2026.csv` nella cartella che `radiowriter --where` stampa,
e quello vince su questo. Questo serve a chi non l'ha scaricato.
"""


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2

    source = Path(argv[1])
    if not source.is_file():
        print(f"non trovo {source}")
        return 1

    m = re.search(r"(20\d\d)", source.name)
    if not m:
        print(f"nel nome di {source.name} non c'e' un anno: non saprei come "
              f"chiamare il file che scrivo")
        return 1
    year = m.group(1)

    out_dir = Path(__file__).resolve().parent.parent / "radiowriter" / "data"
    out_csv = out_dir / f"scimagojr-{year}.csv.gz"
    out_about = out_dir / f"scimagojr-{year}.about.txt"

    rows_in = 0
    kept: list[list[str]] = []
    with open(source, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh, delimiter=";")
        have = set(reader.fieldnames or ())
        missing = [c for c in KEEP if c not in have]
        if missing:
            print(f"{source.name} non ha le colonne {missing} - "
                  f"e' davvero un export di SCImago?")
            return 1
        for row in reader:
            rows_in += 1
            if (row.get("Type") or "").strip().lower() != "journal":
                continue
            kept.append([(row.get(c) or "").strip() for c in KEEP])

    if not kept:
        print(f"{source.name} non ha nessuna riga di tipo journal")
        return 1

    # newline="" anche qui: senza, su Windows ogni riga finirebbe con \r\r\n
    with gzip.open(out_csv, "wt", encoding="utf-8", newline="", compresslevel=9) as out:
        writer = csv.writer(out, delimiter=";")
        writer.writerow(KEEP)
        writer.writerows(kept)

    out_about.write_text(ABOUT.format(
        year=year,
        downloaded=date.today().isoformat(),
        kept=len(KEEP),
        columns="\n  ".join(KEEP),
        rows_in=rows_in,
        rows_out=len(kept),
    ), encoding="utf-8")

    print(f"{out_csv.name}: {len(kept):,} riviste su {rows_in:,} righe, "
          f"{out_csv.stat().st_size:,} byte "
          f"(l'export era {source.stat().st_size:,})")
    print(f"{out_about.name}: scritto")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
