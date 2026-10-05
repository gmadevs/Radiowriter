# Architecture

Radiowriter is a Streamlit app that stores its data in one SQLite file. There
is no server run by the project and no account. The Screening tab is a web
page of its own, served by a second local server inside the same process. The
PDF reader and the study window run as a separate process, which exists only
while their windows are open.

```
radiowriter/
  __main__.py     the `radiowriter` command: starts the Streamlit server, opens a browser
  app.py          the interface: search, library, writing, and the frame around Screening
  bench.py        the Screening page: its local server and its queries
  cards.py        the article cards: badges, abstract, and their CSS
  theme.py        colours and typefaces of the light and dark themes
  paths.py        where the user's files are, per platform
  db.py           schema, additive migrations, every query
  pubmed.py       E-utilities: esearch, efetch, and the MEDLINE parser
  querybuilder.py composing a query from concept blocks
  issg.py         the four published ISSG search filters
  strategies.py   Radiopaedia heading → PubMed search strategy
  editorial.py    the journals and the query of each editorial group
  modalities.py   the search terms of the 43 imaging modalities
  highlight.py    highlighting the search terms in titles and abstracts
  journals.py     reading the SCImago CSV
  semantic_scholar.py  citation counts
  unpaywall.py    whether a legal free copy exists, and where
  library.py      the PDF library: file names, recognising a PDF, open-access downloads
  highlights.py   reading and writing highlights in a PDF, keeping the ticks
  study.py        the reader and study windows (pywebview), and the Radiopaedia article list
  web/viewer.html the PDF reader (PDF.js)
  web/screening.html  the Screening page (HTML and JavaScript, no library)
  structure.py    the 23 article structures
  lint.py         Radiopaedia's linter rules
  radiopaedia.py  citations, numbering, Markdown → Radiopaedia's HTML
  draft_io.py     exporting and importing one draft
  backup.py       exporting and restoring the archive
  data/           the files transcribed from Radiopaedia, with their dates, and the SCImago table
```

The Streamlit interface is all in `app.py`. `__main__.py` uses Streamlit only
to start the server. The other modules do not import Streamlit, so they can be
called from a script and tested without a browser. The `check_*.py` tests do
this.

## The database

The database is one SQLite file. Migrations only add: `PRAGMA table_info`
gives the existing columns, and `ALTER TABLE ADD COLUMN` adds the missing
ones. No migration drops or rewrites data, so an archive created by an older
version keeps working.

| Table | Contents |
|---|---|
| `articles` | one row per PMID, with its read and flagged state |
| `screened_pmids` | the PMIDs of read articles that were deleted, so that searches can skip them |
| `lists`, `list_items` | reading lists |
| `drafts`, `draft_refs`, `draft_searches` | the drafts, their references and their attached searches |
| `searches` | the search history |
| `journal_metrics`, `journal_issns` | the contents of the SCImago file |
| `citation_cache` | resolved citations |
| `pdfs` | one PDF per article: file name, SHA-256, source |
| `pdf_highlights` | the highlights read from each PDF, and which are done |
| `settings` | email, keys, preferences |

The journal metrics are in a table so that the quartile filter can be a JOIN.
The Screening tab pages its results in SQL, and the number of pages is
calculated from the filtered total. Filtering in Python would require loading
about 30,000 journal rows on every rerun and would make SQL paging
impossible.

## Two Streamlit behaviours the code works around

Streamlit discards the state of a widget that is not drawn, so a control
that is hidden goes back to its default value. The search filters are drawn
only in **Custom**, and the Radiopaedia headings only when their panel is
open. To keep their values, `keep_defaults()` in `app.py` writes them back
into the session state on every run.

Streamlit does not allow writing to a widget's `key` after the widget has
been created. Code that changes the value of a control uses one of two
methods:

- it runs in a callback, which executes before the widgets of that run are
  created;
- it changes the key, which creates a new widget that reads its `value=`
  again.

Both are used, with a comment at each place.

## What runs on a click

