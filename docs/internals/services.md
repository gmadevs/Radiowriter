# The services it calls

The app sends data to four services:

| Service | What is sent | What is returned |
|---|---|---|
| [NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25497/) | the query, your email address, and your API key if set. For a PDF you add whose article is not in the archive, its DOI or title. | the PubMed records |
| [Unpaywall](https://unpaywall.org/products/api) | a DOI and your email address | whether a free copy exists, and where |
| [Semantic Scholar](https://api.semanticscholar.org/) | PMIDs, and your API key if set | citation counts and, where known, a link to a free PDF |
| [radiopaedia.work/cite](https://radiopaedia.work) | an identifier you cited | the formatted citation |

The app also makes these requests:

- **⤓ Save free PDF** downloads the file from the open-access link that
  Unpaywall or Semantic Scholar returned. The request goes to the publisher
  or repository in that link, with a browser `User-Agent` header.
- The PDF reader loads [PDF.js](https://www.jsdelivr.com/package/npm/pdfjs-dist)
  (version 4.10.38) from the jsdelivr CDN. The PDF itself is not sent
  anywhere: pywebview serves it to the reader from a server on your own
  computer.
- The Radiopaedia window of the study window is radiopaedia.org, opened with
  your login. With the **Radiopaedia search** option, the text you search for
  is sent to radiopaedia.org.

The links on an article card (PubMed, LibKey, DOI, free full text) open in
your browser. The LibKey link contains your library ID and the PMID.

## The email address is not authentication

NCBI and Unpaywall require a contact address in every request, so that they
can reach a user whose requests cause a problem. Neither service sends mail
to the address or requires an account. Without an address, Unpaywall returns
HTTP 422.

## Rate limits

- NCBI allows 3 requests a second, or 10 with an API key. The app waits
  0.34 seconds between requests without a key and 0.11 seconds with one.
- Unpaywall states a limit of 100,000 requests a day and no limit per second.
  The app waits 0.1 seconds between requests, which is about 10 a second.
- Semantic Scholar is queried in batches of 100 PMIDs, 1.3 seconds apart, or
  in batches of 500, 0.15 seconds apart, with an API key.
- radiopaedia.work/cite is queried one identifier at a time, 0.4 seconds
  apart.

## Phrases PubMed does not find {#what-not-found-means}

PubMed lists the phrases it could not match in `errorlist.phrasesnotfound`.
The app shows them as a warning and does not treat them as an error.

The reason is the ISSG filters. They are published search strings several
thousand characters long, and they contain terms that match nothing in
MEDLINE, for example `chemotreatment*`. If an unmatched phrase were an error,
a search with a guidelines filter and no results would fail with a message
about syntax, when the query is valid and there are no results on the
subject.

A search field that does not exist (`errorlist.fieldsnotfound`) is an error,
and the app reports it.

## Free PDF links: Unpaywall before Semantic Scholar

Both services can return a link to a free PDF. When both have one, the app
uses Unpaywall's.
