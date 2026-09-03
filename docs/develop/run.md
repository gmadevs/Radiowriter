# Run from source

```bash
git clone https://github.com/gmadevs/Radiowriter.git
cd Radiowriter
python3 -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e .
radiowriter
```

`-e` means editable: the command runs the code in the folder, so an edit shows
up on the next reload without reinstalling.

To work on a throwaway archive instead of your real one:

```bash
RADIOWRITER_HOME=/tmp/rw-dev radiowriter
```

## The house style

- **Comments and docstrings in Italian, without accented letters** — `e'`,
  `perche'`, `piu'`. **Interface text in English.**
- Comments explain *why*, not *what*. If a line looks odd, the comment says
  what goes wrong without it.
- Modules live one level deep in `radiowriter/` and import each other with
  `from radiowriter import db`.
- Migrations are additive: `PRAGMA table_info` plus `ALTER TABLE ADD COLUMN`,
  driven by an `EXTRA_*_COLUMNS` dictionary in `db.py`. Never destructive.
- Few dependencies, each with its reason written next to it in
  `pyproject.toml` when the reason is not obvious.
- Data transcribed from someone else lives in `radiowriter/data/` with the date
  it was transcribed, and it says plainly what is theirs and what is ours.

Read a file through before writing in it. The voice is consistent and easy to
break.

## Two things about Streamlit worth knowing before you start

**State is discarded for widgets that are not drawn.** Hiding a control means
losing its value, silently, back to the default. Verify before assuming
otherwise — it costs a five-line test.

**A widget's key cannot be written after the widget exists.** Change a
control's value from a callback (they run before that run's widgets are
created), or put a counter in the key so the next one is a new widget that
reads its `value=` again. Both patterns are in the code, commented.

## The documentation site

```bash
npm install
npm run docs:dev        # http://localhost:5173/Radiowriter/
npm run docs:build      # writes docs/.vitepress/dist
```

CI builds it on every push that touches `docs/` and publishes it to
[gmadevs.github.io/Radiowriter](https://gmadevs.github.io/Radiowriter/).

The deploy job is skipped while the repository is private, because Pages on a
private repository needs a paid plan. The site is still built in that case, so
a broken link or a bad config is caught either way.

## Screenshots

They are taken by a script, not by hand, because a hand-taken screenshot ages
in silence: a button gets renamed, the picture does not, and the page that was
meant to explain ends up lying.

```bash
pip install playwright && playwright install chromium
python3 scripts/shots.py
```

It builds a throwaway archive in `/tmp` with a made-up email, runs a real
PubMed search in it, drives the app and writes `docs/public/shots/*.png`.

**It never touches your archive.** The results are real papers; the identity is
not. Without that separation the screenshots would carry the email address and
the library ID of whoever took them.

If a control it looks for is gone, the script fails instead of photographing
the wrong thing.
