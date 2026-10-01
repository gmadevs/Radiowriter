# Journal quartiles and open access

## Journal quartiles and SJR

Quartiles and SJR come from SCImago. A copy of the 2025 table is included, so
they need no setup. To use a newer table, see
[Install](/guide/install#journal-quartiles).

::: danger These metrics are not the Journal Impact Factor
The Impact Factor is published by Clarivate in the Journal Citation Reports.
It is not in the SCImago file and the app does not show it.

SCImago gives two different metrics:

- **SJR** weights each citation by the rank of the journal it comes from, so
  a citation from a highly ranked journal counts more. The quartiles are
  based on SJR.
- **Cites/doc (2y)** is the mean number of citations per paper over the last
  two years. It is calculated like an impact factor, but on Scopus data and
  not on Web of Science data, so the values differ from the Impact Factor.

The app shows both, each with its label.
:::

The quartile badge is green for Q1 and red for Q4. It shows the best quartile
the journal has in any of its SCImago categories. The line under the badges
lists every category with its quartile. For example, a journal can be Q1 in
*Medicine (miscellaneous)* and Q3 in *Radiology*.

### Journals without a quartile

About one article in ten has no quartile, because its journal is not in the
SCImago file. Examples are Cureus, medRxiv and most case-report journals.
These articles show no quartile badge. In the filters they are under
*Not in SCImago*.

### How articles are matched to journals {#matching-is-by-issn}

Articles are matched to SCImago journals by ISSN. PubMed and SCImago often
write the name of the same journal differently, for example *Medicine* and
*Medicine (United States)*, but the ISSN is the same in both.

In the archive this was tested on, the ISSN matched about nine articles in
ten. An article with no ISSN match is then matched by exact journal title,
which adds a few more. Approximate title matching is not used: it would add
about 1% more matches and could give an article the quartile of a different
journal with a similar name.

For articles saved before the app stored ISSNs, the ISSN is read from the
MEDLINE record, which is stored in full for every article.

## Open access

Unpaywall reports whether a paper has a legal free copy, and where it is.
LibKey is a different service: it opens the copy your library subscribes to.

| Status | Meaning |
|---|---|
| **gold** | The journal is fully open access |
| **hybrid** | A subscription journal in which this paper was made open access for a fee |
| **green** | A copy is in a repository or in PubMed Central |
| **bronze** | Free to read on the publisher's site, with no licence. The publisher can withdraw access. |
| **closed** | No free copy |

There are two ways to look it up:

- in the Screening tab, click **🔓 Check open access for N articles on this
  page**;
- tick **Open access (Unpaywall)** in the sidebar before a search, so that
  new records are checked as they are downloaded.

The app makes one request per DOI, at about 10 requests a second. Articles
without a DOI are not checked.
