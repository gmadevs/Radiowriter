#!/usr/bin/env python3
"""La scheda Write, guidata senza browser.

    python3 check_app.py

`check_rules.py` e `check_structure.py` provano i due motori; questo prova il
filo che li lega all'interfaccia, che e' dove stanno gli sbagli che i motori
non possono avere: Streamlit non lascia scrivere la voce di un widget dopo che
il widget e' stato creato, e la prima versione di questo pannello lo faceva in
due punti - inserire i titoli funzionava, e la pagina restava indietro fino al
ricaricamento successivo.

`AppTest` esegue l'app vera in memoria e permette di premere i bottoni per
chiave, quindi quello che si prova qui e' esattamente il codice che gira.
"""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile

# PRIMA di importare `db`: la suite esegue l'app vera, e l'app all'avvio fa
# pulizia degli articoli gia' letti. Su un database usa e getta non c'e' niente
# da perdere; sull'archivio vero ci sarebbe.
_TMP_DB = os.path.join(tempfile.mkdtemp(prefix="radiopaedia-test-"), "test.db")
os.environ["RADIOPAEDIA_DB"] = _TMP_DB

from streamlit.testing.v1 import AppTest    # noqa: E402

# Il file dell'app sta nel package, non piu' accanto a questo script.
APP = str(pathlib.Path(__file__).resolve().parent / "radiowriter" / "app.py")

from radiowriter import db          # noqa: E402
from radiowriter import draft_io    # noqa: E402
from radiowriter import structure as sx  # noqa: E402

db.init_db()

# L'app appena installata mostra la schermata del primo avvio e si ferma li'.
# Tutto quello che si prova sotto e' l'app gia' configurata: la schermata di
# setup ha la sua prova, in fondo.
db.save_settings({"ncbi_email": "prova@esempio.it"})

BODY = """# Epidemiology

A cerebral abscess doesn't occur often, and a recent study showed 15mm lesions
in the 1990s [@27859258].

# Radiographic Features

The lesion was heterogenous on CT [@27859258]. The the appearance is classic!

- Oedema of the white matter.
- ring enhancement
"""

checked = 0
failed = 0


def is_(what: str, got, want) -> None:
    global checked, failed
    checked += 1
    if str(got) == str(want):
        print(f"OK  {what}")
        return
    failed += 1
    print(f"NO  {what}\n      ottenuto {got!r}\n      atteso   {want!r}")


def fresh(body: str = BODY) -> tuple[AppTest, int]:
    """Una bozza di prova, e l'app aperta sulla scheda Write con quella
    selezionata. Viene cancellata dal chiamante."""
    draft_id = db.create_draft("Cerebral abscess (test)", body_md=body)
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["draft_id"] = draft_id
    at.run()
    return at, draft_id


def exceptions(at: AppTest) -> list[str]:
    return [str(e.value) for e in at.exception]


def body_of(draft_id: int) -> str:
    return db.get_draft(draft_id)["body_md"]


# ---------------------------------------------------------------------------
# la pagina si apre senza rompersi
# ---------------------------------------------------------------------------

at, draft_id = fresh()
try:
    is_("la scheda Write si apre senza eccezioni", exceptions(at), "[]")

    # ------------------------------------------------------------------
    # inserire i titoli obbligatori
    # ------------------------------------------------------------------
    button = next(b for b in at.button if b.key == f"ins_{draft_id}")
    is_("il bottone offre i quattro obbligatori che mancano",
        button.label, "Insert 4 heading(s)")

    at = button.click().run()
    is_("...e premerlo non solleva niente", exceptions(at), "[]")
    is_("i titoli entrano nell'ordine del canone",
        " > ".join(h.title for h in sx.headings_in(body_of(draft_id))),
        "Epidemiology > Clinical presentation > Pathology > Radiographic Features > "
        "Treatment and prognosis > Differential diagnosis")

    button = next(b for b in at.button if b.key == f"ins_{draft_id}")
    is_("dopo l'inserimento non ne resta nessuno spuntato",
        button.label, "Insert 0 heading(s)")
    is_("...e la casella del testo mostra il testo nuovo",
        at.text_area[0].value.strip().endswith("# Differential diagnosis"), "True")
