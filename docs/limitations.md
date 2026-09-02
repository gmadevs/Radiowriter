# Known limitations

Written down because finding them yourself, halfway through a search, is worse.

## The searching

**200 records by default, not everything PubMed found.** The count says how many
matched; the app downloads the first slice of them, most recent first. Raise
*Max records to download* in the sidebar if you need more, but a search that
returns four thousand results is usually a search worth narrowing instead.

**The filters on the results do not go back to PubMed.** They narrow what was
already downloaded. If a paper was outside the first 200, no filter here will
find it.

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

## The app itself

**One person at a time.** It serves a page to your own browser on localhost.
There is no login and no sharing; two people cannot screen the same archive.

**No undo.** Deleting a list, a draft or an article is immediate. The backup in
the sidebar is the undo.

**Articles marked read are purged at startup**, and their PMIDs remembered so
they do not come back in a later search. An article in a reading list is never
purged.
