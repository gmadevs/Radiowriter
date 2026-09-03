#!/usr/bin/env python3
"""Gli screenshot delle docs, presi dall'app vera.

    python3 scripts/shots.py

Perche' uno script e non qualche schermata fatta a mano: le schermate fatte a
mano invecchiano in silenzio. Un pulsante cambia nome, l'immagine no, e la
pagina che dovrebbe spiegare finisce per mentire. Cosi' invece si rifanno in un
comando, e se qualcosa non si trova piu' lo script si ferma invece di
fotografare la cosa sbagliata.

**Non tocca il tuo archivio.** Ne monta uno usa e getta in una cartella
temporanea, con un'email finta, e ci fa dentro una ricerca vera - i risultati
sono veri articoli PubMed, l'identita' no. Senza questo negli screenshot
finirebbero l'email e l'identificativo della biblioteca di chi li ha presi.

Serve playwright:

    pip install playwright && playwright install chromium
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / "docs" / "public" / "shots"
HOME = Path("/tmp/radiowriter-shots")
PORT = 8802
WIDTH, HEIGHT = 1440, 900

# La ricerca degli screenshot. Un argomento stretto: cinquanta risultati si
# leggono, duemila fanno una schermata di numeri.
TERMS = '"Joubert syndrome" OR "molar tooth sign"'
DEMO_EMAIL = "you@hospital.org"


def build_archive() -> None:
    """Un archivio nuovo, con dentro le metriche delle riviste."""
    if HOME.exists():
        shutil.rmtree(HOME)
    HOME.mkdir(parents=True)

    csv = next((p for folder in (ROOT / "data", ROOT)
                for p in folder.glob("scimagojr*.csv")), None)
    if csv:
        shutil.copy(csv, HOME / csv.name)

    db_file = HOME / "pubmed_database.db"
    env = dict(os.environ, RADIOWRITER_HOME=str(HOME), RADIOPAEDIA_DB=str(db_file))
    subprocess.run([sys.executable, "-c", f"""
import os
os.environ["RADIOPAEDIA_DB"] = {str(db_file)!r}
from radiowriter import db, journals as jr
db.init_db()
db.save_settings({{"ncbi_email": {DEMO_EMAIL!r}, "unpaywall_email": {DEMO_EMAIL!r},
                  "libkey_library_id": "", "page_size": "10"}})
if jr.find_file():
    db.import_journal_metrics(jr.read())
"""], cwd=ROOT, env=env, check=True)


def settle(page, seconds: float = 2.0) -> None:
    """Streamlit ridisegna a ondate: si aspetta che smetta.

    `networkidle` da solo non basta - il websocket resta aperto per sempre e
    non c'e' mai un momento in cui la rete tace."""
    page.wait_for_timeout(int(seconds * 1000))


def shoot(page, name: str) -> None:
    page.screenshot(path=str(SHOTS / f"{name}.png"))
    print(f"  ok  {name}")


def take(page) -> None:
    settle(page, 3)
    shoot(page, "01-search")

    # --- il compositore a blocchi ------------------------------------------
    page.get_by_text("Blocks", exact=False).first.click()
    settle(page)
    page.get_by_placeholder("one wording of this concept").first.fill("Joubert syndrome")
    page.keyboard.press("Tab")
    settle(page)
    page.get_by_role("button", name="Another wording").first.click()
    settle(page)
    page.get_by_placeholder("one wording of this concept").nth(1).fill("molar tooth sign")
    page.keyboard.press("Tab")
    settle(page)
    page.get_by_role("button", name="Add a block").click()
    settle(page)
    page.get_by_placeholder("one wording of this concept").last.fill("MRI")
    page.keyboard.press("Tab")
    settle(page, 3)
    # Un filo piu' in basso: la query composta e' il punto di tutta la
    # schermata, e tagliata a meta' non spiega niente.
    page.mouse.wheel(0, 150)
    settle(page)
    shoot(page, "02-blocks")

    # --- una ricerca vera, e i suoi filtri ---------------------------------
    page.get_by_text("One line", exact=False).first.click()
    settle(page)
    page.get_by_placeholder('e.g. "Joubert syndrome" OR "molar tooth sign"').fill(TERMS)
    page.keyboard.press("Tab")
    settle(page)
    page.get_by_role("button", name="Search PubMed").click()
    page.wait_for_selector("text=Search complete", timeout=180_000)
    settle(page, 4)

    page.get_by_text("Filter these results", exact=False).first.click()
    settle(page, 2)
    page.mouse.wheel(0, 620)
    settle(page, 2)
    shoot(page, "03-results")

    # --- lo screening -------------------------------------------------------
    page.mouse.wheel(0, -620)
    settle(page)
    page.get_by_role("button", name="Select all").click()
    settle(page, 3)
    page.get_by_role("button", name="Save", exact=False).first.click()
    settle(page, 5)
    page.get_by_role("tab", name="Screening", exact=False).click()
    settle(page, 5)
    page.mouse.wheel(0, 480)
    settle(page, 2)
    shoot(page, "04-screening")

    # --- la scrittura -------------------------------------------------------
    page.mouse.wheel(0, -480)
    settle(page)
    page.get_by_role("tab", name="Write", exact=False).click()
    settle(page, 3)
    page.get_by_role("button", name="New draft").click()
    settle(page, 4)
    page.get_by_role("textbox", name="Article title").fill("Joubert syndrome")
    page.keyboard.press("Tab")
    settle(page, 2)
    page.get_by_role("textbox", name="Body (Markdown)").fill(
        "Joubert syndrome is a rare autosomal recessive neurodevelopmental\n"
        "disorder defined by a distinctive hindbrain malformation, the molar\n"
        "tooth sign [@31710777].\n\n"
        "# Epidemiology\n\ncontent pending\n\n"
        "# Radiographic features\n\n## MRI\n\n"
        "The molar tooth sign is best appreciated on axial images through the\n"
        "midbrain.\n")
    page.keyboard.press("Tab")
    settle(page, 4)

    # La citazione si risolve prima di fotografare: "[PMID 31710777 - not
    # resolved yet]" nella casella delle referenze mostra l'app a meta' lavoro.
    resolve = page.get_by_role("button", name="Resolve", exact=False)
    if resolve.count():
        resolve.first.click()
        settle(page, 12)
    page.mouse.wheel(0, -2000)
    settle(page, 2)
    shoot(page, "05-write")

    # --- la struttura dei titoli -------------------------------------------
    page.get_by_text("Headings", exact=False).first.click()
    settle(page, 3)
    page.mouse.wheel(0, 420)
    settle(page, 2)
    shoot(page, "06-headings")


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Serve playwright:  pip install playwright && playwright install chromium",
              file=sys.stderr)
        return 1

    SHOTS.mkdir(parents=True, exist_ok=True)
    build_archive()

    env = dict(os.environ, RADIOWRITER_HOME=str(HOME),
               RADIOPAEDIA_DB=str(HOME / "pubmed_database.db"))
    server = subprocess.Popen(
        [sys.executable, "-m", "radiowriter", "--port", str(PORT), "--no-browser"],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT},
                                    device_scale_factor=2, color_scheme="light")
            for _ in range(60):
                try:
                    page.goto(f"http://localhost:{PORT}", timeout=3000)
                    page.wait_for_selector(".app-title", timeout=3000)
                    break
                except Exception:
                    time.sleep(1)
            else:
                raise SystemExit("il server non e' mai partito")
            take(page)
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=10)

    print()
    for shot in sorted(SHOTS.glob("*.png")):
        print(f"  {shot.stat().st_size // 1024:5} KB  {shot.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
