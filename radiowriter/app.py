"""Radiowriter - la letteratura dietro un articolo Radiopaedia.

Tre fasi, che sono le tre schede:
  1. Ricerca   - interroga PubMed, da sola riga o componendo la query a
                 blocchi, ordina i risultati per influenza (Semantic Scholar) e
                 per prestigio della rivista (SCImago), e salva quelli scelti.
  2. Screening - sfoglia l'archivio, apre i full text via LibKey o Unpaywall,
                 marca letto/segnalato, raccoglie in liste.
  3. Scrittura - la bozza dell'articolo con la struttura che Radiopaedia
                 raccomanda per quel tipo, le citazioni risolte, il linter, e
                 l'HTML da incollare nel loro editor.
"""

from __future__ import annotations

import html
import math
import sqlite3
import time
from datetime import date

import pandas as pd
import requests
import streamlit as st

from radiowriter import backup
from radiowriter import db
from radiowriter import draft_io
from radiowriter import issg
from radiowriter import journals as jr
from radiowriter import lint
from radiowriter import pubmed
from radiowriter import querybuilder as qb
from radiowriter import radiopaedia as rp
from radiowriter import semantic_scholar as s2
from radiowriter import strategies as stg
from radiowriter import structure as sx
from radiowriter import unpaywall as upw

PAGE_SIZE_OPTIONS = [10, 20, 50, 100]
SORT_OPTIONS = {
    "Influential citations (S2)": "influential_citations",
    "Total citations (S2)": "citation_count",
    "Citations per year": "citations_per_year",
    "Most recent": "year",
    "Journal SJR": "_sjr",
}
TODAY = date.today()
MAX_SEARCH_RESULTS = 1000
SEARCH_PAGE_SIZE_OPTIONS = [10, 25, 50, 100]

# "Recent reviews" non e' un pulsante che riscrive i filtri e poi sparisce: e'
# un interruttore che resta acceso o spento, e mentre e' acceso QUESTI sono i
# filtri. Averlo come pulsante voleva dire non poter piu' sapere, guardando la
# schermata, se la ricerca era ristretta alle review o no - i singoli controlli
# dicevano il come, nessuno diceva il perche'.
RECENT_REVIEWS_LABEL = "★ Recent reviews"
RECENT_REVIEWS_WHAT = (
    "Last 10 years · full text · English · humans · and the publication types "
    "PubMed calls reviews and syntheses (Review, Systematic Review, "
    "Meta-Analysis, Guideline, Consensus Statement…)."
)

# Nel fascio ci sono solo i FILTRI, cioe' quello che cambia la domanda fatta a
# PubMed. Quanti record scaricare, cosa saltare, se arricchire con le citazioni
# e con l'open access sono preferenze dell'app: stanno nella sidebar e non le
# tocca ne' il fascio ne' "azzera".
SEARCH_FILTER_PRESETS = {
    "reviews": {
        "sf_years": 10,
        "sf_fulltext": True,
        "sf_english": True,
        "sf_humans": True,
        "sf_types": list(pubmed.DEFAULT_TYPE_LABELS),
        "sf_issg": [],
    },
    # Tutto spento vuol dire tutto spento, compreso il limite di data: prima
    # "azzera" lasciava gli ultimi cinquant'anni, che e' un filtro travestito
    # da assenza di filtro.
    "open": {
        "sf_years": 0,
        "sf_fulltext": False,
        "sf_english": False,
        "sf_humans": False,
        "sf_types": [],
        "sf_issg": [],
    },
}

# Le preferenze, col loro valore di partenza.
SEARCH_PREFS = {
    "sf_max_results": 200,
    "sf_exclude": db.EXCLUDE_MODES["db"],
    "sf_s2": True,
    "sf_oa": False,
}

st.set_page_config(page_title="Radiowriter", layout="wide", page_icon="🔬")

db.init_db()


@st.cache_resource
def boot_cleanup() -> int:
    """Girata una sola volta per avvio dell'app, non a ogni rerun di Streamlit."""
    return db.cleanup_read_articles()


removed_at_boot = boot_cleanup()


@st.cache_resource
def load_journal_metrics() -> dict:
    """Il file SCImago dentro il database, una volta sola per avvio.

    Si fa da se' al primo avvio invece di aspettare che qualcuno prema un
    pulsante: il file e' nella cartella del progetto, e chi ce l'ha messo lo ha
    messo li' perche' i quartili si vedano. Se non c'e' non e' un guasto -
    l'app funziona come prima, semplicemente senza quartili."""
    status = db.journal_metrics_status()
    if status["journals"]:
        return {"loaded": False, **status}
    path = jr.find_file()
    if path is None:
        return {"loaded": False, "missing": True, **status}
    try:
        n = db.import_journal_metrics(jr.read(path))
    except jr.JournalDataError as exc:
        return {"loaded": False, "error": str(exc), **status}
    db.match_journals()
    return {"loaded": True, "file": path.name, "n": n, **db.journal_metrics_status()}


journal_status = load_journal_metrics()

if "settings" not in st.session_state:
    st.session_state.settings = db.get_settings()
settings = st.session_state.settings

# I valori di partenza vanno messi PRIMA che qualunque widget nasca: un widget
# senza `value=` prende il proprio default (per un number_input, il minimo), e
# se la voce in session_state arrivasse dopo sarebbe troppo tardi - la sidebar
# mostrerebbe 10 record da scaricare invece di 200.
for _key, _value in {**SEARCH_FILTER_PRESETS["reviews"], **SEARCH_PREFS}.items():
    st.session_state.setdefault(_key, _value)


# ---------------------------------------------------------------------------
# helper
# ---------------------------------------------------------------------------

def libkey_url(pmid: str) -> str | None:
    lib = (settings.get("libkey_library_id") or "").strip()
    return f"https://libkey.io/libraries/{lib}/{pmid}" if lib else None


def unpaywall_email() -> str:
    """L'email che va nelle chiamate a Unpaywall.

    Se non se n'e' messa una apposta si usa quella dell'NCBI: sono due servizi
    che chiedono la stessa cosa per la stessa ragione - sapere chi sta
    chiamando, per poterlo avvisare se qualcosa va storto - e farla scrivere
    due volte sarebbe solo un modo di dimenticarne una."""
    return ((settings.get("unpaywall_email") or "").strip()
            or (settings.get("ncbi_email") or "").strip())


def http_session() -> requests.Session:
    if "http" not in st.session_state:
        st.session_state.http = requests.Session()
    return st.session_state.http


def on_toggle(pmid: str, field: str, widget_key: str) -> None:
    """Callback della checkbox: salva subito il nuovo valore nel DB."""
    value = st.session_state[widget_key]
    try:
        db.set_status(pmid, field, value)
    except sqlite3.Error as e:
        # Senza questo l'app va in crash e la spunta resta girata pur non
        # essendo stata salvata: si riporta la checkbox allo stato reale.
        st.session_state[widget_key] = not value
        st.error(f"Could not save the change for PMID {pmid}: {e}")


def on_pick(pmid: str, widget_key: str) -> None:
    """Riporta la spunta 'Save' di una scheda dei risultati nella selezione."""
    st.session_state.setdefault("search_selection", {})[pmid] = bool(
        st.session_state[widget_key])


def on_list_toggle(pmid: str, list_id: int, widget_key: str) -> None:
    """Callback della spunta di una lista: scrive subito, come le altre."""
    value = st.session_state[widget_key]
    try:
        if value:
            db.add_to_list(list_id, [pmid], note="from screening")
        else:
            db.remove_from_list(list_id, pmid)
    except sqlite3.Error as e:
        st.session_state[widget_key] = not value
        st.error(f"Could not change the list for PMID {pmid}: {e}")


def on_list_rename(list_id: int, widget_key: str, previous: str, field: str) -> None:
    """Rinomina o cambia la nota quando il campo perde il fuoco.

    Se il nome e' gia' di un'altra lista il database rifiuta, e la casella
    tornerebbe a mostrare un nome che non e' stato salvato: si rimette quello
    di prima. Qui si puo', perche' i callback girano prima che i widget di
    questo giro esistano."""
    value = st.session_state[widget_key]
    ok = (db.rename_list(list_id, name=value) if field == "name"
          else db.rename_list(list_id, note=value))
    if not ok:
        st.session_state[widget_key] = previous
        st.toast(f"“{value}” is already the name of another list.")


def apply_search_preset(name: str) -> None:
    """Riscrive i filtri di ricerca con uno dei fasci. Va usata come callback:
    i widget si ricreano dopo, e ripartono dai valori nuovi."""
    st.session_state.update(SEARCH_FILTER_PRESETS[name])


def on_recent_reviews() -> None:
    """L'interruttore acceso rimette il suo fascio; spento non tocca niente.

    Spegnendolo i valori restano quelli che erano: e' il modo in cui uno lo usa
    davvero - accende il fascio, poi lo spegne per cambiare una cosa sola. Se
    spegnerlo azzerasse tutto, per togliere il vincolo della lingua bisognerebbe
    riscrivere anche gli altri cinque."""
    if st.session_state.get("sf_recent"):
        st.session_state.update(SEARCH_FILTER_PRESETS["reviews"])


def number(value) -> float | None:
    """Un numero da una cella, o None. Le colonne che arrivano da una LEFT JOIN
    senza corrispondenza tornano come NaN, non come None, e NaN e' un float che
    passa qualsiasi controllo di verita': senza questo una rivista non
    agganciata si stamperebbe addosso un badge che dice `nan`."""
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(out) else out


# Tipi di pubblicazione che non dicono niente a chi sta screenando: "Journal
# Article" ce l'hanno quasi tutti, e da chi era finanziato uno studio non e'
# una cosa che si guarda scorrendo un elenco. Occupavano tre righe di badge per
# scheda e coprivano quelli che contano - Review, Meta-Analysis, Guideline.
NOISY_TYPES = {"journal article", "english abstract", "comparative study",
               "validation study", "historical article"}


def useful_types(text: str, limit: int = 3) -> list[str]:
    out = []
    for kind in (t.strip() for t in clean(text).split(";")):
        low = kind.lower()
        if not kind or low in NOISY_TYPES or low.startswith("research support"):
            continue
        if kind not in out:
            out.append(kind)
    return out[:limit]


def citation_badge(total, influential, per_year) -> str:
    """Un badge solo per le citazioni, invece di tre.

    Tre numeri messi in fila su tre pillole diverse si leggono come tre fatti;
    sono lo stesso fatto guardato da tre lati, e su una riga sola si confrontano
    fra articoli molto piu' in fretta."""
    total = number(total)
    if total is None:
        return ""
    bits = [f"{int(total):,} cites"]
    infl = number(influential)
    if infl:
        bits.append(f"{int(infl)} infl")
    rate = number(per_year)
    if rate:
        bits.append(f"{rate:.1f}/yr")
    return "<span>" + html.escape(" · ".join(bits)) + "</span>"


def journal_badges(metric) -> list[str]:
    """I badge della rivista, gia' in HTML: quartile colorato, SJR, citazioni.

    Vuoto quando la rivista non e' agganciata. Una che in SCImago non c'e' -
    Cureus, medRxiv, meta' dei giornali di case report - non ha un quartile, e
    dargliene uno grigio direbbe che il dato e' scarso invece che assente."""
    if metric is None:
        return []
    out = []
    quartile = clean(metric["quartile"])
    sjr = number(metric["sjr"])
    cites = number(metric["cites_per_doc"])
    if quartile:
        text = f"{quartile} · SJR {sjr:.2f}" if sjr is not None else quartile
        out.append(f'<span class="{quartile.lower()}">{html.escape(text)}</span>')
    elif sjr is not None:
        out.append(f"<span>SJR {sjr:.2f}</span>")
    if cites is not None:
        out.append(f"<span>{cites:.1f} cites/doc (2y)</span>")
    return out


def oa_badge(status) -> str:
    """Il badge dell'open access. Verde solo quando il full text c'e' davvero."""
    text = upw.label(status)
    if not text:
        return ""
    css = "oa" if (status or "").lower() not in ("closed", "unknown") else "oa-closed"
    return f'<span class="{css}">{html.escape(text)}</span>'


def clean(value) -> str:
    """Testo sicuro da una cella: le colonne aggiunte dopo sono NULL sui record
    storici, e pandas le restituisce come NaN (che stampato diventa 'nan')."""
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() in ("nan", "none", "<na>") else text


