"""Le regole del linter Radiopaedia, applicate alla bozza prima di pubblicarla.

Il linter di radiopaedia.work legge l'articolo PUBBLICATO: gli si passa uno
slug e va a leggerselo sul sito. Su una bozza non c'e' niente da leggere, ed e'
esattamente quando servirebbe. Quindi le regole sono trascritte in
`data/lint-rules.json` - 42 errori, 27 warning, 10 suggerimenti, tutto
l'elenco - e girano qui, in locale, senza che esca niente dal computer.

Cosa viene lintato: l'HTML che `radiopaedia.py` produce, cioe' esattamente
quello che finisce negli appunti e poi nell'editor. Non il markdown. Meta'
delle regole parlano di `<sup>`, `<strong>`, `<em>` e dei titoli, e il markdown
quei tag non li ha ancora; lintare il sorgente vorrebbe dire riscrivere quelle
regole a mano, e riscritte non sarebbero piu' le loro.

Il motore e' un sottoinsieme di Vale, che e' quello su cui il linter e'
costruito, e il file usa il vocabolario di Vale perche' e' quello che stampa il
loro elenco: `existence`, `substitution`, `capitalization`, `occurrence`,
`repetition` sono le regole a pattern, `script` sono le quattro che il loro
elenco non stampa perche' pattern non sono.

NON sostituisce il linter vero. Loro sanno cose che qui non si sanno: le
eccezioni che Radiopaedia ha registrato, il vocabolario dietro `Acronyms`, e
tutto quello che hanno aggiunto dal giorno della trascrizione in poi. Dove i
due non vanno d'accordo, ha ragione il loro. Quello che si guadagna e' l'unica
cosa che loro non possono dare: una risposta su un testo mai pubblicato.
"""

from __future__ import annotations

import html as html_mod
import json
from dataclasses import dataclass
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path

import regex

DATA_DIR = Path(__file__).with_name("data")
RULES_FILE = DATA_DIR / "lint-rules.json"
NAMES_FILE = DATA_DIR / "proper-nouns.txt"
ACRONYMS_FILE = DATA_DIR / "acronyms.txt"

# I titoli di sezione di un articolo Radiopaedia PUBBLICATO sono h4, i
# sottotitoli h5. La bozza si esporta in h3/h4 perche' e' quello che l'editor
# si aspetta di ricevere, ma le regole sono scritte contro la pagina
# pubblicata: `BiographicalLifespan` cerca `<h4>History and etymology</h4>` e
# `HeadingCitation` guarda da `h2` in giu'. Quindi per lintare si rende
# l'articolo un'altra volta, alla profondita' a cui verra' pubblicato.
LINT_TOP_HEADING = 4


class LintError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# testo
# ---------------------------------------------------------------------------

def tidy(value) -> str:
    """Una riga sola, qualunque cosa sia entrata."""
    return " ".join(str(value or "").split())


TAG = regex.compile(r"<[^>]*>")


def plain(html: str) -> str:
    """Il testo di un pezzo di markup: tag via, entita' sciolte."""
    raw = str(html or "")
    if "<" not in raw and "&" not in raw:
        return tidy(raw)
    return tidy(html_mod.unescape(TAG.sub(" ", raw)))


FOLD = [
    (regex.compile(r"[‘’ʼ]"), "'"),
    (regex.compile(r"[“”]"), '"'),
    (regex.compile(r"[–—−]"), "-"),
    (regex.compile(r"[​-‍⁠﻿­]"), ""),
]


def fold(value) -> str:
    """La tipografia riportata alle forme piatte.

    Serve piu' di quanto sembri: gli articoli sono pieni di spazi a larghezza
    zero, e uno di quelli - invisibile - basta perche' una parola non venga
    piu' riconosciuta come la stessa parola."""
    out = str(value or "")
    for pattern, to in FOLD:
        out = pattern.sub(to, out)
    return tidy(out)


def flat(value) -> str:
    """Come `fold`, ma senza spazi e senza maiuscole: si confrontano le lettere."""
    return "".join(fold(value).split()).lower()


# ---------------------------------------------------------------------------
# a pezzi
# ---------------------------------------------------------------------------

BLOCK_TAGS = frozenset(
    "p li h1 h2 h3 h4 h5 h6 dd dt td th caption figcaption blockquote pre".split())

# Un marcatore di citazione: `<sup>1,2</sup>`. Serve toglierlo quando si cerca
# la riga del markdown da cui viene un blocco, perche' li' quel numero non
# c'e': nel sorgente c'e' `[@27859258]`, e il numero nasce solo all'export.
CITATION = regex.compile(r"<sup\b[^>]*>.*?</sup>", regex.S | regex.I)


