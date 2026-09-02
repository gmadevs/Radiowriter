# Matching journals to SCImago

Two catalogues have to be joined: PubMed's records and SCImago's ranking. They
name journals differently — *Medicine* against *Medicine (United States)*,
*European journal of radiology* against *European Journal of Radiology*.

## By ISSN

The ISSN is the same number in both. On a real archive of 2,455 articles:

| | |
|---|---|
| matched by ISSN | 2,207 (90%) |
| matched by exact normalised title | 4 |
| **not matched** | **244 (10%)** |

The unmatched ten percent are not a failure of the matching. They are journals
SCImago does not list at all: Cureus alone is 111 of them, plus medRxiv,
*Experimental and Therapeutic Medicine*, and a long tail of case-report
journals. They get no quartile, which is the honest answer.

## Why not fuzzy titles

A suffix match on the title was tried. It raised the hit rate by about one
percent and matched *Radiology case reports* to *Journal of Radiology Case
Reports* — a different journal, with a different quartile. A wrong quartile is
worse than a missing one, because a missing one is visibly missing.

## The historical archive

Articles saved before ISSNs were stored have no ISSN column. They do have the
raw MEDLINE block, which the app has always kept in full, and the block has
`IS` lines. The backfill reads them from there and fills the column in on the
way past.

The same records have the abbreviation glued to the full title in their
`journal` field — `Eur J Radiol European journal of radiology` — because an
older version of the app wrote it that way. The raw block keeps `TA` and `JT`
apart, so the clean title is recovered from there too. The original value is
not overwritten.

## Verifying the strategies

Every MeSH descriptor and subheading used by `strategies.py` was checked
against the live PubMed API. A descriptor that does not exist does not return
zero results — PubMed reports it in `errorlist`, and the app used to treat that
as fatal. One typo would have made a whole search fail with a message about
syntax.

`check_mesh_live.py` re-runs the check. It is the only test that needs the
network, which is why it is not in the ordinary suite.