finally:
    db.delete_draft(draft_id)

# ---------------------------------------------------------------------------
# uno solo, a una riga che non e' la sua
# ---------------------------------------------------------------------------

at, draft_id = fresh("# Epidemiology\n\nCommon.\n\n# Pathology\n\nGliotic.\n")
try:
    heading = next(s for s in at.selectbox if s.key == f"one_{draft_id}")
    # `options` sono le etichette gia' formattate, non le righe del canone:
    # si sceglie per indice.
    at = heading.select_index(
        next(i for i, o in enumerate(heading.options)
             if o.strip() == "Microscopic appearance")).run()
    at = next(n for n in at.number_input if n.key == f"line_{draft_id}").set_value(3).run()

    is_("una riga nella sezione sbagliata viene segnalata", len(at.warning) >= 1, "True")
    is_("...e dice sotto cosa va e dove e' finito",
        "va sotto \"Pathology\"" in at.warning[0].value
        and "dentro \"Epidemiology\"" in at.warning[0].value, "True")

    at = next(b for b in at.button if b.key == f"canon_{draft_id}").click().run()
    is_("messo dove dice la struttura, finisce sotto il proprio genitore",
        " > ".join(f"{h.level}:{h.title}" for h in sx.headings_in(body_of(draft_id))),
        "1:Epidemiology > 1:Pathology > 2:Microscopic appearance")
finally:
    db.delete_draft(draft_id)

at, draft_id = fresh("# Epidemiology\n\nCommon.\n\n# Pathology\n\nGliotic.\n")
try:
    heading = next(s for s in at.selectbox if s.key == f"one_{draft_id}")
    # `options` sono le etichette gia' formattate, non le righe del canone:
    # si sceglie per indice.
    at = heading.select_index(
        next(i for i, o in enumerate(heading.options)
             if o.strip() == "Microscopic appearance")).run()
    at = next(n for n in at.number_input if n.key == f"line_{draft_id}").set_value(3).run()
    at = next(b for b in at.button if b.key == f"here_{draft_id}").click().run()
    is_("messo dove dico io, finisce dove dico io",
        " > ".join(f"{h.level}:{h.title}" for h in sx.headings_in(body_of(draft_id))),
        "1:Epidemiology > 2:Microscopic appearance > 1:Pathology")
finally:
    db.delete_draft(draft_id)

# ---------------------------------------------------------------------------
# il lint
# ---------------------------------------------------------------------------

at, draft_id = fresh()
try:
    at = next(b for b in at.button if b.key == f"lint_{draft_id}").click().run()
    is_("il lint gira senza sollevare", exceptions(at), "[]")
    said = " ".join(m.value for m in at.markdown)
    is_("...e conta quello che ha trovato", "error(s)" in said and "warning(s)" in said, "True")
    is_("...e nomina una regola precisa", "Contractions" in said, "True")
finally:
    db.delete_draft(draft_id)

# ---------------------------------------------------------------------------
# lo switch fra markdown e formattato
# ---------------------------------------------------------------------------

at, draft_id = fresh()
try:
    is_("si parte in markdown, con la casella",
        len([t for t in at.text_area if t.key.startswith(f"body_{draft_id}")]), 1)

    switch = next(s for s in at.segmented_control if s.key == f"mode_{draft_id}")
    at = switch.set_value("◫ Formatted").run()
    is_("passando a formattato non si solleva niente", exceptions(at), "[]")
    is_("...e la casella sparisce",
        len([t for t in at.text_area if t.key.startswith(f"body_{draft_id}")]), 0)

    shown = " ".join(h.body for h in at.get("html"))
    is_("...e l'anteprima mostra i titoli resi", "<h3>Epidemiology</h3>" in shown, "True")
    is_("...con i marcatori di citazione al posto giusto", "<sup>1</sup>" in shown, "True")
    is_("...e la bibliografia sotto", "References" in shown, "True")

    # il testo non si perde nel viaggio di andata e ritorno
    switch = next(s for s in at.segmented_control if s.key == f"mode_{draft_id}")
    at = switch.set_value("✎ Markdown").run()
    box = next(t for t in at.text_area if t.key.startswith(f"body_{draft_id}"))
    is_("tornando indietro il testo e' ancora tutto li'", box.value, BODY)
