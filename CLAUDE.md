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

## Standing rule

The README, every page in `docs/` and the interface text were rewritten to
these rules between `b2287cb` and the commit "Rewrite the interface text in
plain prose". New text follows the same rules. Run the measuring script on
any page you change, and run the seven `check_*.py` scripts after changing
interface text, because some checks match it.
