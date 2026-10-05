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
# e la cartella dei dati, dove l'app crea la libreria dei PDF
os.environ["RADIOWRITER_HOME"] = os.path.dirname(_TMP_DB)

from streamlit.testing.v1 import AppTest    # noqa: E402

# Il file dell'app sta nel package, non piu' accanto a questo script.
APP = str(pathlib.Path(__file__).resolve().parent / "radiowriter" / "app.py")

from radiowriter import db          # noqa: E402
from radiowriter import modalities as _mod    # noqa: E402
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
        "belongs under \"Pathology\"" in at.warning[0].value
        and "inside \"Epidemiology\"" in at.warning[0].value, "True")

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

    # le modalita' di imaging
    mod_pick = next(m for m in at.multiselect if (m.key or "").startswith("mod_picked"))
    # ATTENZIONE: `options` di un multiselect sotto AppTest sono le etichette
    # GIA' passate per format_func, non i valori. `set_value` invece vuole i
    # valori. Confrontare le etichette e' comunque il controllo che serve: e'
    # quello che si legge nella tendina, e verifica che il gruppo si veda.
    is_("l'elenco delle modalita' mostra la famiglia accanto al nome",
        mod_pick.options,
        [f"{_mod.group_of(n)} › {n}" for n in _mod.covered()])
    is_("...e comincia dalla radiologia tradizionale",
        mod_pick.options[0], "Plain radiography and fluoroscopy › Radiograph (plain film)")
    is_("...e le modalita' sono tutte quelle del modulo",
        len(mod_pick.options), len(_mod.MODALITIES))

    at = mod_pick.set_value(["CT", "Doppler ultrasound"]).run()
    is_("scegliere due modalita' non solleva", exceptions(at), "[]")
    at = next(b for b in at.button if b.key == "mod_add").click().run()
    is_("aggiungerle non solleva", exceptions(at), "[]")

    added = [i.value for i in qb_texts(at) if i.value.startswith("(")]
    is_("...e ognuna arriva come una riga sua, non tutte in una",
        sum(1 for a in added if "Tomography, X-Ray Computed" in a
            or "Ultrasonography, Doppler" in a), 2)

    final = [x.value for x in at.code]
    is_("la query finale contiene le modalita' scelte",
        any('"Tomography, X-Ray Computed"[Mesh]' in c
            and '"Ultrasonography, Doppler"[Mesh]' in c for c in final), "True")
    is_("...e resta bilanciata",
        all(c.count("(") == c.count(")") for c in final), "True")

    # "MeSH only" deve togliere le keyword, non aggiungere un secondo blocco
    at = next(r for r in at.radio if r.key == "mod_mode").set_value("MeSH only").run()
    pick2 = next(m for m in at.multiselect if (m.key or "").startswith("mod_picked"))
    at = pick2.set_value(["Elastography"]).run()
    at = next(b for b in at.button if b.key == "mod_add").click().run()
    only_mesh = [i.value for i in qb_texts(at)
                 if "Elasticity Imaging" in i.value]
    is_("'MeSH only' porta il descrittore e non le keyword",
        len(only_mesh) == 1 and "elastograph*[tiab]" not in only_mesh[0], "True")
finally:
    db.delete_draft(draft_id)

# ---------------------------------------------------------------------------
# lo Screening
# ---------------------------------------------------------------------------
#
# Non e' piu' una scheda Streamlit: e' una pagina servita da `bench.py` e
# mostrata in un iframe. Qui si prova solo che l'app la monti; quello che la
# pagina fa lo prova `check_bench.py`, con richieste vere al suo server.

from radiowriter import bench as _bench          # noqa: E402

at = AppTest.from_file(APP, default_timeout=60)
at.run()
is_("l'app si apre con lo Screening montato", exceptions(at), "[]")
frames = [f.proto.src for f in at.get("iframe")]
is_("lo Screening e' un iframe solo", len(frames), 1)
is_("...che punta al banco su questa macchina, col suo gettone",
    frames[0].startswith(f"http://127.0.0.1:{_bench.start().port}/?t={_bench.start().token}"),
    "True")
is_("...e gli dice il tema e le misure del testo",
    "&theme=" in frames[0] and "&v=" in frames[0], "True")