finally:
    db.delete_draft(draft_id)

# ---------------------------------------------------------------------------
# la bozza come file
# ---------------------------------------------------------------------------

at, draft_id = fresh()
try:
    names = [b.label for b in at.download_button]
    is_("l'export offre tutti e due i file",
        sorted(n for n in names if "Export" in n), "['\u2913 Export .json', '\u2913 Export .md']")

    # il giro completo: quello che l'export scrive, riletto dall'import
    data = draft_io.bundle(draft_id)
    back = draft_io.read_bundle(draft_io.to_json(data))
    is_("il json riletto ha lo stesso testo", back["body_md"], data["body_md"])
    copy_id = draft_io.create_from(back)
    try:
        is_("...e rientra come bozza NUOVA", copy_id != draft_id, "True")
        is_("...con la sua bibliografia", db.draft_identifiers(copy_id), db.draft_identifiers(draft_id))
    finally:
        db.delete_draft(copy_id)

    try:
        draft_io.read_bundle('{"hello": "world"}')
        is_("un file estraneo viene rifiutato", "accettato", "rifiutato")
    except draft_io.DraftIOError:
        is_("un file estraneo viene rifiutato", "rifiutato", "rifiutato")
finally:
    db.delete_draft(draft_id)

# ---------------------------------------------------------------------------
# il compositore di ricerche a blocchi
# ---------------------------------------------------------------------------
#
# Il motore (`querybuilder`) lo prova `check_search.py`. Qui si prova il filo:
# che le chiavi dei widget reggano l'aggiunta e la rimozione di righe, che e'
# il punto in cui Streamlit tiene il valore per chiave e non per posizione.

draft_id = db.create_draft("Cerebral abscess (test)", body_md=BODY)
try:
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    is_("l'app si apre senza eccezioni", exceptions(at), "[]")

    at = next(c for c in at.segmented_control if c.key == "search_how").set_value(
        "⛁ Blocks").run()
    is_("il compositore si apre senza eccezioni", exceptions(at), "[]")

    def qb_texts(app):
        return [i for i in app.text_input if (i.key or "").startswith("qbt_")]

    is_("si parte da un blocco con un termine solo", len(qb_texts(at)), 1)

    at = qb_texts(at)[0].set_value("Joubert syndrome").run()
    at = next(b for b in at.button if (b.key or "").startswith("qba_")).click().run()
    is_("aggiungere un sinonimo non solleva", exceptions(at), "[]")
    is_("...e il primo termine resta dov'era", qb_texts(at)[0].value, "Joubert syndrome")

    at = qb_texts(at)[1].set_value("molar tooth sign").run()
    at = next(b for b in at.button if b.key == "qb_add_block").click().run()
    at = qb_texts(at)[2].set_value("MRI").run()
    is_("tre termini in due blocchi", len(qb_texts(at)), 3)

    codes = [c.value for c in at.code]
    is_("la query composta e' quella attesa",
        any(c == '("Joubert syndrome"[tiab] OR "molar tooth sign"[tiab]) AND MRI[tiab]'
            for c in codes), "True")

    # togliere il termine di mezzo: le chiavi portano un id che non si riusa,
    # quindi il terzo non deve scivolare nella casella del secondo
    middle = qb_texts(at)[1].key.split("_")[-1]
    at = next(b for b in at.button
              if (b.key or "").startswith("qbx_")
              and (b.key or "").endswith("_" + middle)).click().run()
    is_("togliere un termine non solleva", exceptions(at), "[]")
    is_("...e non fa scivolare i valori degli altri",
        [i.value for i in qb_texts(at)], "['Joubert syndrome', 'MRI']")

    # le strategie dai titoli della bozza
    at = next(r for r in at.radio if r.key == "stg_source").set_value("A draft").run()
    picked = next(m for m in at.multiselect if (m.key or "").startswith("stg_picked"))
    is_("i titoli della bozza offrono le loro strategie",
        sorted(picked.options), "['Epidemiology', 'Radiographic features']")

    at = picked.set_value(["Epidemiology"]).run()
    at = next(b for b in at.button if b.key == "stg_add").click().run()
    is_("aggiungere una strategia non solleva", exceptions(at), "[]")
    added = [i.value for i in qb_texts(at) if i.value.startswith("(")]
    is_("...e finisce in un blocco come pezzo di query gia' scritto",
        len(added) == 1 and '"Epidemiology"[Mesh]' in added[0], "True")

    is_("la query finale tiene insieme i termini e la strategia",
        any('"Joubert syndrome"[tiab]' in c and '"Epidemiology"[Mesh]' in c
            for c in [x.value for x in at.code]), "True")
