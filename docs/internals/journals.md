# Matching journals to SCImago

The app joins PubMed's records to SCImago's journal table. The two sources
write journal names differently, for example *Medicine* and *Medicine (United
States)*, or *European journal of radiology* and *European Journal of
Radiology*.

## Which SCImago file is used {#which-file-and-why-that-one}

A `scimagojr*.csv` file that the user downloaded is used if there is one.
Otherwise the copy inside the package is used.

The user's file is used even when its data is older than the included copy,
so that an upgrade of the app does not replace a file the user chose.
`paths.journal_csv_origin()` returns the path together with the rule that
chose it, as `db_origin()` does for the database. The sidebar and
`radiowriter --where` both take their text from it.

The included copy is SCImago's export reduced by `scripts/trim_scimago.py`:

- it keeps the 10 columns that `journals.read()` reads;
- it keeps the rows whose `Type` is `journal`, which are 30,412;
- it is compressed with gzip, from 11.2 MB to 1.37 MB.

The column names, the separator and the decimal comma are unchanged, so
`journals.read()` reads the included copy and a downloaded file with the same
code. `check_journals.py` checks that the included copy can be read, that it
has only rows of type `journal`, and that its quartiles are Q1 to Q4.

## Matching by ISSN {#by-issn}

The ISSN is the same in PubMed and in SCImago. In an archive of 2,455
articles the result was:

| Result | Articles |
|---|---|
| matched by ISSN | 2,207 (90%) |
| matched by exact normalised title | 4 |
| not matched | 244 (10%) |

The unmatched articles are in journals that SCImago does not list. Cureus
accounts for 111 of the 244. Others are medRxiv, *Experimental and
Therapeutic Medicine* and many case-report journals. These articles get no
quartile.

For the title match, both titles are normalised: lower case, `&` replaced by
"and", and every character that is not a letter or a digit replaced by a
space.

## Why approximate title matching is not used {#why-not-fuzzy-titles}

A match on the end of the title was tested. It raised the match rate by about
1% and matched *Radiology case reports* to *Journal of Radiology Case
Reports*, which is a different journal with a different quartile. An article
with no quartile shows no badge, so the user can see that the value is
missing. A wrong quartile looks the same as a correct one.

## Articles saved by older versions {#the-historical-archive}

Articles saved before the app stored ISSNs have an empty ISSN column. The app
stores the full MEDLINE record of every article, and the record has `IS`
lines. `match_journals` reads the ISSN from there and fills in the column.

In the same articles, the `journal` field holds the abbreviation followed by
the full title, for example `Eur J Radiol European journal of radiology`,
because an older version of the app wrote it that way. The MEDLINE record has
the two in separate fields, `TA` and `JT`, and the full title is read from
`JT`. It is stored in the `journal_title` column. The `journal` field is not
changed.

## Checking the MeSH terms {#verifying-the-strategies}

A MeSH descriptor that does not exist matches nothing. PubMed reports it in
`errorlist`, and no offline test can detect it. A misspelt descriptor in a
strategy would therefore pass every other test and never find anything.

`check_mesh_live.py` asks the PubMed API about every controlled-vocabulary
term used by `strategies.py` and `modalities.py`. It is the only test that
needs the network, so it is not run with the others. Run it when you change
the strategies or the modalities, and each January, when MeSH is updated.
