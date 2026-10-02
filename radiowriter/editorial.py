"""La letteratura recente per un gruppo editoriale di Radiopaedia.

Un gruppo editoriale (CNS, e poi gli altri) non si descrive con dei termini di
ricerca ma con delle riviste: quelle dove esce cio' che un editor di quel
gruppo dovrebbe aver visto. Le riviste si prendono dal file SCImago gia'
caricato, e la ricerca chiede a PubMed le revisioni e le linee guida entrate
in quelle riviste dall'ultima volta.

Un gruppo e' fatto di ANELLI. Ogni anello sceglie delle riviste e puo' avere
un filtro di argomento:

    - le riviste del mestiere (neuroradiologia, colonna), per titolo;
    - quelle di radiologia generale, per categoria;
    - quelle di neurologia clinica, per categoria.

Per il CNS si prendono tutte intere: le sfoltisce chi fa lo screening. Il
filtro di argomento resta a disposizione dei gruppi che verranno - a un gruppo
che pesca da riviste generaliste puo' servire.

SCImago non ha una categoria "neuroradiologia" ne' una "colonna": quelle
riviste si riconoscono dal titolo. Le altre dalla categoria, e solo se in
QUELLA categoria sono Q1 - il quartile della rivista e' il migliore fra le sue
categorie, e una rivista Q1 in oncologia puo' essere Q3 in radiologia.

Qui non c'e' ne' rete ne' Streamlit: si compone la query e si fanno i conti
sulle date. A PubMed la manda `pubmed.esearch`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from radiowriter import issg
from radiowriter import journals as jr

# La prima volta, quanto indietro.
FIRST_RUN_DAYS = 30

# Le volte dopo si riparte da qualche giorno PRIMA dell'ultima. Un record
# appena entrato in PubMed spesso non ha ancora il tipo di pubblicazione
# ("Review" arriva con l'indicizzazione): con le date a filo, quello che oggi
# non risulta una revisione domani lo sarebbe, ma fuori dalla finestra. I
# doppioni non costano niente, perche' i PMID gia' noti si saltano.
OVERLAP_DAYS = 7

# Revisioni, sistematiche e no, e metanalisi: i tipi di PubMed. `systematic[sb]`
# e' il filtro di PubMed per le sistematiche, e funziona sul testo: prende
# anche quelle non ancora indicizzate.
REVIEW_TYPES = ('(Review[pt] OR "Systematic Review"[pt] OR "Meta-Analysis"[pt] '
                'OR systematic[sb])')

@dataclass(frozen=True)
class Ring:
    """Un insieme di riviste, e l'eventuale filtro di argomento.

    `category` + Q1 in quella categoria, oppure `title_words` + uno dei
    `quartiles` (il migliore della rivista)."""
    name: str
    category: str = ""
    title_words: tuple[str, ...] = ()
    quartiles: tuple[str, ...] = ("Q1",)
    topic: str = ""


@dataclass(frozen=True)
class Group:
    key: str
    label: str
    rings: tuple[Ring, ...] = field(default_factory=tuple)

    @property
    def list_name(self) -> str:
        """La lista di lettura in cui finisce quello che si scarica."""
        return f"Editorial group: {self.label}"


GROUPS: dict[str, Group] = {
    "cns": Group("cns", "CNS", (
        Ring("Neuroradiology, neuroimaging and spine journals",
             title_words=("neuroradiol", "neuroimag", "spine", "spinal"),
             quartiles=("Q1", "Q2")),
        Ring("Radiology journals",
             category="Radiology, Nuclear Medicine and Imaging"),
        Ring("Neurology journals", category="Neurology (clinical)"),
    )),
}


def _in_ring(journal: dict, ring: Ring) -> bool:
    if ring.title_words:
        title = (journal.get("title") or "").lower()
        return (journal.get("quartile") in ring.quartiles
                and any(w in title for w in ring.title_words))
    return any(name == ring.category and q in ring.quartiles
               for name, q in jr.categories_of(journal.get("categories") or ""))


def journals_of(group: Group, journals: list[dict]) -> list[tuple[Ring, list[dict]]]:
    """Le riviste di ogni anello, ognuna in un anello solo: il primo che la
    prende. L'ordine degli anelli conta quando uno ha un filtro di argomento:
    una rivista presa intera da un anello non deve finire anche sotto il
    filtro di un altro."""
    taken: set[int] = set()
    out = []
    for ring in group.rings:
        mine = [j for j in journals
                if j["id"] not in taken and j.get("issns") and _in_ring(j, ring)]
        taken.update(j["id"] for j in mine)
        mine.sort(key=lambda j: -(j.get("sjr") or 0))
        out.append((ring, mine))
    return out


def _issn(code: str) -> str:
    """`2296858X` -> `"2296-858X"[IS]`: PubMed li vuole col trattino."""
    return f'"{code[:4]}-{code[4:]}"[IS]'


def journal_clause(rings: list[tuple[Ring, list[dict]]]) -> str:
    """Le riviste, anello per anello, ognuno col proprio filtro di argomento."""
    parts = []
    for ring, journals in rings:
        codes = sorted({i for j in journals for i in j["issns"] if len(i) == 8})
        if not codes:
            continue
        issns = "(" + " OR ".join(_issn(c) for c in codes) + ")"
        parts.append(f"({issns} AND {ring.topic})" if ring.topic else issns)
    return "(" + " OR ".join(parts) + ")" if parts else ""


def since_for(last_run: str | None, today: date | None = None) -> date:
    """Da che giorno cercare: un mese fa la prima volta, poi dall'ultima
    esecuzione meno la sovrapposizione."""
    today = today or date.today()
    try:
        last = date.fromisoformat((last_run or "")[:10])
    except ValueError:
        return today - timedelta(days=FIRST_RUN_DAYS)
    return min(last, today) - timedelta(days=OVERLAP_DAYS)


def date_clause(since: date) -> str:
    """Per data di INGRESSO in PubMed (`edat`), non di pubblicazione: un
    articolo datato al mese prossimo o caricato in ritardo ha una data di
    pubblicazione che non dice quando lo si poteva trovare."""
    return f'("{since:%Y/%m/%d}"[edat] : "3000"[edat])'


def build_query(group: Group, journals: list[dict], since: date) -> str:
    """La query intera, o '' se nel file delle riviste non c'e' niente per
    questo gruppo."""
    where = journal_clause(journals_of(group, journals))
    if not where:
        return ""
    kinds = f"({REVIEW_TYPES} OR {issg.clause(['guidelines_standard'])})"
    return f"{where} AND {kinds} AND english[la] AND {date_clause(since)}"


def setting_key(group: Group) -> str:
    """Dove sta scritta, nelle impostazioni, la data dell'ultima esecuzione."""
    return f"recent_last_{group.key}"
