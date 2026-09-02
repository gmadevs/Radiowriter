#!/usr/bin/env python3
"""Le regole del linter, provate su prosa scritta apposta per farle scattare.

    python3 check_rules.py

`data/lint-rules.json` e' una trascrizione battuta a mano, e ognuno dei suoi
duecentosessanta pattern e' un'occasione per aver sbagliato una barra rovescia.
Un pattern che non compila lo si scopre al caricamento e costa la propria
regola e nient'altro; un pattern che compila e non becca NIENTE non lo scopre
nessuno, ed e' quello il guasto che vale un test: una regola che ha smesso di
scattare e' indistinguibile da un articolo senza niente che non va.

`raises` dice che una regola DEVE scattare su questo markup; `quiet` dice che
non deve. I casi `quiet` si guadagnano il posto due volte: una regola che
scatta su tutto passa ogni `raises` di questo file ed e' comunque inutile.
"""

from __future__ import annotations

import sys

from radiowriter import lint

RULES = lint.rules()
PRINTED = {r.name: r.check for r in RULES}

checked = 0
failed = 0


def _run(rule: str, html: str) -> list[lint.Finding]:
    if rule not in PRINTED:
        raise SystemExit(f"non esiste nessuna regola {rule} in lint-rules.json")
    return lint.lint_html(html, compiled=RULES)


def raises(rule: str, html: str, why: str = "") -> None:
    global checked, failed
    checked += 1
    found = _run(rule, html)
    if any(f.check == PRINTED[rule] for f in found):
        return
    failed += 1
    print(f"FAIL  {rule} non e' scattata su {html!r}" + (f" - {why}" if why else ""))
    others = sorted({f.check for f in found})
    if others:
        print(f"      (cosa e' scattato: {', '.join(others)})")


def quiet(rule: str, html: str, why: str = "") -> None:
    global checked, failed
    checked += 1
    hit = next((f for f in _run(rule, html) if f.check == PRINTED[rule]), None)
    if hit is None:
        return
    failed += 1
    print(f"FAIL  {rule} e' scattata su {html!r}" + (f" - {why}" if why else ""))
    print(f"      {hit.message}")


p = lambda s: f"<p>{s}</p>"          # noqa: E731
li = lambda s: f"<ul><li>{s}</li></ul>"   # noqa: E731
h = lambda s: f"<h4>{s}</h4>"        # noqa: E731

# ---------------------------------------------------------------------------
# errori
# ---------------------------------------------------------------------------

raises("AMPM", p("The scan was at 4PM on the ward."))
quiet("AMPM", p("The scan was at 4 PM on the ward."))

raises("AdjectivalHyphens", p("A trans-abdominal approach was used."))
quiet("AdjectivalHyphens", p("A trans-sphenoidal approach was used."))
quiet("AdjectivalHyphens", p("The post-contrast images were normal."), "eccezione")

raises("ApproximationSpacing", p("The lesion measured ~ 15 mm."))
quiet("ApproximationSpacing", p("The lesion measured ~15 mm."))

raises("BetweenAnd", p("It occurs between 3 to 5 years of age."))
quiet("BetweenAnd", p("It occurs between 3 and 5 years of age."))

raises("BiographicalDatePosition", p("<strong>Wilhelm Roentgen (1845-1923)</strong> described it."))
raises("BiographicalDateSpacing", p("<strong>Wilhelm Roentgen</strong>(1845-1923) described it."))
raises("BiographicalName", p("<strong>Wilhelm C Roentgen</strong> (1845-1923) described it."))

raises("CeleSuffix", p("A large meningocoele was seen."))
quiet("CeleSuffix", p("A large meningocele was seen."))

raises("CitationOrder", p("First point <sup>3</sup> and second <sup>1</sup>."))
quiet("CitationOrder", p("First point <sup>1</sup> and second <sup>2</sup>."))

raises("CitationSyntax", p("Widely reported <sup>1,2,3</sup>."), "tre di fila vogliono il trattino")
raises("CitationSyntax", p("Widely reported <sup>1-2</sup>."), "due vogliono la virgola")
quiet("CitationSyntax", p("Widely reported <sup>1-3</sup>."))
quiet("CitationSyntax", p("Widely reported <sup>1,2</sup>."))

raises("CitationPrecedingSpace", p("It needs evidence<sup>2</sup>."))
quiet("CitationPrecedingSpace", p("The lesion was 5 mm<sup>2</sup>."), "un'unita', non una citazione")
raises("CitationPunctuationSpace", p("It needs evidence <sup>2</sup> ."))
raises("CitationPunctuationSup", p("It needs evidence <sup>2.</sup>"))

