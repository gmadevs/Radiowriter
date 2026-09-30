# PDFs and the study window

The **3 Library** tab keeps one PDF per article, named after its citation. The
study window puts a Radiopaedia page next to one of those PDFs and lists the
passages you highlighted in it, so you can tick each one off once it is in
your article.

## Getting a PDF into the library

There are three ways, and in each case the file is renamed:

```
Author Year - Journal - Title [PMID 12345678].pdf
```

The author is the first author's surname. The journal is the abbreviation
PubMed gives (`J Oral Maxillofac Surg`), and a long title is shortened. The
PMID makes the name unique, and means the file can still be matched to its
article if the database is lost.

**Open access.** When Unpaywall or Semantic Scholar knows a free copy, the
Screening tab shows **⤓ Save free PDF**. The app downloads it directly. Many
free links lead to the publisher's web page instead of the file; the app says
so, and you download the PDF from that page yourself.

**From Downloads.** LibKey goes through your library's login, which is in your
browser, so these PDFs you download yourself as usual. The Library tab looks
at your Downloads folder (the last 30 days) and reads each new PDF. It looks
for a DOI first, then a PMID, then the article's title on the first page. When
one of them matches an article in the archive, it offers **Move into
library**. The file is moved, not copied. A PDF it cannot match gets a field
for the PMID.

**By hand.** *📎 Attach a PDF by hand*, at the bottom of the Library tab, takes
a file and a PMID.

An article that has a PDF is not purged at startup when it is marked read, as
with articles in a reading list.

Both folders can be changed under ⚙️ Settings in the sidebar: *PDF library
folder* (default: `PDFs` inside the data folder) and *Downloads folder to
watch*. Only file names are stored in the database, so the library folder can
be moved to another disk and pointed at again.

## Highlights

Highlight a PDF with any program that writes standard PDF annotations:
Preview on a Mac (⌃⌘H), Acrobat, most iPad readers. Highlight, underline,
squiggly and strike-through all count. A note attached to a highlight comes
along with it. Sticky notes on their own do not, because there is no text
under them.

The app reads the highlights from the file whenever the file changes. The
ticks are stored in the database, not in the PDF, so the file stays as you
downloaded and marked it. If you add highlights and save again, the ones you
had already ticked stay ticked. A highlight you delete from the PDF also
disappears from the list.

In the Library tab, each PDF with highlights has a
*🖍 12 highlight(s) · 3 done* section with one checkbox per highlight.

## The study window

**4 Write** → *🪟 Study window*. Choose:

- **The Radiopaedia page.** It can come from the list of their articles, from
  their own search, or from a URL you paste. The page you choose is saved with
  the draft.
- **A PDF.** The ones cited in this draft are marked ★ at the top.
- **The layout.** Side by side, or one above the other.

**Open study window** opens two windows. On the left is Radiopaedia itself: a
real browser window where you can sign in and edit. The login is kept between
sessions, separately from your usual browser. On the right is the PDF with two
views.

**Highlights** shows one box per highlight, in reading order, with its page,
its colour and its note. *Copy* puts the text on the clipboard. *Show in PDF*
jumps to it. Tick the box when the passage is in your article. *Hide done*
hides the ticked ones.

**PDF** shows the document, fitted to the window, with the current highlight
outlined and the finished ones marked ✓. A bar at the bottom steps through the
highlights:

| Key | |
|---|---|
| `J` or `→` | next |
| `K` or `←` | previous |
| `Enter` | mark done and go to the next one still open |
| `X` or space | tick or untick |
| `H` / `P` | Highlights view / PDF view |

**Open to highlight** opens the PDF in your system viewer. Save there, and the
new highlights appear in the window within a few seconds. Ticks made in the
Library tab show up in the same way.

## The Radiopaedia article list

The list is a CSV exported from Radiopaedia's article search, with the columns
*Title*, *URL*, *Systems*, *Sections* and the date of last edit. Put it in the
data folder that `radiowriter --where` prints. It must be named either
`radiopaedia-articles-<date>.csv` (optionally gzipped) or `search.csv`. With
more than one, the newest name wins. The file is not shipped with the app.
Without it, the other two ways of choosing a page still work.
