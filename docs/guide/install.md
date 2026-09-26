# Install and first run

Radiowriter is a Python program. It starts a small server on your own computer
and serves a page to your own browser — nothing is hosted anywhere, and no page
of yours leaves the machine.

## Install

One command, the same on macOS, Linux and Windows:

```bash
uv tool install radiowriter
```

::: tip Or the very latest
`uv tool install git+https://github.com/gmadevs/Radiowriter` installs from the
repository instead of from the index: whatever is on `main` right now, released
or not.
:::

Then, whenever you want it:

```bash
radiowriter
```

It prints a link and opens `http://localhost:8501`. `Ctrl+C` in the terminal
stops it.

::: details If you do not have uv
macOS and Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows, in PowerShell:

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

`pipx install radiowriter` does the same job if you already have pipx.
:::

Updating is `uv tool upgrade radiowriter`. Removing it is
`uv tool uninstall radiowriter`, and your archive stays where it is.

## First run

The app asks for one thing: an email address.

It is not a sign-up. Two of the services it calls — PubMed and Unpaywall — ask
for a contact address in **every** request, so that when a script starts
hammering their servers they can warn whoever is running it instead of silently
blocking the address. There is nothing to register for, no confirmation mail,
and the address is stored on your computer.

Three more are optional and can wait:

| | What it buys you |
|---|---|
| **NCBI API key** | 10 requests a second instead of 3. Free, from your NCBI account settings. |
| **Semantic Scholar key** | Faster citation lookups. Works without one. |
| **LibKey library ID** | Direct full-text links through your library's subscription. It is your library's Third Iron ID, the number in `libkey.io/libraries/<ID>/…`. |

You can add them later under ⚙️ **Settings** in the sidebar.

## Journal quartiles

Nothing to do: a copy of the SCImago table for 2025 ships with the app. It is
read at first start and your articles are matched to it by ISSN, and
📊 **Journal metrics** in the sidebar says how many matched.

### A newer year

1. Go to [scimagojr.com/journalrank.php](https://www.scimagojr.com/journalrank.php)
2. **Download data** — the link at the top right of the table
3. Drop the CSV into the folder that `radiowriter --where` prints

Any name starting with `scimagojr` wins over the bundled copy — even an older
one, because a file you put there on purpose is a decision and the app does not
overrule it. `radiowriter --where` says which of the two is in use.

::: info Whose data this is
The bundled file is SCImago's, under
[CC BY-NC](https://creativecommons.org/licenses/by-nc/4.0/): cut down to the
columns the app reads and to the rows that are journals, with the numbers
untouched. `radiowriter/data/scimagojr-2025.about.txt` records the download date
and the cut. The NonCommercial term applies to that file.
:::

## Where things are kept

```bash
radiowriter --where
```

| | |
|---|---|
| macOS | `~/Library/Application Support/Radiowriter` |
| Linux | `~/.local/share/radiowriter` |
| Windows | `%LOCALAPPDATA%\Radiowriter` |

One SQLite file holds everything. To keep it somewhere else — an external disk,
a synced folder — set `RADIOWRITER_HOME`:

```bash
RADIOWRITER_HOME=/Volumes/work/radiowriter radiowriter
```

See [Backup and moving computer](/guide/backup) before you copy it around.
