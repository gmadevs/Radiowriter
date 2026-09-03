# Write the article

The **✍️ Write** tab is a Markdown editor that knows two things a plain editor
does not: the structure Radiopaedia recommends for this kind of article, and
how their citations work.

![The Write tab](/shots/05-write.png)

## The structure

Radiopaedia does not have one article structure. It has twenty-three. The
standard one gives a fixed order — Terminology, Epidemiology, Clinical
presentation, Pathology, Radiographic features, Treatment and prognosis,
History and etymology, Differential diagnosis — and then says it holds "in most
instances, except for the following specific special purpose articles", and
lists eighteen of those. An anatomy article wants *Gross anatomy* and *Variant
anatomy* and has no business being asked for *Epidemiology*.

**⌗ Headings** picks which structure the headings come from. It is guessed from
the title and remembered once you change it. Insert the required ones, all of
them, or one at a time on a line you choose — and if you put a heading where its
parent is not, the app says so without refusing.

![The headings panel, and the formatted output](/shots/06-headings.png)

The parent is part of a heading's identity. *Complications* under *Clinical
presentation* are the disease's; under *Treatment and prognosis* they are the
therapy's. An article can want both.

## Citing

Write the identifier, not a number:

```markdown
The lesion was heterogeneous on CT [@27859258].
```

PMID, DOI, PMCID, ISBN or a URL. Numbers are worked out at export from the
order of first appearance, so adding a source halfway through the article does
not mean renumbering anything. Two tokens that turn out to be the same paper —
a PMID and a DOI — become one reference, and the app says so.

**🔎 Resolve citations** asks radiopaedia.work/cite for each one. A resolved
citation is cached forever: it is asked once per identifier, not once per
draft.

## The bibliography

The **References** panel holds the sources of this draft. They come from four
places: added by hand, taken from the text, from your flagged articles, or from
[a reading list](/guide/screen) — which is the natural one, because a list made
for a section of the article *is* that section's bibliography.

## Getting it into their editor

Radiopaedia's editor is WYSIWYG: pasting plain text loses the formatting. Two
buttons copy as **rich text**, so headings, bold and the `<sup>` markers
survive. The article goes in the body; each reference line goes in its own
reference box.

## The linter

Radiopaedia publishes the rules their own linter applies. They are transcribed
in `data/lint-rules.json` and run over your draft before you paste it —
🔴 errors, 🟠 warnings, 🔵 suggestions.

It is run on the HTML rather than the Markdown, because half the rules talk
about `<sup>`, `<strong>`, `<em>` and headings, and in Markdown those tags do
not exist yet.

## Keeping a copy

Two files, and they are two different things. The `.json` is the draft — text,
kind of article, references with their notes, and the citations already
resolved — and it is the one Import reads back. The `.md` is to read: it opens
in anything, years from now.
