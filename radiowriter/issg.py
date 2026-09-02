"""I filtri di ricerca dell'ISSG (InterTASC Information Specialists' Sub-Group).

Sono le stringhe che gli information specialist usano per intercettare un TIPO
di lavoro invece di un argomento: linee guida, revisioni sistematiche,
metanalisi. Non dicono di cosa parla un articolo, dicono che genere di
articolo e'.

Vanno in AND con i termini della ricerca. Se se ne sceglie piu' d'uno si
uniscono in OR fra loro: chiedere insieme "linee guida" e "metanalisi"
significa volere l'uno O l'altro, non un lavoro che sia tutti e due.

NOTA: le stringhe qui sotto sono trascritte come fornite. Quella delle
metanalisi e quella delle revisioni sistematiche sono, parola per parola, la
stessa: nell'ISSG Search Filter Resource la voce copre entrambe le cose. Sono
tenute distinte perche' distinti sono i nomi con cui si cercano, e `clauses()`
toglie i doppioni prima di comporre la query - sceglierle tutt'e due non
raddoppia niente.
"""

from __future__ import annotations

GUIDELINES_BROAD = (
    '"Clinical protocols"[MESH] OR "Consensus"[MESH] OR "Consensus development '
    'conferences as topic"[MESH] OR "Critical pathways"[MESH] OR "Guidelines as topic" '
    '[Mesh:NoExp] OR "Practice guidelines as topic"[MESH] OR "Health planning '
    'guidelines"[MESH] OR "Clinical Decision Rules"[MESH] OR "guideline"[pt] OR '
    '"practice guideline"[pt] OR "consensus development conference"[pt] OR "consensus '
    'development conference, NIH"[pt] OR "position statement*"[tiab] OR "policy '
    'statement*"[tiab] OR "practice parameter*"[tiab] OR "best practice*"[tiab] OR '
    'standards[TI] OR guideline[TI] OR guidelines[TI] OR standards[ot] OR guideline[ot] '
    'OR guidelines[ot] OR guideline*[cn] OR standards[cn] OR consensus*[cn] OR '
    'recommendat*[cn] OR "practice guideline*"[tiab] OR "treatment guideline*"[tiab] OR '
    'CPG[tiab] OR CPGs[tiab] OR "clinical guideline*"[tiab] OR "guideline '
    'recommendation*"[tiab] OR consensus*[tiab] OR ((critical[tiab] OR clinical[tiab] OR '
    'practice[tiab]) AND (path[tiab] OR paths[tiab] OR pathway[tiab] OR pathways[tiab] OR '
    'protocol*[tiab] OR bulletin[tiab] OR bulletins[tiab])) OR recommendat*[ti] OR '
    'recommendat*[ot] OR (care[tiab] AND (standard[tiab] OR path[tiab] OR paths[tiab] OR '
    'pathway[tiab] OR pathways[tiab] OR map[tiab] OR maps[tiab] OR plan[tiab] OR '
    'plans[tiab])) OR (algorithm*[tiab] AND (screening[tiab] OR examination[tiab] OR '
    'test[tiab] OR tested[tiab] OR testing[tiab] OR assessment*[tiab] OR diagnosis[tiab] '
    'OR diagnoses[tiab] OR diagnosed[tiab] OR diagnosing[tiab])) OR (algorithm*[tiab] AND '
    '(pharmacotherap*[tiab] OR chemotherap*[tiab] OR chemotreatment*[tiab] OR therap*[tiab] '
    'OR treatment*[tiab] OR intervention*[tiab]))'
)

