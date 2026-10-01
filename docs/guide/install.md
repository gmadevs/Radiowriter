# Install and first run

Radiowriter is a Python program. It starts a server on your own computer and
serves a page to your browser. The server accepts connections only from the
same computer, so another device on your network cannot open it.

## Install

The command is the same on macOS, Linux and Windows:

```bash
uv tool install radiowriter
```

::: tip Installing from the repository
`uv tool install git+https://github.com/gmadevs/Radiowriter` installs the
current state of the `main` branch, including changes that have not been
released yet.
:::

To start it:

```bash
radiowriter
```

It prints the address and opens `http://localhost:8501` in your browser.
`Ctrl+C` in the terminal stops it.

::: details If you do not have uv
macOS and Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows, in PowerShell:

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

If you already have pipx, `pipx install radiowriter` also works.
:::

To update, run `uv tool upgrade radiowriter`. To remove it, run
`uv tool uninstall radiowriter`. Uninstalling leaves your archive in place.

## First run

The first screen asks for an email address.

PubMed and Unpaywall require a contact address in every request. They use it
to reach you if your requests cause a problem. You do not create an account,
no confirmation mail is sent, and the address is stored only on your computer.

Three other settings are optional:

| Setting | What it does |
|---|---|
| **NCBI API key** | Raises the rate limit from 3 to 10 requests a second. Free, from your NCBI account settings. |
| **Semantic Scholar API key** | Makes citation lookups faster. Lookups also work without a key. |
| **LibKey library ID** | Gives direct full-text links through your library's subscription. It is your library's Third Iron ID, the number in `libkey.io/libraries/<ID>/…`. |

You can add them later under **⚙️ Settings** in the sidebar.

## Journal quartiles

Quartiles need no setup. A copy of the SCImago table for 2025 is included. It
is loaded at the first start and your articles are matched to it by ISSN.
**📊 Journal metrics** in the sidebar shows how many articles were matched.

### Using a newer year

1. Go to [scimagojr.com/journalrank.php](https://www.scimagojr.com/journalrank.php).
2. Click *Download data*, at the top right of the table.
3. Put the CSV in the folder that `radiowriter --where` prints.
4. In the app, open **📊 Journal metrics** in the sidebar and click
   **↻ Reload the file and re-match**.

A file whose name starts with `scimagojr` is used in place of the included
copy, even if its data is older. If there are several, the last one in
alphabetical order is used, so `scimagojr 2026.csv` is chosen over
`scimagojr 2025.csv`. `radiowriter --where` prints which file is in use.

::: info Licence of the SCImago data
The included file is SCImago's data, used under
[CC BY-NC](https://creativecommons.org/licenses/by-nc/4.0/). It has been
reduced to the columns the app reads and to the rows of type "journal". The
values are unmodified. `radiowriter/data/scimagojr-2025.about.txt` records the
download date and what was removed. The NonCommercial term applies to that
file.
:::

## Where the data is stored

```bash
radiowriter --where
```

| | |
|---|---|
| macOS | `~/Library/Application Support/Radiowriter` |
| Linux | `~/.local/share/radiowriter` (or `$XDG_DATA_HOME/radiowriter`) |
| Windows | `%LOCALAPPDATA%\Radiowriter` |

The archive is one SQLite file. To store it somewhere else, for example on an
external disk or in a synced folder, set `RADIOWRITER_HOME`:

```bash
RADIOWRITER_HOME=/Volumes/work/radiowriter radiowriter
```

Read [Backup and moving computer](/guide/backup) before you copy the file.