finally:
    db.delete_draft(draft_id)

# ---------------------------------------------------------------------------
# le liste, dalla scheda di screening
# ---------------------------------------------------------------------------

db.insert_articles([{"pmid": "9001", "title": "Un articolo di prova",
                     "abstract": "niente"}])
list_id = db.create_list("Prova")
try:
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    is_("con una lista in giro l'app si apre lo stesso", exceptions(at), "[]")

    box = next(c for c in at.checkbox if c.key == "inlist_9001_%d_0" % list_id)
    at = box.set_value(True).run()
    is_("spuntare la lista sulla scheda ce lo mette davvero",
        db.list_pmids(list_id), "['9001']")
    is_("...senza sollevare", exceptions(at), "[]")

    box = next(c for c in at.checkbox if c.key == "inlist_9001_%d_1" % list_id)
    at = box.set_value(False).run()
    is_("e toglierla lo toglie", db.list_pmids(list_id), "[]")

    names = [i.value for i in at.text_input if i.key == "lname_%d" % list_id]
    is_("la lista si puo' rinominare dalla sua casella", names, "['Prova']")
finally:
    db.delete_list(list_id)
    conn = db.get_connection()
    conn.execute("DELETE FROM articles WHERE pmid = '9001'")
    conn.commit()
    conn.close()

# ---------------------------------------------------------------------------
# quartili e open access sulle schede
# ---------------------------------------------------------------------------
#
# I motori li provano `check_journals.py` e `check_search.py`. Qui si prova che
# quello che esce da una LEFT JOIN senza corrispondenza non finisca stampato
# addosso a un articolo: NaN e' un float, passa qualsiasi `if`, e verrebbe fuori
# un badge che dice "nan".

from radiowriter import journals as jr          # noqa: E402