GUIDELINES_STANDARD = (
    '"Guideline"[pt] OR "practice guideline"[pt] OR "consensus development '
    'conference"[pt] OR "consensus development conference, NIH"[pt] OR guideline*[ti] OR '
    'standards[ti] OR consensus*[ti] OR recommendat*[ti] OR guideline*[cn] OR '
    'standards[cn] OR consensus*[cn] OR recommendat*[cn] OR "practice parameter*"[ti] OR '
    '"position statement*"[ti] OR "practice bulletin*"[ti] OR "policy statement*"[ti] OR '
    'CPG[ti] OR CPGs[ti] OR "best practice*"[ti] OR (care[ti] AND (path[ti] OR paths[ti] '
    'OR pathway[ti] OR pathways[ti] OR map[ti] OR maps[ti] OR plan[ti] OR plans[ti] OR '
    'standard[ti])) OR ((critical[ti] OR clinical[ti] OR practice[ti]) AND (path[ti] OR '
    'paths[ti] OR pathway[ti] OR pathways[ti] OR protocol*[ti])) OR (algorithm*[ti] AND '
    '(pharmacotherap*[ti] OR chemotherap*[ti] OR chemotreatment*[ti] OR therap*[ti] OR '
    'treatment*[ti] OR intervention*[ti])) OR (algorithm*[ti] AND (screening[ti] OR '
    'examination[ti] OR test[ti] OR tested[ti] OR testing[ti] OR assessment*[ti] OR '
    'diagnosis[ti] OR diagnoses[ti] OR diagnosed[ti] OR diagnosing[ti])) OR '
    'guideline*[ot] OR standards[ot] OR consensus*[ot] OR recommendat*[ot] OR "practice '
    'parameter*"[ot] OR "position statement*"[ot] OR "practice bulletin*"[ot] OR "policy '
    'statement*"[ot] OR CPG[ot] OR CPGs[ot] OR "best practice*"[ot] OR (care[ot] AND '
    '(path[ot] OR paths[ot] OR pathway[ot] OR pathways[ot] OR map[ot] OR maps[ot] OR '
    'plan[ot] OR plans[ot] OR standard[ot])) OR ((critical[ot] OR clinical[ot] OR '
    'practice[ot]) AND (path[ot] OR paths[ot] OR pathway[ot] OR pathways[ot] OR '
    'protocol*[ot])) OR (algorithm*[ot] AND (pharmacotherap*[ot] OR chemotherap*[ot] OR '
    'chemotreatment*[ot] OR therap*[ot] OR treatment*[ot] OR intervention*[ot])) OR '
    '(algorithm*[ot] AND (screening[ot] OR examination[ot] OR test[ot] OR tested[ot] OR '
    'testing[ot] OR assessment*[ot] OR diagnosis[ot] OR diagnoses[ot] OR diagnosed[ot] OR '
    'diagnosing[ot])) OR (("Systematic review"[ti] OR "systematic review"[pt] OR '
    '"systematic review"[ot]) AND ("practice guideline*"[tiab] OR "treatment '
    'guideline*"[tiab] OR "clinical guideline*"[tiab] OR "guideline recommendation*"[tiab]))'
)

