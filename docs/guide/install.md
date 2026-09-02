# Install and first run

Radiowriter is a Python program. It starts a small server on your own computer
and serves a page to your own browser — nothing is hosted anywhere, and no page
of yours leaves the machine.

## Install

One command, the same on macOS, Linux and Windows:

```bash
uv tool install git+https://github.com/gmadevs/Radiowriter
```

::: info Not on PyPI yet
Once `radiowriter` is published to PyPI the command becomes the shorter
`uv tool install radiowriter`. Until then it installs straight from the
repository, which works just as well.
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

`pipx install git+https://github.com/gmadevs/Radiowriter` does the same job if
you already have pipx.
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

Quartiles and SJR need one file, and it is not bundled: SCImago's data is
CC BY-NC and it is a new file every year.

1. Go to [scimagojr.com/journalrank.php](https://www.scimagojr.com/journalrank.php)
2. **Download data** — the link at the top right of the table
3. Drop the CSV into the folder that `radiowriter --where` prints

Any name starting with `scimagojr` works. The app loads it at the next start,
matches your articles by ISSN, and tells you how many it matched under
📊 **Journal metrics** in the sidebar.

Next year, drop the new file in beside it: the most recent name wins.

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
