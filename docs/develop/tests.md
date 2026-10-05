# Tests

The tests are plain Python scripts, without pytest, fixtures or
configuration. Each script prints one line per check, starting with `OK` or
`NO`, then the number of checks and of failures. It exits with a non-zero
status if any check failed. The descriptions of the checks are in Italian.

```bash
python3 check_rules.py       # 147 checks: the Radiopaedia linter rules
python3 check_structure.py   #  24 checks: the article structures
python3 check_search.py      # 159 checks: query building, ISSG, strategies, lists
python3 check_journals.py    #  85 checks: SCImago, matching, Unpaywall, backups
python3 check_library.py     #  76 checks: PDF library, highlights, the Radiopaedia list
python3 check_bench.py       #  87 checks: the Screening page and its local server
python3 check_app.py         # 148 checks: the interface, driven without a browser
```

That is 726 checks. None of them needs the network, and none reads or changes
a real archive. The five scripts that use the database set `RADIOPAEDIA_DB`
to a temporary file before they import `db`. `check_library.py`,
`check_bench.py` and `check_app.py` also set `RADIOWRITER_HOME` to a
temporary folder, because the PDF library is created there.

`check_bench.py` starts the Screening server on a free port of `127.0.0.1`
and sends it real HTTP requests. It checks who may call the server, what the
article pages contain, and every action. It does not run the JavaScript of
`web/screening.html`. `scripts/shots.py` opens that page in a browser.

`check_library.py` creates its PDFs with PyMuPDF, with highlights, and calls
the reader's `ReaderApi` directly. It does not open any window.
`web/viewer.html` has no automated test. Test it by hand when you change it.

## The test that needs the network

```bash
python3 check_mesh_live.py
```

It asks PubMed whether every MeSH descriptor and subheading used in
`strategies.py` and `modalities.py` exists. Run it when you change either
file, and each January, when MeSH is updated. It takes about a minute without
an NCBI API key and about 20 seconds with one.

It reads the NCBI email address and API key from the settings of your
archive, so the email address must be set in the app.

## check_app.py

The other scripts test the modules below the interface. `check_app.py` tests
the interface itself, including how it calls those modules.

`streamlit.testing.v1.AppTest` runs the app in memory and operates its
widgets by key, so the test runs the same `app.py` that is installed:

```python
at = AppTest.from_file(APP, default_timeout=60)
at.run()
at = at.button(key="recent_open_btn").click().run()
is_("the button opens the panel with the editorial groups",
    at.selectbox(key="recent_group").options, "['CNS']")
```

Two kinds of error are found only by this script:

- a value that Streamlit cannot copy passed as a widget option, for example a
  `sqlite3.Row`, which makes the whole page fail;
- a write to `session_state` for a widget that already exists.

The output of `st.caption` is in `at.caption`, and is not included in
`at.markdown`.

## What CI runs

`.github/workflows/test.yml` runs on every push to `main` and on every pull
request, on macOS, Linux and Windows, with Python 3.11 and 3.13.

It runs the six scripts. It then runs `radiowriter --version` and
`radiowriter --where`, starts the installed command, and requests
`/_stcore/health` until the server answers. This last step is the only test
of the `radiowriter` entry point as it is installed.
