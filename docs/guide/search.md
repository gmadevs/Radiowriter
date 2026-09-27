# Search PubMed

Two ways in, chosen with the pills at the top: **One line** takes PubMed syntax
as you write it, **Blocks** builds the query a concept at a time. Blocks has
[its own page](/guide/blocks).

![The search tab](/shots/01-search.png)

## The filters

They sit in a panel that is always open, because a filter you cannot see is a
filter you forget.

### Recent reviews, No filters, Custom

One control with three positions sits at the top of the panel.

- **★ Recent reviews** sets the last 10 years, full text, English, humans, and
  the publication types NLM uses for reviews and syntheses: Review, Systematic
  Review, Scoping Review, Meta-Analysis, Network Meta-Analysis, Evidence
  Synthesis, Guideline, Practice Guideline, Consensus Statement.
- **No filters** turns everything off, date limit included. Only the search
  terms go to PubMed.
- **Custom** is where it moves by itself as soon as you change a control by
  hand. Put everything back as a preset had it and it returns to that preset.

The position is worked out from the values of the controls, so it cannot say
one thing while the query does another. The line under the controls is written
from the same values and says what the query will ask.

### Last N years

**0 means no date limit at all.** Not fifty years, not a hundred: none.

### Humans

This filter leaves out what is indexed as an animal study and not as a human
one: `NOT (animals[mh] NOT humans[mh])`. Asking for `humans[mh]` instead would
also drop every paper NLM has not indexed yet, which means most of the last few
months.

### Kind of publication

Choose one way of asking for it, or none:

- **Publication type (NLM)**: the labels an NLM indexer gave the record.
- **Search filter (ISSG)**: published search filters from the InterTASC
  Information Specialists' Sub-Group. They catch a kind of publication by the
  words it uses, not a subject. Four are available: guidelines broad,
  guidelines standard, meta-analysis and systematic reviews.

You cannot use both at once. They would be joined with AND, and only what
satisfies both would survive, which is usually far fewer results than you
meant. Several choices inside one method are joined with OR. The choice you
made in the other method is kept for when you switch back.

## In the sidebar

Four things are settings rather than filters, so they live in the sidebar and
stay put: how many records to download, what to skip because it is already
known, and whether to enrich with Semantic Scholar and Unpaywall.

## Filtering the results

Once results are in, **⚙ Filter these results** narrows what is shown without
asking PubMed anything again. Every facet carries the count from these very
records:

- **Status** — new, already in the archive, already screened
- **Article type** — the publication types NLM gave these records
- **Journal quartile** — including *Not in SCImago*
- **Words in title or abstract**
- **Published between** — the range of the records you actually have
- **At least this many citations**
- **Only free full text** — if Unpaywall was asked

A line under the panel says *Showing 15 of 200*. What you save, add to a list
or add to a draft is what you can see: a tick left on a record the filter is
hiding does not come along.

![Results, with the facets open](/shots/03-results.png)

## What happens to a search

Every search is logged with its terms, its query and how many it found — 🕘
**Recent searches** at the bottom. A search can be attached to a draft, so the
article records where its bibliography came from.
