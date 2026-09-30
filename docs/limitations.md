# Known limitations

Written down because finding them yourself, halfway through a search, is worse.

## The searching

**At most 9,999 records per search.** That is PubMed's own limit: esearch does
not hand out more, however it is paged. The app downloads everything up to
there, most recent first, and says so when a search goes over. *Records to
download* in the sidebar can set a lower cap. A search that returns thousands
of results is usually worth narrowing anyway, and downloading them takes
minutes, more with citations and open access switched on.

**The filters on the results do not go back to PubMed.** They narrow what was
already downloaded. If a paper was not downloaded, no filter here will find
it.

**Blocks are two levels, not a syntax tree.** Wordings inside a block, blocks
between themselves. `(A OR B) AND (C OR (D AND E))` cannot be drawn — write it
by hand on one line instead, which the app accepts as it is.

**PubMed reads operators left to right.** It does not give AND precedence over
OR the way a programming language would. Each block gets its own brackets for
exactly this reason, but a hand-written line is your own responsibility.

## The journals

**SJR is not the Journal Impact Factor.** The impact factor is Clarivate's, from
the JCR, and is not in any file here. SCImago gives *SJR* — citations weighted
by the prestige of the journals making them — and *cites/doc (2y)*, computed
like an impact factor but over Scopus. Both are shown and both are labelled.

**About one article in ten has no quartile**, because its journal is not in
SCImago at all: Cureus, medRxiv, most case-report journals. They show nothing
rather than a wrong badge.

**Matching is by ISSN only**, plus an exact title match as a fallback. Fuzzy
title matching would raise the hit rate by a percent and would occasionally
give an article the quartile of a different journal with a similar name. A
wrong quartile is worse than no quartile.

## The writing

**The article structures and the linter rules are a transcription.** They were
copied from Radiopaedia's published guidance on 2026-08-04. When theirs change,
this is an old copy until someone redoes it.

**The linter runs on the draft, not on the published article.** It cannot see
what their server would say about images, tags or links.

**Citations are resolved through radiopaedia.work/cite**, which is not ours. If
it is down, citations stay unresolved — the draft is unaffected.

## PDFs and the study window

**PDFs through LibKey are downloaded by you.** They go through your library's
login, which is in your browser. The app picks them up from Downloads, but it
cannot fetch them itself.

**A PDF is recognised by the text in it.** A scanned PDF with no text layer
has no readable DOI, PMID or title, and has to be attached by PMID.

**One PDF per article.** A supplement or a second version replaces the first
file.

**Highlights have to be saved in the PDF.** Programs that keep highlights in
their own database, rather than as annotations in the file, are invisible here.

**The study window needs the network for its PDF reader**, which is loaded from
jsdelivr. Radiopaedia needs it anyway.

**On Linux the study window needs GTK or Qt**, which pip does not install. The
app says so instead of opening it.

**The Radiopaedia article list is only as recent as your export.** Articles
written after it can still be found through their search, inside the window.

## The app itself

**One person at a time.** It serves a page to your own browser on localhost.
There is no login and no sharing; two people cannot screen the same archive.

**No undo.** Deleting a list, a draft or an article is immediate. The backup in
the sidebar is the undo.

**Articles marked read are purged at startup**, and their PMIDs remembered so
they do not come back in a later search. An article in a reading list is never
purged.
