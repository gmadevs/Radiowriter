# Backup and moving computer

The archive is one SQLite file. `radiowriter --where` prints where it is.

A copy of that file is a complete backup of the archive. It includes your
settings.

::: warning The database file contains your email address and API keys
Do not share a copy of the database file. To give the archive to someone
else, or to store it where others can read it, use the `.json` export
described below, which leaves the settings out.
:::

## ⇅ Export and backup

**⇅ Export and backup** in the sidebar writes two kinds of file.

### The `.nbib` file: articles only

A `.nbib` file is in MEDLINE format, the format PubMed exports. Zotero,
EndNote and Mendeley can import it, and so can this app, with
**📥 Import PubMed export**.

Under **What to export**, choose **Everything**, **Flagged only**,
**Still to read** or one reading list, then click the download button.

The file contains only the article records. It does not contain what you
marked read or flagged, the reading lists or the drafts, because MEDLINE has
no fields for them.

::: warning The file contains other people's email addresses
The affiliation lines of a PubMed record often include the email address of
the corresponding author. An export of about 2,000 records contains a few
hundred addresses. They are public on PubMed, but consider this before you
publish the file, for example in a public repository.
:::

### Importing a PubMed export

**📥 Import PubMed export** in the sidebar adds articles from a file or from
pasted text. It reads PubMed's MEDLINE format, in which every record starts
with a `PMID-` line. To get such a file on PubMed, click **Save** and choose
the format **PubMed** (a `.txt` file), or click **Send to**, then **Citation
manager** (a `.nbib` file). The Summary, Abstract, PMID and CSV formats
cannot be imported.

**Add to list** chooses the reading list the imported articles are added to:
an existing list, or **＋ New list…**, which asks for a name. With **No list**,
the default, the articles are saved in the archive only. Articles already in
the archive are added to the list too. Articles you had read and deleted are
not.

After the import, the app reports how many articles were added, how many were
already in the archive, how many were skipped because you had read and
deleted them, and how many were added to the list.

### The `.json` file: the archive

**⤓ Full backup (.json)** writes:

- the articles, with their read and flagged state;
- the PMIDs of the read articles that were deleted;
- the reading lists;
- the drafts, with their text, kind of article and references;
- the search history;
- the resolved citations.

Use this file to move to another computer.

The file does not contain:

- The settings. Your email address, API keys and LibKey ID are left out,
  so that they are not in a file you may share or store online. You enter
  them again after restoring.
- The journal metrics. They are loaded again from the SCImago file.
- The PDFs and what belongs to them. The PDF files, the record of which
  PDF belongs to which article, and the ticks on the highlights are not in
  the backup. The highlights themselves are inside the PDF files.
- Two details of each draft: the Radiopaedia page chosen for the study
  window, and which searches are attached to the draft.

## Restoring a backup

Under **Restore a backup**, in the same panel, choose the `.json` file and
click **Restore it**. Restoring adds what is missing and does not overwrite
or delete anything:

- an article already in the archive is skipped;
- a reading list with the same name as an existing one is not duplicated,
  and the articles it is missing are added to the existing list;
- a draft with the same title as an existing one is skipped;
- a resolved citation already stored is skipped.

The message after the restore gives the number of articles, lists and drafts
added. Restoring an old backup into an archive in use does not remove the
work in it.

The search history is the exception: it is added every time. Restoring the
same backup twice leaves each of its searches twice in **🕘 Recent searches**.

## Moving to a new computer

1. On the old computer, open **⇅ Export and backup** and click
   **⤓ Full backup (.json)**.
2. Copy the PDF library folder, if you use it. **Show folder** in the Library
   tab opens it.
3. On the new computer, run `uv tool install radiowriter`, then
   `radiowriter`.
4. Enter your email address on the first screen.
5. If you use a SCImago file newer than the included one, put it in the
   folder that `radiowriter --where` prints and reload it, as described in
   [Install](/guide/install#journal-quartiles).
6. Open **⇅ Export and backup**, choose the file under **Restore a backup**
   and click **Restore it**.
7. Enter your NCBI API key, Semantic Scholar API key and LibKey library ID
   again under **⚙️ Settings**, if you use them.
8. Add the PDFs again by dragging them onto the Library tab. Their highlights
   are in the files. The ticks on the highlights are not restored.