is_("della vecchia scheda non resta nessun controllo",
    [w.key for kind in ("checkbox", "button") for w in at.get(kind)
     if (w.key or "").startswith(("sel_", "del_", "read_", "flag_", "inlist_", "screen_"))],
    "[]")

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
    is_("...che chiede una cosa sola", "Set your email address" in page, "True")
    is_("...e dice a cosa serve l'email",
        "email address in every request" in page, "True")
    is_("...nominando i servizi", "Unpaywall" in page and "PubMed" in page, "True")
    is_("le schede non ci sono ancora", len(at.tabs), 0)

    email = at.text_input[0]
    is_("il primo campo e' l'email", email.label, "Your email address")

    # un indirizzo che non e' un indirizzo non deve essere salvato: PubMed
    # rifiuta la richiesta, e lo si scoprirebbe molto piu' tardi
    # Il valore e l'invio nello stesso giro, come fa il browser con un form:
    # da Streamlit 1.65 un giro senza invio butta via quello che c'e' scritto
    # nei campi del form, e l'indirizzo arriverebbe vuoto.
    email.set_value("non-una-email")
    at2 = at.button[0].click().run()
    is_("un indirizzo malfatto viene rifiutato", len(at2.error) >= 1, "True")
    is_("...e non viene salvato", db.get_settings().get("ncbi_email"), "")

    at2.text_input[0].set_value("io@ospedale.it")
    at3 = at2.button[0].click().run()
    is_("un indirizzo buono si salva", db.get_settings().get("ncbi_email"),
        "io@ospedale.it")
    is_("...e vale anche per Unpaywall",
        db.get_settings().get("unpaywall_email"), "io@ospedale.it")
    is_("...e adesso l'app si apre davvero", len(at3.tabs), 4)
finally:
    db.save_settings({"ncbi_email": saved_email or "prova@esempio.it",
                      "unpaywall_email": ""})

# ---------------------------------------------------------------------------
# L'interruttore dei filtri a tre posizioni, e i filtri sui risultati
# ---------------------------------------------------------------------------

at = AppTest.from_file(APP, default_timeout=60)
at.run()


def mode_of(app):
    return next(b for b in app.get("button_group") if b.key == "sf_mode")


def query_of(app):
    return [c.value for c in app.code][-1]


def drawn(app, key):
    return any(w.key == key for kind in ("number_input", "checkbox", "radio",
                                         "multiselect", "text_input", "selectbox")
               for w in app.get(kind))


is_("il fascio parte acceso", mode_of(at).value, "reviews")
is_("...e non disegna nessun controllo", drawn(at, "sf_years"), "False")
is_("...ma il punto di domanda che lo spiega si'",
    any("adds these filters" in m.value for m in at.markdown), "True")

at = at.text_input(key="search_terms").set_value("glioma").run()
is_("il fascio chiede solo review e sintesi",
    "Multicenter Study" in query_of(at) or "booksdocs" in query_of(at), "False")
is_("...e humans non scarta i lavori non ancora indicizzati",
    query_of(at).endswith("NOT (animals[mh] NOT humans[mh])"), "True")

at = mode_of(at).set_value("open").run()
is_("No filters lascia solo i termini", query_of(at), "(glioma)")
is_("...non disegna nessun controllo", drawn(at, "sf_years"), "False")
is_("...e nemmeno il punto di domanda",
    any("adds these filters" in m.value for m in at.markdown), "False")

at = mode_of(at).set_value("custom").run()
is_("Custom disegna i controlli", drawn(at, "sf_years"), "True")
is_("...che partono dai valori di Recent reviews", at.session_state["sf_years"], 10)
at = at.number_input(key="sf_years").set_value(0).run()
at = at.checkbox(key="sf_fulltext").uncheck().run()
at = at.checkbox(key="sf_humans").uncheck().run()
at = at.radio(key="sf_type_by").set_value("none").run()
is_("...e la query e' quella che si vede", query_of(at), "(glioma) AND english[la]")
is_("...senza cambiare posizione da sola", mode_of(at).value, "custom")

at = at.radio(key="sf_type_by").set_value("issg").run()
issg_box = at.multiselect(key="sf_issg")
at = issg_box.set_value([issg_box.options[0]]).run()
is_("con l'ISSG il filtro entra nella query", len(query_of(at)) > 200, "True")
at = at.radio(key="sf_type_by").set_value("pt").run()
is_("...e tornando a NLM l'ISSG esce", "Clinical protocols" in query_of(at), "False")
is_("...ma la scelta ISSG resta per quando si torna",
    at.session_state["sf_issg"], [issg_box.options[0]])

at = mode_of(at).set_value("open").run()
is_("da Custom a No filters la query torna nuda", query_of(at), "(glioma)")
at = mode_of(at).set_value("custom").run()
is_("...e tornando a Custom si ritrova quello che si era lasciato",
    (at.session_state["sf_years"], at.session_state["sf_languages"],
     at.session_state["sf_type_by"]), "(0, ['English'], 'pt')")