@dataclass
class Block:
    """Un paragrafo, un titolo, una voce di elenco: l'unita' che il linter
    chiama `line`. Si porta dietro sia il markup sia il testo perche' le regole
    vogliono tutti e due."""
    tag: str
    html: str          # il blocco intero, tag compresi
    text: str          # lo stesso, in chiaro
    bare: str          # lo stesso, senza i marcatori di citazione
    start: int         # dove comincia dentro `Document.raw`
    in_list: bool = False   # dentro un <li>, anche se il blocco e' il <p>

    @property
    def is_heading(self) -> bool:
        return len(self.tag) == 2 and self.tag[0] == "h" and self.tag[1].isdigit()

    @property
    def is_item(self) -> bool:
        """Scope `list`. Un elenco "loose" mette un `<p>` dentro il `<li>`, e
        il blocco piu' interno e' allora il paragrafo: senza questo, meta'
        degli elenchi non verrebbe controllata da `ListCaps` ne' da
        `ListPunctuation` a seconda di come e' scritto il markdown."""
        return self.tag == "li" or self.in_list


class _Segmenter(HTMLParser):
    """I blocchi piu' interni di un HTML, con il markup di ognuno.

    Piu' interni: un `<li>` che contiene un `<p>` porterebbe altrimenti il
    proprio testo due volte, e ogni segnalazione dentro sarebbe doppia. Un
    blocco che ne contiene un altro viene quindi scartato in favore dei figli.
    """

    def __init__(self, html: str):
        super().__init__(convert_charrefs=False)
        self.html = html
        self.lines = [0]
        for line in html.splitlines(keepends=True):
            self.lines.append(self.lines[-1] + len(line))
        self.stack: list[dict] = []
        self.out: list[Block] = []

    def _offset(self) -> int:
        line, col = self.getpos()
        return self.lines[line - 1] + col

    def handle_starttag(self, tag, attrs):
        if tag not in BLOCK_TAGS:
            return
        for frame in self.stack:
            frame["nested"] = True
        self.stack.append({
            "tag": tag, "at": self._offset(), "nested": False,
            "in_list": any(f["tag"] == "li" for f in self.stack),
        })

    def handle_endtag(self, tag):
        if tag not in BLOCK_TAGS:
            return
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]["tag"] != tag:
                continue
            frame = self.stack.pop(i)
            # `self._offset()` e' l'inizio di `</tag>`; il blocco arriva in fondo
            end = self.html.find(">", self._offset())
            end = len(self.html) if end < 0 else end + 1
            if not frame["nested"]:
                markup = self.html[frame["at"]:end]
                self.out.append(Block(
                    tag=tag, html=markup, text=plain(markup),
                    bare=plain(CITATION.sub("", markup)),
                    start=frame["at"], in_list=frame["in_list"]))
            del self.stack[i:]
            return


@dataclass
class Document:
    blocks: list[Block]
    raw: str

    def block_at(self, offset: int) -> int:
        """In quale blocco e' caduto un offset dentro `raw`."""
        found = 0
        lo, hi = 0, len(self.blocks) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            if self.blocks[mid].start <= offset:
                found, lo = mid, mid + 1
            else:
                hi = mid - 1
        return found


def read_document(html: str) -> Document:
    """L'HTML fatto a blocchi, in ordine di lettura.

    `raw` resta l'HTML intero e non i blocchi rimessi insieme: alcune regole
    parlano di una DISTANZA - `BiographicalLifespan` parte da un titolo e
    finisce su un nome qualche paragrafo sotto - e non c'e' nessun blocco che
    contenga tutti e due."""
    parser = _Segmenter(html or "")
    parser.feed(html or "")
    parser.close()
    blocks = sorted(parser.out, key=lambda b: b.start)
    blocks = [b for b in blocks if b.text or "&nbsp;" in b.html]
    return Document(blocks=blocks, raw=html or "")


# ---------------------------------------------------------------------------
# le regole
# ---------------------------------------------------------------------------

@dataclass
class Rule:
    name: str
    check: str              # come lo stampa l'elenco loro: "Adjectival Hyphens"
    severity: str
    kind: str
    scope: frozenset[str]
    message: str
    nonword: bool = False
    ignorecase: bool = False
    tokens: tuple[str, ...] = ()
    raw: tuple[str, ...] = ()
    capture: int | None = None
    maximum: int | None = None
    link: str | None = None
    common: frozenset[str] = frozenset()
    pattern: object = None                  # existence / occurrence / repetition
    swaps: tuple[tuple[object, str], ...] = ()   # substitution
    exceptions: tuple[object, ...] = ()


