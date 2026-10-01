# PDFs and the study window

The **3 Library** tab keeps one PDF per article, named after its citation. The
app's reader shows a PDF, lets you highlight it, and lists the highlights with
a checkbox each, to tick when the passage is in your article. The study window
shows that reader next to the Radiopaedia page you are editing.

## Adding a PDF to the library

There are two ways to add a PDF. In both, the file is renamed:

```
Author Year - Journal - Title [PMID 12345678].pdf
```

The author is the first author's surname. The journal is the abbreviation
PubMed gives (`J Oral Maxillofac Surg`), and a long title is shortened. The
PMID makes the name unique, and lets the file be matched to its article again
if the database is lost.

### Saving an open-access copy

When Unpaywall or Semantic Scholar has a link to a free copy, the card in the
Screening tab shows **⤓ Save free PDF**, which downloads the file. Many free
links lead to the publisher's web page and not to the file. In that case the
app shows a message, and you download the PDF from that page yourself and add
it as described below.

### Adding a PDF you downloaded

LibKey uses your library's login in your browser, so you download these PDFs
in the browser as usual. Then drag them onto **📎 Add PDFs — drop them here**
at the top of the Library tab, one or several at a time. For each file the app
looks for the article in two places:

1. In the archive. It looks for a DOI in the text of the PDF, then a PMID,
   then the title of an archived article on the first page. The button is
   **Add to library**.
2. On PubMed, if the article is not in the archive. It searches by DOI, then
   by title. The title is taken from the PDF's metadata or from the line in
   the largest type on the first page. A title search is accepted only when
   exactly one PubMed article has the same title. The button is
   **Add to archive and library**, which imports the PubMed record first. This
   also works for an article that you marked read and that was deleted from
   the archive.

A PDF that matches no article gets a field where you can type the PMID. With
more than one matched file, **Add all N recognised PDFs** adds them together.
The file you dragged stays where it was. The library keeps its own copy.

Only a DOI or a title is sent to PubMed. A title is sent only when the first
pages look like a paper, meaning that at least two of *Abstract*, *Keywords*,
*Introduction*, *Received* and similar words appear. PubMed is asked about
each file once per run of the app, and only if the NCBI email is set.

### Managing the library

Each PDF in the tab has these buttons:

- **📖 Read** opens it in the reader.
- **Show in folder** shows the file in the system file manager.
- **Rename to the citation** appears when the file name differs from the
  citation name, and renames the file.
- **🗑 Remove** deletes the file from the library, after a confirmation.

The fields above the list filter it by text (title, author or PMID), by
reading list, and by the draft that cites the article.

An article that has a PDF is not deleted at startup when it is marked read.
The same applies to articles in a reading list.

To change the library folder, set **PDF library folder** under **⚙️ Settings**
in the sidebar. The default is `PDFs` inside the data folder. The database
stores only the file names, so you can move the folder to another disk and
then set the new location.

## Reading and highlighting

**📖 Read** in the Library tab, or **📖 Read PDF** on a Screening card, opens
the PDF in the app's reader, in a separate window. The study window uses the
same reader.

The reader has two views. **PDF** shows the document, fitted to the width of
the window. **Highlights** shows one box per highlight, in reading order, with
its page, its colour and its note.

To highlight, select text in the PDF view. A bar appears under the selection,
with four colours (yellow, green, blue, pink) and **U** for underline. The
keyboard shortcuts are `1` to `4` for the colours, `U` for underline, and
`Esc` to cancel.

The highlight is written into the PDF file as a standard annotation, so other
PDF readers, such as Preview or Acrobat, show it too. A highlight is on one
page. A selection that continues on the next page is highlighted on the first
page only.

These actions are on each box of the Highlights view, and in the bar at the
bottom of the PDF view:

- **Note** writes a note into the PDF. Other readers show it as a comment.
- **Delete** removes the highlight from the PDF.
- **Copy** copies the text to the clipboard.
- **Show in PDF** goes to the highlight in the PDF view.
- The checkbox marks the highlight as done. **Hide done** hides the ticked
  ones.

The ticks are stored in the database and not in the PDF. Highlights made in
other programs are also listed: the app reads them again whenever the file
changes. It reads highlight, underline, squiggly and strike-through
annotations, with their notes. A tick is kept when the file is saved again.
A highlight deleted from the PDF is removed from the list.

In the PDF view the current highlight is outlined and the done ones are
marked ✓. The bar at the bottom moves between them:

| Key | Action |
|---|---|
| `J` or `→` | Next highlight |
| `K` or `←` | Previous highlight |
| `Enter` | Mark as done and go to the next one that is not done |
| `X` or space | Tick or untick |
| `H` | Highlights view |
| `P` | PDF view |

In the Library tab, each PDF with highlights has a section such as
*🖍 12 highlight(s) · 3 done*, with the same checkboxes. A tick made there
appears in the reader within about 4 seconds, and a tick made in the reader
appears in the tab when it is redrawn.

## The study window

In the **4 Write** tab, open **🪟 Study window — the Radiopaedia page next to
a PDF** and set three things:

- **Radiopaedia page**: choose it from the article list, from Radiopaedia's
  search, or by pasting a URL. The page of a Radiopaedia article is saved
  with the draft.
- **PDF next to it**: a PDF from the library, or none. The PDFs cited in the
  draft are first in the list and marked ★.
- **Layout**: **◫ Side by side** or **⬒ One above the other**.

**🪟 Open study window** opens two windows. One is Radiopaedia in a browser
window of its own, where you can sign in and edit. The login is kept between
sessions and is separate from your usual browser. The other is the reader
described above.

## The Radiopaedia article list

The article list is a CSV file exported from Radiopaedia's article search,
with the columns *Title*, *URL*, *Systems*, *Sections* and the date of the
last edit. Put it in the data folder that `radiowriter --where` prints. Name
it `radiopaedia-articles-<date>.csv` (it can be gzipped) or `search.csv`. If
there are several `radiopaedia-articles` files, the last one in alphabetical
order is used. `search.csv` is used only when there is no
`radiopaedia-articles` file.

The file is not included with the app. Without it, you can still choose the
page from Radiopaedia's search or by URL.
