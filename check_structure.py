#!/usr/bin/env python3
"""La struttura, provata su bozze scritte a mano.

    python3 check_structure.py

Mettere un titolo nel posto sbagliato e' uno sbaglio che non si vede: un
sottotitolo finito sotto la sezione sbagliata e' identico a uno finito sotto
quella giusta, e ci si accorge quando l'articolo e' pubblicato. Quello che si
fissa qui e' il piazzamento - che a deciderlo sia l'ordine del canone, che un
sottotitolo finisca in fondo alla propria sezione, e che una bozza con le
sezioni in disordine si veda mettere la nuova sopra tutte quelle che precede e
non sopra la prima che il canone nomina.
"""

from __future__ import annotations

import sys

from radiowriter import structure as sx

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


def rows(profile: str) -> dict[str, sx.Row]:
    return {r.entry: r for r in sx.rows_for(profile)}


def shape(md: str) -> str:
    """La bozza ridotta ai suoi titoli, per leggerla in un colpo d'occhio."""
    return " > ".join(f"{h.level}:{h.title}" for h in sx.headings_in(md))


STD = rows("disease")

# ---------------------------------------------------------------------------
# che tipo di articolo e'
# ---------------------------------------------------------------------------

is_("una malattia e' una malattia", sx.guess_profile("Cerebral abscess"), "disease")
is_("un osso e' anatomia", sx.guess_profile("Scaphoid bone"), "anatomy-bone")
is_("un nervo e' anatomia", sx.guess_profile("Median nerve"), "anatomy-nerve")
is_("un nervo che si e' rotto non lo e' piu'",
    sx.guess_profile("Median nerve injury"), "disease")
is_("una frattura prima di un osso", sx.guess_profile("Scaphoid fracture"), "fracture")
is_("un mnemonic prima di una malattia",
    sx.guess_profile("Tuberous sclerosis mnemonic"), "mnemonic")
is_("senza titolo si torna al ripiego", sx.guess_profile(""), "disease")

# ---------------------------------------------------------------------------
# cosa ha gia' la bozza
# ---------------------------------------------------------------------------

is_("un sottotitolo sa sotto cosa sta",
    shape("# Pathology\n\ntesto\n\n## Genetics\n\naltro\n"),
    "1:Pathology > 2:Genetics")

is_("un titolo scritto in altro modo viene riconosciuto lo stesso",
    sorted(sx.present_entries("# Aetiology and pathogenesis\n", "standard")),
    "['Aetiology']")

is_("le maiuscole non contano",
    sorted(sx.present_entries("# Radiographic Features\n", "standard")),
    "['Radiographic features']")

# ---------------------------------------------------------------------------
# il piazzamento
# ---------------------------------------------------------------------------

md = "# Epidemiology\n\nCommon.\n\n# Radiographic features\n\nBright.\n"
out, _ = sx.insert_rows(md, [STD["Clinical presentation"]], "standard")
is_("una sezione va sopra quella che il canone le mette dopo", shape(out),
    "1:Epidemiology > 1:Clinical presentation > 1:Radiographic features")

out, _ = sx.insert_rows("# Pathology\n\ntesto\n", [STD["Pathology/Genetics"]], "standard")
is_("un sottotitolo finisce in fondo alla propria sezione", shape(out),
    "1:Pathology > 2:Genetics")

out, _ = sx.insert_rows("# Epidemiology\n\ntesto\n", [STD["See also"]], "standard")
is_("l'ultima del canone va in fondo", shape(out),
    "1:Epidemiology > 1:See also")

out, _ = sx.insert_rows(
    "# Radiographic features\n\nBright.\n\n# Clinical presentation\n\nPain.\n",
    [STD["Epidemiology"]], "standard")
is_("in disordine, va sopra TUTTE quelle che precede", shape(out),
    "1:Epidemiology > 1:Radiographic features > 1:Clinical presentation")

out, _ = sx.insert_rows(
    "# Pathology\n\ntesto\n",
    [STD["Pathology/Macroscopic appearance"], STD["Pathology/Aetiology"]], "standard")
is_("due sottotitoli escono nell'ordine del canone", shape(out),
    "1:Pathology > 2:Aetiology > 2:Macroscopic appearance")

required = [r for r in sx.rows_for("disease") if r.required]
out, added = sx.insert_rows("", required, "standard")
is_("l'insieme obbligatorio di una malattia esce nell'ordine del canone", shape(out),
    "1:Epidemiology > 1:Clinical presentation > 1:Pathology > "
    "1:Radiographic features > 1:Treatment and prognosis > 1:Differential diagnosis")

out, _ = sx.insert_rows(
    "", [STD["Differential diagnosis"], STD["Epidemiology"],
         STD["Pathology/Genetics"], STD["Pathology"]], "standard")
is_("consegnate in disordine, escono nell'ordine del canone", shape(out),
    "1:Epidemiology > 1:Pathology > 2:Genetics > 1:Differential diagnosis")

out, _ = sx.insert_rows("", [STD["Epidemiology"]], "standard", pending=True)
is_("'content pending' va sotto il titolo quando lo si chiede",
    out.strip(), "# Epidemiology\n\ncontent pending")

# un canone che non e' quello standard
anat = rows("anatomy")
out, _ = sx.insert_rows("# Gross anatomy\n\ntesto\n",
                        [anat["Variant anatomy"]], "anatomy")
is_("l'anatomia usa il proprio canone", shape(out),
    "1:Gross anatomy > 1:Variant anatomy")

# ---------------------------------------------------------------------------
# uno dove dico io
# ---------------------------------------------------------------------------

md = "# Epidemiology\n\nCommon.\n\n# Pathology\n\nGliotic.\n"
p = sx.check_one(md, STD["Pathology/Microscopic appearance"], 3, "standard")
is_("il cursore nella sezione sbagliata viene segnalato", bool(p.conflict), "True")
is_("...e dice in quale sezione e' finito", p.inside, "Epidemiology")

p2 = sx.check_one(md, STD["Pathology/Microscopic appearance"], 7, "standard")
is_("il cursore nella sezione giusta non viene segnalato", p2.conflict, "None")

out = sx.insert_at(md, STD["Pathology/Microscopic appearance"], p.canon_line)
is_("messo dove dice la struttura, finisce sotto il proprio genitore", shape(out),
    "1:Epidemiology > 1:Pathology > 2:Microscopic appearance")

out = sx.insert_at(md, STD["Pathology/Microscopic appearance"], 3)
is_("messo dove dice l'utente, finisce dove dice l'utente", shape(out),
    "1:Epidemiology > 2:Microscopic appearance > 1:Pathology")

print(f"\n{checked} controlli, {failed} falliti")
sys.exit(1 if failed else 0)
