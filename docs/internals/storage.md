# Where the data is stored

```bash
radiowriter --where
```

The command prints the data folder, the database file with the rule that
chose it, and the SCImago file in use. The default data folder is:

| | |
|---|---|
| macOS | `~/Library/Application Support/Radiowriter` |
| Linux | `~/.local/share/radiowriter`, or `$XDG_DATA_HOME/radiowriter` |
| Windows | `%LOCALAPPDATA%\Radiowriter` |

Two environment variables change this:

- `RADIOWRITER_HOME` sets the data folder, for example to keep the archive on
  an external disk.
- `RADIOPAEDIA_DB` sets the path of the database file and takes precedence
  over every other rule. The tests use it, so that a test run cannot change a
  real archive.

## How the database file is chosen {#why-not-beside-the-program}

The app uses the first of these that applies:

1. the file named by `RADIOPAEDIA_DB`;
2. a `pubmed_database.db` in the folder that contains the `radiowriter`
   package, if one exists;
3. `pubmed_database.db` in the data folder.

Rule 3 is the normal case. An installed program cannot keep its data next to
its code: that folder can be read-only, it is replaced at every upgrade, and
on Windows it is inside `%LOCALAPPDATA%\uv\tools`.

Rule 2 keeps older installations working. Earlier versions were run with
`streamlit run app.py` from the project folder and kept the database there.
The app does not move an existing archive.

Rule 2 also applies to a developer install. `pip install -e .` does not copy
the package: it points to the source tree. If the source tree contains a
`pubmed_database.db`, the app uses that file and not the one in the data
folder.

The sidebar shows which archive is in use. Under **🗄 Archive** it gives the
number of articles, lists, drafts and PDFs, and the path of the file. When
rule 1 or rule 2 chose the file, a third line says so:

```
🗄 Archive · 2,453 articles · 1 draft(s)
~/Documents/Radiowriter/pubmed_database.db
Next to the source code, not in the data folder (why)
```

`radiowriter --where` prints the same information. The app also prints the
path of the archive in the terminal when it starts, with the reason when it
is rule 1 or rule 2.

## The SCImago file

A copy of the SCImago table is included in the package, as
`radiowriter/data/scimagojr-<year>.csv.gz`. It is reduced to the columns the
app reads and to the rows of type "journal".

A `scimagojr*.csv` file you downloaded is used in place of the included copy.
The app looks for one in the data folder, in the project folder and its
`data` subfolder, and in the package folder. If there are several, the last
one in alphabetical order of file name is used, wherever it is. A downloaded
file is used even if its data is older than the included copy.

The table is loaded into the database when the database has no journal
metrics. After that, a new file is loaded only when you click
**↻ Reload the file and re-match** under **📊 Journal metrics**.

## Other contents of the data folder

| Name | Contents |
|---|---|
| `PDFs/` | the PDF library, unless another folder is set in **⚙️ Settings** |
| `study-browser/` | the browser profile of the study window, which holds your Radiopaedia login, and a copy of the reader page |
| `incoming/` | PDFs dropped into the Library tab, until they are added to the library |
| `radiopaedia-articles-*.csv` | the Radiopaedia article list, if you put one there |

These are in the data folder even when the database is next to the source
(rule 2).

The database stores the file names of the PDFs and not their full paths, so
the library folder can be moved.