db.import_journal_metrics([{
    "title": "European Journal of Radiology",
    "norm_title": jr.norm_title("European Journal of Radiology"),
    "issns": ["0720048X"], "sjr": 1.075, "quartile": "Q1", "h_index": 140,
    "cites_per_doc": 4.0, "categories": "Radiology (Q1)", "country": "Netherlands",
    "publisher": "Elsevier",
}])
db.insert_articles([
    {"pmid": "9201", "title": "Con quartile", "abstract": "a",
     "journal": "European journal of radiology",
     "journal_title": "European journal of radiology", "issn": "0720048X"},
    {"pmid": "9202", "title": "Senza quartile", "abstract": "b",
     "journal": "Cureus", "journal_title": "Cureus", "issn": "20408090"},
])
try:
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    is_("con le metriche caricate l'app si apre", exceptions(at), "[]")

    def text_of(app):
        """Tutto quello che la pagina scrive: `st.caption` non finisce fra i
        markdown, e meta' dei conteggi dell'app sono caption."""
        return " ".join([m.value for m in app.markdown]
                        + [c.value for c in app.caption])

    page = text_of(at)
    is_("il quartile si vede, col suo colore", 'class="q1"' in page, "True")
    is_("...e porta lo SJR con se'", "Q1 · SJR 1.07" in page, "True")
    is_("una rivista senza metrica non stampa 'nan'", "nan" in page.lower(), "False")
    is_("...e nemmeno un badge vuoto", 'class="none"' in page, "False")

    # il filtro per quartile deve restringere per davvero, e il conteggio delle
    # pagine con lui: e' una JOIN, non un filtro applicato dopo
    def quartile_filter(app):
        # Va ripreso dall'albero di QUESTO giro: un handle tenuto da prima
        # rigioca lo stato di allora, e le spunte delle schede non ci sono piu'.
        return next(m for m in app.multiselect if m.label == "Journal quartile:")

    at_q1 = quartile_filter(at).set_value(["Q1"]).run()
    is_("il filtro per quartile non solleva", exceptions(at_q1), "[]")
    counts = text_of(at_q1)
    is_("...e conta solo quelli che restano", "**1** articles found" in counts, "True")
    is_("...cioe' quello Q1",
        "Con quartile" in counts and "Senza quartile" not in counts, "True")

    at_none = quartile_filter(at_q1).set_value(["Not in SCImago"]).run()
    counts = text_of(at_none)
    is_("e sa chiedere anche quelli che SCImago non ha",
        "**1** articles found" in counts, "True")
    is_("...che sono l'altro articolo",
        "Senza quartile" in counts and "Con quartile" not in counts, "True")

    # Unpaywall: il pulsante c'e' solo se c'e' un DOI da chiedere
    labels = [b.label for b in at.button]
    is_("senza DOI non si offre di chiedere a Unpaywall",
        any("open access" in (l or "") for l in labels), "False")
finally:
    conn = db.get_connection()
    conn.execute("DELETE FROM articles WHERE pmid IN ('9201', '9202')")
    conn.execute("DELETE FROM journal_issns")
    conn.execute("DELETE FROM journal_metrics")
    conn.commit()
    conn.close()

# ---------------------------------------------------------------------------
# una lista come sorgente di bibliografia
# ---------------------------------------------------------------------------

db.insert_articles([{"pmid": "9301", "title": "Da mettere in bibliografia",
                     "abstract": "c", "journal": "Radiology"}])
list_id = db.create_list("Per il capitolo")
db.add_to_list(list_id, ["9301"])
draft_id = db.create_draft("Bozza di prova", body_md="# Epidemiology\n\nTesto.\n")
try:
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["draft_id"] = draft_id
    at.run()
    is_("la scheda Write si apre con una lista in giro", exceptions(at), "[]")

    source = next(s for s in at.selectbox if s.key == f"refsrc_{draft_id}")
    is_("le liste si offrono accanto ai segnalati",
        source.options, "['★ Flagged', '🗂 Per il capitolo']")

    at = source.set_value("🗂 Per il capitolo").run()
    add_all = next(b for b in at.button if b.key == f"refall_{draft_id}")
    is_("...e si possono aggiungere tutti in una volta", add_all.label, "Add all 1")

    at = add_all.click().run()
    is_("premerlo non solleva", exceptions(at), "[]")
    is_("l'articolo della lista e' in bibliografia",
        db.draft_identifiers(draft_id), "['9301']")
    is_("...con scritto da quale lista viene",
        db.draft_ref_rows(draft_id)[0]["note"], "from the list “Per il capitolo”")

    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["draft_id"] = draft_id
    at.run()
    at = next(s for s in at.selectbox
              if s.key == f"refsrc_{draft_id}").set_value("🗂 Per il capitolo").run()
    page = " ".join([m.value for m in at.markdown] + [c.value for c in at.caption])
    is_("chi c'e' gia' non viene riofferto",
        "All 1 of them are already in the list." in page, "True")
