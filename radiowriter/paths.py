"""Dove stanno i file dell'utente quando l'app non e' piu' una cartella.

Finche' si lanciava con `streamlit run app.py` dalla cartella del progetto, il
database poteva stare li' accanto. Installata come programma non si puo': la
cartella dove finisce il codice e' di sola lettura, cambia a ogni
aggiornamento, e su Windows sta dentro `%LOCALAPPDATA%\\uv\\tools` - un posto
che nessuno andra' mai a cercare per farsi un backup.

Quindi i dati stanno dove ogni sistema dice che i dati vanno:

    macOS    ~/Library/Application Support/Radiowriter
    Linux    ~/.local/share/radiowriter          (o $XDG_DATA_HOME)
    Windows  %LOCALAPPDATA%\\Radiowriter

`RADIOWRITER_HOME` scavalca tutto: serve a chi vuole tenersi l'archivio su un
disco esterno, e serve ai test, che girano su una cartella usa e getta.

CHI STA GIA' LAVORANDO NON DEVE ACCORGERSI DI NIENTE. Se accanto al codice c'e'
un `pubmed_database.db` - cioe' se questa e' l'installazione di prima, quella
che gira dalla cartella del progetto - si continua a usare quello. Spostare
d'ufficio l'archivio di qualcuno sotto il naso e' il genere di cosa che si fa
una volta e poi si passa la serata a spiegare dove sono finiti i suoi dati.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "Radiowriter"
DB_NAME = "pubmed_database.db"

# La cartella del codice. Ci si guarda dentro per due ragioni: l'installazione
# storica che teneva li' il database, e il file SCImago che qualcuno puo' aver
# lasciato accanto al progetto invece che nella cartella dei dati.
PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent


def _default_home() -> Path:
    override = os.environ.get("RADIOWRITER_HOME")
    if override:
        return Path(override).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")
        return Path(base) / APP_NAME
    base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    return Path(base) / APP_NAME.lower()


def home(create: bool = True) -> Path:
    """La cartella dei dati dell'utente."""
    path = _default_home()
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


# Da dove viene il percorso del database. Non e' un dettaglio interno: se
# l'archivio non e' quello che uno si aspetta, la ragione e' sempre una di
# queste tre, e l'app deve poterla dire invece di lasciarlo indovinare.
FROM_ENV = "env"            # RADIOPAEDIA_DB
FROM_SOURCE = "beside-code"  # accanto al codice: installazione storica o `pip install -e`
FROM_DATA_DIR = "data-dir"   # la cartella dei dati del sistema, il caso normale


def db_origin() -> tuple[Path, str]:
    """(percorso del database, quale delle tre regole l'ha scelto)."""
    explicit = os.environ.get("RADIOPAEDIA_DB")
    if explicit:
        return Path(explicit).expanduser(), FROM_ENV

    beside_code = PROJECT_DIR / DB_NAME
    if beside_code.exists():
        return beside_code, FROM_SOURCE

    return home() / DB_NAME, FROM_DATA_DIR


def db_path() -> Path:
    """Il file del database.

    `RADIOPAEDIA_DB` continua a valere e vince su tutto: e' quello che usano i
    test per non toccare l'archivio vero, ed e' in giro da prima di questo
    modulo."""
    return db_origin()[0]


def short(path: Path) -> str:
    """Il percorso con la home abbreviata in `~`: piu' corto e piu' leggibile
    in una barra laterale stretta."""
    try:
        return "~/" + str(path.relative_to(Path.home()))
    except ValueError:
        return str(path)


def journal_csv() -> Path | None:
    """Il file SCImago piu' recente, se c'e'.

    Si guarda prima nella cartella dei dati - li' lo mette chi installa l'app -
    e poi accanto al codice, per l'installazione storica. Si sceglie per nome
    al contrario, cosi' `scimagojr 2026.csv` batte `scimagojr 2025.csv` e
    aggiornare vuol dire solo lasciarci cadere il file nuovo.
    """
    found: list[Path] = []
    for folder in (home(create=False), PROJECT_DIR / "data", PROJECT_DIR, PACKAGE_DIR):
        try:
            if folder.is_dir():
                found.extend(p for p in folder.glob("scimagojr*.csv") if p.is_file())
        except OSError:
            continue
    if not found:
        return None
    return sorted(found, key=lambda p: (p.name.lower(), str(p)), reverse=True)[0]


def describe() -> str:
    """Una riga da mostrare nella UI: dove stanno le cose."""
    return str(db_path().parent)
