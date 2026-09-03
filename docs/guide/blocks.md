# Build a query in blocks

A serious search is not a string. It is two or three **concepts** — the disease,
the modality, the kind of study — each written in every way the literature
writes it, and joined with AND.

```
Block 1   "Joubert syndrome"[tiab] OR "molar tooth sign"[tiab]
Block 2   MRI[tiab] OR "magnetic resonance"[tiab]
──────────────────────────────────────────────────────────────
("Joubert syndrome"[tiab] OR "molar tooth sign"[tiab]) AND (MRI[tiab] OR …)
```

Inside a block, **OR**: any one of the wordings is enough. Between blocks,
**AND**: all of them must hold.

![Two concept blocks](/shots/02-blocks.png)

## The parts of a block

**＋ Another wording** adds a line. That is what it is for: *myocardial
infarction*, *MI*, *heart attack* are one concept written three ways, and a
paper that uses any of them should be found.

**The field** next to each line — Title/Abstract, MeSH terms, Publication type,
Author, Journal and the rest. Multi-word terms get their quotation marks
automatically. Anything you have already tagged yourself is left alone: paste
`"Brain Abscess"[Mesh]` and it stays exactly that.

**The operator** between blocks is AND by default; OR and NOT are there too. A
NOT block subtracts — a good way to drop case reports.

PubMed reads operators left to right and does not give AND precedence over OR.
Each block gets its own brackets for that reason, so what the preview shows is
what PubMed does.

## Terms from the Radiopaedia headings

The headings of an article are already the outline of the search. `Epidemiology`
means looking for prevalence and incidence; `Treatment and prognosis` means
therapy and survival; `MRI` means magnetic resonance.

Open **⌗ Terms from the Radiopaedia headings**, choose where the headings come
from — one of your drafts, or the structure Radiopaedia recommends for a kind
of article — and each heading becomes a piece of query:

| | |
|---|---|
| **MeSH only** | Controlled vocabulary: precise, but only reaches what MEDLINE has already indexed. A paper from three months ago is not in it yet. |
| **Keywords only** | Words in the title and abstract: catches the not-yet-indexed and the way authors actually write, at the price of some noise. |
| **MeSH + keywords** | Both. This is how a search-strategy block is normally built. |

127 headings have a strategy. The ones that do not — *See also*, *Practical
points* — are sections of an article rather than angles to search, and are not
offered.

They all go into **one** block, joined by OR. Putting them in separate blocks
would AND them together and ask PubMed for a paper that is about epidemiology
*and* MRI *and* prognosis at once, which is almost always nothing.

::: tip Every MeSH term is verified
The controlled-vocabulary terms were checked against the live PubMed API — a
descriptor that does not exist returns zero results forever without saying why.
`check_mesh_live.py` re-runs that check when MeSH changes, once a year.
:::
