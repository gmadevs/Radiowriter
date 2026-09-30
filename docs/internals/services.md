# The services it calls

Four services receive something from you:

| | What is sent | What comes back |
|---|---|---|
| [NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25497/) | the query, your email, your API key if set; for a PDF you add whose article is not in the archive, its DOI or title | the records |
| [Unpaywall](https://unpaywall.org/products/api) | a DOI, your email | whether a free copy exists, and where |
| [Semantic Scholar](https://api.semanticscholar.org/) | PMIDs, your API key if set | citation counts |
| [radiopaedia.work/cite](https://radiopaedia.work) | an identifier you cited | the formatted citation |

Three more requests send nothing of yours:

- **⤓ Save free PDF** downloads the file from the open-access link that
  Unpaywall or Semantic Scholar returned.
- The study window loads [PDF.js](https://www.jsdelivr.com/package/npm/pdfjs-dist)
  (version 4.10.38) from jsdelivr. Your PDF is not sent anywhere: PDF.js reads
  it from a small server on your own computer.
- The left-hand study window is radiopaedia.org itself, with your login.

## The email is not authentication

Both NCBI and Unpaywall require a contact address in every request. It exists so
that a caller whose script misbehaves can be warned rather than silently
blocked. Neither sends mail, neither has an account to create. Unpaywall
returns 422 without one; NCBI throttles harder.

## Rate limits

NCBI allows 3 requests a second, 10 with an API key, and the app paces itself
accordingly. Unpaywall publishes 100,000 calls a day and no per-second limit;
the app takes ten a second, which is what a polite client does.

## What "not found" means

PubMed reports phrases it could not match in `errorlist.phrasesnotfound` — but
only when the search returned nothing at all. It is not a broken query, and the
app treats it as information rather than an error.

This matters because the ISSG filters, which are published strings thousands of
characters long, contain terms that match nothing in the whole of MEDLINE:
`chemotreatment*` is one. Treating that as fatal made every zero-result search
with a guidelines filter fail with a message about syntax, hiding the real
reason — there is nothing on that subject.

A field that does not exist is a different matter, and still raises.

## Unpaywall over Semantic Scholar

Both can offer a free PDF link. When they disagree, Unpaywall wins: it is the
service that does only this.
