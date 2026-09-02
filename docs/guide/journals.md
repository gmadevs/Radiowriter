# Journal quartiles and open access

## Where a paper was published

Quartiles and SJR come from the SCImago file you dropped in the data folder —
see [Install](/guide/install#journal-quartiles).

::: danger This is not the Journal Impact Factor
The impact factor is Clarivate's and lives in the Journal Citation Reports,
which is a different product and is not in any file here.

SCImago gives two numbers, and they are two different things:

- **SJR** — how much regard the journal is held in. It does not count
  citations, it weighs them: a citation from *Radiology* is worth more than one
  from a journal nobody reads. This is what the quartiles are built on.
- **Cites/doc (2y)** — mean citations per paper over the last two years.
  Computed the way an impact factor is computed, but over Scopus rather than
  Web of Science, so the numbers are not the same ones.

Both are shown, both are labelled.
:::

The badge is green for Q1 through red for Q4. The quartile in the badge is the
**best** the journal holds in any of its categories; the line underneath breaks
it down, which for a radiologist often says more — Q1 in *Medicine
(miscellaneous)* and Q3 in *Radiology* are two different facts.

### About one in ten has no quartile

Because its journal is not in SCImago at all. Cureus, medRxiv, most
case-report journals. Those show no badge rather than a grey one: a missing
number and a poor number are different, and the display should not blur them.

### Matching is by ISSN

Not by title. What PubMed calls a journal and what SCImago calls it are often
the same journal written two ways — *Medicine* against *Medicine (United
States)* — while the ISSN is the same number for both. On a real archive the
ISSN matches nine articles in ten, exactly; an exact title match adds a
handful. Fuzzy title matching would add another percent and would occasionally
hand an article the quartile of a different journal with a similar name.

Articles saved before ISSNs were stored are matched from the raw MEDLINE block,
which has always been kept in full.

## Open access

Unpaywall says whether a paper has a legally free copy, and where. It is not
the same thing as LibKey: LibKey goes through what your library pays for,
Unpaywall finds what anyone can open.

| | |
|---|---|
| **gold** | The journal is fully open; the paper was born free |
| **hybrid** | Paywalled journal, this paper was released — someone paid |
| **green** | A copy sits in a repository or in PubMed Central |
| **bronze** | Readable on the publisher's site with no licence: free today, maybe not tomorrow |
| **closed** | Nothing |

Ask for it a page at a time from the Screening tab, or tick *Open access
(Unpaywall)* in the sidebar so searches arrive with it already looked up. One
call per DOI, about ten a second.
