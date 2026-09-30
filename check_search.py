#!/usr/bin/env python3
"""Il compositore di ricerche, i filtri ISSG, le strategie e le liste.

    python3 check_search.py

Niente rete: quello che si prova qui e' come si scrive una query e come si
tengono le liste, non cosa risponde PubMed. I termini di vocabolario
controllato di `strategies` e di `modalities` li verifica `check_mesh_live.py`,
che sta a parte proprio perche' e' l'unico che ha bisogno della rete.
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import date

_TMP_DB = os.path.join(tempfile.mkdtemp(prefix="radiopaedia-lists-"), "test.db")
os.environ["RADIOPAEDIA_DB"] = _TMP_DB

from radiowriter import db                      # noqa: E402
from radiowriter import highlight as hl         # noqa: E402
from radiowriter import issg                    # noqa: E402
from radiowriter import modalities as mod       # noqa: E402
from radiowriter import pubmed                  # noqa: E402
from radiowriter import querybuilder as qb      # noqa: E402
from radiowriter import strategies as stg       # noqa: E402

db.init_db()

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


# ---------------------------------------------------------------------------
# il compositore
# ---------------------------------------------------------------------------

print("\n--- querybuilder ---")

one = qb.Block(terms=[qb.Term("abscess")])
is_("un termine solo non prende parentesi", qb.compose([one]), "abscess[tiab]")

is_("una frase viene messa fra virgolette",
    qb.render_term("molar tooth sign", "tiab"), '"molar tooth sign"[tiab]')
is_("una parola sola no", qb.render_term("abscess", "tiab"), "abscess[tiab]")
is_("il troncamento resta com'e'", qb.render_term("abscess*", "tiab"), "abscess*[tiab]")
is_("chi ha gia' il suo tag non viene ritaggato",
    qb.render_term('"Brain Abscess"[Mesh]', "tiab"), '"Brain Abscess"[Mesh]')
is_("chi ha gia' un booleano prende le parentesi e basta",
    qb.render_term("abscess OR empyema", "tiab"), "(abscess OR empyema)")
is_("il campo 'All fields' non aggiunge niente",
    qb.render_term("abscess", "all"), "abscess")

concept = qb.Block(terms=[qb.Term("Joubert syndrome"), qb.Term("molar tooth sign")])
modality = qb.Block(terms=[qb.Term("MRI"), qb.Term('"Magnetic Resonance Imaging"[Mesh]')])
excluded = qb.Block(join="NOT", terms=[qb.Term("case reports", "pt")])
is_("i sinonimi vanno in OR, i concetti in AND",
    qb.compose([concept, modality]),
    '("Joubert syndrome"[tiab] OR "molar tooth sign"[tiab]) AND '
    '(MRI[tiab] OR "Magnetic Resonance Imaging"[Mesh])')
is_("un blocco in NOT toglie invece di aggiungere",
    qb.compose([concept, excluded]),
    '("Joubert syndrome"[tiab] OR "molar tooth sign"[tiab]) NOT "case reports"[pt]')

is_("un blocco vuoto non lascia operatori appesi",
    qb.compose([concept, qb.Block(terms=[qb.Term("")]), modality]).count(" AND "), 1)
is_("un blocco spento non c'e'",
    qb.compose([concept, qb.Block(terms=[qb.Term("MRI")], enabled=False)]),
    '("Joubert syndrome"[tiab] OR "molar tooth sign"[tiab])')
is_("senza niente dentro, niente query", qb.compose([]), "")

is_("(A OR B) e' gia' racchiuso", qb.is_wrapped("(A OR B)"), "True")
is_("(A) OR (B) NON e' racchiuso", qb.is_wrapped("(A) OR (B)"), "False")
is_("le virgolette dispari vengono segnalate",
    any("quotation" in m for m in
        qb.problems([qb.Block(terms=[qb.Term('"joubert')])])), "True")
is_("un NOT come primo blocco viene segnalato",
    any("NOT" in m for m in
        qb.problems([qb.Block(join="NOT", terms=[qb.Term("abscess")])])), "True")


# ---------------------------------------------------------------------------
# i filtri ISSG
# ---------------------------------------------------------------------------

print("\n--- filtri ISSG ---")

is_("i filtri sono quattro", len(issg.FILTERS), 4)
is_("senza scelte non si aggiunge niente", issg.clause([]), "")
is_("uno scelto e' racchiuso una volta sola",
    qb.is_wrapped(issg.clause(["guidelines_standard"])), "True")
is_("metanalisi e revisioni sistematiche sono la stessa stringa",
    issg.FILTERS["meta_analysis"][1] == issg.FILTERS["systematic_reviews"][1], "True")
is_("...e sceglierle tutt'e due non la ripete",
    issg.clause(["meta_analysis", "systematic_reviews"]),
    issg.clause(["meta_analysis"]))
# Il conteggio non si fa contando " OR (" nella stringa: le stringhe ISSG ne
# hanno decine al proprio interno. Si confronta con la forma attesa.
is_("due filtri diversi vanno in OR fra loro",
    issg.clause(["guidelines_broad", "meta_analysis"]),
    f"(({issg.GUIDELINES_BROAD}) OR ({issg.EVIDENCE_SYNTHESIS}))")
is_("si accettano anche le etichette della UI",
    issg.clause(["Guidelines — broad"]), issg.clause(["guidelines_broad"]))
for key, (label, text, _) in issg.FILTERS.items():
    is_(f"{key}: parentesi bilanciate", text.count("("), text.count(")"))
    is_(f"{key}: virgolette pari", text.count('"') % 2, 0)


# ---------------------------------------------------------------------------
# build_query
# ---------------------------------------------------------------------------

print("\n--- build_query ---")

TODAY = date(2026, 9, 2)
q = pubmed.build_query("abscess", type_labels=[], years=0, full_text=False,
                       english=False, humans=False, today=TODAY)
is_("i termini sono racchiusi", q, "(abscess)")

q = pubmed.build_query("(A) OR (B)", type_labels=[], years=0, full_text=False,
                       english=True, humans=False, today=TODAY)
is_("un OR di primo livello viene racchiuso prima del filtro",
    q, "((A) OR (B)) AND english[la]")

q = pubmed.build_query("(abscess)", type_labels=[], years=0, full_text=False,
                       english=False, humans=False, today=TODAY)
is_("chi e' gia' racchiuso non prende parentesi doppie", q, "(abscess)")

q = pubmed.build_query("abscess", type_labels=[], years=0, full_text=False,
                       english=False, humans=False, today=TODAY,
                       filters=[issg.clause(["guidelines_standard"])])
is_("il filtro ISSG entra in AND", q.startswith('(abscess) AND ("Guideline"[pt]'), "True")
is_("...e le parentesi restano bilanciate", q.count("("), q.count(")"))

q = pubmed.build_query("abscess", type_labels=[], years=0, full_text=False,
                       english=False, humans=False, today=TODAY, filters=[""])
is_("un filtro vuoto non aggiunge un AND a vuoto", q, "(abscess)")

q = pubmed.build_query("abscess", type_labels=[], years=10, full_text=False,
                       english=False, humans=False, today=TODAY)
is_("gli ultimi N anni partono dalla data giusta",
    '"2016/09/02"[Date - Publication]' in q, "True")

q = pubmed.build_query("abscess", type_labels=[], years=0, full_text=False,
                       english=True, humans=True, today=TODAY)
is_("humans toglie gli studi solo animali, in fondo e con NOT",
    q, "(abscess) AND english[la] NOT (animals[mh] NOT humans[mh])")
is_("...e le parentesi restano bilanciate", q.count("("), q.count(")"))

is_("il fascio delle review non contiene trial ne' libri",
    [t for t in pubmed.REVIEW_TYPE_LABELS
     if t in ("Books and Documents", "Clinical Trial, Phase IV", "Multicenter Study")], [])
is_("...e ogni tipo del fascio esiste nell'elenco",
    all(t in pubmed.DEFAULT_TYPE_LABELS for t in pubmed.REVIEW_TYPE_LABELS), "True")


# ---------------------------------------------------------------------------
# esearch: cosa e' un errore e cosa no
# ---------------------------------------------------------------------------
#
# Senza rete: una finta sessione che risponde quello che risponderebbe PubMed.
# Il caso vero da cui viene questa prova: la stringa ISSG per le linee guida
# contiene `chemotreatment*`, che in tutto MEDLINE non trova niente, e PubMed lo
# segnala ogni volta che la ricerca finisce a zero risultati.

print("\n--- esearch ---")


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload

    def get(self, url, params=None, timeout=None):
        return FakeResponse({"esearchresult": self.payload})


seen_warnings: list[str] = []
total, pmids, excluded = pubmed.esearch(
    "qualsiasi cosa",
    FakeSession({"count": "0", "idlist": [],
                 "errorlist": {"phrasesnotfound": ["chemotreatment*"],
                               "fieldsnotfound": []}}),
    {}, warn=seen_warnings.extend)
is_("una frase senza corrispondenze non fa fallire la ricerca", total, 0)
is_("...e viene riferita a chi ha chiamato", seen_warnings, "['chemotreatment*']")

try:
    pubmed.esearch(
        "qualsiasi cosa",
        FakeSession({"count": "0", "idlist": [],
                     "errorlist": {"phrasesnotfound": [], "fieldsnotfound": ["xy"]}}),
        {})
    is_("un campo inesistente invece solleva", "passato", "sollevato")
except pubmed.PubMedError as exc:
    is_("un campo inesistente invece solleva", "sollevato", "sollevato")
    is_("...dicendo quale", "xy" in str(exc), "True")

total, pmids, excluded = pubmed.esearch(
    "qualsiasi cosa",
    FakeSession({"count": "3", "idlist": ["1", "2", "3"]}),
    {}, exclude={"2"})
is_("i PMID gia' noti si scartano prima di scaricarli", pmids, "['1', '3']")
is_("...e si contano", excluded, 1)


class PagedSession:
    """Una PubMed con 25.000 risultati che, come quella vera, rifiuta di
    andare oltre il 9.999esimo."""

    def __init__(self):
        self.calls = []

    def get(self, url, params=None, timeout=None):
        start, size = params["retstart"], params["retmax"]
        self.calls.append((start, size))
        if start + size > pubmed.ESEARCH_CAP:
            raise AssertionError(f"retstart {start} + retmax {size} oltre il tetto")
        ids = [str(i) for i in range(start, min(start + size, 25000))]
        return FakeResponse({"esearchresult": {"count": "25000", "idlist": ids}})


paged = PagedSession()
total, pmids, excluded = pubmed.esearch("tutto", paged, {"_pause": 0}, max_results=0)
is_("senza limite si prende tutto quello che PubMed da'", len(pmids), pubmed.ESEARCH_CAP)
is_("...senza mai chiedere oltre il suo tetto", paged.calls[-1][0] + paged.calls[-1][1],
    pubmed.ESEARCH_CAP)
is_("...e il totale resta quello vero", total, 25000)
total, pmids, excluded = pubmed.esearch("tutto", PagedSession(), {"_pause": 0},
                                        max_results=700)
is_("un limite scelto vale ancora", len(pmids), 700)


# ---------------------------------------------------------------------------
# le strategie dai titoli
# ---------------------------------------------------------------------------

print("\n--- strategies ---")

is_("un titolo del canone ha la sua strategia", stg.has("Epidemiology"), "True")
is_("un titolo inventato no", stg.has("Fantasia"), "False")
is_("i sinonimi di structure valgono: 'etiology' e' 'Aetiology'",
    stg.terms_for("etiology") == stg.terms_for("Aetiology"), "True")
is_("'CT scan' e' 'CT'", stg.terms_for("CT scan") == stg.terms_for("CT"), "True")
is_("'x-ray' e' 'Plain radiograph'",
    stg.terms_for("x-ray") == stg.terms_for("Plain radiograph"), "True")

mesh = stg.terms_for("MRI", "mesh")
words = stg.terms_for("MRI", "keywords")
both = stg.terms_for("MRI", "both")
is_("solo MeSH da' solo vocabolario controllato",
    all("[Mesh]" in t or "[sh]" in t or "[pt]" in t for t in mesh), "True")
is_("solo keywords da' solo parole del testo",
    all("[tiab]" in t or "[ti]" in t or "[tw]" in t for t in words), "True")
is_("le due insieme sono l'unione", both, mesh + words)

frag = stg.fragment("Epidemiology")
is_("la strategia e' un blocco racchiuso", qb.is_wrapped(frag), "True")
is_("...e tiene i termini in OR", " OR " in frag, "True")
is_("un titolo senza strategia non ne inventa una", stg.fragment("Fantasia"), "")

pairs = stg.suggest(["MRI", "mri imaging", "Epidemiology", "See also"], "both")
is_("lo stesso titolo scritto due volte da' una strategia sola", len(pairs), 2)
is_("...nell'ordine dell'articolo", [n for n, _ in pairs], "['MRI', 'Epidemiology']")

bad = [t for name in stg.covered() for t in stg.terms_for(name)
       if "?" in t or t.count('"') % 2 or t.count("(") != t.count(")")]
is_("nessun termine con jolly Ovid o virgolette dispari", bad, [])

# Una virgola dimenticata fra due voci della lista non e' un errore di sintassi:
# Python le incolla, e resta un termine solo che a PubMed non trova niente. In un
# file di settecento righe scritto a mano e' la cosa piu' facile da fare e la
# piu' difficile da vedere. Un termine sano finisce con UN tag di campo e non ne
# ha altri in mezzo.
FIELD_TAG = __import__("re").compile(r"\[[A-Za-z][A-Za-z0-9 :,/._-]*\]")
merged = []
for name in stg.covered():
    for term in stg.terms_for(name):
        tags = FIELD_TAG.findall(term)
        if len(tags) != 1 or not term.rstrip().endswith("]"):
            merged.append((name, term))
is_("nessun termine con due tag di campo dentro (virgola dimenticata)",
    merged, [])

# Una strategia dev'essere componibile senza rompere la query che la ospita.
built = qb.compose([qb.Block(terms=[qb.Term("joubert syndrome")]),
                    qb.Block(terms=[qb.Term(stg.fragment("MRI"), "raw")])])
is_("una strategia entra in un blocco senza essere ritaggata",
    built.endswith(stg.fragment("MRI")), "True")


# ---------------------------------------------------------------------------
# le liste
# ---------------------------------------------------------------------------

print("\n--- liste ---")

db.insert_articles([
    {"pmid": "111", "title": "Uno", "abstract": "a"},
    {"pmid": "222", "title": "Due", "abstract": "b"},
    {"pmid": "333", "title": "Tre", "abstract": "c"},
])

first = db.create_list("Da leggere", "per il capitolo sulle complicanze")
is_("una lista nuova nasce", isinstance(first, int), "True")
is_("due liste non possono avere lo stesso nome", db.create_list("Da leggere"), None)
is_("una lista senza nome non nasce", db.create_list("   "), None)

second = db.create_list("Ottimi")
is_("aggiungere due articoli ne aggiunge due",
    db.add_to_list(first, ["111", "222"]), 2)
is_("riaggiungere lo stesso non lo raddoppia", db.add_to_list(first, ["111"]), 0)
is_("un articolo puo' stare in due liste", db.add_to_list(second, ["111"]), 1)
is_("la lista sa cosa contiene", db.list_pmids(first), "['111', '222']")
is_("e si sa in quali liste sta un articolo",
    sorted(n for _, n in db.lists_for(["111"])["111"]), "['Da leggere', 'Ottimi']")
is_("chi non e' in nessuna lista non compare", "333" in db.lists_for(["333"]), "False")

rows = {r["name"]: r for r in db.list_lists()}
is_("il conto degli articoli e' giusto", rows["Da leggere"]["n_items"], 2)
is_("e quello dei non letti pure", rows["Da leggere"]["n_unread"], 2)

db.set_status("111", "is_read", True)
rows = {r["name"]: r for r in db.list_lists()}
is_("un articolo letto scala i non letti", rows["Da leggere"]["n_unread"], 1)

is_("la pulizia all'avvio non tocca chi sta in una lista",
    db.cleanup_read_articles(), 0)
is_("...e infatti l'articolo e' ancora li'", db.list_pmids(first), "['111', '222']")
is_("...e nemmeno risulta gia' screenato", "111" in db.known_pmids("decided"), "True")

db.set_status("333", "is_read", True)
is_("chi non e' in nessuna lista invece viene tolto", db.cleanup_read_articles(), 1)

is_("rinominare funziona", db.rename_list(first, name="Da leggere subito"), "True")
is_("rinominare col nome di un'altra no", db.rename_list(first, name="Ottimi"), "False")
is_("...e il nome resta quello di prima",
    db.get_list(first)["name"], "Da leggere subito")
is_("la nota si cambia da sola", db.rename_list(first, note="nuova nota"), "True")
is_("...senza toccare il nome", db.get_list(first)["name"], "Da leggere subito")

db.remove_from_list(first, "222")
is_("togliere un articolo dalla lista lo toglie", db.list_pmids(first), "['111']")
is_("...ma lo lascia in archivio", "222" in db.known_pmids("db"), "True")

db.delete_list(first)
is_("la lista cancellata sparisce", db.get_list(first), None)
is_("...e non lascia righe orfane", db.lists_for(["111"]).get("111"),
    "[(%d, 'Ottimi')]" % second)
is_("...e l'articolo resta in archivio", "111" in db.known_pmids("db"), "True")

# ---------------------------------------------------------------------------
# le modalita' di imaging
# ---------------------------------------------------------------------------
print("\n--- modalita' di imaging ---")

is_("una modalita' c'e'", mod.has("CT"), "True")
is_("una inventata no", mod.has("Risonanza magnetica"), "False")

# Ogni modalita' in un gruppo e ogni gruppo di modalita' vere: senza questo, una
# voce aggiunta a MODALITIES e non messa in GROUPS non comparirebbe
# nell'interfaccia - `covered()` legge i gruppi - e non se ne accorgerebbe
# nessuno, perche' offline funziona tutto.
grouped = [n for names in mod.GROUPS.values() for n in names]
is_("ogni modalita' sta in un gruppo",
    sorted(set(mod.MODALITIES)) == sorted(set(grouped)), "True")
is_("...e nessuna in due gruppi", len(grouped), len(set(grouped)))
is_("l'elenco segue l'ordine dei gruppi", mod.covered(), grouped)
is_("ogni modalita' sa il suo gruppo",
    all(mod.group_of(n) for n in mod.covered()), "True")
is_("una inventata non ne ha uno", mod.group_of("Risonanza magnetica"), "")

mesh = mod.terms_for("Doppler ultrasound", "mesh")
words = mod.terms_for("Doppler ultrasound", "keywords")
both = mod.terms_for("Doppler ultrasound", "both")
is_("i termini mesh sono vocabolario controllato",
    all("[Mesh]" in x or "[sh]" in x or "[pt]" in x for x in mesh), "True")
is_("le keyword no", any("[Mesh]" in x for x in words), "False")
is_("le due insieme sono l'unione", both, mesh + words)
is_("una modalita' inventata non da' termini", mod.terms_for("Risonanza"), [])

# Il sottotitolo di modalita' e' la trappola che questo modulo esiste per
# evitare: il MeSH li ha fusi in `diagnostic imaging`, quindi `ultrasonography[sh]`
# non vuol dire ecografia, vuol dire imaging - e in una modalita' allarga invece
# di restringere. Ne resta uno solo, e solo dove e' quello che si vuole dire.
sh_terms = [(n, x) for n in mod.covered() for x in mod.terms_for(n, "mesh")
            if "[sh]" in x]
is_("il solo sottotitolo che resta e' 'diagnostic imaging' in 'Any imaging'",
    sh_terms, [("Any imaging (broad)", '"diagnostic imaging"[sh]')])
is_("...e i sottotitoli fusi non sono tornati in strategies",
    [n for n in stg.covered() for x in stg.terms_for(n, "mesh")
     if x in ("radiography[sh]", "ultrasonography[sh]",
              '"radionuclide imaging"[sh]')], [])

frag = mod.fragment("CT")
is_("un frammento e' racchiuso in parentesi",
    frag.startswith("(") and frag.endswith(")"), "True")
is_("una modalita' inventata non da' frammento", mod.fragment("Risonanza"), "")

two = mod.clause(["MRI", "MR perfusion"])
is_("piu' modalita' finiscono in un OR solo", two.count("(") - two.count(")"), 0)
is_("...senza doppioni",
    two.count('"Magnetic Resonance Imaging"[Mesh]'), 1)
is_("nessuna modalita' scelta non da' clausola", mod.clause([]), "")
is_("None nemmeno", mod.clause(None), "")
is_("una sola modalita' da' il suo frammento",
    mod.clause(["Elastography"]), mod.fragment("Elastography"))

bad = [x for n in mod.covered() for x in mod.terms_for(n)
       if "?" in x or x.count('"') % 2 or x.count("(") != x.count(")")]
is_("nessun termine con jolly Ovid o virgolette dispari", bad, [])

# La stessa virgola dimenticata di `strategies`: Python incolla due righe e
# resta un termine con due tag dentro, che a PubMed non trova niente.
merged = []
for name in mod.covered():
    for term in mod.terms_for(name):
        if len(FIELD_TAG.findall(term)) != 1 or not term.rstrip().endswith("]"):
            merged.append((name, term))
is_("nessun termine con due tag di campo dentro (virgola dimenticata)",
    merged, [])

built = qb.compose([qb.Block(terms=[qb.Term("pancreatic neoplasms")]),
                    qb.Block(terms=[qb.Term(mod.fragment("CT"), "raw")])])
is_("una modalita' entra in un blocco senza essere ritaggata",
    built.endswith(mod.fragment("CT")), "True")
is_("...e il blocco che la ospita resta bilanciato",
    built.count("(") == built.count(")"), "True")


# ---------------------------------------------------------------------------
# evidenziazione dei termini cercati
# ---------------------------------------------------------------------------

print("\n--- evidenziazione ---")

is_("frasi e parole, senza tag di campo ne' operatori",
    hl.terms_of('("brain abscess"[MeSH Terms] OR abscess[tiab]) AND MRI'),
    ["brain abscess", "abscess", "MRI"])
is_("quello che sta dopo NOT non si accende",
    hl.terms_of("glioma NOT (child* OR pediatric) NOT review[pt]"), ["glioma"])
is_("le parole di una lettera non contano", hl.terms_of("a OR b"), [])

rx = hl.pattern(hl.terms_of('"contrast enhanced" abscess child*'))
is_("plurale, trattino e asterisco",
    hl.mark("Contrast-enhanced scans of abscesses in children", rx),
    "<mark>Contrast-enhanced</mark> scans of <mark>abscesses</mark> in "
    "<mark>children</mark>")
is_("...solo a parola intera", hl.mark("preabscess", rx), "preabscess")
is_("...e l'HTML resta escapato, anche accanto a un termine",
    hl.mark("abscess <b> & co", rx), "<mark>abscess</mark> &lt;b&gt; &amp; co")
is_("senza termini si escapa e basta", hl.mark("a < b", None), "a &lt; b")

print(f"\n{checked} controlli, {failed} falliti")
sys.exit(1 if failed else 0)