# tutti i filtri di PubMed, in Custom
at = at.radio(key="sf_type_by").set_value("none").run()
at = at.multiselect(key="sf_languages").set_value(["English", "Italian"]).run()
at = at.checkbox(key="sf_abstract").check().run()
at = at.multiselect(key="sf_ages").set_value(["Aged: 65+ years"]).run()
at = at.checkbox(key="sf_female").check().run()
at = at.checkbox(key="sf_nopreprints").check().run()
is_("i filtri di PubMed entrano nella query nell'ordine dei gruppi", query_of(at),
    "(glioma) AND fha[Filter] AND (english[la] OR italian[Filter]) "
    "AND female[Filter] AND aged[Filter] NOT preprint[pt]")
at = at.radio(key="sf_date_by").set_value("range").run()
at = at.number_input(key="sf_year_from").set_value(2010).run()
at = at.number_input(key="sf_year_to").set_value(2015).run()
is_("l'intervallo di anni prende il posto degli ultimi N anni",
    '("2010/01/01"[Date - Publication] : "2015/12/31"[Date - Publication])'
    in query_of(at), "True")
is_("...e la riga sotto i controlli lo dice",
    any("Published 2010–2015" in c.value for c in at.caption), "True")
at = mode_of(at).set_value("reviews").run()
is_("Recent reviews non si porta dietro i filtri di Custom",
    "fha[Filter]" in query_of(at) or "italian" in query_of(at), "False")
is_("...senza sollevare", exceptions(at), "[]")

# i titoli di Radiopaedia come filtro
is_("la riga dei titoli parte chiusa", drawn(at, "hd_picked"), "False")
at = at.button(key="hd_open_btn").click().run()
is_("...e il pulsante la apre", drawn(at, "hd_picked"), "True")
is_("i titoli offerti sono quelli del tipo di articolo",
    "Epidemiology" in at.multiselect(key="hd_picked").options, "True")
before = query_of(at)
at = at.multiselect(key="hd_picked").set_value(
    ["Epidemiology", "Treatment and prognosis"]).run()
is_("i titoli scelti entrano nella query, in OR fra loro",
    '"Prevalence"[Mesh]' in query_of(at) and "prognos" in query_of(at), "True")
is_("...come un gruppo in piu', in AND col resto",
    query_of(at).count(" AND "), before.count(" AND ") + 1)
at = at.radio(key="hd_mode").set_value("keywords").run()
is_("Keywords only toglie i MeSH", "[Mesh]" in query_of(at), "False")
at = at.button(key="hd_open_btn").click().run()
is_("chiusa la riga, i titoli restano nella query", "prevalence[tiab]" in query_of(at), "True")
is_("...e il pulsante dice quanti sono",
    at.button(key="hd_open_btn").label, "⌗ Radiopaedia headings (2)")
is_("...con i loro nomi sotto",
    any("Headings in the query: Epidemiology, Treatment and prognosis." == c.value
        for c in at.caption), "True")
at = mode_of(at).set_value("open").run()
is_("No filters toglie anche i titoli", query_of(at), "(glioma)")
at = mode_of(at).set_value("custom").run()
is_("...che tornano con Custom", "prevalence[tiab]" in query_of(at), "True")
at = at.button(key="hd_open_btn").click().run()
at = at.selectbox(key="hd_profile").set_value("anatomy").run()
is_("cambiare tipo di articolo svuota i titoli scelti",
    at.session_state["hd_picked"], [])
is_("...senza sollevare", exceptions(at), "[]")

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
    {"pmid": "8802", "title": "Due",
     "abstract": "Costava $1 M, poi $780,000. RESULTS: T2* e L*/a*/b* <b>.",
     "journal": "Radiology", "year": "2010", "pub_types": "Case Reports",
     "citation_count": 2, "oa_status": "closed", "oa_fetched_at": "2026-01-01"},
]
at.session_state["search_total"] = 2
at.session_state["search_terms_used"] = "bambini"
at.run()
is_("con dei risultati in sessione l'app non solleva", exceptions(at), "[]")
is_("i termini della ricerca fatta si evidenziano nell'abstract",
    any("parla di <mark>bambini</mark>" in h.proto.body for h in at.get("html")),
    "True")

at_open = at.toggle(key="abs_open_search").set_value(True).run()
is_("aprire gli abstract nei risultati resta al riavvio, e lo Screening lo legge da li'",
    db.get_settings()["abstracts_open"], "1")
is_("...con gli abstract aperti davvero",
    all(e.proto.expanded for e in at_open.expander if e.label == "Abstract"), "True")
