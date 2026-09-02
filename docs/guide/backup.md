# Backup and moving computer

Everything is one SQLite file. `radiowriter --where` prints it.

Copying that file is a complete backup and a complete move — but it carries
your settings too, **your email and any API keys included**. For anything you
might hand to somebody else, use the export instead.

## ⇅ Export and backup

In the sidebar. Two formats, and they are two different things.

### `.nbib` — the articles

PubMed's own MEDLINE export. This app reads it back, and so do Zotero, EndNote
and Mendeley. Export everything, only the flagged, only what is still to read,
or one reading list.

It contains the articles and nothing else. What you marked read, what you
flagged, which list something is in, your drafts — MEDLINE has no fields for
any of that, and writing them in would mean producing a file that calls itself
MEDLINE without being it.

::: warning It contains other people's email addresses
PubMed's affiliation lines usually carry the corresponding author's email. An
export of a couple of thousand records contains a few hundred of them. They are
public in PubMed, but republishing the file in bulk is a different act from
having it. Think before putting one in a repository.
:::

### `.json` — the whole archive

Articles **with their state**, reading lists, drafts with their bibliography,
the search history, the citations already resolved. This is the one for moving
to another computer.

**Settings are deliberately left out.** A backup file travels — a Dropbox, a
memory stick, an attachment — and an email address and API keys inside it would
be a leak waiting to happen. Typing them again takes a minute.

Journal metrics are left out for a different reason: they rebuild from the
SCImago file in a second, and carrying thirty thousand rows that regenerate
themselves is just weight.

## Restoring

Drop the `.json` into **Restore a backup**. Nothing is overwritten: what is
already there stays, and only what is missing is added. An article, a list or
a draft that already exists is skipped, and the count tells you how many.

Which means restoring the same backup twice does nothing the second time, and
restoring an old backup onto a working archive cannot destroy the work in it.

## Moving to a new computer, step by step

1. On the old one: **⇅ Export and backup → Full backup (.json)**
2. On the new one: `uv tool install radiowriter`, then `radiowriter`
3. Give it your email at the first-run screen
4. Drop the SCImago CSV into the folder `radiowriter --where` prints
5. **⇅ Export and backup → Restore a backup**, choose the file, restore
6. Re-enter your NCBI key and LibKey ID under ⚙️ Settings if you use them