Streamlit runs a script again from the top on every click. Three of the four
tabs are functions decorated with `st.fragment` (`search_tab`, `library_tab`,
`write_tab`). A click inside one of them runs only that function. The sidebar
and the other tabs are not run. A call to `st.rerun()` inside a tab runs the
whole script.

The article counts at the top of the sidebar are a fragment that runs every 5
seconds, because saving or deleting an article in a tab does not run the
sidebar.

The export files are built when their download button is clicked:
`st.download_button` receives a function as `data`. The numbers under the
buttons come from `COUNT` queries.

`check_app.py` does not cover a tab running alone: `AppTest` runs the whole
script on every interaction.

## The Screening page

Screening is the tab with the most clicks, several hundred ticks in a
session. As a Streamlit fragment, a tick took about 0.46 seconds on an
archive of 4,126 articles, and about 1.15 seconds before the tabs were
fragments. As a web page, a tick on **Select** changes the page without a
request, **✅ Read** takes about 15 milliseconds,
and a new page of articles about 20.

`bench.py` starts a `ThreadingHTTPServer` from the standard library on
`127.0.0.1`, on a port chosen by the system, the first time the app runs.
`app.py` shows `web/screening.html` from that server in an iframe inside the
tab. The page asks the server for JSON (`/api/state`, `/api/articles`) and
posts each action (`/api/status`, `/api/membership`, `/api/delete` and the
others). `bench.py` does not import Streamlit.

The server refuses a request unless all of these hold:

- the request carries the token of this run. The token is random, 32 bytes,
  and new at every start. The page receives it in its address and sends it
  back in the header `X-Radiowriter-Token`. Another website does not know the
  token, and cannot send a custom header without a CORS permission, which the
  server never gives;
- the `Host` header is `127.0.0.1` or `localhost` with the server's port, so a
  hostname pointed at the computer from outside (DNS rebinding) is refused;
- a write is a `POST` with a JSON body.

The page has a Content Security Policy that allows no outside resource and
allows framing only by a page on `localhost` or `127.0.0.1`.

The text of an article reaches the page in two ways. Titles, badges and
abstracts are escaped on the server by `cards.py` and `highlight.py`, the
same functions that draw the search results. Every other field is written by
the page as text. A full-text address is made a link only if it starts with
`http://` or `https://`.

The page reads the archive again when its tab becomes visible, because a
search may have saved articles in the meantime. The theme and the text sizes
are in the address of the iframe: when they change, the page is reloaded and
keeps its filters and its selection.

## The reader and the study window

Radiopaedia cannot be shown inside the Streamlit page. A site with a login
does not allow other pages to frame it, and a framed page would not have the
session cookies, so editing would not work. The study window is therefore a
separate program built on [pywebview](https://pywebview.flowrl.com), which
uses the browser engine of the system (WebKit on macOS, Edge WebView2 on
Windows, GTK or Qt on Linux).

pywebview has to run on the main thread of its process. In the app's process
that thread is used by Streamlit. **🪟 Open study window** and **📖 Read**
therefore start `python -m radiowriter.study` as a child process and return
immediately.

The reader window loads `web/viewer.html`, which renders the PDF with
[PDF.js](https://mozilla.github.io/pdf.js/). It gets its data through
pywebview's JavaScript bridge (`ReaderApi` in `study.py`). The bridge reads
and writes the same SQLite file as the app.

A highlight made in the reader is written into the PDF with PyMuPDF, as an
incremental save, which appends to the file without rewriting the rest. The
app then reads the highlight back from the file in the same way as a
highlight made in another program. All highlights therefore enter the list
through `highlights.sync`.

The reader asks for the state every 4 seconds. `highlights.sync` reads the
PDF again only when its modification time has changed. This is how a tick
made in the Library tab appears in the reader.

Each highlight has a key made from its page, its kind and its position,
rounded to 3 decimal places of the page size. When the file is read again, a
highlight with the same key keeps its tick, even if the program that saved
the file moved it slightly.
