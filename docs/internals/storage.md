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

This also catches a case that surprises people: `pip install -e .` does not
copy anything, it points at the source tree — so a developer install finds the
database sitting next to the source rather than the one in the data folder.
That is the rule working as intended, but from outside it looks as if the app
picked an archive at random.

**Which is why the app says so.** The sidebar shows the archive it is using,
how much is in it, and — when the answer is not the ordinary one — where the
path came from:

```
🗄 Archive · 2,453 articles · 1 draft
~/Documents/Radiowriter/pubmed_database.db
Next to the source, not the data folder — why
```

`radiowriter --where` prints the same thing with the reason spelled out, and so
does the line the app writes when it starts.

## The SCImago file

Looked for in the data folder first, then beside the code. The most recent name
wins, so next year's file is installed by dropping it in.

It is not bundled: SCImago's data is CC BY-NC, it is eleven megabytes, and it
is a new file every year.
