# Search PubMed

The control at the top of the tab chooses between two ways of searching.
**✎ One line** takes PubMed syntax as you type it. **⛁ Blocks** builds the
query one concept at a time, and is described in
[Build a query in blocks](/guide/blocks).

![The search tab](/shots/01-search.png)

## Recent literature of an editorial group

The panel at the top of the tab fetches the recent reviews and guidelines of
a Radiopaedia editorial group. It searches by journal and does not use the
search terms or the filters below it.

1. Choose the group under **Editorial group**. CNS is the only group for now.
2. Click **📰 Fetch recent literature**.

The first run covers the last 30 days. Later runs start 7 days before the
previous run, because PubMed adds the publication type to some records a few
days after they appear. Articles already in the archive are skipped, so the
overlap does not create duplicates. The date of the last run is shown next to
the button.

The search uses the date an article was added to PubMed, and returns reviews,
systematic reviews, meta-analyses and guidelines in English. Guidelines are
found with the ISSG filter *Guidelines (standard)*.

The journals come from the SCImago file. For CNS they are:

| Journals | How they are chosen | Articles kept |
|---|---|---|
| Neuroradiology, neuroimaging and spine | Title contains "neuroradiol", "neuroimag", "spine" or "spinal", and best quartile Q1 or Q2 (32 journals) | All |
| Radiology | Q1 in the category *Radiology, Nuclear Medicine and Imaging* (84 journals) | All |
| Neurology | Q1 in the category *Neurology (clinical)* (91 journals) | All |

The numbers are for the SCImago table of 2025. A run covering 30 days
returned about 600 articles on 2 October 2026.

Every article found is saved in the archive and added to the reading list
**Editorial group: CNS**. To screen them, open the Screening tab and choose
that list under **In list:**. An article in a list is not deleted at startup
when it is marked read, so the list keeps the articles you have screened
until you remove them from it or delete the list.

The run is recorded in **🕘 Recent searches**.

## The filters

The filter panel is always shown, below the search terms.

### Recent reviews, No filters, Custom

The control at the top of the panel has three positions.

- **★ Recent reviews** sets the last 10 years, full text, English, humans, and
  these NLM publication types: Review, Systematic Review, Scoping Review,
  Meta-Analysis, Network Meta-Analysis, Evidence Synthesis, Guideline,
  Practice Guideline, Consensus Statement.
- **No filters** turns every filter off, including the date limit. Only the
  search terms are sent to PubMed.
- **Custom** is selected automatically when you change any control by hand.
  If you set the controls back to the values of a preset, that preset is
  selected again.

The line under the controls describes the filters that the query will apply.
It is written from the same values as the query.

### Last N years

0 means no date limit.

### Humans

This filter excludes records indexed as animal studies and not as human
studies: `NOT (animals[mh] NOT humans[mh])`. It does not use `humans[mh]`,
because that would also exclude every record NLM has not indexed yet, which
includes most papers from the last few months.

### Kind of publication

Choose **Any** or one of two methods:

- **Publication type (NLM)** uses the labels an NLM indexer gave the record.
- **Search filter (ISSG)** uses published search filters from the InterTASC
  Information Specialists' Sub-Group. They find a kind of publication by the
  words it uses. Four are available: guidelines (broad), guidelines
  (standard), meta-analysis and systematic reviews.

The two methods cannot be used together. They would be joined with AND, and
only records matching both would be returned. Several choices within one
method are joined with OR. If you switch method, the choices you made in the
other one are kept for when you switch back.

## Settings in the sidebar

Four settings under **⚙ Search behaviour** in the sidebar apply to every
search and are not changed by the presets:

- **Records to download**: how many records are downloaded in detail.
- **Skip what is already known**: which records to leave out because they are
  already in the database.
- **Citations (Semantic Scholar)**: look up citation counts.
- **Open access (Unpaywall)**: look up whether a free copy exists.

## Filtering the results

When a search has returned results, **⚙ Filter these results** narrows what
is shown. PubMed is not queried again.

- **Status**: new, already in the archive, or already screened.
- **Article type**: the publication types NLM gave these records.
- **Journal quartile**: includes *Not in SCImago*.
- **Words in title or abstract**.
- **Published between**: limited to the years of the records you have.
- **At least this many citations**: available after citations have been
  looked up.
- **Only free full text**: available if **Open access (Unpaywall)** was
  ticked before the search.

The status, article type and quartile options show how many of the results
match each one.

When a filter hides some results, a line above the table reads, for example,
*Showing 15 of 200*. Saving, adding to a list and adding to a draft apply only
to the records shown. A record that is ticked but hidden by a filter is not
included.

![Results, with the filters open](/shots/03-results.png)

## The search log

Every search is recorded. **🕘 Recent searches**, at the bottom of the tab,
lists each search with its date, its terms, and the number of records found,
downloaded and saved.

When you add results to a draft as references, the search is attached to that
draft, so the draft records which search its references came from.