# lo Screening scrive la stessa voce per conto suo: al giro dopo l'app la segue
db.save_settings({"abstracts_open": "0"})
at_open = at_open.run()
is_("chiuderli dallo Screening li chiude anche nei risultati",
    at_open.toggle(key="abs_open_search").value, "False")

# L'abstract e' testo, non Markdown: `$...$` non deve diventare una formula ne'
# `*...*` un corsivo, e l'HTML scritto dentro si vede com'e'.
shown_html = " ".join(h.proto.body for h in at.get("html")
                      if "class=\"abstract\"" in h.proto.body)
is_("l'abstract arriva intero, dollari compresi",
    "Costava $1 M, poi $780,000." in shown_html, "True")
is_("...gli asterischi restano asterischi", "T2* e L*/a*/b*" in shown_html, "True")
is_("...l'HTML dentro l'abstract e' escapato", "&lt;b&gt;" in shown_html, "True")
is_("...e un'etichetta in mezzo al testo apre una sezione",
    '<span class="lbl">RESULTS</span>' in shown_html, "True")

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
    "does not move an existing archive" in _cli._why(_paths.FROM_SOURCE), "True")

# Il pannello della letteratura recente: chiuso finche' non si preme il pulsante.
at = AppTest.from_file(APP, default_timeout=60)
at.run()
is_("il pulsante della letteratura recente c'e'",
    "Fetch recent literature" in at.button(key="recent_open_btn").label, "True")
is_("...e il pannello parte chiuso",
    any(w.key == "recent_group" for w in at.selectbox), "False")
at = at.button(key="recent_open_btn").click().run()
is_("premuto, mostra il menu dei gruppi editoriali",
    at.selectbox(key="recent_group").options, "['CNS']")
is_("...la lista in cui salvare, con quella del gruppo per prima",
    at.selectbox(key="recent_list_cns").value, "Editorial group: CNS")
is_("...che puo' anche essere una lista nuova",
    at.selectbox(key="recent_list_cns").options[-1], "＋ New list…")
is_("...il pulsante che parte", at.button(key="recent_go").disabled, "False")
is_("...e dice che non ha mai girato",
    any("Never run" in c.value for c in at.caption), "True")
at = at.selectbox(key="recent_list_cns").set_value("＋ New list…").run()
is_("una lista nuova senza nome non fa partire niente",
    at.button(key="recent_go").disabled, "True")
at = at.text_input(key="recent_list_new").set_value("  Da  leggere ").run()
is_("...col nome si'", at.button(key="recent_go").disabled, "False")
is_("...e il nome e' quello ripulito",
    any("“Da leggere”" in c.value for c in at.caption), "True")
is_("...senza sollevare", exceptions(at), "[]")

# Nessun nome importato in testa all'app viene riassegnato piu' sotto. E'
# successo con `s2`: quattro colonne chiamate `s1..s4` coprivano il modulo di
# Semantic Scholar, e con i filtri su Custom la ricerca andava in errore.
import ast as _ast                                # noqa: E402
_tree = _ast.parse(pathlib.Path(APP).read_text(encoding="utf-8"))
_imported = {(a.asname or a.name).split(".")[0] for n in _tree.body
             if isinstance(n, (_ast.Import, _ast.ImportFrom)) for a in n.names}
_rebound = sorted({x.id for x in _ast.walk(_tree)
                   if isinstance(x, _ast.Name) and isinstance(x.ctx, _ast.Store)
                   and x.id in _imported})
is_("nessun modulo importato dall'app viene coperto da una variabile", _rebound, "[]")

# L'import dalla barra laterale: la lista si sceglie prima di importare.
is_("l'import chiede in che lista mettere i record",
    at.selectbox(key="import_list").options[0], "No list")
is_("...e di default in nessuna", at.selectbox(key="import_list").value, "No list")
at = at.selectbox(key="import_list").set_value("＋ New list…").run()
is_("una lista nuova senza nome non importa",
    at.button(key="import_go").disabled, "True")
at = next(r for r in at.radio if r.label == "Method:").set_value("Paste raw text").run()
at = next(t for t in at.text_area if t.label.startswith("PubMed text")).set_value(
    "PMID- 990001\nTI  - Un lavoro importato\nDP  - 2026\n").run()
at = at.text_input(key="import_list_new").set_value("Importati").run()
at = at.button(key="import_go").click().run()
_imported = {r["name"]: r for r in db.list_lists()}.get("Importati")
is_("importando, la lista nasce", _imported is not None, "True")
is_("...con dentro il record importato",
    db.list_pmids(_imported["id"]) if _imported else None, "['990001']")
is_("...senza sollevare", exceptions(at), "[]")

print(f"\n{checked} controlli, {failed} falliti")
sys.exit(1 if failed else 0)