raises("ColonSpacing", p("The findings were as follows : oedema."))
quiet("ColonSpacing", p("The findings were as follows: oedema."))
quiet("ColonSpacing", p("The albumin:globulin ratio was raised."), "un rapporto")

raises("Contractions", p("It doesn't enhance after contrast."))
quiet("Contractions", p("It does not enhance after contrast."))

raises("DateFormat", p("It was described on January 1st, 2020 in the journal."))
quiet("DateFormat", p("It was described on 1 January 2020 in the journal."))

raises("EmDash", p("The lesion — a large one — was resected."))
raises("EnDash", p("The lesion – a large one – was resected."))

raises("Exclamation", p("This is a classic appearance!"))
raises("FetusSpelling", p("The foetus was normal."))
quiet("FetusSpelling", p("The fetus was normal."))

raises("HeadingCitation", h("Radiographic features <sup>2</sup>"))
raises("HeadingPunctuation", h("Radiographic features:"))
quiet("HeadingPunctuation", h("Radiographic features"))

raises("HeadingsSpacing", "<h4> Radiographic features</h4>")
raises("HybridImagingSlash", p("A PET/CT was performed."))
quiet("HybridImagingSlash", p("A PET-CT was performed."))

raises("IsotopeNotation", p("Imaging used 18F labelled tracer."))
quiet("IsotopeNotation", p("Imaging used F-18 labelled tracer."))

raises("LinkPlacement", p('<strong>See the <a href="/x">article</a></strong> for more.'))
raises("LinkPlacement", h('See the <a href="/x">article</a>'))

raises("ListPunctuation", li("oedema of the white matter."))
quiet("ListPunctuation", li("oedema of the white matter"))
quiet("ListPunctuation", li("oedema, mass effect, etc."), "eccezione")

raises("MedicalMisspellings", p("The azygous vein was dilated."))
quiet("MedicalMisspellings", p("The azygos vein was dilated."))

raises("NumberComparisons", p("Lesions were &gt; 5 mm across."))
quiet("NumberComparisons", p("Lesions were &gt;5 mm across."))

raises("NumberSpacing", p("The range was 10 - 20 mm."))
quiet("NumberSpacing", p("The range was 10-20 mm."))

raises("OptionalPlurals", p("The lesion(s) were resected."))
raises("Periods", p("It was reported by the R.C.R. committee."))
raises("Quotes", p('It is called a "target sign."'))

raises("So", p("So the lesion was resected."))
quiet("So", p("The lesion was therefore resected."))

raises("Spacing", p("It was resected.The patient recovered."))
raises("SpinalLevelSpacing", p("The disc at T4 - 5 was degenerate."))
quiet("SpinalLevelSpacing", p("The disc at T4-5 was degenerate."))

raises("StrongListColonPosition", li("<strong>appearance:</strong> hyperdense"))
raises("SulfurSpelling", p("Barium sulphate was given."))
quiet("SulfurSpelling", p("Barium sulfate was given."))

raises("Uncomparables", p("This is the most complete resection."))
quiet("Uncomparables", p("This is a complete resection."))

raises("Units", p("The lesion was 15mm across."))
quiet("Units", p("The lesion was 15 mm across."))
quiet("Units", p("Imaging used Tc-99m labelled tracer."), "eccezione")

raises("WordsWeNeverUse", p("Motion artefact obscured the study."))
quiet("WordsWeNeverUse", p("Motion artifact obscured the study."))

# ---------------------------------------------------------------------------
# warning
# ---------------------------------------------------------------------------

raises("AcceptedAbbreviations", p("The xray showed no fracture."))
quiet("AcceptedAbbreviations", p("The radiograph showed no fracture."))

raises("Acronyms", p("The PRES was extensive on imaging."))
quiet("Acronyms", p("Posterior reversible encephalopathy syndrome (PRES) was extensive. The PRES resolved."))
quiet("Acronyms", p("ADEM (acute disseminated encephalomyelitis) is demyelinating. ADEM is rare."),
      "la E e la M escono tutt'e due da una parola composta")
quiet("Acronyms", p("The CT and the MRI both showed a T2 hyperintense lesion."),
      "nessuno le scrive per esteso")

raises("Ampersand", p("The head &amp; body were imaged."))
quiet("Ampersand", p("The head and body were imaged."))
quiet("Ampersand", p("Staining with H&amp;E was performed."), "eccezione")
quiet("Ampersand", p("Imaging of the head &amp; neck was performed."), "eccezione")

raises("Colons", p("The findings were: Oedema was present."))
quiet("Colons", p("The findings were: oedema was present."))
quiet("Colons", p("The findings were: CT showed oedema."), "eccezione")

raises("DiscSpelling", p("The disk was degenerate."))
quiet("DiscSpelling", p("The disc was degenerate."))