finally:
    db.delete_draft(draft_id)
    db.delete_list(list_id)
    conn = db.get_connection()
    conn.execute("DELETE FROM articles WHERE pmid = '9301'")
    conn.commit()
    conn.close()

# ---------------------------------------------------------------------------
# il primo avvio
# ---------------------------------------------------------------------------
#
# Senza email la ricerca non parte. Prima l'app si apriva lo stesso e lo si
# scopriva al primo tentativo di cercare; adesso lo dice subito, e dice perche'.

saved_email = db.get_settings().get("ncbi_email")
db.save_settings({"ncbi_email": "", "unpaywall_email": ""})
try:
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    is_("senza email si apre la schermata del primo avvio", exceptions(at), "[]")

    page = " ".join([m.value for m in at.markdown] + [c.value for c in at.caption]
                    + [h.value for h in at.subheader])
    is_("...che chiede una cosa sola", "One thing to set up" in page, "True")
    is_("...e dice a cosa serve l'email",
        "email address in every request" in page, "True")
    is_("...nominando i servizi", "Unpaywall" in page and "PubMed" in page, "True")
    is_("le schede non ci sono ancora", len(at.tabs), 0)

    email = at.text_input[0]
    is_("il primo campo e' l'email", email.label, "Your email address")

    # un indirizzo che non e' un indirizzo non deve essere salvato: PubMed
    # rifiuta la richiesta, e lo si scoprirebbe molto piu' tardi
    at2 = email.set_value("non-una-email").run()
    at2 = at2.button[0].click().run()
    is_("un indirizzo malfatto viene rifiutato", len(at2.error) >= 1, "True")
    is_("...e non viene salvato", db.get_settings().get("ncbi_email"), "")

    at3 = at2.text_input[0].set_value("io@ospedale.it").run()
    at3 = at3.button[0].click().run()
    is_("un indirizzo buono si salva", db.get_settings().get("ncbi_email"),
        "io@ospedale.it")
    is_("...e vale anche per Unpaywall",
        db.get_settings().get("unpaywall_email"), "io@ospedale.it")
    is_("...e adesso l'app si apre davvero", len(at3.tabs), 3)
finally:
    db.save_settings({"ncbi_email": saved_email or "prova@esempio.it",
                      "unpaywall_email": ""})

# ---------------------------------------------------------------------------
# "Recent reviews" come interruttore, e i filtri sui risultati
# ---------------------------------------------------------------------------

at = AppTest.from_file(APP, default_timeout=60)
at.run()

toggle = next(t for t in at.toggle if t.key == "sf_recent")
is_("il fascio parte acceso", toggle.value, "True")
is_("...e con lui i filtri sono bloccati",
    next(n for n in at.number_input if n.key == "sf_years").disabled, "True")
is_("...sugli ultimi dieci anni", at.session_state["sf_years"], 10)

at_off = toggle.set_value(False).run()
is_("spegnendolo i filtri si sbloccano",
    next(n for n in at_off.number_input if n.key == "sf_years").disabled, "False")
is_("...senza azzerarli sotto le mani", at_off.session_state["sf_years"], 10)
is_("...e senza sollevare", exceptions(at_off), "[]")

at_clear = next(b for b in at_off.button if b.key == "sf_clear").click().run()
is_("azzerare toglie anche il limite di data",
    at_clear.session_state["sf_years"], 0)
is_("...e i tipi di articolo", at_clear.session_state["sf_types"], "[]")

# zero anni = nessuna clausola di data nella query
from radiowriter import pubmed as _pm             # noqa: E402
from datetime import date as _date   # noqa: E402
is_("zero anni non mette nessun limite di data",
    "Date - Publication" in _pm.build_query(
        "x", type_labels=[], years=0, full_text=False, english=False,
        humans=False, today=_date(2026, 9, 2)), "False")

