# Where the data lives

```bash
radiowriter --where
```

| | |
|---|---|
| macOS | `~/Library/Application Support/Radiowriter` |
| Linux | `~/.local/share/radiowriter`, or `$XDG_DATA_HOME` |
| Windows | `%LOCALAPPDATA%\Radiowriter` |

`RADIOWRITER_HOME` overrides all of it, which is how an archive lives on an
external disk. `RADIOPAEDIA_DB` points at one specific file and wins over
everything; the test suite uses it so that running the tests cannot touch a
real archive.

## Why not beside the program

When it ran as `streamlit run app.py` from a project folder, the database could
sit next to the code. Installed as a program it cannot: that folder is
read-only, it changes at every upgrade, and on Windows it is inside
`%LOCALAPPDATA%\uv\tools`, which nobody will ever think to back up.

**An existing installation is left alone.** If there is a `pubmed_database.db`
next to the code, that one keeps being used. Moving somebody's archive out from
under them is the sort of thing you do once and then spend the evening
explaining.

## The SCImago file

Looked for in the data folder first, then beside the code. The most recent name
wins, so next year's file is installed by dropping it in.

It is not bundled: SCImago's data is CC BY-NC, it is eleven megabytes, and it
is a new file every year.