def fmt_int(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "–"
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "–"


# ---------------------------------------------------------------------------
# stile
# ---------------------------------------------------------------------------

try:
    title_rem = float(settings.get("title_font_rem") or 1.35)
except ValueError:
    title_rem = 1.35

quartile_css = " ".join(
    f".art-badges span.{q.lower()} {{ background: {bg}; color: {fg}; font-weight: 600; }}"
    for q, (fg, bg) in jr.QUARTILE_COLOURS.items()
)

st.markdown(
    f"""
    <style>
      .app-title {{
        font-size: 1.5rem; font-weight: 700; letter-spacing: -.01em;
        margin: 0 0 .5rem 0;
      }}
      .art-title {{
        font-size: {title_rem}rem;
        font-weight: 650;
        line-height: 1.28;
        margin: 0 0 .25rem 0;
      }}
      /* Denso apposta: si sfogliano centinaia di record, e ogni riga di aria
         in piu' e' un articolo in meno per schermata. Si stringe lo spazio fra
         i blocchi e dentro le schede, non il testo - quello resta leggibile. */
      div[data-testid="stVerticalBlock"] {{ gap: .55rem; }}
      div[data-testid="stExpander"] summary {{ padding: .3rem .6rem; }}
      div[data-testid="stExpander"] details {{ border-radius: .4rem; }}
      .art-meta {{ font-size: .85rem; opacity: .72; margin-bottom: .3rem; }}
      .art-badges {{ font-size: .78rem; margin-bottom: .3rem;
                     display: flex; flex-wrap: wrap; gap: .3rem; }}
      .art-badges span {{
        display: inline-block; padding: .05rem .45rem; margin: 0;
        border-radius: .35rem; background: rgba(128,128,128,.16);
        white-space: nowrap;
      }}
      /* Il quartile e' l'unica cosa in questa riga che si legge di colpo:
         verde Q1, rosso Q4, come un semaforo. Gli altri badge restano grigi
         apposta - se fossero colorati anche loro non si vedrebbe piu' niente. */
      {quartile_css}
      .art-badges span.oa {{ background: #e3f5ed; color: #0b8457; font-weight: 600; }}
      .art-badges span.oa-closed {{ background: rgba(128,128,128,.18); opacity: .8; }}
      /* titolo degli expander (abstract) leggermente piu' grande del default */
      div[data-testid="stExpander"] summary p {{ font-size: {max(0.95, title_rem - 0.3):.2f}rem; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# `st.title` occupa due righe su una finestra normale e le ruba a quello che
# si sta guardando. In un'app che si tiene aperta tutto il giorno il titolo
# serve a sapere dove sei, non a fare da copertina.
st.markdown(
    '<div class="app-title">🔬 Radiowriter</div>',
    unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# il primo avvio
# ---------------------------------------------------------------------------

# Chi apre l'app la prima volta non sa che deve dare un'email, e soprattutto non
# sa perche': senza una ragione detta, chiedere un indirizzo appena aperta una
# cosa sembra la solita raccolta di contatti. Non lo e', e vale la pena dirlo -
# nessuno dei tre servizi manda posta, nessuno chiede di registrarsi, e l'email
# resta su questo computer, in un file SQLite.

SERVICES = [
    ("PubMed (NCBI E-utilities)", True,
     "Searches and downloads the records. **Wants an email in every "
     "request**: it is how NCBI can reach whoever is calling when a script "
     "starts hammering their servers — a warning instead of a silent block. "
     "No registration, no mail."),
    ("Unpaywall", True,
     "Says whether a paper has a legally free copy, and where. It wants an "
     "email in every request for the same reason. No key, no registration."),
    ("Semantic Scholar", False,
     "Citations and influential citations, which is how results get ranked "
     "by importance. Works without a key, just more slowly."),
    ("LibKey", False,
     "The direct link to the full text through your library's subscription. "
     "It needs the library's ID, not an email."),
]


def setup_screen() -> None:
    """La schermata del primo avvio: un campo obbligatorio e il perche'."""
    # Il titolo lo stampa gia' il modulo, qualche riga sopra.
    st.subheader("One thing to set up, and it takes a minute")

    st.markdown(
        "This app talks to a few public services on your behalf. Two of them "
        "want **an email address in every request** — not to write to you, but "
        "so they can tell who is calling if something goes wrong. There is "
        "nothing to register for, and the address stays on this computer, in "
        "the app's own database file."
    )

    with st.form("first_run"):
        email = st.text_input(
            "Your email address", placeholder="you@hospital.org",
            help="It goes to PubMed and to Unpaywall as the caller's address.")

        st.caption("**What each service is for**")
        for name, required, why in SERVICES:
            st.markdown(
                f"- **{name}** — {'*required*' if required else '*optional*'}. {why}")

        with st.expander("Optional keys and IDs — you can add them later",
                         expanded=False):
            api_key = st.text_input(
                "NCBI API key", type="password",
                help="Raises the rate limit from 3 to 10 requests a second. "
                     "Free, from your NCBI account settings.")
            s2_key = st.text_input(
                "Semantic Scholar API key", type="password",
                help="Makes the citation lookup faster. Free, on request.")
            libkey = st.text_input(
                "LibKey library ID",
                help="Your library's Third Iron ID — it appears in the URL "
                     "libkey.io/libraries/<ID>/…")

        go, skip = st.columns([1, 1])
        started = go.form_submit_button("Save and start", type="primary",
                                        width="stretch")
        skipped = skip.form_submit_button(
            "Skip — I only want to read the archive", width="stretch")

    if started:
        if "@" not in email or "." not in email.split("@")[-1]:
            st.error("That does not look like an email address. PubMed rejects "
                     "the request if it is not a real one.")
            return
        db.save_settings({
            "ncbi_email": email.strip(),
            "unpaywall_email": email.strip(),
            "ncbi_api_key": api_key.strip(),
            "s2_api_key": s2_key.strip(),
            "libkey_library_id": libkey.strip(),
        })
        st.session_state.settings = db.get_settings()
        st.rerun()

    if skipped:
        # Non si salva niente: la prossima volta la schermata ritorna, ed e'
        # giusto - senza email la ricerca non parte, e scoprirlo al primo
        # tentativo sarebbe peggio che rivedere questa pagina.
        st.session_state.setup_skipped = True
        st.rerun()

    st.caption("You can change all of this later under ⚙️ Settings in the sidebar.")


if (not (settings.get("ncbi_email") or "").strip()
        and not st.session_state.get("setup_skipped")):
    setup_screen()
    st.stop()


# ---------------------------------------------------------------------------
# sidebar: impostazioni + import manuale
# ---------------------------------------------------------------------------

with st.sidebar:
    if removed_at_boot:
        st.info(f"🧹 {removed_at_boot} already-read articles were purged at startup.")

    with st.expander("⚙️ Settings", expanded=not settings.get("ncbi_email")):
        with st.form("settings_form"):
            ncbi_email = st.text_input(
                "NCBI email", value=settings.get("ncbi_email", ""),
                help="Required by the E-utilities to identify the caller.")
            ncbi_key = st.text_input(
                "NCBI API key (optional)", value=settings.get("ncbi_api_key", ""),
                type="password", help="Raises the limit from 3 to 10 requests/second.")
            s2_key = st.text_input(
                "Semantic Scholar API key (optional)", value=settings.get("s2_api_key", ""),
                type="password", help="Without a key, enrichment is slower (~1 batch/sec).")
            libkey_id = st.text_input(
                "LibKey library ID", value=settings.get("libkey_library_id", ""),
                help="Your library's 'Third Iron library ID': it appears in the "
                     "URL libkey.io/libraries/<ID>/...")
            upw_email = st.text_input(
                "Unpaywall email", value=settings.get("unpaywall_email", ""),
                help="Unpaywall asks for an email in every request — it is not "
                     "a key and there is nothing to register. Left empty, the "
                     "NCBI email above is used.")
            font_rem = st.slider(
                "Title size (rem)", 1.0, 2.2, title_rem, 0.05)
            if st.form_submit_button("Save settings", width="stretch"):
                values = {
                    "ncbi_email": ncbi_email.strip(),
                    "ncbi_api_key": ncbi_key.strip(),
                    "s2_api_key": s2_key.strip(),
                    "libkey_library_id": libkey_id.strip(),
                    "unpaywall_email": upw_email.strip(),
                    "title_font_rem": f"{font_rem:.2f}",
                }
                db.save_settings(values)
                st.session_state.settings = db.get_settings()
                st.rerun()

    # Queste quattro non sono filtri della ricerca, sono il modo in cui l'app si
    # comporta: si scelgono una volta e si lasciano stare. Stavano in mezzo ai
    # filtri, dove costringevano a scorrere ogni volta oltre roba che non si
    # tocca mai. Sono qui, sempre visibili, e la scheda di ricerca resta breve.
    st.markdown("**⚙ Search behaviour**")
    max_results = st.number_input(
        "Max records to download", 10, MAX_SEARCH_RESULTS, step=10,
        key="sf_max_results",
        help="PubMed is queried in full regardless: this only caps how many "
             "records are downloaded in detail.")
    exclude_label = st.selectbox(
        "Skip what is already known", list(db.EXCLUDE_MODES.values()),
        key="sf_exclude",
        help="Applied right after esearch: a discarded PMID costs neither a "
             "PubMed nor a Semantic Scholar call.")
    exclude_mode = next(k for k, v in db.EXCLUDE_MODES.items() if v == exclude_label)
    use_s2 = st.checkbox("Citations (Semantic Scholar)", key="sf_s2")
    use_oa = st.checkbox("Open access (Unpaywall)", key="sf_oa")
    st.divider()

    with st.expander("📊 Journal metrics", expanded=False):
        st.caption(
            "Quartiles and SJR come from the SCImago file in the project "
            "folder. **This is not the Journal Impact Factor**: that one is "
            "Clarivate's and lives in the JCR. SJR weighs citations by the "
            "prestige of who makes them; *cites/doc (2y)* is the one computed "
            "like an impact factor, but over Scopus."
        )
        found_file = jr.find_file()
        if found_file is None:
            st.warning(
                "No SCImago file found. Download the CSV from scimagojr.com "
                "and drop it into the project folder — any name starting with "
                "`scimagojr`.")
        else:
            status = db.journal_metrics_status()
            st.caption(f"`{found_file.name}` — **{status['journals']:,}** journals · "
                       f"**{status['matched']:,}** of {status['articles']:,} "
                       f"articles matched to one.")
            if st.button("↻ Reload the file and re-match", width="stretch"):
                with st.status("Reading the SCImago file…", expanded=True) as box:
                    try:
                        rows = jr.read(found_file)
                    except jr.JournalDataError as exc:
                        box.update(label="Could not read it", state="error")
                        st.error(str(exc))
                    else:
                        box.write(f"{len(rows):,} journals read.")
                        db.import_journal_metrics(rows)
                        box.write("Matching the archive by ISSN…")
                        matched, seen = db.match_journals()
                        box.update(
                            label=f"{matched:,} of {seen:,} articles matched.",
                            state="complete")
                        load_journal_metrics.clear()
            st.caption(
                "Articles are matched by ISSN, which is exact. The ones left "
                "over are journals SCImago does not list at all — they show no "
                "quartile rather than a wrong one.")

    with st.expander("⇅ Export and backup", expanded=False):
        st.caption(
            "Two formats, and they are two different things. **`.nbib`** is "
            "PubMed's own export: the articles, and nothing else. Any reference "
            "manager reads it, and so does the import below. **`.json`** is the "
            "whole archive — what you marked read, what you flagged, your "
            "lists, your drafts — and it is the one to use when moving to "
            "another computer."
        )

        scopes = {"Everything": ("all", None),
                  "Flagged only": ("flagged", None),
                  "Still to read": ("unread", None)}
        for row in db.list_lists():
            scopes[f"List: {row['name']}"] = ("list", row["id"])
        picked = st.selectbox("What to export", list(scopes), key="exp_scope")
        scope, scope_list = scopes[picked]
        to_export = db.articles_for_export(scope, scope_list)
        st.download_button(
            f"⤓ {len(to_export)} article(s) as .nbib",
            data=backup.to_medline(to_export),
            file_name=backup.medline_filename(picked.replace("List: ", "")),
            mime="text/plain", width="stretch", disabled=not to_export,
            key="exp_medline")
        st.caption("Read, flagged, lists and drafts are not in a `.nbib`: "
                   "MEDLINE has no field for them.")

        st.divider()
        whole = backup.bundle()
        n = backup.counts(whole)
        st.download_button(
            "⤓ Full backup (.json)", data=backup.to_json(whole),
            file_name=backup.json_filename(), mime="application/json",
            width="stretch", key="exp_json")
        st.caption(
            f"{n['articles']:,} articles · {n['lists']} list(s) · "
            f"{n['drafts']} draft(s) · {n['citations']} resolved citation(s). "
            "**Settings are left out on purpose** — a backup file travels, and "
            "your email and keys should not travel with it."
        )

        st.divider()
        st.caption("**Restore a backup.** Nothing is overwritten: whatever is "
                   "already here is kept, and only what is missing is added.")
        incoming = st.file_uploader("Backup file", type=["json"],
                                    key="restore_file", label_visibility="collapsed")
        if incoming is not None:
            try:
                parsed = backup.read_bundle(incoming.getvalue())
            except backup.BackupError as exc:
                st.error(str(exc))
            else:
                got = backup.counts(parsed)
                st.caption(f"Written {str(parsed.get('exported'))[:10]} — "
                           f"{got['articles']:,} articles, {got['lists']} list(s), "
                           f"{got['drafts']} draft(s).")
                if st.button("Restore it", type="primary", width="stretch",
                             key="restore_go"):
                    with st.spinner("Putting it back…"):
                        report = backup.restore(parsed)
                    st.success(
                        f"Added {report['articles']:,} articles, "
                        f"{report['lists']} list(s) with {report['list_items']} "
                        f"entries, {report['drafts']} draft(s).")
                    st.rerun()

    with st.expander("📥 Import PubMed export", expanded=False):
        import_type = st.radio("Method:", ["Upload .txt file", "Paste raw text"])
        input_text = ""
        if import_type == "Upload .txt file":
            uploaded = st.file_uploader("PubMed export file", type=["txt", "nbib"])
            if uploaded is not None:
                input_text = uploaded.read().decode("utf-8", errors="replace")
        else:
            input_text = st.text_area("PubMed text (MEDLINE format):", height=200)

        if st.button("Import into database", width="stretch"):
            if input_text.strip():
                parsed = pubmed.parse_medline_text(input_text)
                added, skipped_screened, already = db.insert_articles(parsed)
                st.success(
                    f"Found {len(parsed)} articles. Imported {added} new ones "
                    f"({already} already in the archive, {skipped_screened} read and "
                    f"discarded in the past)."
                )
            else:
                st.warning("Nothing to import.")


# ---------------------------------------------------------------------------
# paginazione, condivisa da ricerca e screening
# ---------------------------------------------------------------------------

def render_pager(n_pages: int, key: str, *, compact: bool,
                 state_key: str = "screen_page") -> None:
    """Barra di paginazione. `compact` = prec/succ + salto diretto; altrimenti
    elenco numerato delle pagine. `state_key` dice quale contatore di pagina
    muovere: le schede della ricerca e quelle dello screening ne hanno uno
    per uno."""
    page = st.session_state.get(state_key, 1)

    if compact:
        c_prev, c_jump, c_next = st.columns([1, 2, 1])
        if c_prev.button("‹ Previous", disabled=page <= 1, key=f"{key}_prev",
                         width="stretch"):
            st.session_state[state_key] = page - 1
            st.rerun()
        with c_jump:
            # la chiave include la pagina corrente: senza, il widget conserva il
            # proprio vecchio valore e "rimanda indietro" i salti fatti con i
            # pulsanti numerati in fondo alla lista
            target = st.number_input(
                f"Page (of {n_pages})", 1, n_pages, page, 1,
                key=f"{key}_num_{page}_{n_pages}", label_visibility="collapsed")
            if target != page:
                st.session_state[state_key] = int(target)
                st.rerun()
        if c_next.button("Next ›", disabled=page >= n_pages, key=f"{key}_next",
                         width="stretch"):
            st.session_state[state_key] = page + 1
            st.rerun()
        return

    # elenco numerato: finestra di 7 pagine attorno a quella corrente, con i
    # bordi sempre raggiungibili
    window = {1, n_pages, page}
    window.update(range(max(1, page - 3), min(n_pages, page + 3) + 1))
    numbers = sorted(window)

    items: list[int | None] = []
    previous = 0
    for n in numbers:
        if previous and n - previous > 1:
            items.append(None)  # separatore
        items.append(n)
        previous = n

    cols = st.columns(len(items) + 2)
    if cols[0].button("«", disabled=page <= 1, key=f"{key}_first",
                      width="stretch"):
        st.session_state[state_key] = 1
        st.rerun()
    for col, item in zip(cols[1:-1], items):
        if item is None:
            col.markdown("<div style='text-align:center'>…</div>", unsafe_allow_html=True)
            continue
        if col.button(str(item), key=f"{key}_p{item}", width="stretch",
                      type="primary" if item == page else "secondary"):
            st.session_state[state_key] = item
            st.rerun()
    if cols[-1].button("»", disabled=page >= n_pages, key=f"{key}_last",
                       width="stretch"):
        st.session_state[state_key] = n_pages
        st.rerun()


# ---------------------------------------------------------------------------
# le faccette sui risultati gia' scaricati
# ---------------------------------------------------------------------------

def results_filters(records: list[dict], metric_of, status_by_pmid: dict,
                    gen: int) -> list[dict]:
    """Restringe i risultati SENZA rifare la ricerca.

    E' un'altra cosa dai filtri della query, e vale la pena tenerle separate:
    quelli decidono cosa PubMed spedisce e costano una ricerca ogni volta che
    li tocchi; questi decidono cosa guardi adesso, sono immediati e si
    ripensano venti volte. Un tipo di articolo tolto qui puo' essere rimesso
    subito dopo senza aspettare niente.

    Le chiavi dei widget portano dentro `gen`, che cambia a ogni ricerca nuova:
    un filtro dimenticato acceso nasconderebbe i risultati della ricerca
    seguente senza che si capisca perche'.
    """
    if not records:
        return records

    def counted(options: dict[str, int]) -> tuple[list[str], object]:
        return list(options), (lambda o: f"{o} ({options[o]})")

    # --- quello che c'e' davvero in questi risultati ---------------------
    status_counts: dict[str, int] = {}
    for state in status_by_pmid.values():
        status_counts[state] = status_counts.get(state, 0) + 1

    type_counts: dict[str, int] = {}
    for rec in records:
        for kind in {t.strip() for t in clean(rec.get("pub_types")).split(";") if t.strip()}:
            type_counts[kind] = type_counts.get(kind, 0) + 1
    type_options = dict(sorted(type_counts.items(), key=lambda kv: -kv[1]))

    NO_METRIC = "Not in SCImago"
    quartile_counts: dict[str, int] = {}
    for rec in records:
        metric = metric_of(rec)
        key = (metric["quartile"] if metric is not None else None) or NO_METRIC
        quartile_counts[key] = quartile_counts.get(key, 0) + 1
    quartile_options = {q: quartile_counts[q]
                        for q in jr.QUARTILES + [NO_METRIC] if q in quartile_counts}

    n_free = sum(1 for rec in records
                 if clean(rec.get("oa_status")) not in ("", "closed", "unknown"))
    asked_oa = any(clean(rec.get("oa_fetched_at")) for rec in records)

    years = sorted({int(y) for y in (clean(r.get("year")) for r in records)
                    if y.isdigit()})
    has_cites = any(rec.get("citation_count") is not None for rec in records)

    key = lambda name: f"rf_{name}_{gen}"    # noqa: E731

    def clear() -> None:
        for name in ("status", "types", "quartile", "oa", "years", "cites", "text"):
            st.session_state.pop(key(name), None)

    active = any(st.session_state.get(key(n)) for n in
                 ("status", "types", "quartile", "oa", "cites", "text"))

    with st.expander("⚙ Filter these results" + (" — on" if active else ""),
                     expanded=active):
        st.caption("Narrows what is shown below. PubMed is not queried again.")

        c1, c2 = st.columns(2)
        with c1:
            opts, fmt = counted(status_counts)
            f_status = st.multiselect("Status", opts, format_func=fmt,
                                      key=key("status"))
            opts, fmt = counted(type_options)
            f_types = st.multiselect(
                "Article type", opts, format_func=fmt, key=key("types"),
                help="The publication types NLM assigned to these very records.")
        with c2:
            opts, fmt = counted(quartile_options)
            f_quartile = st.multiselect("Journal quartile", opts, format_func=fmt,
                                        key=key("quartile"))
            f_text = st.text_input(
                "Words in title or abstract", key=key("text"),
                placeholder="e.g. paediatric")

        c3, c4 = st.columns(2)
        with c3:
            if asked_oa:
                f_oa = st.checkbox(f"Only free full text ({n_free})",
                                   key=key("oa"))
            else:
                f_oa = False
                st.caption("Open access: not looked up for these records — "
                           "tick *Check open access with Unpaywall* in Filters "
                           "before searching.")
            f_cites = st.number_input(
                "At least this many citations", 0, 10000, step=1,
                key=key("cites"), disabled=not has_cites,
                help=None if has_cites else
                "No citation data: enrich with Semantic Scholar first.")
        with c4:
            if len(years) > 1:
                f_years = st.slider("Published between", years[0], years[-1],
                                    (years[0], years[-1]), key=key("years"))
            else:
                f_years = None
            st.write("")
            st.button("✕ Clear these filters", on_click=clear,
                      key=f"rf_clear_{gen}", width="stretch")

    def keep(rec: dict) -> bool:
        if f_status and status_by_pmid.get(rec["pmid"]) not in f_status:
            return False
        if f_types:
            mine = {t.strip() for t in clean(rec.get("pub_types")).split(";")}
            if not mine & set(f_types):
                return False
        if f_quartile:
            metric = metric_of(rec)
            quartile = (metric["quartile"] if metric is not None else None) or NO_METRIC
            if quartile not in f_quartile:
                return False
        if f_oa and clean(rec.get("oa_status")) in ("", "closed", "unknown"):
            return False
        if f_cites:
            got = rec.get("citation_count")
            if got is None or got < f_cites:
                return False
        if f_years:
            year = clean(rec.get("year"))
            # Un record senza anno non si butta via: e' un dato che manca, non
            # un articolo fuori dall'intervallo.
            if year.isdigit() and not (f_years[0] <= int(year) <= f_years[1]):
                return False
        if f_text:
            needle = f_text.strip().lower()
            haystack = (clean(rec.get("title")) + " "
                        + clean(rec.get("abstract"))).lower()
            if needle and needle not in haystack:
                return False
        return True

    return [rec for rec in records if keep(rec)]


# ---------------------------------------------------------------------------
# il compositore di ricerche a blocchi
# ---------------------------------------------------------------------------

# I blocchi vivono in session_state come dizionari, non come dataclass: ogni
# riga ha un `id` che non viene mai riusato, e la chiave dei widget si costruisce
# da li'. Senza, togliere il secondo di tre termini farebbe scalare le chiavi di
# uno e il testo del terzo comparirebbe nella casella del secondo - Streamlit
# tiene il valore per chiave, non per posizione.

def qb_next_id() -> int:
    st.session_state.qb_seq = st.session_state.get("qb_seq", 0) + 1
    return st.session_state.qb_seq


def qb_new_term(text: str = "", field: str = "tiab") -> dict:
    return {"id": qb_next_id(), "text": text, "field": field}


def qb_new_block(join: str = "AND", terms: list[dict] | None = None,
                 label: str = "") -> dict:
    return {"id": qb_next_id(), "label": label, "join": join, "inner": "OR",
            "enabled": True, "terms": terms if terms is not None else [qb_new_term()]}


def qb_state() -> list[dict]:
    if "qb_blocks" not in st.session_state:
        st.session_state.qb_blocks = [qb_new_block()]
    return st.session_state.qb_blocks


def qb_model(raw: list[dict]) -> list[qb.Block]:
    """Dai dizionari della UI ai blocchi che `querybuilder` sa comporre."""
    return [
        qb.Block(
            label=b.get("label", ""),
            terms=[qb.Term(t.get("text", ""), t.get("field", "tiab"))
                   for t in b.get("terms", [])],
            inner=b.get("inner", "OR"),
            join=b.get("join", "AND"),
            enabled=bool(b.get("enabled", True)),
        )
        for b in raw
    ]


def qb_block_name(n: int, block: dict) -> str:
    return block.get("label") or f"Block {n}"


def strategy_panel(blocks: list[dict]) -> None:
    """Termini di ricerca ricavati dai titoli di un articolo Radiopaedia.

    I titoli di un articolo sono gia' la scaletta della ricerca da fare: se
    nella bozza c'e' `Epidemiology` la ricerca vuole prevalenza e incidenza, se
    c'e' `MRI` vuole la risonanza. Qui si sceglie da dove prendere i titoli - la
    bozza vera, o la struttura che Radiopaedia raccomanda per quel tipo di
    articolo - e ogni titolo diventa un pezzo di query.

    Vanno tutti in UN blocco solo, in OR fra loro. Metterli in blocchi diversi
    li legherebbe in AND, e chiederebbe a PubMed un lavoro che parla insieme di
    epidemiologia, risonanza e prognosi: quasi sempre zero risultati."""
    st.caption(
        "Every heading is turned into the terms the literature actually uses "
        "for it — controlled vocabulary (MeSH), words from the title and "
        "abstract, or both."
    )

    source = st.radio(
        "Take the headings from", ["A draft", "An article type"],
        horizontal=True, key="stg_source", label_visibility="collapsed")

    titles: list[str] = []
    if source == "A draft":
        drafts = db.list_drafts()
        if not drafts:
            st.caption("No drafts yet — write one in the Write tab, or take the "
                       "headings from an article type instead.")
            return
        # Si sceglie per id e non per riga: un widget con `key` finisce in
        # session_state, che Streamlit copia in profondita', e una sqlite3.Row
        # non e' copiabile - la pagina intera andrebbe in errore.
        by_id = {r["id"]: r for r in drafts}
        chosen_id = st.selectbox(
            "Draft", list(by_id), format_func=lambda i: by_id[i]["title"],
            key="stg_draft")
        if chosen_id is None:
            return
        titles = [h.title for h in sx.headings_in(by_id[chosen_id]["body_md"] or "")]
        if not titles:
            st.caption("That draft has no headings yet.")
            return
    else:
        try:
            labels = sx.profile_labels()
        except sx.StructureError as exc:
            st.warning(str(exc))
            return
        names = list(labels)
        profile = st.selectbox(
            "Kind of article", names, format_func=lambda n: labels[n],
            key="stg_profile")
        titles = [r.title for r in sx.rows_for(profile)]

    mode_key = st.radio(
        "Terms", list(stg.MODES), horizontal=True, key="stg_mode",
        format_func=lambda k: stg.MODES[k])

    pairs = stg.suggest(titles, mode_key)
    if not pairs:
        st.caption("None of those headings has a search strategy — they are "
                   "sections of the article rather than angles to search.")
        return

    st.caption(f"{len(pairs)} of the {len(set(titles))} headings have one.")
    # Nella chiave c'e' un contatore, come per la casella del testo della bozza:
    # dopo aver aggiunto le strategie la scelta va svuotata, e Streamlit non
    # lascia scrivere la voce di un widget gia' creato. Cambiando la chiave il
    # widget successivo e' un widget nuovo, e riparte vuoto.
    stamp = st.session_state.get("stg_gen", 0)
    picked = st.multiselect(
        "Headings", [name for name, _ in pairs], key=f"stg_picked_{stamp}",
        placeholder="Choose the headings to turn into terms…")

    if picked:
        by_name = dict(pairs)
        with st.container(height=150, border=True):
            for name in picked:
                st.caption(f"**{name}** → `{by_name[name]}`")

    targets = ["A new block, joined with AND"] + [
        f"Into {qb_block_name(n, b)}" for n, b in enumerate(blocks, 1)]
    # anche qui la chiave si muove con le opzioni: se un blocco viene tolto,
    # la scelta di prima non esiste piu' fra quelle possibili
    target = st.selectbox("Where do they go", targets,
                          key=f"stg_target_{len(blocks)}_{stamp}")

    if st.button(f"Add {len(picked)} strateg{'y' if len(picked) == 1 else 'ies'}",
                 disabled=not picked, key="stg_add", type="primary"):
        by_name = dict(pairs)
        # `raw`: sono gia' scritte in sintassi PubMed, tag di campo compresi,
        # e appiccicargliene un altro le romperebbe
        terms = [qb_new_term(by_name[name], "raw") for name in picked]
        if target == targets[0]:
            blocks.append(qb_new_block(join="AND", terms=terms,
                                       label="Radiopaedia headings"))
        else:
            blocks[targets.index(target) - 1]["terms"].extend(terms)
        st.session_state.stg_gen = stamp + 1
        st.rerun()


def search_builder() -> str:
    """Il compositore. Ritorna la stringa di ricerca che ne esce."""
    blocks = qb_state()

    st.caption(
        "**One block per concept** — the disease, the modality, the kind of "
        "study. Inside a block you write the same thing in every way the "
        "literature writes it, and those lines are joined by **OR** (any one is "
        "enough). The blocks are joined by **AND** (all of them must hold). "
        "PubMed reads the operators left to right, so what you see below is "
        "what it does."
    )

    to_drop: int | None = None
    for n, block in enumerate(blocks, 1):
        with st.container(border=True):
            head_op, head_name, head_del = st.columns([1, 4, 0.6])
            if n == 1:
                head_op.caption("")
            else:
                block["join"] = head_op.selectbox(
                    "Joined by", qb.OPERATORS,
                    index=qb.OPERATORS.index(block.get("join", "AND")),
                    key=f"qbj_{block['id']}", label_visibility="collapsed")
            block["label"] = head_name.text_input(
                "Block name", value=block.get("label", ""),
                key=f"qbl_{block['id']}", label_visibility="collapsed",
                placeholder=f"Block {n} — a name, if you want one")
            head_del.write("")
            if head_del.button("🗑", key=f"qbd_{block['id']}",
                               disabled=len(blocks) == 1,
                               help="Remove this block"):
                to_drop = n - 1

            drop_term: int | None = None
            for m, term in enumerate(block["terms"]):
                c_text, c_field, c_del = st.columns([4, 1.6, 0.6])
                term["text"] = c_text.text_input(
                    "Term", value=term.get("text", ""),
                    key=f"qbt_{block['id']}_{term['id']}",
                    label_visibility="collapsed",
                    placeholder="one wording of this concept")
                term["field"] = c_field.selectbox(
                    "Field", list(qb.FIELDS),
                    index=list(qb.FIELDS).index(term.get("field", "tiab")),
                    format_func=lambda k: qb.FIELD_LABELS[k],
                    key=f"qbf_{block['id']}_{term['id']}",
                    label_visibility="collapsed")
                c_del.write("")
                if c_del.button("✕", key=f"qbx_{block['id']}_{term['id']}",
                                disabled=len(block["terms"]) == 1,
                                help="Remove this term"):
                    drop_term = m
            if drop_term is not None:
                block["terms"].pop(drop_term)
                st.rerun()

            b_add, b_inner, b_prev = st.columns([1.2, 1.2, 3])
            if b_add.button("＋ Another wording", key=f"qba_{block['id']}",
                            width="stretch",
                            help="Another way the same thing gets written — "
                                 "“myocardial infarction”, “MI”, “heart "
                                 "attack”. They are joined with OR, so a paper "
                                 "matching any one of them is found."):
                block["terms"].append(qb_new_term())
                st.rerun()
            block["inner"] = b_inner.selectbox(
                "Joined by", ["OR", "AND", "NOT"],
                index=["OR", "AND", "NOT"].index(block.get("inner", "OR")),
                key=f"qbi_{block['id']}", label_visibility="collapsed",
                help="How the lines inside this block are joined. OR is what a "
                     "list of wordings wants: any one of them is enough.")
            rendered = qb.render_block(qb_model([block])[0])
            b_prev.caption(f"`{rendered}`" if rendered else "empty — no terms yet")

    if to_drop is not None:
        blocks.pop(to_drop)
        st.rerun()

    add_col, clear_col, _ = st.columns([1, 1, 3])
    if add_col.button("＋ Add a block", width="stretch", key="qb_add_block"):
        blocks.append(qb_new_block())
        st.rerun()
    if clear_col.button("↺ Start over", width="stretch", key="qb_reset"):
        st.session_state.qb_blocks = [qb_new_block()]
        st.rerun()

    with st.expander("⌗ Terms from the Radiopaedia headings", expanded=False):
        strategy_panel(blocks)

    for msg in qb.problems(qb_model(blocks)):
        if not msg.startswith("No terms yet"):
            st.warning(msg)

    return qb.compose(qb_model(blocks))


tab_search, tab_screen, tab_write = st.tabs(
    ["🔎 PubMed search", "📚 Screening", "✍️ Write"])


# ---------------------------------------------------------------------------
# TAB 1 - ricerca
# ---------------------------------------------------------------------------

with tab_search:
    how = st.segmented_control(
        "How to search", ["✎ One line", "⛁ Blocks"], default="✎ One line",
        key="search_how", label_visibility="collapsed",
        help="One line takes PubMed syntax as you write it. Blocks builds the "
             "query one concept at a time — synonyms in OR, concepts in AND — "
             "and can turn the headings of a Radiopaedia article into terms.")

    if how == "⛁ Blocks":
        terms = search_builder()
        if terms:
            st.caption("The search terms this builds:")
            st.code(terms, language="text")
    else:
        terms = st.text_input(
            "Search terms",
            key="search_terms",
            placeholder='e.g. "Joubert syndrome" OR "molar tooth sign"',
            help="Accepts native PubMed syntax (AND/OR/NOT, [Title/Abstract], [MeSH Terms]...).",
        )

    # I filtri stanno SEMPRE a schermo, senza expander. Non e' una scelta di
    # gusto: un widget dentro un `st.expander` fa ripartire lo script e
    # l'expander si ridisegna col proprio `expanded=` di default, cioe' si
    # richiude a ogni spunta. E non si puo' nemmeno smettere di disegnarli
    # quando il pannello e' chiuso, perche' Streamlit butta via lo stato dei
    # widget che non disegna: il numero di anni tornerebbe al suo default senza
    # che nessuno l'abbia toccato. Sempre visibili, e compatti.
    st.session_state.setdefault("sf_recent", True)

    with st.container(border=True):
        tg, clr = st.columns([4, 1])
        with tg:
            st.toggle(
                RECENT_REVIEWS_LABEL, key="sf_recent", on_change=on_recent_reviews,
                help="A bundle, not a button: while it is on, these are the "
                     "filters, and the controls below show what it set. Switch "
                     "it off to change them by hand.")
        clr.button(
            "↺ Clear all", key="sf_clear", width="stretch",
            on_click=apply_search_preset, args=("open",),
            help="Every filter off, no date limit: only the search terms are left.")

        locked = bool(st.session_state.sf_recent)
        st.caption(("**On** — " if locked else "**Off.** It would set: ")
                   + RECENT_REVIEWS_WHAT
                   + (" Switch it off to change any of them." if locked else ""))

        fc1, fc2, fc3 = st.columns([1, 2, 2])
        with fc1:
            # zero e' un valore legittimo e vuol dire "nessun limite di data".
            # Prima il minimo era 1: non c'era modo di dire "tutta la
            # letteratura", e cinquant'anni sembravano quello senza esserlo.
            years = st.number_input(
                "Last N years", 0, 100, step=1, key="sf_years", disabled=locked,
                help="0 = no date limit at all.")
            st.caption("No date limit." if not years else f"Since {TODAY.year - int(years)}.")
        with fc2:
            type_labels = st.multiselect(
                "Article types", pubmed.DEFAULT_TYPE_LABELS, key="sf_types",
                disabled=locked,
                help="PubMed's own publication types, as NLM assigned them.")
        with fc3:
            # I filtri ISSG non dicono DI COSA parla un lavoro, dicono CHE
            # GENERE di lavoro e': sono le stringhe con cui gli information
            # specialist intercettano linee guida e revisioni sistematiche.
            issg_labels = st.multiselect(
                "Study design filters (ISSG)", list(issg.LABELS.values()),
                key="sf_issg",
                help="Published search filters from the InterTASC Information "
                     "Specialists' Sub-Group. They catch a kind of publication "
                     "by the words it uses, not by a subject. Choosing more "
                     "than one asks for either of them.")

        bc1, bc2, bc3 = st.columns(3)
        f_fulltext = bc1.checkbox("Full text", key="sf_fulltext", disabled=locked)
        f_english = bc2.checkbox("English", key="sf_english", disabled=locked)
        f_humans = bc3.checkbox("Humans", key="sf_humans", disabled=locked)

        for label in issg_labels:
            st.caption(f"· **{label}** — {issg.FILTERS[issg.BY_LABEL[label]][2]}")
        issg_clause = issg.clause(issg_labels)
        if issg_clause:
            st.caption(f"The ISSG filter adds {len(issg_clause):,} characters "
                       f"to the query.")
        if issg_clause and (locked or type_labels):
            # Sono due modi di chiedere la stessa cosa, e messi insieme non
            # sommano: moltiplicano. `Review[pt]` prende quello che gli
            # indicizzatori NLM hanno etichettato review; l'ISSG prende quello
            # che si presenta come tale nel titolo, nell'abstract e nelle parole
            # dell'autore. In AND restano solo i lavori che sono tutt'e due, e
            # sono molti meno di quanto uno si aspetti.
            st.warning(
                "**Two filters for the same idea.** "
                + (f"“{RECENT_REVIEWS_LABEL}”" if locked else "*Article types*")
                + " restricts by the publication type NLM assigned; an ISSG "
                "filter restricts by the words the paper uses. They are joined "
                "with AND, so only what satisfies both survives — usually far "
                "fewer results than you meant. Pick one approach.")

    query_preview = ""
    if terms.strip():
        try:
            query_preview = pubmed.build_query(
                terms, type_labels=type_labels, years=int(years),
                full_text=f_fulltext, english=f_english, humans=f_humans,
                filters=[issg_clause])
        except pubmed.PubMedError as exc:
            st.warning(str(exc))
        else:
            # con un filtro ISSG dentro la query supera i tremila caratteri:
            # stamparla per intero seppellirebbe il pulsante di ricerca
            if len(query_preview) > 700:
                with st.expander(f"The query PubMed receives "
                                 f"({len(query_preview):,} characters)",
                                 expanded=False):
                    st.code(query_preview, language="text")
            else:
                st.code(query_preview, language="text")

    if st.button("🔎 Search PubMed", type="primary", disabled=not query_preview):
        email = (settings.get("ncbi_email") or "").strip()
        if not email:
            st.error("Set the NCBI email in the sidebar first (⚙️ Settings).")
        else:
            api_key = (settings.get("ncbi_api_key") or "").strip()
            params = pubmed.ncbi_params(email, api_key)
            params["_pause"] = pubmed.pause(api_key)
            session = http_session()
            status = st.status("Querying PubMed...", expanded=True)
            try:
                already = db.known_pmids(exclude_mode)
                unmatched: list[str] = []
                total, pmids, n_excluded = pubmed.esearch(
                    query_preview, session, params, max_results=int(max_results),
                    exclude=already,
                    progress=lambda n, exc, seen, tot: status.write(
                        f"PMIDs examined {seen}/{tot} — {n} new, {exc} already known and skipped"),
                    warn=unmatched.extend)
                if unmatched:
                    # non e' un errore: PubMed le nomina solo quando il totale e'
                    # zero, e le stringhe pubblicate dell'ISSG ne contengono
                    status.write(
                        "ℹ️ Nothing in PubMed matches these pieces of the query: "
                        + ", ".join(f"`{u}`" for u in dict.fromkeys(unmatched))
                        + ". The rest of the query ran normally.")
                status.write(
                    f"PubMed reports **{total}** results. "
                    f"Skipped **{n_excluded}** already in the database, "
                    f"downloading **{len(pmids)}**."
                )
                records = pubmed.efetch(
                    pmids, session, params,
                    progress=lambda n, t: status.write(f"Details downloaded: {n}/{t}"))
                status.write(f"Complete records: {len(records)}.")

                if use_s2 and records:
                    status.write("Fetching citation data from Semantic Scholar...")
                    try:
                        enrich = s2.enrich(
                            [r["pmid"] for r in records],
                            api_key=(settings.get("s2_api_key") or "").strip(),
                            progress=lambda n, t: status.write(f"Semantic Scholar: {n}/{t}"))
                    except s2.SemanticScholarError as exc:
                        enrich = {}
                        status.write(f"⚠️ Semantic Scholar unavailable: {exc}")
                    for rec in records:
                        rec.update(enrich.get(rec["pmid"], {}))
                    found = sum(1 for v in enrich.values() if v.get("s2_paper_id"))
                    status.write(
                        f"Citation data found for {found} of {len(enrich)} records.")

                if use_oa and records:
                    email = unpaywall_email()
                    with_doi = {clean(r.get("doi")).lower(): r for r in records
                                if clean(r.get("doi"))}
                    if not email:
                        status.write("⚠️ Unpaywall skipped: no email set in the "
                                     "sidebar settings.")
                    elif not with_doi:
                        status.write("No DOIs among these records: nothing to "
                                     "ask Unpaywall.")
                    else:
                        status.write(f"Asking Unpaywall about {len(with_doi)} DOIs…")
                        oa = upw.enrich(
                            list(with_doi), email, session,
                            progress=lambda n, t: status.write(f"Unpaywall: {n}/{t}"))
                        for doi, found in oa.items():
                            rec = with_doi.get(doi)
                            if rec:
                                rec["oa_status"] = found["oa_status"]
                                rec["oa_url"] = found["oa_url"]
                                rec["oa_fetched_at"] = found["oa_fetched_at"]
                        free = sum(1 for v in oa.values()
                                   if v["oa_status"] not in ("closed", "unknown"))
                        status.write(f"{free} of {len(oa)} have a free full text.")

                for rec in records:
                    rec["source_query"] = query_preview

                search_id = db.log_search(terms.strip(), query_preview, total, len(records))
                st.session_state.search_results = records
                st.session_state.search_id = search_id
                st.session_state.search_total = total
                st.session_state.search_excluded = n_excluded
                st.session_state.search_selection = {}
                st.session_state.search_gen = st.session_state.get("search_gen", 0) + 1
                status.update(
                    label=(f"Search complete: {len(records)} new records."
                           if records else
                           f"No new results: all {n_excluded} matches found are "
                           f"already in the database."),
                    state="complete", expanded=not records)
            except (pubmed.PubMedError, requests.RequestException) as exc:
                status.update(label="Search failed", state="error", expanded=True)
                st.error(f"Error during the search: {exc}")

    results = st.session_state.get("search_results") or []

    if results:
        in_db, screened = db.classify_pmids([r["pmid"] for r in results])
        selection = st.session_state.setdefault("search_selection", {})
        gen = st.session_state.get("search_gen", 0)

        # Lo stato di ogni record - nuovo, gia' in archivio, gia' screenato -
        # si sa prima di disegnare: serve alle faccette, che ci filtrano sopra.
        status_by_pmid = {
            rec["pmid"]: ("screened" if rec["pmid"] in screened else
                          "in archive" if rec["pmid"] in in_db else "new")
            for rec in results
        }

        st.divider()
        head_l, head_r = st.columns([2, 1])
        with head_l:
            st.subheader(
                f"{len(results)} records downloaded "
                f"(out of {st.session_state.get('search_total', len(results))} found)")
            n_excluded = st.session_state.get("search_excluded", 0)
            if n_excluded:
                st.caption(f"🚫 {n_excluded} results excluded: already in the database.")
        with head_r:
            sort_label = st.selectbox("Sort by", list(SORT_OPTIONS), index=0)
        sort_col = SORT_OPTIONS[sort_label]

        # Le metriche delle riviste di QUESTA pagina di risultati, in due query.
        # I record non sono ancora in archivio, quindi un aggancio salvato non
        # ce l'hanno: si chiedono le poche riviste che compaiono qui.
        def journal_key(rec) -> str:
            return jr.norm_title(rec.get("journal_title") or rec.get("journal") or "")

        by_issn, by_title = db.metrics_for(
            [i for rec in results for i in (rec.get("issn") or "").split("; ")],
            [journal_key(rec) for rec in results])

        def metric_of(rec):
            for issn in (rec.get("issn") or "").split("; "):
                if issn in by_issn:
                    return by_issn[issn]
            return by_title.get(journal_key(rec))

        shown = results_filters(results, metric_of, status_by_pmid, gen)

        def sort_key(rec):
            if sort_col == "_sjr":
                metric = metric_of(rec)
                v = metric["sjr"] if metric is not None else None
            else:
                v = rec.get(sort_col)
            try:
                return -float(v)
            except (TypeError, ValueError):
                return float("inf")  # i record senza dato finiscono in fondo

        ordered = sorted(shown, key=sort_key)
        if len(shown) != len(results):
            st.caption(f"**Showing {len(shown)} of {len(results)}** — "
                       f"{len(results) - len(shown)} hidden by the filters above.")

        rows = []
        for rec in ordered:
            pmid = rec["pmid"]
            state = status_by_pmid[pmid]
            metric = metric_of(rec)
            rows.append({
                "Save": selection.get(pmid, state == "new"),
                "Status": state,
                "PMID": pmid,
                "Q": (metric["quartile"] if metric is not None else None) or "",
                "SJR": number(metric["sjr"]) if metric is not None else None,
                "Year": clean(rec.get("year")),
                "Cites": rec.get("citation_count"),
                "Infl.": rec.get("influential_citations"),
                "Cites/yr": rec.get("citations_per_year"),
                "Title": clean(rec.get("title")),
                "Journal": clean(rec.get("journal")),
                "Type": clean(rec.get("pub_types")),
                "PubMed": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "LibKey": libkey_url(pmid) or "",
            })
        table = pd.DataFrame(rows)

        b1, b2, b3, b4, b5 = st.columns([1, 1, 1, 1.4, 1.6])
        if b1.button("Select all"):
            st.session_state.search_selection = {r["PMID"]: True for r in rows}
            st.session_state.search_gen = gen + 1
            st.rerun()
        if b2.button("Clear selection"):
            st.session_state.search_selection = {r["PMID"]: False for r in rows}
            st.session_state.search_gen = gen + 1
            st.rerun()
        if b3.button("New ones only"):
            st.session_state.search_selection = {
                r["PMID"]: r["Status"] == "new" for r in rows}
            st.session_state.search_gen = gen + 1
            st.rerun()
        with b4:
            view = st.radio("View", ["Cards", "Table"], horizontal=True,
                            key="search_view", label_visibility="collapsed")
        with b5:
            per_page = st.selectbox(
                "Cards per page", SEARCH_PAGE_SIZE_OPTIONS, index=1,
                key="search_per_page", label_visibility="collapsed",
                format_func=lambda n: f"{n} per page",
                disabled=view == "Table")

        if view == "Table":
            edited = st.data_editor(
                table,
                key=f"results_editor_{gen}_{sort_col}",
                hide_index=True,
                width="stretch",
                height=520,
                disabled=[c for c in table.columns if c != "Save"],
                column_config={
                    "Save": st.column_config.CheckboxColumn("Save", width="small"),
                    "Status": st.column_config.TextColumn("Status", width="small"),
                    "PMID": st.column_config.TextColumn("PMID", width="small"),
                    "Q": st.column_config.TextColumn(
                        "Q", width="small",
                        help="SCImago's best quartile for the journal"),
                    "SJR": st.column_config.NumberColumn("SJR", width="small",
                                                         format="%.2f"),
                    "Year": st.column_config.TextColumn("Year", width="small"),
                    "Cites": st.column_config.NumberColumn("Cites", width="small",
                                                           help="Total citations (Semantic Scholar)"),
                    "Infl.": st.column_config.NumberColumn("Infl.", width="small",
                                                           help="Influential citations (Semantic Scholar)"),
                    "Cites/yr": st.column_config.NumberColumn("Cites/yr", width="small",
                                                              format="%.2f"),
                    "Title": st.column_config.TextColumn("Title", width="large"),
                    "Journal": st.column_config.TextColumn("Journal", width="medium"),
                    "Type": st.column_config.TextColumn("Type", width="medium"),
                    "PubMed": st.column_config.LinkColumn("PubMed", display_text="open",
                                                          width="small"),
                    "LibKey": st.column_config.LinkColumn("LibKey", display_text="full text",
                                                          width="small"),
                },
            )

            for pmid, keep in zip(edited["PMID"], edited["Save"]):
                selection[str(pmid)] = bool(keep)
        else:
            # stessa resa della scheda Screening: e' li' che si legge davvero, e
            # scorrere una tabella senza abstract non dice quasi niente
            n_pages = max(1, -(-len(ordered) // per_page))
            fingerprint = (gen, sort_col, per_page)
            if st.session_state.get("search_fingerprint") != fingerprint:
                st.session_state.search_fingerprint = fingerprint
                st.session_state.search_page = 1
            page = min(max(1, st.session_state.get("search_page", 1)), n_pages)
            st.session_state.search_page = page
            st.caption(f"Page {page} of {n_pages} — showing "
                       f"{min(per_page, len(ordered) - (page - 1) * per_page)} "
                       f"of {len(ordered)} records.")
            if n_pages > 1:
                render_pager(n_pages, "search_top", compact=True,
                             state_key="search_page")

            for rec in ordered[(page - 1) * per_page: page * per_page]:
                pmid = rec["pmid"]
                state = status_by_pmid.get(pmid, "new")
                # la spunta di default finisce subito nella selezione, altrimenti
                # il contatore "Save N selected" direbbe zero senza un click
                checked = selection.setdefault(pmid, state == "new")

                with st.container(border=True):
                    col_meta, col_actions = st.columns([5, 1.3])

                    with col_meta:
                        mark = {"new": "🆕 ", "in archive": "📥 ",
                                "screened": "✅ "}[state]
                        st.markdown(
                            f'<div class="art-title">{mark}'
                            f'{html.escape(clean(rec.get("title")) or "No title available")}</div>',
                            unsafe_allow_html=True,
                        )
                        meta_bits = [b for b in [
                            html.escape(clean(rec.get("authors"))),
                            html.escape(clean(rec.get("journal"))),
                            html.escape(clean(rec.get("pub_date")) or clean(rec.get("year"))),
                            f"PMID {pmid}",
                        ] if b]
                        st.markdown(f'<div class="art-meta">{" · ".join(meta_bits)}</div>',
                                    unsafe_allow_html=True)

                        badges = journal_badges(metric_of(rec))
                        free_badge = oa_badge(rec.get("oa_status"))
                        if free_badge:
                            badges.append(free_badge)
                        badges.extend(html.escape(t)
                                      for t in useful_types(rec.get("pub_types")))
                        cites = citation_badge(rec.get("citation_count"),
                                               rec.get("influential_citations"),
                                               rec.get("citations_per_year"))
                        if cites:
                            badges.append(cites)
                        if badges:
                            st.markdown(
                                '<div class="art-badges">'
                                + "".join(b if b.startswith("<span") else f"<span>{b}</span>"
                                          for b in badges)
                                + "</div>",
                                unsafe_allow_html=True,
                            )

                        links = [f"[PubMed](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)"]
                        lk = libkey_url(pmid)
                        if lk:
                            links.append(f"[🔓 LibKey full text]({lk})")
                        doi = clean(rec.get("doi"))
                        if doi:
                            links.append(f"[DOI](https://doi.org/{doi})")
                        free = clean(rec.get("oa_url")) or clean(rec.get("oa_pdf_url"))
                        if free:
                            links.append(f"[Free full text]({free})")
                        st.markdown(" · ".join(links))

                    with col_actions:
                        # la chiave porta dentro `gen`: i pulsanti Select all /
                        # Clear selection lo incrementano, e cosi' le spunte si
                        # ricreano invece di restare ferme sul valore vecchio
                        pick_key = f"pick_{gen}_{pmid}"
                        st.checkbox("💾 Save", value=checked, key=pick_key,
                                    on_change=on_pick, args=(pmid, pick_key))
                        st.caption(state)

                    with st.expander("Abstract", expanded=False):
                        st.write(clean(rec.get("abstract")) or "No abstract available.")

            if n_pages > 1:
                st.divider()
                render_pager(n_pages, "search_bottom", compact=False,
                             state_key="search_page")

        # Solo quello che si vede. Col filtro per quartile acceso, una spunta
        # lasciata su un record ora nascosto non deve finire in un salvataggio
        # che nessuno ha piu' davanti agli occhi.
        visible = [r for r in ordered if selection.get(r["pmid"])]
        n_selected = len(visible)
        save_col, list_col, draft_col = st.columns([1.2, 2, 2])
        with save_col:
            if st.button(f"💾 Save {n_selected} selected", type="primary",
                         disabled=n_selected == 0):
                chosen = visible
                added, skipped_screened, already = db.insert_articles(chosen)
                db.bump_search_saved(st.session_state.get("search_id"), added)
                st.success(
                    f"Saved {added} new articles "
                    f"({already} already in the archive, {skipped_screened} read and "
                    f"discarded in the past). Go to the Screening tab."
                )
        with list_col:
            # Una lista non e' uno stato dell'articolo: e' un raccoglitore che
            # decidi tu, e lo stesso lavoro puo' stare in piu' liste. Per finirci
            # deve pero' essere in archivio, altrimenti la lista conterrebbe un
            # PMID di cui non si sa piu' niente: si salva e si mette in lista in
            # un gesto solo.
            existing = db.list_lists()
            names = [r["name"] for r in existing]
            NEW = "＋ New list…"
            target_name = st.selectbox(
                "Add to list", [NEW] + names, index=None,
                label_visibility="collapsed",
                placeholder="Add selected to a list…", key="search_list_pick")
            fresh_name = ""
            if target_name == NEW:
                fresh_name = st.text_input(
                    "New list name", key="search_list_new",
                    label_visibility="collapsed", placeholder="Name of the new list")
            if target_name is not None and st.button(
                    f"🗂 Add {n_selected} to list", disabled=n_selected == 0,
                    key="search_list_add", width="stretch"):
                if target_name == NEW:
                    list_id = db.create_list(fresh_name)
                    if list_id is None:
                        st.error("Give the list a name that no other list has.")
                        list_id = None
                else:
                    list_id = next(r["id"] for r in existing if r["name"] == target_name)
                if list_id is not None:
                    chosen = visible
                    added, _, _ = db.insert_articles(chosen)
                    db.bump_search_saved(st.session_state.get("search_id"), added)
                    n_in = db.add_to_list(list_id, [r["pmid"] for r in chosen],
                                          note="from a search")
                    label = fresh_name if target_name == NEW else target_name
                    st.success(f"{n_in} article(s) added to “{label}” "
                               f"({added} of them new to the archive).")

        with draft_col:
            # la stessa selezione serve due scopi: entrare in coda di screening
            # e diventare bibliografia di un articolo che stai scrivendo
            open_drafts = db.list_drafts()
            if open_drafts:
                target = st.selectbox(
                    "Add to draft", open_drafts, index=None,
                    format_func=lambda r: r["title"], label_visibility="collapsed",
                    placeholder="Add selected to a draft…")
                if target is not None and st.button(
                        f"✍️ Add {n_selected} as references", disabled=n_selected == 0):
                    pmids = [r["pmid"] for r in visible]
                    n_added = db.add_draft_refs(target["id"], pmids, note="from a search")
                    if st.session_state.get("search_id"):
                        db.attach_search(target["id"], st.session_state["search_id"])
                    st.success(f"Added {n_added} reference(s) to “{target['title']}” "
                               f"and attached this search to it.")

        if not libkey_url("0"):
            st.caption("💡 Set the LibKey library ID in the sidebar to get "
                       "direct full-text links.")

    with st.expander("🕘 Recent searches", expanded=False):
        history = db.recent_searches()
        if history:
            st.dataframe(
                pd.DataFrame([dict(r) for r in history])[
                    ["run_at", "terms", "n_found", "n_fetched", "n_saved"]
                ].rename(columns={"run_at": "When", "terms": "Terms",
                                  "n_found": "Found", "n_fetched": "Downloaded",
                                  "n_saved": "Saved"}),
                hide_index=True, width="stretch",
            )
        else:
            st.caption("No searches recorded yet.")


# ---------------------------------------------------------------------------
# TAB 2 - screening
# ---------------------------------------------------------------------------

with tab_screen:
    st.subheader("📚 Articles in the archive")

    all_lists = db.list_lists()

    # ----------------------------------------------------------------------
    # le liste
    # ----------------------------------------------------------------------
    with st.expander(f"🗂 Lists ({len(all_lists)})", expanded=False):
        st.caption(
            "A list is a folder you decide: the papers for one section, the good "
            "ones from yesterday's search. Read and flagged are two states and "
            "the same for everybody; lists are as many as you like, and an "
            "article can be in several at once. **An article in a list is never "
            "purged at startup**, even once you mark it read — so a list keeps "
            "what it holds until you say otherwise."
        )

        with st.form("new_list_form", clear_on_submit=True):
            n1, n2, n3 = st.columns([2, 3, 1])
            new_name = n1.text_input("Name", label_visibility="collapsed",
                                     placeholder="Name of a new list")
            new_note = n2.text_input("Note", label_visibility="collapsed",
                                     placeholder="What it is for (optional)")
            n3.write("")
            if n3.form_submit_button("＋ Create", width="stretch"):
                if not new_name.strip():
                    st.warning("A list needs a name.")
                elif db.create_list(new_name, new_note) is None:
                    st.error(f"“{new_name.strip()}” is already the name of a list.")
                else:
                    st.rerun()

        if not all_lists:
            st.caption("No lists yet. Create one here, or from the results of a "
                       "search with “Add selected to a list…”.")

        for lst in all_lists:
            with st.container(border=True):
                e1, e2, e3 = st.columns([2, 3, 0.6])
                name_key = f"lname_{lst['id']}"
                note_key = f"lnote_{lst['id']}"
                e1.text_input(
                    "Name", value=lst["name"], key=name_key,
                    label_visibility="collapsed", on_change=on_list_rename,
                    args=(lst["id"], name_key, lst["name"], "name"))
                e2.text_input(
                    "Note", value=lst["note"] or "", key=note_key,
                    label_visibility="collapsed", placeholder="What it is for",
                    on_change=on_list_rename,
                    args=(lst["id"], note_key, lst["note"] or "", "note"))
                e3.write("")
                if e3.button("🗑", key=f"ldel_{lst['id']}",
                             help="Delete this list"):
                    st.session_state.confirm_list_delete = lst["id"]
                    st.rerun()
                st.caption(
                    f"{lst['n_items']} article(s) · {lst['n_unread']} still to read"
                    + (f" · last touched {str(lst['updated_at'])[:10]}"
                       if lst["updated_at"] else ""))

        if st.session_state.get("confirm_list_delete"):
            doomed = db.get_list(st.session_state.confirm_list_delete)
            if doomed:
                st.warning(
                    f"Delete the list “{doomed['name']}”? The articles stay in "
                    f"the archive — a list is a way of looking at them, not "
                    f"where they live.")
                y, n = st.columns([1, 5])
                if y.button("Yes, delete the list", type="primary",
                            key="ldel_yes"):
                    db.delete_list(st.session_state.confirm_list_delete)
                    st.session_state.confirm_list_delete = None
                    st.rerun()
                if n.button("Cancel", key="ldel_no"):
                    st.session_state.confirm_list_delete = None
                    st.rerun()
            else:
                st.session_state.confirm_list_delete = None

    f1, f2, f3, f4 = st.columns([1, 1.2, 2.2, 1])
    with f1:
        filter_status = st.selectbox("Show:", ["All", "To read", "Read", "Flagged ★"])
    with f2:
        ANY_LIST = "Any list"
        list_choice = st.selectbox(
            "In list:", [ANY_LIST] + [r["name"] for r in all_lists],
            help="Only the articles in one list. Lists are managed above.")
        list_filter_id = next(
            (r["id"] for r in all_lists if r["name"] == list_choice), None)
    with f3:
        search_query = st.text_input("🔍 Search title, abstract or PMID:", "")
    with f4:
        try:
            default_size = PAGE_SIZE_OPTIONS.index(int(settings.get("page_size") or 10))
        except (ValueError, TypeError):
            default_size = 0
        page_size = st.selectbox("Articles per page:", PAGE_SIZE_OPTIONS, index=default_size)

    NO_METRIC = "Not in SCImago"
    quartiles = st.multiselect(
        "Journal quartile:", jr.QUARTILES + [NO_METRIC],
        help="SCImago's best quartile for the journal. “Not in SCImago” are "
             "the journals the file does not list at all — Cureus, medRxiv, "
             "most case-report journals.")

    order_label = st.radio(
        "Sort by:",
        ["Recently added", "Influential citations", "Total citations",
         "Citations per year", "Year", "Journal SJR"],
        horizontal=True,
    )
    ORDER_SQL = {
        "Recently added": "a.created_at DESC",
        "Influential citations": "a.influential_citations DESC NULLS LAST, a.created_at DESC",
        "Total citations": "a.citation_count DESC NULLS LAST, a.created_at DESC",
        "Citations per year": "a.citations_per_year DESC NULLS LAST, a.created_at DESC",
        "Year": "a.year DESC NULLS LAST, a.created_at DESC",
        "Journal SJR": "m.sjr DESC NULLS LAST, a.created_at DESC",
    }

    # la combinazione filtri/ricerca cambia il numero di pagine: si riparte da 1
    fingerprint = (filter_status, search_query.strip(), page_size, order_label,
                   list_filter_id, tuple(quartiles))
    if st.session_state.get("screen_fingerprint") != fingerprint:
        st.session_state.screen_fingerprint = fingerprint
        st.session_state.screen_page = 1
    if str(page_size) != settings.get("page_size"):
        db.save_settings({"page_size": str(page_size)})
        st.session_state.settings["page_size"] = str(page_size)

    # La JOIN sulle metriche e' LEFT: un articolo la cui rivista non sta in
    # SCImago deve restare nell'elenco, senza quartile, non sparire.
    FROM = ("FROM articles a "
            "LEFT JOIN journal_metrics m ON m.id = a.journal_metric_id")
    where = " WHERE 1=1"
    params: list = []
    if filter_status == "To read":
        where += " AND a.is_read = 0"
    elif filter_status == "Read":
        where += " AND a.is_read = 1"
    elif filter_status == "Flagged ★":
        where += " AND a.is_flagged = 1"
    if search_query.strip():
        where += " AND (a.title LIKE ? OR a.abstract LIKE ? OR a.pmid LIKE ?)"
        q = f"%{search_query.strip()}%"
        params.extend([q, q, q])
    if list_filter_id is not None:
        where += " AND a.pmid IN (SELECT pmid FROM list_items WHERE list_id = ?)"
        params.append(list_filter_id)
    if quartiles:
        picked = [q for q in quartiles if q in jr.QUARTILES]
        bits = []
        if picked:
            bits.append(f"m.quartile IN ({', '.join('?' * len(picked))})")
            params.extend(picked)
        if NO_METRIC in quartiles:
            # senza aggancio, oppure agganciata a una rivista che nel file non
            # ha un quartile: per chi guarda sono la stessa cosa
            bits.append("(a.journal_metric_id IS NULL OR m.quartile IS NULL)")
        where += " AND (" + " OR ".join(bits) + ")"

    conn = db.get_connection()
    try:
        total = conn.execute(f"SELECT COUNT(*) {FROM}{where}", params).fetchone()[0]
        n_pages = max(1, -(-total // page_size))
        page = min(max(1, st.session_state.get("screen_page", 1)), n_pages)
        st.session_state.screen_page = page

        # NOTA: si carica una sola pagina per volta. Renderizzare migliaia di
        # articoli insieme rende ogni rerun talmente lento da perdere i click.
        df = pd.read_sql_query(
            "SELECT a.pmid, a.title, a.abstract, a.journal, a.journal_title, "
            "a.pub_date, a.year, a.doi, a.authors, a.pub_types, a.citation_count, "
            "a.influential_citations, a.citations_per_year, a.oa_pdf_url, "
            "a.s2_fetched_at, a.is_read, a.is_flagged, "
            "a.oa_status, a.oa_url, a.oa_fetched_at, "
            "m.quartile, m.sjr, m.cites_per_doc, m.categories, "
            "m.title AS journal_scimago "
            f"{FROM}{where} ORDER BY {ORDER_SQL[order_label]} LIMIT ? OFFSET ?",
            conn,
            params=params + [page_size, (page - 1) * page_size],
        )
    finally:
        conn.close()

    st.caption(f"**{total}** articles found — page {page} of {n_pages} "
               f"({len(df)} on this page).")

    if n_pages > 1:
        render_pager(n_pages, "top", compact=True)

    # si guarda s2_fetched_at, non citation_count: un lavoro troppo recente per
    # essere indicizzato da S2 resterebbe altrimenti "da recuperare" per sempre
    missing_s2 = [str(p) for p, t in zip(df["pmid"], df["s2_fetched_at"]) if pd.isna(t)]
    if missing_s2:
        if st.button(f"📈 Fetch citations for {len(missing_s2)} articles on this page"):
            try:
                enrich = s2.enrich(missing_s2,
                                   api_key=(settings.get("s2_api_key") or "").strip())
            except s2.SemanticScholarError as exc:
                st.error(f"Semantic Scholar unavailable: {exc}")
            else:
                conn = db.get_connection()
                try:
                    for pmid, vals in enrich.items():
                        conn.execute(
                            "UPDATE articles SET citation_count = ?, influential_citations = ?, "
                            "citations_per_year = ?, s2_paper_id = ?, oa_pdf_url = ?, "
                            "s2_fetched_at = ? WHERE pmid = ?",
                            (vals["citation_count"], vals["influential_citations"],
                             vals["citations_per_year"], vals["s2_paper_id"],
                             vals["oa_pdf_url"], vals["s2_fetched_at"], pmid),
                        )
                    conn.commit()
                finally:
                    conn.close()
                found = sum(1 for v in enrich.values() if v["s2_paper_id"])
                st.success(
                    f"Queried {len(enrich)} articles: {found} found on Semantic "
                    f"Scholar, {len(enrich) - found} not indexed yet."
                )
                st.rerun()

    # Open access: si chiede solo per chi ha un DOI e non e' mai stato chiesto.
    # Unpaywall risponde per DOI, e un lavoro senza DOI non ha nulla da cercare.
    need_oa = [str(d) for d, doi, when in
               zip(df["pmid"], df["doi"], df["oa_fetched_at"])
               if clean(doi) and pd.isna(when)]
    if need_oa:
        if st.button(f"🔓 Check open access for {len(need_oa)} articles on this page"):
            email = unpaywall_email()
            if not email:
                st.error("Set an email in the sidebar first (⚙️ Settings): "
                         "Unpaywall requires one in every request.")
            else:
                by_doi = {clean(doi).lower(): str(pmid)
                          for pmid, doi in zip(df["pmid"], df["doi"])
                          if clean(doi)}
                bar = st.progress(0.0, "Asking Unpaywall…")
                found = upw.enrich(
                    list(by_doi), email, http_session(),
                    progress=lambda n, t: bar.progress(n / t, f"{n}/{t}"))
                written = db.store_oa(found, by_doi)
                open_now = sum(1 for r in found.values()
                               if r.get("oa_status") not in ("closed", "unknown"))
                st.success(f"Checked {written} articles: {open_now} have a free "
                           f"full text.")
                st.rerun()

    # In quali liste stanno gli articoli di QUESTA pagina, in una query sola:
    # chiederlo scheda per scheda sarebbe una query per articolo, e la pagina
    # ne mostra fino a cento.
    membership = db.lists_for([str(p) for p in df["pmid"]])

    for _, row in df.iterrows():
        pmid = str(row["pmid"])
        is_read = bool(row["is_read"])
        is_flagged = bool(row["is_flagged"])
        in_lists = membership.get(pmid, [])
        in_list_ids = {i for i, _ in in_lists}

        with st.container(border=True):
            col_meta, col_actions = st.columns([5, 1.3])

            with col_meta:
                mark = ("★ " if is_flagged else "") + ("✅ " if is_read else "📖 ")
                st.markdown(
                    f'<div class="art-title">{mark}'
                    f'{html.escape(clean(row["title"]) or "No title available")}</div>',
                    unsafe_allow_html=True,
                )
                # Il nome della rivista: quello di SCImago se l'aggancio c'e',
                # altrimenti il titolo pulito, altrimenti quello che c'e' in
                # archivio - che nei record vecchi e' l'abbreviazione incollata
                # al titolo esteso, "Eur J Radiol European journal of radiology".
                journal_name = (clean(row["journal_scimago"])
                                or clean(row["journal_title"])
                                or clean(row["journal"]))
                meta_bits = [b for b in [
                    html.escape(clean(row["authors"])),
                    html.escape(journal_name),
                    html.escape(clean(row["pub_date"]) or clean(row["year"])),
                    f"PMID {pmid}",
                ] if b]
                st.markdown(f'<div class="art-meta">{" · ".join(meta_bits)}</div>',
                            unsafe_allow_html=True)

                # il quartile per primo: e' quello che si cerca con l'occhio
                badges = journal_badges(row)
                oa = oa_badge(clean(row["oa_status"]))
                if oa:
                    badges.append(oa)
                badges.extend(html.escape(t) for t in useful_types(row["pub_types"]))
                cites = citation_badge(row["citation_count"],
                                       row["influential_citations"],
                                       row["citations_per_year"])
                if cites:
                    badges.append(cites)
                for _, list_name in in_lists:
                    badges.append("🗂 " + html.escape(list_name))
                if badges:
                    st.markdown(
                        '<div class="art-badges">'
                        + "".join(b if b.startswith("<span") else f"<span>{b}</span>"
                                  for b in badges)
                        + "</div>",
                        unsafe_allow_html=True,
                    )
                if clean(row["categories"]):
                    # Il quartile del badge e' il migliore che la rivista ha in
                    # una qualsiasi delle sue categorie. Qui c'e' il dettaglio,
                    # che per un radiologo dice di piu': Q1 in "Medicine
                    # (miscellaneous)" e Q3 in "Radiology" sono due cose diverse.
                    st.caption(f"in {clean(row['categories'])}")

                links = [f"[PubMed](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)"]
                lk = libkey_url(pmid)
                if lk:
                    links.append(f"[🔓 LibKey full text]({lk})")
                doi = clean(row["doi"])
                if doi:
                    links.append(f"[DOI](https://doi.org/{doi})")
                # Unpaywall prima di Semantic Scholar: e' il servizio che fa
                # solo questo, e quando i due dissentono ha ragione lui
                free = clean(row["oa_url"]) or clean(row["oa_pdf_url"])
                if free:
                    links.append(f"[Free full text]({free})")
                st.markdown(" · ".join(links))

            with col_actions:
                # La chiave include lo stato letto dal DB. Streamlit ignora
                # `value=` quando la `key=` esiste gia' in session_state: se il
                # DB viene cambiato da fuori (un'altra scheda del browser, la
                # pulizia all'avvio) la spunta continuerebbe a mostrare il
                # valore vecchio, e il click successivo riscriverebbe quello.
                # Legando la chiave allo stato, il widget si ricrea e riparte
                # dal DB.
                key_read = f"read_{pmid}_{int(is_read)}"
                st.checkbox("✅ Read", value=is_read, key=key_read,
                            on_change=on_toggle, args=(pmid, "is_read", key_read))
                key_flag = f"flag_{pmid}_{int(is_flagged)}"
                st.checkbox("★ Flagged", value=is_flagged, key=key_flag,
                            on_change=on_toggle, args=(pmid, "is_flagged", key_flag))
                if all_lists:
                    # La chiave porta dentro l'appartenenza letta dal database,
                    # per la stessa ragione delle due spunte qui sopra: se la
                    # lista cambia da un'altra parte - dalla scheda di ricerca,
                    # da un'altra finestra - il widget si rifa' e riparte dal
                    # dato vero invece di ripetere quello vecchio.
                    label = (f"🗂 {len(in_lists)} list(s)" if in_lists
                             else "🗂 Add to a list")
                    with st.popover(label, width="stretch"):
                        for lst in all_lists:
                            here = lst["id"] in in_list_ids
                            key_list = f"inlist_{pmid}_{lst['id']}_{int(here)}"
                            st.checkbox(
                                lst["name"], value=here, key=key_list,
                                on_change=on_list_toggle,
                                args=(pmid, lst["id"], key_list))

            with st.expander("Abstract", expanded=False):
                st.write(clean(row["abstract"]) or "No abstract available.")

    if n_pages > 1:
        st.divider()
        render_pager(n_pages, "bottom", compact=False)


# ---------------------------------------------------------------------------
# TAB 3 - scrittura di un articolo Radiopaedia
# ---------------------------------------------------------------------------

def rich_copy_box(html_body: str, *, label: str, height: int, key: str) -> None:
    """Riquadro con l'HTML gia' reso e un pulsante che lo copia FORMATTATO.

    E' il punto centrale di tutta la scheda. L'editor di Radiopaedia e'
    WYSIWYG: incollargli testo semplice perde grassetti, titoli ed elenchi.
    Quello che invece accetta e' il flavour `text/html` degli appunti.

    Due vie, in quest'ordine, e l'ordine conta:

    1. `navigator.clipboard.write` con un Blob `text/html`. Mette negli
       appunti ESATTAMENTE l'HTML dato: `<h3>`, `<strong>`, `<sup>` e nulla
       piu'.
    2. `document.execCommand('copy')` su una selezione, per i browser che
       negano l'API. In questo caso il browser serializza i nodi
       selezionati e ci INLINEA lo stile calcolato: per questo la selezione
       cade su una copia nuda e fuori schermo del contenuto, non sul riquadro
       di anteprima - copiare quello si porterebbe dentro l'articolo i font e
       i colori dell'anteprima.
    """
    payload = html_body or "<p><em>Nothing to copy yet.</em></p>"
    st.html(
        f"""
        <style>
          .rc-wrap {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
                      Roboto, sans-serif; }}
          .rc-bar {{ display: flex; gap: .5rem; align-items: center;
                     margin-bottom: .5rem; }}
          .rc-btn {{ font: inherit; font-size: .85rem; padding: .35rem .9rem;
                     border-radius: .5rem; border: 1px solid rgba(128,128,128,.4);
                     background: #fff; cursor: pointer; }}
          .rc-btn:hover {{ border-color: #ff4b4b; color: #ff4b4b; }}
          .rc-msg {{ font-size: .8rem; opacity: .75; }}
          .rc-body {{ border: 1px solid rgba(128,128,128,.3); border-radius: .5rem;
                      padding: .9rem 1.1rem; overflow: auto; background: #fff;
                      color: #111; height: {max(80, height - 60)}px; }}
          .rc-body h3 {{ font-size: 1.15rem; margin: .9rem 0 .4rem; }}
          .rc-body h4 {{ font-size: 1rem; margin: .8rem 0 .35rem; }}
          .rc-body p {{ margin: .5rem 0; line-height: 1.5; }}
          .rc-body sup {{ color: #0b6; font-weight: 600; }}
          .rc-body ol, .rc-body ul {{ margin: .5rem 0 .5rem 1.3rem; }}
          /* la sorgente della copia: fuori schermo e senza una sola regola
             di stile, cosi' non c'e' niente da inlineare */
          #raw-{key} {{ position: absolute; left: -10000px; top: 0; width: 700px; }}
        </style>
        <div class="rc-wrap">
          <div class="rc-bar">
            <button class="rc-btn" id="btn-{key}">{html.escape(label)}</button>
            <span class="rc-msg" id="msg-{key}"></span>
          </div>
          <div class="rc-body" id="src-{key}">{payload}</div>
        </div>
        <div id="raw-{key}" aria-hidden="true">{payload}</div>
        <script>
        (function () {{
          const btn = document.getElementById("btn-{key}");
          const raw = document.getElementById("raw-{key}");
          const msg = document.getElementById("msg-{key}");
          function say(t) {{ msg.textContent = t;
                             setTimeout(() => {{ msg.textContent = ""; }}, 5000); }}

          function bySelection() {{
            const range = document.createRange();
            range.selectNodeContents(raw);
            const sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(range);
            let done = false;
            try {{ done = document.execCommand("copy"); }} catch (e) {{ done = false; }}
            sel.removeAllRanges();
            return done;
          }}

          /* L'API clipboard. Da quando questo blocco vive nella pagina vera
             (`st.html`) e non piu' nell'iframe di un componente, la
             permission policy non la nega piu' - ed e' l'unica via che mette
             negli appunti l'HTML esatto. L'altra lo fa serializzare al
             browser, che ci inlinea lo stile calcolato (`font-family: Times`,
             `color: rgb(0,0,0)`) e se lo porterebbe dentro l'articolo. */
          async function viaClipboardAPI(w) {{
            if (!w || !w.navigator || !w.navigator.clipboard || !w.ClipboardItem) return false;
            await w.navigator.clipboard.write([new w.ClipboardItem({{
              "text/html": new w.Blob([raw.innerHTML], {{ type: "text/html" }}),
              "text/plain": new w.Blob([raw.innerText], {{ type: "text/plain" }}),
            }})]);
            return true;
          }}

          btn.addEventListener("click", async () => {{
            btn.dataset.route = "";
            try {{
              if (await viaClipboardAPI(window)) {{
                btn.dataset.route = "clipboard-api";
                return say("Copied ✓ — clean HTML");
              }}
            }} catch (e) {{
              btn.dataset.err = (e && e.name ? e.name : "?") + ": " +
                                (e && e.message ? e.message : e);
            }}
            if (bySelection()) {{
              btn.dataset.route = "exec-command";
              // onesto: per questa via il browser inlinea lo stile calcolato,
              // e se l'editor di Radiopaedia non lo scarta finisce nel testo
              return say("Copied ✓ — via selection, your browser added inline styling");
            }}
            btn.dataset.route = "failed";
            say("The browser refused the copy — select the box and press ⌘C.");
          }});
        }})();
        </script>
        """,
        unsafe_allow_javascript=True,
    )


# ---------------------------------------------------------------------------
# la struttura dei titoli
# ---------------------------------------------------------------------------

def body_key_for(draft_id: int) -> str:
    """La chiave della casella del testo, con dentro un contatore.

    Streamlit tiene il contenuto di un widget in `session_state` e da li' lo
    rimette dopo il rerun, ignorando il `value=` che gli passi; e non lascia
    scrivere quella voce dopo che il widget e' stato creato - solleva, ed e'
    giusto, perche' significherebbe cambiare sotto il naso una casella che
    l'utente sta usando.

    Quindi quando siamo NOI a cambiare il testo si cambia la chiave: il widget
    successivo e' un widget nuovo, e un widget nuovo il suo `value=` lo legge.
    Il contatore e' quello che rende la chiave nuova."""
    return f"body_{draft_id}_{st.session_state.get(f'bodyn_{draft_id}', 0)}"


def set_body(draft_id: int, body_md: str) -> None:
    """Il testo nuovo nel database, e la casella buttata via e rifatta."""
    db.save_draft(draft_id, body_md=body_md)
    st.session_state[f"bodyn_{draft_id}"] = st.session_state.get(f"bodyn_{draft_id}", 0) + 1


def heading_panel(draft, body_md: str) -> None:
    """I titoli che questo tipo di articolo dovrebbe avere.

    Il canone risponde a due domande diverse: quali sezioni MANCANO a un
    articolo che c'e' gia', e quali dovrebbero esserci in assoluto. La seconda
    e' quella utile adesso, con la bozza ancora quasi vuota.

    Tutti, quelli che scegli, o uno solo a una riga precisa. L'ultimo e'
    l'unico che puo' andare storto, e la gerarchia e' come: `Microscopic
    appearance` messo in mezzo a `Radiographic features` e' il sottotitolo
    della cosa sbagliata, e sembra tale e quale a uno finito al posto giusto.
    Quindi la riga chiesta si confronta con la sezione in cui cade davvero, e
    dove le due non vanno d'accordo si dice - senza rifiutare."""
    try:
        labels = sx.profile_labels()
    except sx.StructureError as exc:
        st.warning(str(exc))
        return

    names = list(labels)
    saved = draft["profile"] if "profile" in draft.keys() else None
    current = saved or sx.guess_profile(draft["title"])
    if current not in names:
        current = sx.canon().fallback

    profile_key = f"profile_{draft['id']}"

    def remember(did=draft["id"], key=profile_key):
        """Si salva solo quello che hai scelto tu.

        Scrivere anche quello indovinato lo trasformerebbe in una decisione: la
        volta dopo sarebbe indistinguibile da una scelta, e la riga che dice
        "tirato a indovinare dal titolo" sparirebbe proprio quando serve."""
        db.save_draft(did, profile=st.session_state.get(key))

    pick, opts = st.columns([2, 1])
    with pick:
        chosen = st.selectbox(
            "Kind of article", names, index=names.index(current),
            format_func=lambda n: labels[n], key=profile_key, on_change=remember,
            help="Radiopaedia has twenty-three structures, not one. This picks "
                 "which of them the headings come from; it is guessed from the "
                 "title and remembered once you change it.")
    if not saved:
        st.caption("Guessed from the title — change it if it is wrong.")

    canon_name = sx.canon().profiles[chosen]["canon"]
    rows = sx.rows_for(chosen)
    present = sx.present_entries(body_md, canon_name)
    missing = [r for r in rows if r.entry not in present]

    with opts:
        pending = st.checkbox(
            "with `content pending`", key=f"pending_{draft['id']}",
            help="Radiopaedia's own word for a section that is there and empty. "
                 "The linter has a rule that finds them again later.")

    if not missing:
        st.success("Every heading this structure names is already in the draft.")
        return

    st.caption(f"{len(rows) - len(missing)} of {len(rows)} already in the draft · "
               f"**bold** are the ones this kind of article must have")

    # Le caselle. Le obbligatorie partono spuntate perche' sono quelle che
    # Radiopaedia chiede, non quelle che di solito si vogliono.
    #
    # Nella chiave c'e' lo stesso contatore della casella del testo, per lo
    # stesso motivo: appena il testo cambia queste caselle sono widget nuovi e
    # ripartono da capo. Senza, quelle appena inserite resterebbero spuntate -
    # e spuntarle a mano dopo non si puo', perche' Streamlit non lascia toccare
    # la voce di un widget gia' creato.
    stamp = st.session_state.get(f"bodyn_{draft['id']}", 0)
    pick_key = lambda row: f"pick_{draft['id']}_{stamp}_{row.entry}"   # noqa: E731

    box = st.container(height=260, border=True)
    picked: list[sx.Row] = []
    with box:
        for row in missing:
            key = pick_key(row)
            if key not in st.session_state:
                st.session_state[key] = row.required
            indent = "\u2003" * (row.level - 1)
            label = f"{indent}**{row.title}**" if row.required else f"{indent}{row.title}"
            if st.checkbox(label, key=key):
                picked.append(row)

    def set_all(how: str) -> None:
        # Gira come callback, cioe' PRIMA che i widget di questo giro esistano:
        # e' l'unico momento in cui scrivere in quelle voci e' permesso.
        for row in missing:
            st.session_state[pick_key(row)] = (
                how == "all" or (how == "required" and row.required))

    c1, c2, c3, c4 = st.columns([1, 1, 1, 2.2])
    c1.button("Required", key=f"req_{draft['id']}", on_click=set_all, args=("required",),
              width="stretch")
    c2.button("All", key=f"all_{draft['id']}", on_click=set_all, args=("all",),
              width="stretch")
    c3.button("None", key=f"none_{draft['id']}", on_click=set_all, args=("none",),
              width="stretch")
    if c4.button(f"Insert {len(picked)} heading(s)", type="primary", disabled=not picked,
                 key=f"ins_{draft['id']}", width="stretch"):
        # Nell'ordine del canone, non in quello in cui li hai spuntati: si
        # piazzano a vicenda, e un sottotitolo ha bisogno che il proprio
        # genitore sia entrato prima.
        new_md, added = sx.insert_rows(body_md, picked, canon_name, pending=pending)
        set_body(draft["id"], new_md)
        st.toast(f"{len(added)} heading(s) inserted, in the structure's order.")
        st.rerun()

    # ------------------------------------------------------------------
    # uno solo, a una riga precisa
    # ------------------------------------------------------------------
    with st.expander("Put one on a line of my choosing", expanded=False):
        n_lines = len(body_md.splitlines())
        one, where = st.columns([2, 1])
        row = one.selectbox(
            "Heading", missing, format_func=lambda r: "  " * (r.level - 1) + r.title,
            key=f"one_{draft['id']}", label_visibility="collapsed")
        line = where.number_input("Line", min_value=1, max_value=max(1, n_lines + 1),
                                  value=max(1, n_lines + 1), step=1,
                                  key=f"line_{draft['id']}",
                                  help="The line of the Markdown box above that "
                                       "the heading goes in front of.")
        if row is not None:
            plan = sx.check_one(body_md, row, int(line), canon_name)
            if plan.conflict:
                st.warning(plan.conflict + f" La struttura lo metterebbe alla "
                                           f"riga {plan.canon_line}.")
            a, b = st.columns(2)
            if a.button(f"Put it on line {plan.canon_line} (the structure's place)",
                        key=f"canon_{draft['id']}", width="stretch"):
                set_body(draft["id"],
                         sx.insert_at(body_md, row, plan.canon_line, pending=pending))
                st.rerun()
            if b.button(f"Put it on line {int(line)} anyway", key=f"here_{draft['id']}",
                        width="stretch"):
                set_body(draft["id"],
                         sx.insert_at(body_md, row, int(line), pending=pending))
                st.rerun()


# ---------------------------------------------------------------------------
# il lint della bozza
# ---------------------------------------------------------------------------

SEVERITY_MARK = {"error": "🔴", "warning": "🟠", "suggestion": "🔵"}


def lint_panel(draft, body_md: str, numbers: dict) -> None:
    """Le regole del linter Radiopaedia, sulla bozza, prima di pubblicarla.

    Si linta l'HTML e non il markdown: meta' delle regole parlano di `<sup>`,
    `<strong>`, `<em>` e dei titoli, e nel markdown quei tag non ci sono
    ancora. E lo si rende alla profondita' a cui l'articolo verra' PUBBLICATO,
    non a quella in cui si incolla: le regole sono scritte contro la pagina di
    Radiopaedia, dove una sezione e' un `h4`."""
    st.caption(
        "The linter at radiopaedia.work reads the published article, so it has "
        "nothing to read while you are still writing. These are its own rules, "
        f"transcribed on {lint.transcribed_on()} and run here — nothing leaves "
        "the computer. It does not replace the real thing: Radiopaedia has "
        "registered exceptions that this cannot see, so where the two disagree, "
        "believe theirs."
    )

    if st.button("Lint the draft", type="primary", key=f"lint_{draft['id']}"):
        st.session_state[f"lintrun_{draft['id']}"] = True

    if not st.session_state.get(f"lintrun_{draft['id']}"):
        return

    try:
        html_for_lint = rp.to_html(body_md, numbers, top_heading=lint.LINT_TOP_HEADING)
        findings = lint.attach_lines(lint.lint_html(html_for_lint), body_md)
    except lint.LintError as exc:
        st.error(str(exc))
        return

    shown = [f for f in findings if not f.hushed]
    hushed = [f for f in findings if f.hushed]
    counts = lint.tally(findings)

    if not shown:
        st.success("Nothing to fix." + (
            f" ({len(hushed)} set aside by the shared lists.)" if hushed else ""))
        return

    st.markdown(
        f"**{counts['error']}** error(s) · **{counts['warning']}** warning(s) · "
        f"**{counts['suggestion']}** suggestion(s)")

    only = st.multiselect(
        "Show", ["error", "warning", "suggestion"], default=["error", "warning", "suggestion"],
        key=f"sev_{draft['id']}", label_visibility="collapsed")

    for finding in shown:
        if finding.severity not in only:
            continue
        where = f"line {finding.line}" if finding.line else f"block {finding.block + 1}"
        with st.container(border=True):
            st.markdown(
                f"{SEVERITY_MARK.get(finding.severity, '⚪')} **{finding.check}** · {where}"
                + (f" · [style guide](https://radiopaedia.org{finding.link})"
                   if finding.link else ""))
            st.write(finding.message)
            # Il pezzo di testo in questione, con dentro segnato cosa lo ha
            # fatto scattare: il messaggio dice cosa non va, questo dice dove.
            snippet = finding.snippet
            if not finding.whole and finding.length:
                a, b = finding.at, finding.at + finding.length
                snippet = f"{snippet[:a]}⟦{snippet[a:b]}⟧{snippet[b:]}"
            st.caption(snippet[:400] + ("…" if len(snippet) > 400 else ""))

    if hushed:
        with st.expander(f"{len(hushed)} set aside by the shared lists", expanded=False):
            st.caption(
                "Proper nouns that may open a list item, and acronyms nobody "
                "needs spelled out. The two files live in `data/`.")
            for finding in hushed:
                st.caption(f"· **{finding.matched}** — {finding.check} "
                           f"(covered by “{finding.known}”)")


# ---------------------------------------------------------------------------
# la barra di formattazione
# ---------------------------------------------------------------------------

# I bottoni NON stanno dentro l'iframe del componente, e non e' un dettaglio.
# Cliccare dentro un iframe sposta il fuoco, quindi la casella del testo lo
# perde, quindi Streamlit manda il valore e fa ripartire lo script: ogni
# grassetto sarebbe un giro di server, e la nostra modifica correrebbe contro
# il rerun che lei stessa ha provocato. Cosi' invece l'iframe fa solo da
# innesco - inietta la barra nella pagina vera e si nasconde - e li' il
# `preventDefault` sul mousedown impedisce al fuoco di muoversi: nessun blur,
# nessun rerun, il cursore resta dov'era.
#
# Che si possa fare lo dimostra `rich_copy_box`, che usa `window.parent` per la
# stessa ragione: l'iframe di un componente e' same-origin con la pagina.

TOOLBAR_JS = r"""
<span id="mdanchor-__KEY__" style="display:none"></span>
<script>
(function () {
  /* `st.html` inietta nella pagina vera, non in un iframe: `P` e `doc` sono
     quelli del documento dove sta anche la casella di testo. Al posto
     dell'elemento iframe si usa come segnaposto lo span qui sopra.
     NOTA: dentro questo script non si scrivono tag in chiaro, nemmeno nei
     commenti - il sanificatore di `st.html` butta via tutto il blocco. */
  const P = window, doc = document, me = doc.getElementById("mdanchor-__KEY__");
  if (!doc || !me) return;
  const ID = "mdbar-__KEY__";

  /* La casella e' il primo textarea che nel documento viene DOPO questo
     segnaposto. Cercarla per etichetta la legherebbe a come e' scritta;
     cosi' invece la si trova per posizione, che e' quella che decidiamo noi. */
  function area() {
    const all = doc.querySelectorAll("textarea");
    for (let i = 0; i < all.length; i++) {
      if (me.compareDocumentPosition(all[i]) & Node.DOCUMENT_POSITION_FOLLOWING) return all[i];
    }
    return null;
  }

  /* React non ascolta l'assegnazione, ascolta il setter nativo: senza questo
     la modifica si vedrebbe sullo schermo e Streamlit non la riceverebbe mai. */
  const nativeSet = Object.getOwnPropertyDescriptor(
      P.HTMLTextAreaElement.prototype, "value").set;

  function commit(ta, value, from, to) {
    nativeSet.call(ta, value);
    ta.dispatchEvent(new P.Event("input", { bubbles: true }));
    ta.focus();
    ta.setSelectionRange(from, to);
  }

  function wrap(ta, open, close, holder) {
    const v = ta.value, a = ta.selectionStart, b = ta.selectionEnd;
    const inside = v.slice(a, b);
    /* gia' avvolto: si toglie, invece di raddoppiare i marcatori */
    if (inside && v.slice(a - open.length, a) === open && v.slice(b, b + close.length) === close) {
      return commit(ta, v.slice(0, a - open.length) + inside + v.slice(b + close.length),
                    a - open.length, b - open.length);
    }
    const text = inside || holder;
    const from = a + open.length;
    commit(ta, v.slice(0, a) + open + text + close + v.slice(b), from, from + text.length);
  }

  function link(ta) {
    const v = ta.value, a = ta.selectionStart, b = ta.selectionEnd;
    const text = v.slice(a, b) || "text";
    const from = a + text.length + 3;          /* subito dopo "](" */
    commit(ta, v.slice(0, a) + "[" + text + "](url)" + v.slice(b), from, from + 3);
  }

  /* I marcatori di riga - titoli ed elenchi - valgono su tutte le righe
     toccate dalla selezione. Si toglie sempre quello che c'e' gia', altrimenti
     un titolo diventa "## # Titolo" e un elenco si annida da solo. */
  const MARKER = /^[ \t]*(#{1,6}[ \t]+|[-+*][ \t]+|\d+\.[ \t]+)/;

  function prefix(ta, mark, numbered) {
    const v = ta.value;
    const a = v.lastIndexOf("\n", ta.selectionStart - 1) + 1;
    let b = v.indexOf("\n", ta.selectionEnd);
    if (b < 0) b = v.length;
    const lines = v.slice(a, b).split("\n");
    const bare = lines.map(l => l.replace(MARKER, ""));
    const of = (i) => numbered ? (i + 1) + ". " : mark;
    /* se ce l'hanno gia' tutte, il bottone lo toglie */
    const on = lines.every((l, i) => l === of(i) + bare[i]) && lines.some(l => l.trim());
    const text = bare.map((l, i) => (on || !l.trim()) ? l : of(i) + l).join("\n");
    commit(ta, v.slice(0, a) + text + v.slice(b), a, a + text.length);
  }

  const TOOLS = [
    ["B",    "Bold  ⌘B",                        ta => wrap(ta, "**", "**", "bold")],
    ["I",    "Italic  ⌘I",                      ta => wrap(ta, "*", "*", "italic")],
    ["H1",   "Section heading — h3 on Radiopaedia", ta => prefix(ta, "# ", false)],
    ["H2",   "Subheading — h4",                 ta => prefix(ta, "## ", false)],
    ["H3",   "Sub-subheading — h5",             ta => prefix(ta, "### ", false)],
    ["•",    "Bulleted list",                   ta => prefix(ta, "- ", false)],
    ["1.",   "Numbered list",                   ta => prefix(ta, "", true)],
    ["🔗",   "Link  ⌘K",                        ta => link(ta)],
    ["[@]",  "Citation — the identifier itself, not a number",
                                                ta => wrap(ta, "[@", "]", "27859258")],
  ];

  function style() {
    if (doc.getElementById("mdbar-style")) return;
    const css = doc.createElement("style");
    css.id = "mdbar-style";
    css.textContent =
      ".mdbar{display:flex;flex-wrap:wrap;gap:.25rem;margin:0 0 .35rem 0}" +
      ".mdbar button{font:inherit;font-size:.8rem;line-height:1;min-width:2rem;" +
        "padding:.4rem .55rem;border-radius:.4rem;cursor:pointer;" +
        "border:1px solid rgba(128,128,128,.35);background:transparent;color:inherit}" +
      ".mdbar button:hover{border-color:#ff4b4b;color:#ff4b4b}" +
      ".mdbar button.b{font-weight:700}.mdbar button.i{font-style:italic}" +
      ".mdbar .sep{width:1px;margin:.15rem .3rem;background:rgba(128,128,128,.3)}";
    doc.head.appendChild(css);
  }

  function build() {
    const ta = area();
    if (!ta) return null;
    const old = doc.getElementById(ID);
    if (old) old.remove();

    const bar = doc.createElement("div");
    bar.className = "mdbar";
    bar.id = ID;
    TOOLS.forEach(([label, tip, run], n) => {
      if (n === 2 || n === 5 || n === 7) bar.appendChild(
        Object.assign(doc.createElement("div"), { className: "sep" }));
      const b = doc.createElement("button");
      b.type = "button";
      b.textContent = label;
      b.title = tip;
      if (label === "B") b.className = "b";
      if (label === "I") b.className = "i";
      /* il fuoco non si muove: senza questo la casella lo perde, Streamlit
         manda il valore e fa ripartire lo script sotto le nostre mani */
      b.addEventListener("mousedown", e => e.preventDefault());
      b.addEventListener("click", e => {
        e.preventDefault();
        const now = area();
        if (now) run(now);
      });
      bar.appendChild(b);
    });

    const host = ta.closest('[data-testid="stTextArea"]') || ta.parentElement;
    host.parentElement.insertBefore(bar, host);

    if (!ta.dataset.mdbar) {
      ta.dataset.mdbar = "1";
      ta.addEventListener("keydown", e => {
        if (!(e.metaKey || e.ctrlKey) || e.altKey) return;
        const k = e.key.toLowerCase();
        if (k === "b") { e.preventDefault(); wrap(ta, "**", "**", "bold"); }
        else if (k === "i") { e.preventDefault(); wrap(ta, "*", "*", "italic"); }
        else if (k === "k") { e.preventDefault(); link(ta); }
      });
    }
    return bar;
  }

  style();
  build();

  /* Streamlit ridisegna, e quando ridisegna si porta via anche la barra:
     la si rimette. Un osservatore solo, sostituito a ogni giro, altrimenti
     se ne accumulerebbe uno per rerun. */
  P.__mdbars = P.__mdbars || {};
  if (P.__mdbars[ID]) { try { P.__mdbars[ID].disconnect(); } catch (e) {} }
  let waiting = false;
  const watch = new P.MutationObserver(() => {
    if (waiting || doc.getElementById(ID)) return;
    waiting = true;
    P.setTimeout(() => { waiting = false; build(); }, 60);
  });
  watch.observe(doc.body, { childList: true, subtree: true });
  P.__mdbars[ID] = watch;
})();
</script>
"""


def markdown_toolbar(key: str) -> None:
    """La barra sopra la casella del testo."""
    st.html(TOOLBAR_JS.replace("__KEY__", key), unsafe_allow_javascript=True)


# ---------------------------------------------------------------------------
# l'anteprima
# ---------------------------------------------------------------------------

PREVIEW_CSS = """
<style>
  .mdprev { border: 1px solid rgba(128,128,128,.3); border-radius: .5rem;
            padding: 1rem 1.25rem; min-height: 460px; }
  .mdprev h3 { font-size: 1.2rem; margin: 1rem 0 .4rem; font-weight: 600; }
  .mdprev h4 { font-size: 1.05rem; margin: .9rem 0 .35rem; font-weight: 600; }
  .mdprev h5 { font-size: .95rem; margin: .8rem 0 .3rem; font-weight: 600; }
  .mdprev h3:first-child, .mdprev h4:first-child { margin-top: 0; }
  .mdprev p { margin: .5rem 0; line-height: 1.6; }
  .mdprev ul, .mdprev ol { margin: .5rem 0 .5rem 1.4rem; }
  .mdprev li { margin: .2rem 0; line-height: 1.55; }
  .mdprev sup { color: #0b8457; font-weight: 600; padding-left: .1rem; }
  .mdprev table { border-collapse: collapse; margin: .6rem 0; }
  .mdprev th, .mdprev td { border: 1px solid rgba(128,128,128,.35);
                           padding: .3rem .55rem; }
  .mdprev .empty { opacity: .6; font-style: italic; }
  .mdprev .refs { margin-top: 1.4rem; padding-top: .8rem;
                  border-top: 1px solid rgba(128,128,128,.25); }
  .mdprev .refs .ref { font-size: .85rem; opacity: .85; margin: .3rem 0;
                       line-height: 1.5; }
  .mdprev .refs .none { font-size: .85rem; opacity: .7; font-style: italic; }
</style>
"""


def preview_box(article_html: str, reference_lines: list[str]) -> None:
    """L'articolo come sara', numeri di citazione compresi.

    Non e' l'anteprima di un markdown qualunque: e' lo STESSO HTML che il
    bottone di copia mette negli appunti, quindi quello che si vede qui e'
    quello che l'editor di Radiopaedia ricevera'. E ci sono sotto le
    referenze, perche' e' li' che si vede se un numero e' finito storto."""
    body = article_html or '<p class="empty">Nothing written yet.</p>'
    # Le righe arrivano gia' numerate e gia' nella forma `N. testo`, che e' la
    # riga esatta di un box dell'editor: si mostrano com'e', non dentro un
    # elenco che ci rimetterebbe davanti un secondo numero.
    refs = ("".join(f'<div class="ref">{line}</div>' for line in reference_lines)
            if reference_lines else
            '<p class="none">No references cited yet.</p>')
    st.html(
        PREVIEW_CSS
        + f'<div class="mdprev">{body}'
        + f'<div class="refs"><strong>References</strong>{refs}</div></div>'
    )


with tab_write:
    drafts = db.list_drafts()

    head, new_col, del_col = st.columns([3, 1, 1])
    with head:
        if drafts:
            labels = {f"{r['title']}  ·  {r['n_refs']} refs": r["id"] for r in drafts}
            ids = list(labels.values())
            current = st.session_state.get("draft_id")
            index = ids.index(current) if current in ids else 0
            chosen = st.selectbox("Draft", list(labels), index=index)
            st.session_state.draft_id = labels[chosen]
        else:
            st.session_state.draft_id = None
            st.info("No drafts yet — create one to start writing.")
    with new_col:
        st.write("")
        if st.button("＋ New draft", width="stretch"):
            st.session_state.draft_id = db.create_draft("Untitled article")
            st.rerun()
    with del_col:
        st.write("")
        if st.session_state.get("draft_id") and st.button(
                "🗑 Delete", width="stretch"):
            st.session_state.confirm_delete = st.session_state.draft_id
            st.rerun()

    if st.session_state.get("confirm_delete"):
        target = db.get_draft(st.session_state.confirm_delete)
        if target:
            st.warning(f"Delete the draft “{target['title']}” and its reference list? "
                       "This cannot be undone.")
            yes, no = st.columns([1, 5])
            if yes.button("Yes, delete", type="primary"):
                db.delete_draft(st.session_state.confirm_delete)
                st.session_state.confirm_delete = None
                st.session_state.draft_id = None
                st.rerun()
            if no.button("Cancel"):
                st.session_state.confirm_delete = None
                st.rerun()
        else:
            st.session_state.confirm_delete = None

    # ----------------------------------------------------------------------
    # una bozza che arriva da un file
    # ----------------------------------------------------------------------
    with st.expander("⇅ Import a draft from a file", expanded=False):
        st.caption(
            "The `.json` written by Export, from this computer or another one. "
            "It comes back with its text, its kind of article, its reference "
            "list and the citations already resolved. It always lands as a NEW "
            "draft — nothing open is overwritten."
        )
        picked_file = st.file_uploader(
            "Draft file", type=["json"], key="draft_import",
            label_visibility="collapsed")
        if picked_file is not None:
            try:
                incoming = draft_io.read_bundle(picked_file.getvalue())
            except draft_io.DraftIOError as exc:
                st.error(str(exc))
            else:
                st.caption(
                    f"**{incoming['title']}** — "
                    f"{len(incoming['body_md'].splitlines())} lines, "
                    f"{len(incoming['references'])} reference(s)"
                    + (f", exported {incoming['exported'][:10]}"
                       if incoming["exported"] else ""))
                if st.button("Import as a new draft", type="primary"):
                    st.session_state.draft_id = draft_io.create_from(incoming)
                    st.rerun()

    draft_id = st.session_state.get("draft_id")
    draft = db.get_draft(draft_id) if draft_id else None

    if draft:
        # ------------------------------------------------------------------
        # editor + pannello laterale
        # ------------------------------------------------------------------
        # Le citazioni e la numerazione si calcolano PRIMA di disegnare, perche'
        # ora servono anche sopra: l'anteprima mostra l'articolo coi numeri al
        # loro posto, e i numeri non si sanno finche' non si sono lette le
        # citazioni - e' da DOI e PMID che si capisce quando due token diversi
        # sono lo stesso lavoro.
        title_key = f"title_{draft['id']}"
        body_key = body_key_for(draft["id"])
        body_md = st.session_state.get(body_key, draft["body_md"] or "")

        cited = rp.cited_identifiers(body_md)
        listed = db.draft_identifiers(draft["id"])
        wanted = sorted(set(cited) | set(listed))
        citations = db.cached_citations(wanted)
        numbers = rp.numbering(body_md, citations)
        merged = rp.merged_groups(numbers)

        cited_not_listed = [i for i in cited if i not in listed]
        listed_not_cited = [i for i in listed if i not in numbers]
        unresolved = [i for i in wanted if not (citations.get(i) or {}).get("citation")]

        col_edit, col_side = st.columns([2.2, 1])

        with col_edit:
            def autosave(did=draft["id"], tkey=title_key, bkey=body_key):
                """Salva quando il campo perde il fuoco: una bozza persa
                perche' si e' cambiata scheda non e' un rischio accettabile."""
                db.save_draft(did, title=st.session_state.get(tkey),
                              body_md=st.session_state.get(bkey))

            st.text_input("Article title", value=draft["title"], key=title_key,
                          on_change=autosave)

            def switched(did=draft["id"]):
                """Cambiando vista la casella va rifatta da capo.

                In anteprima la casella non viene disegnata, e Streamlit butta
                via lo stato dei widget che non disegna piu'. Cambiare il
                contatore la fa rinascere come widget nuovo, che il proprio
                `value=` lo legge - e lo legge dal database, dove il salvataggio
                al blur ha appena scritto. Senza, tornando in scrittura si
                rischia di rivedere il testo di prima."""
                st.session_state[f"bodyn_{did}"] = st.session_state.get(f"bodyn_{did}", 0) + 1

            mode = st.segmented_control(
                "View", ["✎ Markdown", "◫ Formatted"], default="✎ Markdown",
                key=f"mode_{draft['id']}", on_change=switched,
                label_visibility="collapsed",
                help="The formatted view is not a generic Markdown preview: it "
                     "is the very HTML the copy button puts on the clipboard, "
                     "so it is what the Radiopaedia editor will receive.")

            if mode == "◫ Formatted":
                preview_box(
                    rp.to_html(body_md, numbers, top_heading=draft["top_heading"] or 3),
                    rp.reference_lines(numbers, citations))
                st.caption(
                    "Read-only — switch back to Markdown to edit. "
                    "Citation numbers come from the order of first appearance."
                )
            else:
                markdown_toolbar(f"body{draft['id']}")
                st.text_area(
                    "Body (Markdown)", value=draft["body_md"] or "", key=body_key,
                    height=460, on_change=autosave,
                    help="Cite with [@27859258] — the identifier itself (PMID, DOI, "
                         "PMCID, ISBN). Numbers are worked out at export from the "
                         "order of first appearance.",
                )
                st.caption(
                    "`#` → h3 (section) · `##` → h4 · `**bold**` · `*italic*` · "
                    "`- list` · `[text](url)` · `[@27859258]` cites. "
                    "⌘B bold · ⌘I italic · ⌘K link. "
                    "Saved when a field loses focus."
                )

            with st.expander("⌗ Headings — the structure this kind of article "
                             "should have", expanded=False):
                heading_panel(draft, body_md)

        with col_side:
            st.markdown("**References**")
            st.caption(f"{len(set(numbers.values()))} cited in the text · "
                       f"{len(listed)} in the list")
            for n, idents in sorted(merged.items()):
                st.caption(f"↳ {' and '.join(idents)} are the same paper — "
                           f"both are reference {n}.")

            if cited_not_listed:
                st.warning(f"{len(cited_not_listed)} cited but not in the list.")
                if st.button("Add them to the list", width="stretch"):
                    db.add_draft_refs(draft["id"], cited_not_listed, note="from the text")
                    st.rerun()

            if unresolved:
                if st.button(f"🔎 Resolve {len(unresolved)} citation(s)",
                             type="primary", width="stretch"):
                    bar = st.progress(0.0, "Asking radiopaedia.work/cite…")
                    session = http_session()
                    failed = []
                    for i, ident in enumerate(unresolved, 1):
                        try:
                            db.store_citation(rp.fetch_citation(ident, session))
                        except rp.CiteError as exc:
                            failed.append(f"{ident}: {exc}")
                        bar.progress(i / len(unresolved), f"{i}/{len(unresolved)}")
                        if i < len(unresolved):
                            time.sleep(0.4)
                    if failed:
                        st.error("Not resolved:\n\n" + "\n\n".join(failed))
                    else:
                        st.rerun()

            with st.form(f"add_ref_{draft['id']}", clear_on_submit=True):
                raw = st.text_input("Add by identifier",
                                    placeholder="PMID, DOI, PMCID, ISBN or URL")
                if st.form_submit_button("Add reference", width="stretch"):
                    ident = rp.normalise_identifier(raw)
                    if ident:
                        db.add_draft_refs(draft["id"], [ident], note="added by hand")
                        st.rerun()

            # Da dove pesca la bibliografia: i segnalati, o una delle liste.
            # Sono due modi diversi di aver gia' deciso che un lavoro serve, e
            # una lista fatta per una sezione dell'articolo e' esattamente la
            # bibliografia di quella sezione.
            with st.expander("From the archive", expanded=False):
                reading_lists = db.list_lists()
                FLAGGED = "★ Flagged"
                sources = [FLAGGED] + [f"🗂 {r['name']}" for r in reading_lists]
                source = st.selectbox(
                    "Source", sources, key=f"refsrc_{draft['id']}",
                    label_visibility="collapsed")

                if source == FLAGGED:
                    rows = db.flagged_articles()
                    note = "from the archive"
                else:
                    chosen_list = reading_lists[sources.index(source) - 1]
                    rows = db.list_articles(chosen_list["id"])
                    note = f"from the list “{chosen_list['name']}”"

                already = set(listed)
                available = [r for r in rows if r["pmid"] not in already]
                if not rows:
                    st.caption("Nothing here yet.")
                elif not available:
                    st.caption(f"All {len(rows)} of them are already in the list.")
                else:
                    titles = {r["pmid"]: clean(r["title"]) for r in rows}
                    picked = st.multiselect(
                        "Articles", [r["pmid"] for r in available],
                        format_func=lambda p: f"{p} — {titles[p][:60]}",
                        label_visibility="collapsed",
                        placeholder=f"Choose from {len(available)}…",
                        key=f"refpick_{draft['id']}_{source}")
                    # Uno sotto l'altro, non affiancati: questa colonna e'
                    # stretta, e due pulsanti in fila ci finiscono a capo in
                    # mezzo alla parola.
                    if st.button(f"Add {len(picked)}", disabled=not picked,
                                 key=f"refadd_{draft['id']}", width="stretch"):
                        db.add_draft_refs(draft["id"], picked, note=note)
                        st.rerun()
                    if st.button(f"Add all {len(available)}",
                                 key=f"refall_{draft['id']}", width="stretch"):
                        db.add_draft_refs(
                            draft["id"], [r["pmid"] for r in available], note=note)
                        st.rerun()
                    if len(rows) != len(available):
                        st.caption(f"{len(rows) - len(available)} already in the list.")

            st.divider()
            st.markdown("**Searches**")
            history = db.recent_searches(30)
            attached = db.draft_search_list(draft["id"])
            attached_ids = {r["id"] for r in attached}
            for row in attached:
                c1, c2 = st.columns([5, 1])
                c1.caption(f"**{row['terms']}** — {row['n_found']} found, "
                           f"{row['n_saved']} saved")
                if c2.button("✕", key=f"detach_{draft['id']}_{row['id']}"):
                    db.detach_search(draft["id"], row["id"])
                    st.rerun()
            free = [r for r in history if r["id"] not in attached_ids]
            if free:
                pick = st.selectbox(
                    "Attach a search", free,
                    format_func=lambda r: f"{r['terms']} ({r['n_found']} found)",
                    index=None, placeholder="Choose a search…")
                if pick is not None and st.button("Attach", width="stretch"):
                    db.attach_search(draft["id"], pick["id"])
                    st.rerun()
            elif not attached:
                st.caption("No searches recorded yet — run one in the PubMed search tab.")

        # ------------------------------------------------------------------
        # anteprima ed export
        # ------------------------------------------------------------------
        st.divider()
        st.subheader("Paste into the Radiopaedia editor")
        st.caption(
            "The editor is WYSIWYG: plain text loses the formatting. These two "
            "boxes copy as rich text, so headings, bold and the <sup> markers "
            "survive the paste. The article goes in the body; each reference "
            "line goes in its own reference box."
        )

        article_html = rp.to_html(body_md, numbers, top_heading=draft["top_heading"] or 3)
        lines = rp.reference_lines(numbers, citations)
        refs_html = "<br>".join(lines) if lines else ""

        ex_left, ex_right = st.columns([2.2, 1])
        with ex_left:
            rich_copy_box(article_html, label="📋 Copy article (formatted)",
                          height=430, key=f"art{draft['id']}")
        with ex_right:
            rich_copy_box(refs_html, label=f"📋 Copy {len(lines)} reference(s)",
                          height=430, key=f"ref{draft['id']}")

        if listed_not_cited:
            st.caption(
                f"⚠️ {len(listed_not_cited)} reference(s) in the list are never cited "
                f"in the text and are therefore not numbered: "
                + ", ".join(listed_not_cited[:6])
                + (" …" if len(listed_not_cited) > 6 else "")
            )

        with st.expander("HTML source", expanded=False):
            st.caption(
                "What the button puts on the clipboard. Useful to check what "
                "the editor received, or to paste somewhere that takes HTML."
            )
            st.code(article_html, language="html")

        with st.expander("Reference list, one line per box", expanded=False):
            for line in lines:
                st.code(line, language="text")
            for ident in listed_not_cited:
                rec = citations.get(ident) or {}
                c1, c2 = st.columns([5, 1.3])
                c1.caption(f"not cited — {rec.get('title') or ident}")
                if c2.button("✕", key=f"drop_{draft['id']}_{ident}"):
                    db.remove_draft_ref(draft["id"], ident)
                    st.rerun()

        # ------------------------------------------------------------------
        # la bozza come file
        # ------------------------------------------------------------------
        st.divider()
        st.subheader("Keep a copy")
        st.caption(
            "Two files, and they are two different things. The `.json` is the "
            "draft — text, kind of article, references with their notes, and "
            "the citations already resolved — and it is the one Import reads "
            "back. The `.md` is to read: it opens in anything, years from now. "
            "Import takes the JSON only, because the Markdown has none of the "
            "other three in it and reading it back would lose them silently."
        )
        bundle = draft_io.bundle(draft["id"])
        dl_json, dl_md, _ = st.columns([1, 1, 2])
        dl_json.download_button(
            "⤓ Export .json", data=draft_io.to_json(bundle),
            file_name=draft_io.filename(bundle, ".json"), mime="application/json",
            width="stretch", key=f"dljson_{draft['id']}")
        dl_md.download_button(
            "⤓ Export .md", data=draft_io.to_markdown(bundle),
            file_name=draft_io.filename(bundle, ".md"), mime="text/markdown",
            width="stretch", key=f"dlmd_{draft['id']}")

        # ------------------------------------------------------------------
        # il lint
        # ------------------------------------------------------------------
        st.divider()
        st.subheader("Lint the draft")
        lint_panel(draft, body_md, numbers)