# La voce che copre insieme metanalisi e revisioni sistematiche.
EVIDENCE_SYNTHESIS = (
    '"systematic"[filter] OR "meta-analysis"[pt] OR "meta-analysis as topic"[mh] OR "meta '
    'analy*"[tw] OR metanaly*[tw] OR metaanaly*[tw] OR "met analy*"[tw] OR "integrative '
    'research"[tiab] OR "integrative review*"[tiab] OR "integrative overview*"[tiab] OR '
    '"research integration*"[tiab] OR "research overview*"[tiab] OR "collaborative '
    'review*"[tiab] OR "collaborative overview*"[tiab] OR "systematic review"[pt] OR '
    '"systematic reviews as topic"[mh] OR "systematic review*"[tiab] OR "technology '
    'assessment*"[tiab] OR "technology overview*"[tiab] OR "technology appraisal*"[tiab] '
    'OR "Technology Assessment, Biomedical"[mh] OR HTA[tiab] OR HTAs[tiab] OR "comparative '
    'efficacy"[tiab] OR "comparative effectiveness"[tiab] OR "outcomes research"[tiab] OR '
    '"indirect comparison*"[tiab] OR "Bayesian comparison"[tiab] OR (("indirect '
    'treatment"[tiab] OR "mixed-treatment"[tiab]) AND comparison*[tiab]) OR Embase*[tiab] '
    'OR Cinahl*[tiab] OR "systematic overview*"[tiab] OR "methodological overview*"[tiab] '
    'OR "methodologic overview*"[tiab] OR "methodological review*"[tiab] OR "methodologic '
    'review*"[tiab] OR "quantitative review*"[tiab] OR "quantitative overview*"[tiab] OR '
    '"quantitative synthes*"[tiab] OR "pooled analy*"[tiab] OR Cochrane[tiab] OR '
    'Medline[tiab] OR Pubmed[tiab] OR Medlars[tiab] OR handsearch*[tiab] OR "hand '
    'search*"[tiab] OR "meta-regression*"[tiab] OR metaregression*[tiab] OR "data '
    'synthes*"[tiab] OR "data extraction"[tiab] OR "data abstraction*"[tiab] OR "mantel '
    'haenszel"[tiab] OR peto[tiab] OR "der-simonian"[tiab] OR dersimonian[tiab] OR "fixed '
    'effect*"[tiab] OR "multiple treatment comparison"[tiab] OR "mixed treatment '
    'meta-analys*"[tiab] OR "umbrella review*"[tiab] OR (("multiple paramet*"[tiab]) AND '
    '("evidence synthesis"[tiab])) OR (("multi-paramet*"[tiab]) AND ("evidence '
    'synthesis"[tiab])) OR ((multiparameter*[tiab]) AND ("evidence synthesis"[tiab])) OR '
    '"Cochrane Database Syst Rev"[Journal] OR "health technology assessment winchester, '
    'england"[Journal] OR "Evid Rep Technol Assess (Full Rep)"[Journal] OR "Evid Rep '
    'Technol Assess (Summ)"[Journal] OR "Int J Technol Assess Health Care"[Journal] OR '
    '"GMS Health Technol Assess"[Journal] OR "Health Technol Assess (Rockv)"[Journal] OR '
    '"Health Technol Assess Rep"[Journal]'
)

# chiave interna -> (etichetta nella UI, stringa, riga di aiuto)
FILTERS: dict[str, tuple[str, str, str]] = {
    "guidelines_broad": (
        "Guidelines — broad",
        GUIDELINES_BROAD,
        "Catches anything that reads like a recommendation: many results, "
        "much noise.",
    ),
    "guidelines_standard": (
        "Guidelines — standard",
        GUIDELINES_STANDARD,
        "The precise one: publication type and title, little noise.",
    ),
    "meta_analysis": (
        "Meta-analysis",
        EVIDENCE_SYNTHESIS,
        "Meta-analyses and quantitative syntheses.",
    ),
    "systematic_reviews": (
        "Systematic reviews",
        EVIDENCE_SYNTHESIS,
        "The same string as Meta-analysis: in the ISSG resource one entry "
        "covers both.",
    ),
}

LABELS = {key: label for key, (label, _, _) in FILTERS.items()}
BY_LABEL = {label: key for key, label in LABELS.items()}


def clause(names: list[str] | None) -> str:
    """La clausola unica da mettere in AND con i termini.

    I doppioni si tolgono: metanalisi e revisioni sistematiche sono la stessa
    stringa, e metterla due volte in OR con se stessa non cambia i risultati ma
    raddoppia una query che e' gia' lunga tremila caratteri.
    """
    seen: list[str] = []
    for name in names or []:
        key = name if name in FILTERS else BY_LABEL.get(name)
        if not key:
            continue
        text = FILTERS[key][1]
        if text not in seen:
            seen.append(text)
    if not seen:
        return ""
    if len(seen) == 1:
        return f"({seen[0]})"
    return "(" + " OR ".join(f"({s})" for s in seen) + ")"
