# Security

## Reporting a vulnerability

Open a [security advisory](https://github.com/gmadevs/Radiowriter/security/advisories/new).
Please do not open a public issue for something exploitable.

## What the app serves

Radiowriter runs on your computer and serves a page to your own browser on
`localhost`. The server accepts connections only from the same computer. There
is no account and no server run by the project.

The Screening tab is served by a second local server, on `127.0.0.1` and on a
port chosen at start. It can change and delete articles, so it answers only
requests that carry a random token created at each start, that name
`127.0.0.1` or `localhost` as host, and, for a change, that are a JSON `POST`.
A page from another website cannot meet these conditions. The details are in
[the architecture page](https://gmadevs.github.io/Radiowriter/internals/architecture).

## What is stored, and where

The archive is one SQLite file in your user data folder. `radiowriter --where`
prints the path.

| | |
|---|---|
| macOS | `~/Library/Application Support/Radiowriter` |
| Linux | `~/.local/share/radiowriter` (or `$XDG_DATA_HOME/radiowriter`) |
| Windows | `%LOCALAPPDATA%\Radiowriter` |

The file holds the articles you saved, your reading lists, your drafts and
your settings.

> **The settings include your email address and the API keys you entered.**
> The file is not encrypted. Anyone with access to your user account can read
> it.

The data folder also holds the PDF library and `study-browser/`, the browser
profile of the study window, which contains your Radiopaedia login. The app
sets each PDF it saves to be readable by its owner only, where the file system
allows it.

## What is sent over the network

The app sends data to four services:

| Service | What is sent | What it is for |
|---|---|---|
| [NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25497/) | the query, your email address, and your API key if set. For a PDF you add whose article is not in the archive, its DOI or title. | searching PubMed and downloading records |
| [Unpaywall](https://unpaywall.org/products/api) | a DOI and your email address | finding a legal free copy |
| [Semantic Scholar](https://api.semanticscholar.org/) | PMIDs, and your API key if set | citation counts |
| [radiopaedia.work/cite](https://radiopaedia.work) | an identifier you cited | the formatted citation |

It also makes these requests:

- **⤓ Save free PDF** downloads the file from the publisher or repository in
  the open-access link.
- The PDF reader loads PDF.js from the jsdelivr CDN. The PDF itself is not
  sent anywhere.
- The Radiopaedia window of the study window is radiopaedia.org, opened with
  your login.

The email address is not authentication. NCBI and Unpaywall require a contact
address in every request, so that they can reach a user whose requests cause a
problem. Neither service sends mail to the address.

LibKey links are built on your computer and are opened only when you click
them. A LibKey link contains your library ID and the PMID.

The full list is in
[The services it calls](https://gmadevs.github.io/Radiowriter/internals/services).

## Backups

**⇅ Export and backup** writes two kinds of file:

- A `.nbib` file with the articles, in MEDLINE format. The affiliation lines
  of a PubMed record often include the email address of the corresponding
  author, so an export of about 2,000 records contains a few hundred
  addresses. They are public on PubMed, but consider this before you publish
  the file.
- A `.json` file with the whole archive. It does not contain the settings, so
  a backup you share does not include your email address or your keys.

## Sharing your archive

The database file contains your settings. To give your archive to someone,
use the `.json` backup and do not copy the `.db` file.
