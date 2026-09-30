# Architecture

A Streamlit app, a SQLite file, and a handful of modules that each own one
thing. No server of ours and no account. The only second process is the study
window, and it runs only while it is open.

```
radiowriter/
  __main__.py     the `radiowriter` command: starts the server, opens a browser
  app.py          the interface — the only module that imports streamlit
  paths.py        where the user's files live, per platform
  db.py           schema, additive migrations, every query
  pubmed.py       E-utilities: esearch, efetch, and the MEDLINE parser
  querybuilder.py composing a query from concept blocks
  issg.py         the four published ISSG search filters
  strategies.py   Radiopaedia heading → PubMed search strategy
  journals.py     reading the SCImago CSV
  semantic_scholar.py  citation counts
  unpaywall.py    is there a legal free copy, and where
  library.py      the PDF library: file names, Downloads, open-access downloads
  highlights.py   reading the highlights out of a PDF, keeping the ticks
  study.py        the study window (pywebview), and the Radiopaedia article list
  web/viewer.html the PDF reader inside the study window (PDF.js)
  structure.py    the twenty-three article structures
  lint.py         Radiopaedia's linter rules
  radiopaedia.py  citations, numbering, Markdown → their HTML
  draft_io.py     a single draft in and out of a file
  backup.py       the archive in and out of a file
  data/           what was transcribed from Radiopaedia, with its date
```

`app.py` is the only place that knows about Streamlit. Everything below it is
ordinary Python that can be called from a script and tested without a browser —
which is what the `check_*.py` suite does.

## The database

One SQLite file. Migrations are additive and never destructive: `PRAGMA
table_info` tells us which columns are missing, `ALTER TABLE ADD COLUMN` adds
them. The archive predates most of the features in it and has to keep working.

| Table | |
|---|---|
| `articles` | one row per PMID, with its state |
| `screened_pmids` | read and deleted, so they do not come back |
| `lists`, `list_items` | reading lists |
| `drafts`, `draft_refs`, `draft_searches` | the articles being written |
| `searches` | the history |
| `journal_metrics`, `journal_issns` | the SCImago file, as a table |
| `citation_cache` | a resolved citation is resolved forever |
| `pdfs` | one PDF per article: file name, SHA-256, where it came from |
| `pdf_highlights` | the highlights read from each PDF, and which are done |
| `settings` | email, keys, preferences |

Journal metrics are a table rather than a lookup in memory because filtering by
quartile has to be a JOIN. Doing it in Python would mean loading thirty
thousand rows on every rerun and — worse — giving up SQL paging: the page count
is computed on the filtered total, and only the database knows it.

## Streamlit, and the two things it does that surprise people

**A widget's state is discarded when the widget is not drawn.** Hide a control
behind a collapsed panel and its value silently reverts to the default. This is
why the search filters are always on screen rather than inside an expander.

**A widget's `key` cannot be written after the widget exists.** Anything that
changes a control's value from code has to happen in a callback, which runs
before the widgets of that run are created — or the key has to change, which
makes it a new widget that reads its `value=` again. Both idioms are used, and
commented where they are.

## The study window

Radiopaedia cannot be shown inside the Streamlit page. A site with a login does
not let other pages frame it, and a framed page would not have your session
cookies anyway, so you could not edit. The study window is therefore a separate
program: [pywebview](https://pywebview.flowrl.com), which uses the system's
own browser engine (WebKit on macOS, Edge WebView2 on Windows, GTK or Qt on
Linux).

pywebview must run on the main thread of its process, and in the app's
process that thread belongs to Streamlit. So **Open study window** starts
`python -m radiowriter.study` as a child process and returns immediately.

The right-hand window loads `web/viewer.html`, which renders the PDF with
[PDF.js](https://mozilla.github.io/pdf.js/). It gets its data through
pywebview's JavaScript bridge (`ReaderApi` in `study.py`), and the bridge
reads and writes the same SQLite file as the app. That is why a tick made in
one place shows up in the other: the viewer asks for the state every four
seconds, and `highlights.sync` re-reads the PDF only if its modification time
has changed.

Each highlight is identified by its page, its kind and its position, rounded.
When the file is read again, a highlight with the same key keeps its tick, even
if the program that saved the file moved it by a fraction of a point.
