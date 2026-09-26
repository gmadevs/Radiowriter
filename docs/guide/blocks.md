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

## Imaging modalities

The modality is one of the three concepts a search is made of, and it is the one
most often got wrong, because every technique has three or four names and nobody
uses all of them. Searching `ultrasound` loses the papers that say
*sonography*; searching `MRI` loses the ones that only write *magnetic
resonance*; and neither finds what is indexed under the MeSH descriptor and
never named in the abstract.

Open **🩻 Imaging modalities** and pick from the list. 43 modalities in nine
families — plain radiography and fluoroscopy, CT, MRI, ultrasound, nuclear
medicine, vascular and interventional, contrast studies, breast imaging, and the
across-modality ones. Each is written out in every form the literature uses:

| Pick | You get |
|---|---|
| **Doppler ultrasound** | three MeSH descriptors, plus `doppler`, `duplex ultraso*`, `power doppler`, both spellings of *colour*, and `resistive index` |
| **Transoesophageal echocardiography** | the descriptor, plus `transoesophageal`, `transesophageal`, `TOE` and `TEE` |
| **Cholangiography (ERCP, MRCP, PTC)** | three descriptors, plus `ERCP`, `MRCP`, `cholangiograph*` and `percutaneous transhepatic` |

The same three modes apply as for the headings, and they go into one block
joined by OR: picking CT and ultrasound means either one, not a paper that used
both. If you do want both, add two blocks — which is an explicit thing to do
rather than a surprise.

::: warning Short abbreviations are limited to the title
`US`, `MR` and `CT` on their own are ambiguous in an abstract: `US` matches every
paper that writes "US population", `MR` every "Mr Smith". Where the abbreviation
is too short to be safe it is restricted to the title with `[ti]`, and the
coverage is made up by the descriptor and the spelled-out forms.
:::

::: danger Why there are no modality subheadings
There is no `ultrasonography[sh]` here, and that is deliberate. MeSH merged
`radiography`, `ultrasonography` and `radionuclide imaging` into a single
subheading, `diagnostic imaging`, and PubMed maps the old names onto it — asked
one at a time they all return the same 1,665,656 records, and the difference
between any two of them is zero in both directions.

So `ultrasonography[sh]` does not mean ultrasound. It means *this paper involves
imaging*, and on its own it drags in 376,616 CT papers. It looks like it
narrows and it widens instead, which is the worst way for a query to be wrong.
The descriptors do separate properly, so only those are used.
`"diagnostic imaging"[sh]` is still there, but only under *Any imaging (broad)*,
where it says what it means.
:::