def check_name(name: str) -> str:
    """"StrongListColonPosition" -> "Strong List Colon Position", che e' come
    l'elenco del linter scrive i propri nomi."""
    return regex.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(name or "")).strip() or "Finding"


def _compile(pattern: str, flags: int, where: str):
    """Un pattern che non compila si porta via la propria regola e nient'altro.

    Il file e' una trascrizione, e le trascrizioni hanno refusi: far saltare
    tutto il linter per una barra rovescia sbagliata sarebbe la reazione
    sbagliata."""
    try:
        return regex.compile(pattern, flags)
    except regex.error as exc:
        print(f"[lint] pattern non compilato in {where}: {pattern!r} ({exc})")
        return None


def _group(rule_nonword: bool, tokens) -> str:
    """Vale racchiude i token in confini di parola, a meno che la regola non
    dica `nonword`, e concatena `raw` davanti a tutto."""
    joined = "|".join(tokens)
    return f"(?:{joined})" if rule_nonword else rf"\b(?:{joined})\b"


def compile_rules(spec: dict) -> list[Rule]:
    out: list[Rule] = []
    for item in spec.get("rules", []):
        flags = regex.I if item.get("ignorecase") else 0
        rule = Rule(
            name=item["name"],
            check=check_name(item["name"]),
            severity=item.get("severity", "warning"),
            kind=item.get("kind", "existence"),
            scope=frozenset(item.get("scope") or ["text"]),
            message=item.get("message", ""),
            nonword=bool(item.get("nonword")),
            ignorecase=bool(item.get("ignorecase")),
            tokens=tuple(item.get("tokens") or ()),
            raw=tuple(item.get("raw") or ()),
            capture=item.get("capture"),
            maximum=item.get("max"),
            link=item.get("link"),
            common=frozenset(a.upper() for a in item.get("common") or ()),
            exceptions=tuple(filter(None, (
                _compile(e, regex.I if item.get("ignorecase") else 0, item["name"])
                for e in item.get("exceptions") or ()))),
        )

        if rule.kind == "substitution":
            # Un pattern per scambio, non un'alternanza sola: quaranta
            # contrazioni in un pattern direbbero CHE una ha fatto centro, non
            # QUALE, e quale e' tutto il messaggio.
            swaps = []
            for frm, to in item.get("swaps") or []:
                pattern = frm if rule.nonword else rf"\b(?:{frm})\b"
                compiled = _compile(pattern, flags, rule.name)
                if compiled is not None:
                    swaps.append((compiled, to))
            rule.swaps = tuple(swaps)
        elif rule.kind != "script" and rule.tokens:
            rule.pattern = _compile(
                "".join(rule.raw) + _group(rule.nonword, rule.tokens), flags, rule.name)

        out.append(rule)
    return out


