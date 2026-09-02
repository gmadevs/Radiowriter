# Security

## Reporting a vulnerability

Open a [security advisory](https://github.com/gmadevs/Radiowriter/security/advisories/new).
Please do not open a public issue for something exploitable.

## What this app handles

Radiowriter runs on your computer and serves a page to your own browser on
`localhost`. There is no account, no server of ours, and nothing is uploaded
anywhere.

### What it stores, and where

Everything lives in one SQLite file in your user data folder — run
`radiowriter --where` to see the exact path.

| | |
|---|---|
| macOS | `~/Library/Application Support/Radiowriter` |
| Linux | `~/.local/share/radiowriter` (or `$XDG_DATA_HOME`) |
| Windows | `%LOCALAPPDATA%\Radiowriter` |

The file holds the articles you saved, your reading lists, your drafts, and
your settings — **including the email address and any API keys you entered**.
It is not encrypted. Anyone with access to your user account can read it.

### What leaves your computer

Only what a search needs, and only to these four:

| Service | What it is sent | Why |
|---|---|---|
| [NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25497/) | your query, your email, your API key if set | to search and fetch records |
| [Unpaywall](https://unpaywall.org/products/api) | a DOI, your email | to find a legal free copy |
| [Semantic Scholar](https://api.semanticscholar.org/) | PMIDs, your API key if set | citation counts |
| [radiopaedia.work/cite](https://radiopaedia.work) | an identifier you cite | to resolve a citation |

The email is not authentication: both NCBI and Unpaywall require a contact
address in every request so they can warn a caller whose script misbehaves
instead of silently blocking it. Neither sends mail.

LibKey links are built locally and only opened when you click them.

### Backups

`⇅ Export and backup` writes two kinds of file:

- **`.nbib`** — the articles in MEDLINE format. Note that PubMed's own
  affiliation lines often contain the corresponding author's email address, so
  an export of a large archive contains hundreds of third-party addresses.
  They are public in PubMed, but think before republishing the file.
- **`.json`** — the whole archive. **Settings are deliberately left out**, so a
  backup you share does not carry your email or your keys.

### Sharing your archive

The database file itself does carry your settings. If you want to hand your
archive to someone, use the `.json` backup rather than copying the `.db`.