# le faccette sui risultati, con dei record finti in sessione
at = AppTest.from_file(APP, default_timeout=60)
at.session_state["search_results"] = [
    {"pmid": "8801", "title": "Uno", "abstract": "parla di bambini",
     "journal": "Radiology", "year": "2020", "pub_types": "Review",
     "citation_count": 40, "oa_status": "gold", "oa_fetched_at": "2026-01-01"},
    {"pmid": "8802", "title": "Due", "abstract": "parla di adulti",
     "journal": "Radiology", "year": "2010", "pub_types": "Case Reports",
     "citation_count": 2, "oa_status": "closed", "oa_fetched_at": "2026-01-01"},
]
at.session_state["search_total"] = 2
at.run()
is_("con dei risultati in sessione l'app non solleva", exceptions(at), "[]")

types = next(m for m in at.multiselect if (m.key or "").startswith("rf_types_"))
is_("le faccette contano i tipi che ci sono davvero",
    sorted(types.options), "['Case Reports (1)', 'Review (1)']")

at_f = types.set_value(["Review"]).run()
shown = " ".join([m.value for m in at_f.markdown] + [c.value for c in at_f.caption])
is_("filtrare per tipo nasconde l'altro", "Showing 1 of 2" in shown, "True")
is_("...e resta quello giusto", "Uno" in shown and "Due" not in shown, "True")

oa = next(c for c in at_f.checkbox if (c.key or "").startswith("rf_oa_"))
is_("l'open access si puo' filtrare quando e' stato chiesto",
    oa.label, "Only free full text (1)")

at_c = next(n for n in at_f.number_input
            if (n.key or "").startswith("rf_cites_")).set_value(10).run()
shown = " ".join([m.value for m in at_c.markdown] + [c.value for c in at_c.caption])
is_("si filtra anche per citazioni", "Showing 1 of 2" in shown, "True")

at_z = next(b for b in at_c.button
            if (b.key or "").startswith("rf_clear_")).click().run()
shown = " ".join([m.value for m in at_z.markdown] + [c.value for c in at_z.caption])
is_("azzerare le faccette rimette tutto", "Showing" in shown, "False")
is_("...senza sollevare", exceptions(at_z), "[]")

# ---------------------------------------------------------------------------
# dove sta l'archivio, detto a schermo
# ---------------------------------------------------------------------------
#
# Chi si trova davanti un archivio inatteso deve poter LEGGERE da dove viene.
# Senza, l'unica strada e' aprire un terminale e indovinare - ed e' successo.

from radiowriter import paths as _paths       # noqa: E402

at = AppTest.from_file(APP, default_timeout=60)
at.run()
side = " ".join([m.value for m in at.sidebar.markdown]
                + [c.value for c in at.sidebar.caption])
is_("la barra laterale dice quanti articoli ci sono",
    "Archive" in side and "articles" in side, "True")
is_("...e mostra il percorso del file",
    _paths.short(_paths.db_path()) in side, "True")
is_("i test girano su un database scelto da RADIOPAEDIA_DB",
    _paths.db_origin()[1], _paths.FROM_ENV)
is_("...e la barra laterale lo dice invece di tacere",
    "RADIOPAEDIA_DB" in side, "True")

# La ragione va detta anche quando il database sta accanto al codice, che e' il
# caso che ha generato il dubbio: sembra che l'app abbia scelto a caso.
from radiowriter import __main__ as _cli      # noqa: E402
for origin in (_paths.FROM_ENV, _paths.FROM_SOURCE, _paths.FROM_DATA_DIR):
    is_(f"la riga di comando spiega l'origine '{origin}'",
        bool(_cli._why(origin).strip()), "True")
is_("...e per l'archivio accanto al codice dice perche' non viene spostato",
    "never moved out" in _cli._why(_paths.FROM_SOURCE), "True")

print(f"\n{checked} controlli, {failed} falliti")
sys.exit(1 if failed else 0)
