"""`radiowriter` da riga di comando: accende il server e apre il browser.

Streamlit e' fatto per essere lanciato con `streamlit run qualcosa.py`, che
per chi installa un programma e' un dettaglio implementativo da non dover
sapere. Qui lo si avvia da dentro, con `bootstrap.run`, che e' la stessa cosa
che fa il comando `streamlit` - non un sottoprocesso, quindi non c'e' un
secondo interprete da trovare ne' un PATH da sperare che sia giusto.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent / "app.py"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="radiowriter",
        description="Find the literature for a Radiopaedia article, screen it, "
                    "and write the article against it.")
    parser.add_argument("--port", type=int, default=8501,
                        help="port to serve on (default: 8501)")
    parser.add_argument("--no-browser", action="store_true",
                        help="do not open a browser window")
    parser.add_argument("--where", action="store_true",
                        help="print where the archive is kept, and exit")
    parser.add_argument("--version", action="store_true",
                        help="print the version, and exit")
    args = parser.parse_args(argv)

    from radiowriter import paths

    if args.version:
        print(f"radiowriter {_version()}")
        return 0

    if args.where:
        db_file, origin = paths.db_origin()
        print(f"data folder: {paths.home(create=False)}")
        print(f"database:    {db_file}")
        print(f"             {_why(origin)}")
        csv = paths.journal_csv()
        print(f"SCImago CSV: {csv if csv else '(none - quartiles are off)'}")
        return 0

    # La cartella dei dati si crea adesso, prima che parta il server: se il
    # disco e' pieno o i permessi sono sbagliati, il messaggio si legge nel
    # terminale invece di finire in una pagina bianca del browser.
    try:
        paths.home()
    except OSError as exc:
        print(f"Cannot create the data folder {paths.home(create=False)}: {exc}",
              file=sys.stderr)
        return 1

    from streamlit.web import bootstrap

    flags = {
        "server.port": args.port,
        "server.headless": args.no_browser,
        "browser.gatherUsageStats": False,
        # L'app e' un programma sul computer di chi la usa: il menu con
        # "Deploy" e "Report a bug" parla di Streamlit Cloud, che non c'entra.
        "client.toolbarMode": "minimal",
        "global.developmentMode": False,
    }
    db_file, origin = paths.db_origin()
    print(f"Radiowriter - http://localhost:{args.port}")
    print(f"Archive: {db_file}")
    if origin != paths.FROM_DATA_DIR:
        # Il caso normale non ha bisogno di spiegazioni; gli altri due si'.
        print(f"         {_why(origin)}")
    print("Press Ctrl+C to stop.")
    bootstrap.load_config_options(flag_options=flags)
    bootstrap.run(str(APP), False, [], flags)
    return 0


def _why(origin: str) -> str:
    """Perche' l'archivio e' quello e non un altro.

    Detto sempre, non solo quando qualcosa va storto: chi si trova davanti un
    archivio inatteso deve poterlo leggere, non dedurlo."""
    from radiowriter import paths

    if origin == paths.FROM_ENV:
        return "(chosen by RADIOPAEDIA_DB)"
    if origin == paths.FROM_SOURCE:
        return ("(found next to the source, so that one is used - "
                "an existing archive is never moved out from under you)")
    return "(the data folder for this platform)"


def _version() -> str:
    try:
        from importlib.metadata import version
        return version("radiowriter")
    except Exception:
        return "unknown (running from a source tree)"


if __name__ == "__main__":
    sys.exit(main())
