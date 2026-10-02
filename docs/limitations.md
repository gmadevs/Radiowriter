# Known limitations

## Searching

- A search downloads at most 9,999 records. This is the limit of PubMed's
  esearch service. The app downloads the most recent records up to that
  number and shows a message when a search has more. To reach the older
  records, narrow the search, for example by years. **Records to download**
  in the sidebar sets a lower limit. Downloading several thousand records
  takes a few minutes, and longer when citations and open access are looked
  up.
- The filters on the results are not sent to PubMed. They filter the records
  that were downloaded. A record that was not downloaded cannot be found with
  them.
- The block builder has two levels: lines inside a block, and blocks. A query
  with deeper nesting, such as `(A OR B) AND (C OR (D AND E))`, cannot be
  built in blocks. Type it on one line, which the app sends as written.
- PubMed reads operators from left to right and does not give AND precedence
  over OR. The block builder puts each block in brackets. In a query typed on
  one line, you have to add the brackets yourself.

- **📰 Fetch recent literature** takes its journals from the SCImago file.
  A journal that SCImago does not list, or lists in another category, is not
  searched. The journals are not limited by topic, so the results include
  radiology reviews on other body regions and neurology reviews that are not
  about imaging.
- The date of the last run of **📰 Fetch recent literature** is a setting.
  It is not in the `.json` backup, so after a restore on another computer the
  first run covers the last 30 days again.

## Journals

- SJR is not the Journal Impact Factor. The Impact Factor is published by
  Clarivate in the JCR and is not in the SCImago file. SCImago gives *SJR*,
  which weights citations by the rank of the citing journal, and *cites/doc
  (2y)*, which is calculated like an impact factor but on Scopus data. The
  app shows both, each with its label.
- About one article in ten has no quartile, because its journal is not in the
  SCImago file. Examples are Cureus, medRxiv and most case-report journals.
  These articles show no quartile badge.
- Articles are matched to journals by ISSN, and by exact title when the ISSN
  finds nothing. Approximate title matching is not used. It would add about
  1% more matches and could give an article the quartile of a different
  journal with a similar name.
- A newer SCImago file is not loaded automatically. After putting it in the
  data folder, click **↻ Reload the file and re-match** under
  **📊 Journal metrics**.

## Writing

- The article structures and the linter rules are copies of Radiopaedia's
  published guidance. The structures were transcribed on 2026-08-04 and the
  linter rules on 2026-08-27. Changes Radiopaedia makes after those dates are
  not included until the files are updated.
- The linter runs on the draft and not on the published article. It does not
  check images, tags or links, which Radiopaedia's linter checks on its
  server. It also does not have the exceptions registered on Radiopaedia.
- Citations are resolved through radiopaedia.work/cite, a service this
  project does not run. When it is unavailable, citations stay unresolved.
  The text of the draft is not affected.

## PDFs and the study window

- The app cannot download PDFs through LibKey. LibKey uses your library's
  login in your browser. You download the PDF there and drop it into the
  Library tab.
- A free PDF larger than 150 MB is not saved.
- A PDF is recognised by its text. A scanned PDF without a text layer has no
  readable DOI, PMID or title, and you have to type its PMID.
- Only articles that are in PubMed can be added to the library, because the
  archive identifies articles by PMID. A PDF of a book chapter, or from a
  journal PubMed does not index, cannot be added.
- The library holds one PDF per article. Adding a second file for the same
  article, such as a supplement, deletes the first file.
- Highlights made in other programs are listed only if they are saved in the
  PDF as annotations. Programs that keep highlights in their own database do
  not write them to the file.
- A highlight is on one page. A selection that continues on the next page is
  highlighted only on the page where it starts.
- The PDF reader needs a network connection. It loads PDF.js from the
  jsdelivr CDN each time it opens.
- On Linux the study window and the reader need GTK or Qt, which pip does not
  install. Without them the app shows a message and does not open the window.
- The Radiopaedia article list contains the articles that existed when you
  exported it. For newer articles, use the **Radiopaedia search** option of
  the study window.

## Backup

- The `.json` backup does not contain the PDF files, the record of which PDF
  belongs to which article, or the ticks on the highlights. Copy the PDF
  library folder separately. See [Backup](/guide/backup).
- Restoring the same backup twice duplicates its searches in the search
  history.

## The app

- The app is for one user. It serves a page to the browser on the same
  computer. It has no login and no sharing, and two people cannot work on
  the same archive.
- There is no undo. Deleting a list or a draft asks for confirmation and
  cannot be reversed afterwards. A backup made earlier is the only way to
  get the data back.
- Articles marked read are deleted from the archive each time the app
  starts. Their PMIDs are kept, so that later searches can skip them. An
  article in a reading list or with a PDF in the library is not deleted.