@lru_cache(maxsize=1)
def rules() -> list[Rule]:
    if not RULES_FILE.exists():
        raise LintError(f"Manca {RULES_FILE.name}: le regole del linter non si possono leggere.")
    try:
        spec = json.loads(RULES_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LintError(f"{RULES_FILE.name} non e' JSON valido: {exc}") from exc
    return compile_rules(spec)


@lru_cache(maxsize=1)
def transcribed_on() -> str:
    try:
        return json.loads(RULES_FILE.read_text(encoding="utf-8")).get("transcribed", "")
    except Exception:
        return ""


def _read_list(path: Path) -> set[str]:
    """Una voce per riga, `#` commenta. Tenuto cosi' scemo apposta: i file si
    modificano a mano, e un formato con una sintassi da sbagliare sarebbe una
    seconda cosa da azzeccare."""
    if not path.exists():
        return set()
    out = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        entry = line.split("#")[0].strip()
        if entry:
            out.add(entry)
    return out


@lru_cache(maxsize=2)
def _shared(kind: str) -> frozenset[str]:
    return frozenset(_read_list(NAMES_FILE if kind == "names" else ACRONYMS_FILE))


# ---------------------------------------------------------------------------
# a frasi, e le eccezioni
# ---------------------------------------------------------------------------

# Spezzare su un punto e basta mette "e.g." e "1.5 T" e "Dr R F Player" ognuno
# in due, e `OxfordComma` e `Commas` contano PER FRASE: uno spezzone sbagliato
# e' un conto sbagliato, non solo una riga storta.
ABBREVIATION = regex.compile(
    r"(?:\b(?:e\.g|i\.e|cf|vs|etc|approx|no|fig|al|Dr|Prof|Mr|Mrs|Ms|St|Fig)|\b[A-Z]|\d)\.$")
SPLIT = regex.compile(r"(?<=[.?!])\s+")


def sentences(text: str) -> list[tuple[str, int]]:
    """Le frasi di un blocco, ognuna con dove comincia dentro il blocco."""
    out: list[tuple[str, int]] = []
    at = 0
    held, held_at = "", 0
    for part in SPLIT.split(str(text or "")):
        if not held:
            held_at = at
        held = f"{held} {part}" if held else part
        at += len(part) + 1
        if not ABBREVIATION.search(held):
            out.append((held, held_at))
            held = ""
    if held:
        out.append((held, held_at))
    return out


def widen(text: str, start: int, end: int) -> str:
    """Il match allargato di una parola per lato, che e' quello contro cui
    un'eccezione viene davvero provata.

    Vale prova le eccezioni contro il match, e per quasi tutte le regole basta:
    `ListPunctuation` becca "etc." e l'eccezione e' "etc". Ma `Ampersand` becca
    " & " - tre caratteri, nemmeno una lettera - e le sue eccezioni sono "H&E"
    e "head & neck" e "Smith & Jones", nessuna delle quali si puo' trovare
    dentro un match che di lettere non ne ha. Questo e' il contesto piu' stretto
    in cui ogni eccezione del file riesce ancora a dire quello che vuole dire."""
    a, b = start, end
    while a > 0 and text[a - 1].isspace():
        a -= 1
    while a > 0 and not text[a - 1].isspace():
        a -= 1
    while b < len(text) and text[b].isspace():
        b += 1
    while b < len(text) and not text[b].isspace():
        b += 1
    return text[a:b]


def excused(rule: Rule, text: str, start: int, end: int) -> bool:
    if not rule.exceptions:
        return False
    around = widen(text, start, end)
    return any(e.search(around) for e in rule.exceptions)


def fill(message: str, *args) -> str:
    """Il messaggio con i suoi '%s' riempiti, in ordine."""
    out = str(message or "")
    for arg in args:
        out = out.replace("%s", str(arg), 1)
    return out


# ---------------------------------------------------------------------------
# una segnalazione
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    rule: str               # "AdjectivalHyphens"
    check: str              # "Adjectival Hyphens"
    severity: str           # error | warning | suggestion
    message: str
    snippet: str            # il blocco in chiaro, che e' dove sta la cosa
    matched: str            # le parole in questione
    block: int              # quale blocco, in ordine di lettura
    at: int                 # dove comincia il match dentro `snippet`
    length: int
    whole: bool             # riguarda il blocco intero, non un punto
    bare: str = ""          # il blocco senza i numeri, per ritrovare la riga
    link: str | None = None
    line: int | None = None     # la riga del markdown, riempita dopo
    known: str | None = None    # la voce della lista condivisa che lo copre

    @property
    def hushed(self) -> bool:
        return self.known is not None


SEVERITY_ORDER = {"error": 0, "warning": 1, "suggestion": 2}

# Le due regole a cui una lista condivisa sa rispondere. Sono le stesse due che
# lo userscript mette da parte, e per la stessa ragione: su un articolo di
# radiologia meta' di quelle maiuscole SONO nomi propri, e un buon numero di
# quegli acronimi non e' ignoto a nessuno.
LISTS = {"ListCaps": "names", "Acronyms": "acronyms"}


def _covered(rule_name: str, word: str) -> str | None:
    kind = LISTS.get(rule_name)
    if not kind or not word:
        return None
    entries = _shared(kind)
    if kind == "acronyms":
        # Parola intera: questa regola cita l'acronimo e nient'altro, e "PE"
        # non e' "PET".
        low = fold(word).lower()
        return next((e for e in entries if e.lower() == low), None)
    # Per prefisso: il file dice "Alvarado" e la voce e' "Alvarado score".
    text = fold(word).lower()
    return next((e for e in sorted(entries, key=len, reverse=True)
                 if text.startswith(e.lower())), None)


def _finding(doc: Document, index: int, rule: Rule, *, matched: str, message: str,
             start: int = 0, end: int = 0, whole: bool = False) -> Finding:
    block = doc.blocks[index]
    shown = tidy(matched)
    return Finding(
        rule=rule.name, check=rule.check, severity=rule.severity, message=message,
        snippet=block.text, bare=block.bare, matched=shown, block=index,
        at=max(0, start), length=max(0, end - start), whole=whole,
        link=rule.link, known=_covered(rule.name, shown),
    )


# ---------------------------------------------------------------------------
# i motori
# ---------------------------------------------------------------------------

def _units(doc: Document, rule: Rule):
    """Su quali pezzi dell'articolo gira una regola, dato il suo scope.

    Una regola puo' averne piu' d'uno - `So` e `ThereIs` parlano di frasi E di
    voci di elenco E di titoli - e un pezzo e' un blocco, una frase dentro un
    blocco, o per `raw` tutto il documento insieme."""
    for i, block in enumerate(doc.blocks):
        if "text" in rule.scope:
            yield i, block.text, 0
        if "heading" in rule.scope and block.is_heading:
            yield i, block.text, 0
        if "list" in rule.scope and block.is_item:
            yield i, block.text, 0
        if "sentence" in rule.scope:
            for text, at in sentences(block.text):
                yield i, text, at


def run_existence(doc: Document, rule: Rule, out: list[Finding]) -> None:
    if "raw" in rule.scope:
        return run_raw(doc, rule, out)
    if rule.pattern is None:
        return
    for i, text, offset in _units(doc, rule):
        for m in rule.pattern.finditer(text):
            matched = m.group(rule.capture) if rule.capture is not None else m.group(0)
            if not matched:
                continue
            start, end = offset + m.start(), offset + m.end()
            if excused(rule, doc.blocks[i].text, start, end):
                continue
            out.append(_finding(
                doc, i, rule, matched=matched, start=start, end=end,
                message=fill(rule.message, tidy(matched)),
                whole=flat(matched) == flat(doc.blocks[i].text)))


def run_raw(doc: Document, rule: Rule, out: list[Finding]) -> None:
    """Le regole che parlano del markup invece che delle parole.

    Girano su tutto il documento in una volta perche' alcune parlano di una
    distanza. La segnalazione va sul blocco in cui il match FINISCE - quello
    che contiene la cosa da cambiare - e quello che si illumina e' il match coi
    tag tolti, che e' l'unica parte che nel testo esiste davvero."""
    if rule.pattern is None:
        return
    for m in rule.pattern.finditer(doc.raw):
        index = doc.block_at(max(m.start(), m.end() - 1))
        piece = m.group(rule.capture) if rule.capture is not None else m.group(0)
        matched = plain(piece)
        if excused(rule, doc.raw, m.start(), m.end()):
            continue
        # dove sta il match dentro il proprio blocco, cosi' su un paragrafo che
        # lo dice due volte si illumina la copia giusta
        inside = max(0, m.start() - doc.blocks[index].start)
        before = plain(doc.blocks[index].html[:inside])
        out.append(_finding(
            doc, index, rule, matched=matched or doc.blocks[index].text,
            start=len(before), end=len(before) + len(matched),
            message=fill(rule.message, tidy(matched) or tidy(piece)),
            whole=not matched))


def run_substitution(doc: Document, rule: Rule, out: list[Finding]) -> None:
    for i, text, offset in _units(doc, rule):
        for pattern, to in rule.swaps:
            for m in pattern.finditer(text):
                if not m.group(0):
                    continue
                start, end = offset + m.start(), offset + m.end()
                if excused(rule, doc.blocks[i].text, start, end):
                    continue
                # la coppia, nell'ordine in cui ogni messaggio di sostituzione
                # la chiede: cosa dovrebbe dire, poi cosa dice
                out.append(_finding(
                    doc, i, rule, matched=m.group(0), start=start, end=end,
                    message=fill(rule.message, to, tidy(m.group(0)))))


OPENERS = "(\"'‘“"
CLOSERS = ")\"'’”,.;:"


def run_capitalization(doc: Document, rule: Rule, out: list[Finding]) -> None:
    """Maiuscole da frase, per i titoli.

    Solo la prima parola prende la maiuscola. Una dopo puo' averla se e' un
    acronimo che la regola ammette. I nomi propri dentro un titolo sono il
    limite onesto qui, lo stesso che ha il linter: "Down syndrome" va bene e
    questo non lo sa. E' per quello che la regola e' un warning."""
    for i, text, _ in _units(doc, rule):
        words = text.split()
        wrong = None
        for word in words[1:]:
            bare = word.strip(OPENERS + CLOSERS)
            if not bare or not bare[0].isupper():
                continue
            if any(e.fullmatch(bare) for e in rule.exceptions):
                continue
            wrong = bare
            break
        if wrong is None:
            continue
        out.append(_finding(doc, i, rule, matched=text, start=0, end=len(text),
                            whole=True, message=fill(rule.message, tidy(text))))


def run_occurrence(doc: Document, rule: Rule, out: list[Finding]) -> None:
    """Piu' di cinque virgole in una frase, piu' di tre parentesi in un
    paragrafo: un conto, non un posto, quindi si illumina il pezzo intero."""
    pattern = _compile(f"(?:{'|'.join(rule.tokens)})", 0, rule.name)
    if pattern is None:
        return
    for i, text, offset in _units(doc, rule):
        # un elenco di riferimenti non e' prosa: `<sup>2,4,6,11,12</sup>` ha
        # quattro virgole che nessuno ha scritto come punteggiatura
        counted = len(pattern.findall(CITATION.sub("", text)))
        if counted <= (rule.maximum or 0):
            continue
        out.append(_finding(doc, i, rule, matched=text, start=offset,
                            end=offset + len(text), whole=True,
                            message=fill(rule.message, tidy(text))))


# Una parola, poi la stessa parola. Lettere obbligatorie: un elenco di misure
# ripete "-" e "±" tutto il giorno senza volerci dire niente.
REPEATED = regex.compile(r"(\b\S+)(\s+)\1\b", regex.I)
HAS_LETTER = regex.compile(r"[^\W\d_]")


def run_repetition(doc: Document, rule: Rule, out: list[Finding]) -> None:
    for i, text, offset in _units(doc, rule):
        for m in REPEATED.finditer(text):
            if not HAS_LETTER.search(m.group(1)):
                continue
            start, end = offset + m.start(), offset + m.end()
            if excused(rule, doc.blocks[i].text, start, end):
                continue
            out.append(_finding(doc, i, rule, matched=m.group(0), start=start, end=end,
                                message=fill(rule.message, tidy(m.group(1)))))


# ---------------------------------------------------------------------------
# le quattro scritte a mano
# ---------------------------------------------------------------------------

# Quattro delle regole del linter non sono pattern, e il loro elenco lo dice:
# le marca `script` e non stampa nessuna regex. Sono quelle che devono tenere
# a mente qualcosa mentre leggono - a che numero era l'ultima citazione, cosa
# e' gia' stato scritto per esteso, se questo grassetto e' l'unico che la guida
# ammette.
#
# Queste sono NOSTRE, non trascrizioni: il sorgente del linter non e' leggibile,
# quindi qui c'e' la regola come la descrive la loro documentazione. Dove i due
# potrebbero divergere, la risposta da credere e' la loro.

CITE_GROUP = regex.compile(r"<sup\b[^>]*>\s*([\d,\s-]+?)\s*</sup>", regex.I)


def cite_parts(text: str) -> list[dict]:
    """"1,2,4-7" come i numeri che vuol dire, e come i pezzi in cui e' scritto."""
    out = []
    for part in str(text).split(","):
        part = part.strip()
        if not part:
            continue
        span = regex.fullmatch(r"(\d+)\s*-\s*(\d+)", part)
        if span:
            a, b = int(span.group(1)), int(span.group(2))
            numbers = list(range(a, b + 1)) if b >= a else [a, b]
            out.append({"part": part, "dash": True, "from": a, "numbers": numbers})
            continue
        one = regex.fullmatch(r"\d+", part)
        if one:
            n = int(part)
            out.append({"part": part, "dash": False, "from": n, "numbers": [n]})
    return out


def _citation_order(doc: Document, rule: Rule, out: list[Finding]) -> None:
    """Le citazioni si numerano da dove compaiono per la prima volta. Quindi il
    primo numero non ancora usato e' sempre uno piu' del piu' alto che lo e'
    stato. Tutto il resto e' una bibliografia riordinata e un apice no."""
    nxt, seen = 1, set()
    for m in CITE_GROUP.finditer(doc.raw):
        wrong = None
        for part in cite_parts(m.group(1)):
            for n in part["numbers"]:
                if n in seen:
                    continue
                seen.add(n)
                if n != nxt and wrong is None:
                    wrong = n
                nxt = max(nxt, n + 1)
        if wrong is None:
            continue
        index = doc.block_at(m.start())
        out.append(_finding(
            doc, index, rule, matched=m.group(1), whole=True,
            message=f"{rule.message} '{m.group(1)}' introduce {wrong} "
                    f"prima che {max(1, wrong - 1)} sia stato usato."))


def _citation_syntax(doc: Document, rule: Rule, out: list[Finding]) -> None:
    """Due di fila sono una coppia e vogliono la virgola; tre o piu' sono un
    intervallo e vogliono il trattino. Si controllano tutt'e due i versi, perche'
    sbagliano nello stesso articolo: una bibliografia cresciuta a mano finisce
    "1,2,3,4", una sfoltita a mano finisce "3-4"."""
    for m in CITE_GROUP.finditer(doc.raw):
        parts = cite_parts(m.group(1))
        if not parts:
            continue
        says = None
        for part in parts:
            if part["dash"] and len(part["numbers"]) <= 2:
                joined = ",".join(str(n) for n in part["numbers"])
                says = (f"'{part['part']}' copre {len(part['numbers'])}, "
                        f"quindi vuole la virgola: '{joined}'")
                break
        if says is None:
            run: list[int] = []

            def flush(run=run):
                nonlocal says
                if len(run) >= 3 and says is None:
                    says = (f"'{','.join(str(n) for n in run)}' e' una serie di "
                            f"{len(run)}, quindi vuole il trattino: "
                            f"'{run[0]}-{run[-1]}'")
                run.clear()

            for part in parts:
                if part["dash"]:
                    flush()
                    continue
                if run and part["from"] != run[-1] + 1:
                    flush()
                run.append(part["from"])
            flush()
        if says is None:
            continue
        index = doc.block_at(m.start())
        out.append(_finding(doc, index, rule, matched=m.group(1), whole=True,
                            message=f"{rule.message} {says}."))


ACRONYM = regex.compile(r"\b[A-Z][A-Z0-9]+(?:-[A-Z0-9]+)*\b")
JOINING = frozenset("of and the in with for a to on".split())
WORDS = regex.compile(r"[a-z][a-z-]*")


def spells_out(acronym: str, words: list[str]) -> bool:
    """Queste parole scrivono per esteso quell'acronimo?

    La parte scomoda e' appaiare le lettere alle parole, perche' una parola
    composta ne fornisce piu' d'una - la E e la M di ADEM stanno tutt'e due
    dentro "encephalomyelitis". Quindi una lettera puo' essere presa dal mezzo
    della parola che ha preso quella prima, a meno che la parola DOPO non
    cominci con quella lettera, nel qual caso il diritto e' suo."""
    letters = [c for c in acronym.lower() if c.isalnum()]
    li = w = 0
    while li < len(letters):
        if w >= len(words):
            return False
        word = words[w]
        if not word or word[0] != letters[li]:
            if word in JOINING:
                w += 1
                continue
            return False
        taken, pos = 1, 1
        while li + taken < len(letters):
            following = words[w + 1] if w + 1 < len(words) else None
            if following and following[0] == letters[li + taken]:
                break
            at = word.find(letters[li + taken], pos)
            if at < 0:
                break
            pos, taken = at + 1, taken + 1
        li += taken
        w += 1
    return True


def _acronyms(doc: Document, rule: Rule, out: list[Finding]) -> None:
    """Un acronimo va scritto per esteso prima di appoggiarcisi, e lo si puo'
    fare nei due versi: "... syndrome (PRES)" oppure "PRES (... syndrome)".

    Dove non e' sicuro dice DEFINITO, non il contrario: questa e' la meta'
    locale di un controllo che l'API fa meglio, e un'accusa falsa costa a chi
    legge piu' di una mancata."""
    text = "\n".join(b.text for b in doc.blocks)
    defined: set[str] = set()
    for m in regex.finditer(r"([^.;:()]{0,160}?)\s*\(([^()]{1,120})\)", text):
        before, inside = m.group(1), m.group(2)
        for a in ACRONYM.findall(inside):
            if spells_out(a, WORDS.findall(before.lower())[-12:]):
                defined.add(a)
        for a in ACRONYM.findall(before):
            if spells_out(a, WORDS.findall(inside.lower())):
                defined.add(a)

    raised: set[str] = set()
    for i, block in enumerate(doc.blocks):
        for m in ACRONYM.finditer(block.text):
            word = m.group(0)
            # L'altra meta' di quello che la regola ammette: un acronimo
            # "molto comune (per esempio CT o MRI)". Il linter ha un vocabolario
            # per quello e non lo pubblica, quindi `common` nel file e' nostro.
            if word.upper() in rule.common:
                continue
            if word in defined or word in raised:
                continue
            raised.add(word)
            out.append(_finding(doc, i, rule, matched=word, start=m.start(),
                                end=m.end(), message=fill(rule.message, word)))


def _strong(doc: Document, rule: Rule, out: list[Finding]) -> None:
    """Il grassetto ha tre mestieri e nessun altro: il nome dell'articolo nella
    riga di apertura, il nome di una persona in History and etymology, e
    l'attacco di una voce di elenco - dove i due punti dopo NON sono in
    grassetto, che e' una regola per conto suo."""
    for m in regex.finditer(r"<strong>(.*?)</strong>", doc.raw, regex.S | regex.I):
        index = doc.block_at(m.start())
        if index == 0:
            continue                                  # l'apertura nomina l'articolo
        after = doc.raw[m.end():m.end() + 24]
        if regex.match(r"\s*:", after):
            continue                                  # l'attacco di una voce
        if regex.match(r"\s*\((?:fl\. )?\d{4}", after):
            continue                                  # una persona, con le sue date
        matched = plain(m.group(1))
        if not matched:
            continue
        out.append(_finding(doc, index, rule, matched=matched,
                            message=fill(rule.message, tidy(matched)),
                            whole=flat(matched) == flat(doc.blocks[index].text)))


SCRIPTED = {
    "CitationOrder": _citation_order,
    "CitationSyntax": _citation_syntax,
    "Acronyms": _acronyms,
    "Strong": _strong,
}

RUNNERS = {
    "existence": run_existence,
    "substitution": run_substitution,
    "capitalization": run_capitalization,
    "occurrence": run_occurrence,
    "repetition": run_repetition,
}


# ---------------------------------------------------------------------------
# il giro
# ---------------------------------------------------------------------------

def lint_html(html: str, *, compiled: list[Rule] | None = None) -> list[Finding]:
    """Tutte le regole su tutti i blocchi, in ordine di lettura.

    Una regola che esplode si porta via se stessa e nient'altro: sono
    settantanove, ed e' meglio perderne una che perdere la risposta."""
    doc = read_document(html)
    if not doc.blocks:
        return []

    out: list[Finding] = []
    for rule in (compiled if compiled is not None else rules()):
        try:
            if rule.kind == "script":
                runner = SCRIPTED.get(rule.name)
                if runner is not None:
                    runner(doc, rule, out)
            else:
                runner = RUNNERS.get(rule.kind)
                if runner is not None:
                    runner(doc, rule, out)
        except Exception as exc:                      # noqa: BLE001
            print(f"[lint] regola fallita: {rule.name} ({exc})")

    out.sort(key=lambda f: (f.block, f.at, SEVERITY_ORDER.get(f.severity, 9), f.check))
    return out


# ---------------------------------------------------------------------------
# ...e a che riga del markdown corrisponde
# ---------------------------------------------------------------------------

MD_NOISE = regex.compile(r"\[@[^\]]*\]|[#*_`>]|^\s*[-+*]\s+|^\s*\d+\.\s+")


def _bare(line: str) -> str:
    return flat(MD_NOISE.sub(" ", line))


def attach_lines(findings: list[Finding], body_md: str) -> list[Finding]:
    """La riga del markdown da cui viene ogni segnalazione.

    Si linta l'HTML, ma si CORREGGE il markdown, quindi una segnalazione che
    non sa dire dove guardare e' mezza inutile. L'abbinamento e' per testo e va
    avanti: si cerca il blocco fra le righe non ancora assegnate, cosi' un
    paragrafo ripetuto due volte finisce sulla seconda copia la seconda volta.
    Chi non si trova resta senza riga, che e' meglio di una riga sbagliata."""
    lines = str(body_md or "").splitlines()
    bare = [_bare(line) for line in lines]
    cursor = 0
    for finding in findings:
        # I due lati si confrontano tutt'e due senza citazioni: nel markdown
        # c'e' `[@27859258]`, nell'HTML c'e' gia' il numero, e basta uno dei due
        # a far fallire il confronto.
        wanted = flat(finding.bare or finding.snippet)
        if not wanted:
            continue
        found = None
        for start in (cursor, 0):
            for n in range(start, len(lines)):
                if bare[n] and (bare[n] in wanted or wanted in bare[n]):
                    found = n
                    break
            if found is not None:
                break
        if found is None:
            continue
        finding.line = found + 1
        cursor = found
    return findings


def tally(findings: list[Finding]) -> dict[str, int]:
    counts = {"error": 0, "warning": 0, "suggestion": 0}
    for finding in findings:
        if not finding.hushed:
            counts[finding.severity] = counts.get(finding.severity, 0) + 1
    return counts
