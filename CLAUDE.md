# Radiowriter

## Writing rules for the README, the docs and the text shown in the app

Approved on 2026-10-01. They apply to `README.md`, `docs/**/*.md` and the
English strings of the interface in `radiowriter/`.

- A heading says what the section covers, in a few concrete words.
- Say what the software does and how to use it. Reasoning goes in the
  internals and developer pages, and only the facts that explain a choice.
- One point per sentence. Use a full stop, a comma or brackets where a dash is
  tempting. Target: fewer than 0.3 em dashes per 100 words.
- No "not X, but Y" and no "rather than", unless the reader would otherwise
  assume X.
- No closing morals, aphorisms or remarks about readers.
- Files, headers and the app do not lie, claim, say, want or know.
- Bold only for interface labels, exactly as the UI shows them, and for real
  warnings.
- Numbers instead of adjectives.
- British spelling, as in the existing pages ("licence", "colour").
- Keep every safety, legal and licence statement complete.
- Check every concrete claim against the code: labels, defaults, file names,
  commands, which network requests are made.

Measure a page with the `plain-docs` skill script:

```bash
node ~/.claude/skills/plain-docs/scripts/prose.mjs README.md
```

## Pages to rewrite

One page per commit, in this order.

- [x] README.md
- [x] docs/index.md
- [x] docs/guide/install.md
- [ ] docs/guide/search.md
- [ ] docs/guide/blocks.md
- [ ] docs/guide/screen.md
- [ ] docs/guide/journals.md
- [ ] docs/guide/library.md
- [ ] docs/guide/write.md
- [ ] docs/guide/backup.md
- [ ] docs/limitations.md
- [ ] docs/internals/architecture.md
- [ ] docs/internals/storage.md
- [ ] docs/internals/services.md
- [ ] docs/internals/journals.md
- [ ] docs/develop/run.md
- [ ] docs/develop/tests.md
- [ ] docs/develop/release.md
- [ ] Interface strings in radiowriter/app.py and radiowriter/issg.py
