# Run from source

```bash
git clone https://github.com/gmadevs/Radiowriter.git
cd Radiowriter
python3 -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e .
radiowriter
```

`-e` installs the package in editable mode. The command runs the code in the
folder, so a change is used at the next reload without reinstalling.

## Using a test archive

To run the app on a separate archive, set both variables:

```bash
RADIOWRITER_HOME=/tmp/rw-dev RADIOPAEDIA_DB=/tmp/rw-dev/pubmed_database.db radiowriter
```

`RADIOWRITER_HOME` sets the data folder. It is not enough on its own in a
source checkout: if the project folder contains a `pubmed_database.db`, the
app uses that file. `RADIOPAEDIA_DB` sets the database file and takes
precedence. See [Where the data is stored](/internals/storage).

## Code conventions {#the-house-style}

- Comments and docstrings are in Italian, written without accented letters
  (`e'`, `perche'`, `piu'`). Interface text is in English.
- Comments explain why the code is written as it is. For a line that looks
  unusual, the comment says what goes wrong without it.
- Modules are one level deep in `radiowriter/` and import each other with
  `from radiowriter import db`.
- Migrations only add. They use `PRAGMA table_info` and
  `ALTER TABLE ADD COLUMN`, driven by the `EXTRA_*_COLUMNS` dictionaries in
  `db.py`. No migration drops or rewrites data.
- Dependencies are few. When the reason for one is not obvious, it is written
  next to it in `pyproject.toml`.
- Data transcribed from another source is in `radiowriter/data/`, with the
  date of transcription and a statement of which parts come from the source
  and which were changed here.

Read a file from start to end before changing it, and write in the same
style.

## Writing documentation and interface text

The README, the pages in `docs/` and the English text of the interface
follow the writing rules in `CLAUDE.md`, at the root of the repository. Check
every label, default and file name against the code when you change a page.

## Two Streamlit behaviours to know

Streamlit discards the state of a widget that is not drawn. A control that is
hidden goes back to its default value. If you are not sure whether this
applies to a change, write a short test with `AppTest`.

Streamlit does not allow writing to a widget's key after the widget has been
created. To change the value of a control from code, use one of two methods:

- do it in a callback, which runs before the widgets of that run are created;
- put a counter in the key, so that the next run creates a new widget that
  reads its `value=` again.

Both are used in the code, with a comment at each place.

## The documentation site

```bash
npm install
npm run docs:dev        # http://localhost:5173/Radiowriter/
npm run docs:build      # writes docs/.vitepress/dist
```

CI builds the site on every push to `main` that changes `docs/` and publishes
it to [gmadevs.github.io/Radiowriter](https://gmadevs.github.io/Radiowriter/).

The deploy job runs only when the repository is public, because GitHub Pages
on a private repository needs a paid plan. On a private repository the site
is still built, so a dead link or a configuration error fails the build.

## Screenshots

The screenshots in the documentation are taken by a script, so that they can
be taken again when the interface changes:

```bash
pip install playwright && playwright install chromium
python3 scripts/shots.py
```

The script creates a temporary archive with a made-up email address, runs a
real PubMed search in it, drives the app, and writes
`docs/public/shots/*.png`. It needs the network.

The script does not read or change your archive. The screenshots therefore
do not contain your email address or your library ID. The articles in them
are real PubMed records.

If the script cannot find a control it looks for, it stops with an error.
