# Tests

Plain scripts. They print `OK` or `NO`, count at the end, and exit non-zero if
anything failed. No pytest, no fixtures, no configuration.

```bash
python3 check_rules.py       # 147 — the Radiopaedia linter rules
python3 check_structure.py   #  24 — the article structures
python3 check_search.py      # 125 — query building, ISSG, strategies, lists
python3 check_journals.py    #  85 — SCImago, matching, Unpaywall, backups
python3 check_library.py     #  76 — PDF library, highlights, the Radiopaedia list
python3 check_app.py         # 123 — the interface, driven without a browser
```

580 checks. None of them needs the network, and none touches a real archive:
each script points `RADIOPAEDIA_DB` at a throwaway file before importing `db`.
`check_library.py` and `check_app.py` also point `RADIOWRITER_HOME` at a
throwaway folder, because the PDF library is created there.

`check_library.py` builds its PDFs with PyMuPDF, highlights included, and
tests the study window's `ReaderApi` directly. It does not open any windows.
`web/viewer.html` has no automated test; check it by hand when it changes.

## The one that needs the network

```bash
python3 check_mesh_live.py
```

It asks PubMed whether every MeSH descriptor and subheading in `strategies.py`
still exists. Run it when you change the strategies, and once a year when MeSH
is updated in January. It needs the NCBI email to be set in the app.

## check_app.py

The other scripts test the engines. This one tests the wire between them and
the interface, which is where the mistakes live that an engine cannot make.

`streamlit.testing.v1.AppTest` runs the real app in memory and lets you press
buttons by key, so what is exercised is exactly the code that ships:

```python
at = AppTest.from_file(APP, default_timeout=60)
at.run()
at = at.checkbox(key="sf_english").check().run()
is_("changing a filter by hand moves the control to Custom",
    next(b for b in at.get("button_group") if b.key == "sf_mode").value, "custom")
```

Two real bugs were caught this way and could not have been caught otherwise: a
`sqlite3.Row` passed as a widget option, which is unpicklable and took the whole
page down, and a write to `session_state` after the widget existed.

Note that `st.caption` output is in `at.caption`, not `at.markdown`.

## What CI runs

`.github/workflows/test.yml`, on macOS, Linux and Windows against Python 3.11
and 3.13. It runs the six scripts, then starts the installed command and asks
`/_stcore/health` — because nothing else exercises the entry point, and the
entry point is what breaks only once it is installed.
