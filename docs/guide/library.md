# PDFs and the study window

The **3 Library** tab keeps one PDF per article, named after its citation. The
app's reader shows a PDF, lets you highlight it, and lists the highlights so
you can tick each one off once it is in your article. The study window puts
that reader next to the Radiopaedia page you are editing.

## Getting a PDF into the library

There are two ways, and in each case the file is renamed:

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

**Drop it into the Library tab.** LibKey goes through your library's login,
which is in your browser, so these PDFs you download yourself as usual. Then
drag them onto *📎 Add PDFs* at the top of the Library tab, one or several at
a time. For each file the app looks for its article in two places, much as
Zotero's *Retrieve metadata* does:

1. **In the archive**, by the DOI in the text, then a PMID, then the title of
   an archived article appearing on the first page. The button is **Add to
   library**.
2. **On PubMed**, for PDFs whose article is not in the archive. First by DOI,
   then by title: the title from the PDF's metadata, or the line in the
   largest type on the first page. A title search is accepted only when
   exactly one PubMed article has the same title. The button is **Add to
   archive and library**, which imports the PubMed record first. This works
   even for an article you once marked read and had purged.

A PDF that matches nothing gets a field for the PMID. *Add all* takes every
recognised file at once. The original stays where you dragged it from: the
library keeps its own copy.

PubMed is sent a DOI, or a title, and nothing else. A title is sent only when
the first pages look like a paper, meaning at least two of *Abstract*,
*Keywords*, *Introduction*, *Received* and similar words appear. Each file is
asked about once per run of the app.

An article that has a PDF is not purged at startup when it is marked read, as
with articles in a reading list.

The library folder can be changed under ⚙️ Settings in the sidebar (*PDF
library folder*; the default is `PDFs` inside the data folder). Only file names
are stored in the database, so the folder can be moved to another disk and
pointed at again.

## Reading and highlighting

**📖 Read**, in the Library tab or on a Screening card, opens the PDF in the
app's own reader, in a window of its own. The study window uses the same
reader, next to Radiopaedia.

The reader has two views. **PDF** shows the document, fitted to the window.
**Highlights** shows one box per highlight, in reading order, with its page,
its colour and its note.

**To highlight**, select text in the PDF view. A small bar appears under the
selection: four colours and **U** for underline. The keyboard works too:
`1`–`4` for the colours, `U` for underline, `Esc` to cancel.

The highlight is written into the PDF itself, as a standard annotation, so
Preview, Acrobat or an iPad reader show it too. A highlight lies on one page:
a selection that runs over two pages is highlighted on the first.

On each box, or in the bar at the bottom of the PDF view:

- **Note** writes a note into the PDF, where other readers show it as a
  comment.
- **Delete** removes the highlight from the PDF.
- **Copy** puts the text on the clipboard.
- **Show in PDF** jumps to it.
- The **checkbox** marks it done, once the passage is in your article. *Hide
  done* hides the ticked ones.

The ticks are stored in the database, not in the PDF. Highlights made in
other programs are read too, whenever the file changes: highlight, underline,
squiggly and strike-through, with their notes. A tick stays when the file is
saved again. A highlight deleted from the PDF also disappears from the list.

In the PDF view the current highlight is outlined and the finished ones are
marked ✓. The bar at the bottom steps through them:

| Key | |
|---|---|
| `J` or `→` | next |
| `K` or `←` | previous |
| `Enter` | mark done and go to the next one still open |
| `X` or space | tick or untick |
| `H` / `P` | Highlights view / PDF view |

In the Library tab, each PDF with highlights has a
*🖍 12 highlight(s) · 3 done* section with the same checkboxes. A tick made
there shows up in the reader within a few seconds, and the other way round.

## The study window

**4 Write** → *🪟 Study window*. Choose:

- **The Radiopaedia page.** It can come from the list of their articles, from
  their own search, or from a URL you paste. The page you choose is saved with
  the draft.
- **A PDF.** The ones cited in this draft are marked ★ at the top.
- **The layout.** Side by side, or one above the other.

**Open study window** opens two windows. On the left is Radiopaedia itself: a
real browser window where you can sign in and edit. The login is kept between
sessions, separately from your usual browser. On the right is the reader
described above.

## The Radiopaedia article list

The list is a CSV exported from Radiopaedia's article search, with the columns
*Title*, *URL*, *Systems*, *Sections* and the date of last edit. Put it in the
data folder that `radiowriter --where` prints. It must be named either
`radiopaedia-articles-<date>.csv` (optionally gzipped) or `search.csv`. With
more than one, the newest name wins. The file is not shipped with the app.
Without it, the other two ways of choosing a page still work.