raises("EGListAnd", p("Several causes, e.g. trauma, infection and tumour, are known."))
raises("Ellipses", p("The appearance is classic..."))

raises("Emphasis", p("The lesion was <em>very</em> large."))
quiet("Emphasis", p("The <em>KRAS</em> status was known."), "eccezione")
quiet("Emphasis", p("The <em>TP53</em> gene was mutated."), "i geni sono ammessi")

raises("EponymApostrophe", p("Down's syndrome was diagnosed."))
quiet("EponymApostrophe", p("Down syndrome was diagnosed."))

raises("GreaterLessThanEqualTo", p("Lesions were &lt;= 5 mm across."))
quiet("GreaterLessThanEqualTo", p("Lesions were ≤ 5 mm across."))

raises("GreySpelling", p("The gray matter was spared."))
quiet("GreySpelling", p("The grey matter was spared."))
quiet("GreySpelling", p("A dose of 50 gray was given."), "l'unita', dopo un numero")

raises("HeadingsCase", h("Radiographic Features"))
quiet("HeadingsCase", h("Radiographic features"))
quiet("HeadingsCase", h("Findings on CT"), "eccezione")

raises("HeterogeneousSpelling", p("The mass was heterogenous."))
quiet("HeterogeneousSpelling", p("The mass was heterogeneous."))

raises("Illusions", p("The the lesion was resected."))
quiet("Illusions", p("The lesion was resected."))

raises("Latin", p("It is caused by trauma, eg. a fall."))
raises("ListCaps", li("Oedema of the white matter"))
quiet("ListCaps", li("oedema of the white matter"))
quiet("ListCaps", li("MRI of the white matter"), "un acronimo")
quiet("ListCaps", li("Down syndrome"), "eccezione")

raises("Litotes", p("The effect was not small."))
raises("NumberFormatting", p("The ratio was .75 overall."))
quiet("NumberFormatting", p("The ratio was 0.75 overall."))

raises("NumbersOver10000", p("There were 25000 cases."))
quiet("NumbersOver10000", p("There were 25,000 cases."))

raises("OrganismNotation", p("Caused by <em>Mycobacterium Tuberculosis</em> infection."))
raises("Pending", p("Content pending"))

raises("PersonalNames", p("Described by Dr. Player in the journal."))
quiet("PersonalNames", p("Described by Dr Player in the journal."))

raises("PrefixHyphens", p("An extra-medullary lesion was seen."))
quiet("PrefixHyphens", p("An extra-axial lesion was seen."))
quiet("PrefixHyphens", p("An extramedullary lesion was seen."))

raises("Ranges", p("It occurs from 3-5 years of age."))
raises("SpinalLevelFormat", p("The disc at T2-T3 was degenerate."))
quiet("SpinalLevelFormat", p("The disc at T2-3 was degenerate."))

raises("Strong", p("The lesion is common.") + p("It is <strong>always</strong> bright."))
quiet("Strong", p("First.") + li("<strong>appearance</strong>: hyperdense"),
      "l'attacco di una voce di elenco")

raises("UnitCapitalisation", p("Imaging at 3 Tesla was performed."))
quiet("UnitCapitalisation", p("Imaging at 3 tesla was performed."))

# ---------------------------------------------------------------------------
# suggerimenti
# ---------------------------------------------------------------------------

raises("BiographicalLifespan",
       "<h4>History and etymology</h4>" + p("Described by <strong>Wilhelm Roentgen</strong> in 1895."))

raises("Commas", p("It is seen in the brain, the cord, the nerves, the eyes, "
                   "the ears, the nose, and the ears."))
quiet("Commas", p("It is seen in the brain and the cord."))

raises("HiddenSpace", p("The lesion was&nbsp;large."))
raises("InlineEG", p("It has several causes (e.g. trauma and infection)"))

raises("MRIVendorSequences", p("A FISP sequence was acquired."))
raises("OxfordComma", p("The opacity was patchy, reticulonodular or mixed."))
quiet("OxfordComma", p("The opacity was patchy, reticulonodular, or mixed."))

raises("Parentheses", p("The lesion (large) was resected (fully) without "
                        "complication (none) at surgery (open)."))
quiet("Parentheses", p("The lesion (large) was resected (fully)."))

raises("Recency", p("A recent study showed benefit."))
quiet("Recency", p("A 2019 study showed benefit."))
quiet("Recency", p("A recent infarct was seen."), "la recenza clinica e' un reperto")

raises("Semicolons", p("It was large; it was resected."))
raises("ThereIs", p("There is a large lesion."))
quiet("ThereIs", p("A large lesion is present."))

print(f"\n{checked} controlli, {failed} falliti")
sys.exit(1 if failed else 0)
