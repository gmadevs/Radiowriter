"""Le schede degli articoli: i badge, l'abstract, e il loro CSS.

Niente Streamlit qui dentro. Le stesse funzioni disegnano le schede dei
risultati di ricerca, che stanno nell'app Streamlit, e quelle del banco dello
Screening (`bench.py`), che e' una pagina web servita a parte: scritte in un
posto solo, le due non possono mostrare lo stesso articolo in due modi.

Tutto quello che esce da qui e' HTML gia' escapato, pronto per essere messo
nella pagina cosi' com'e'.
"""

from __future__ import annotations

import html
import math
import re

from radiowriter import highlight
from radiowriter import theme
from radiowriter import unpaywall as upw


def number(value) -> float | None:
    """Un numero da una cella, o None. Le colonne che arrivano da una LEFT JOIN
    senza corrispondenza tornano come NaN, non come None, e NaN e' un float che
    passa qualsiasi controllo di verita': senza questo una rivista non
    agganciata si stamperebbe addosso un badge che dice `nan`."""
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(out) else out


# Tipi di pubblicazione che non dicono niente a chi sta screenando: "Journal
# Article" ce l'hanno quasi tutti, e da chi era finanziato uno studio non e'
# una cosa che si guarda scorrendo un elenco. Occupavano tre righe di badge per
# scheda e coprivano quelli che contano - Review, Meta-Analysis, Guideline.
NOISY_TYPES = {"journal article", "english abstract", "comparative study",
               "validation study", "historical article"}


def useful_types(text: str, limit: int = 3) -> list[str]:
    out = []
    for kind in (t.strip() for t in clean(text).split(";")):
        low = kind.lower()
        if not kind or low in NOISY_TYPES or low.startswith("research support"):
            continue
        if kind not in out:
            out.append(kind)
    return out[:limit]


def citation_badge(total, influential, per_year) -> str:
    """Un badge solo per le citazioni, invece di tre.

    Tre numeri messi in fila su tre pillole diverse si leggono come tre fatti;
    sono lo stesso fatto guardato da tre lati, e su una riga sola si confrontano
    fra articoli molto piu' in fretta."""
    total = number(total)
    if total is None:
        return ""
    bits = [f"{int(total):,} cites"]
    infl = number(influential)
    if infl:
        bits.append(f"{int(infl)} infl")
    rate = number(per_year)
    if rate:
        bits.append(f"{rate:.1f}/yr")
    return "<span>" + html.escape(" · ".join(bits)) + "</span>"


def journal_badges(metric) -> list[str]:
    """I badge della rivista, gia' in HTML: quartile colorato, SJR, citazioni.

    Vuoto quando la rivista non e' agganciata. Una che in SCImago non c'e' -
    Cureus, medRxiv, meta' dei giornali di case report - non ha un quartile, e
    dargliene uno grigio direbbe che il dato e' scarso invece che assente."""
    if metric is None:
        return []
    out = []
    quartile = clean(metric["quartile"])
    sjr = number(metric["sjr"])
    cites = number(metric["cites_per_doc"])
    if quartile:
        text = f"{quartile} · SJR {sjr:.2f}" if sjr is not None else quartile
        out.append(f'<span class="{quartile.lower()}">{html.escape(text)}</span>')
    elif sjr is not None:
        out.append(f"<span>SJR {sjr:.2f}</span>")
    if cites is not None:
        out.append(f"<span>{cites:.1f} cites/doc (2y)</span>")
    return out


def oa_badge(status) -> str:
    """Il badge dell'open access. Verde solo quando il full text c'e' davvero."""
    text = upw.label(status)
    if not text:
        return ""
    css = "oa" if (status or "").lower() not in ("closed", "unknown") else "oa-closed"
    return f'<span class="{css}">{html.escape(text)}</span>'


def clean(value) -> str:
    """Testo sicuro da una cella: le colonne aggiunte dopo sono NULL sui record
    storici, e pandas le restituisce come NaN (che stampato diventa 'nan')."""
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() in ("nan", "none", "<na>") else text


# Un'etichetta di sezione dentro un abstract scritto tutto di seguito: parole
# maiuscole e due punti subito dopo la fine di una frase. I record scaricati
# adesso le hanno gia' su paragrafi separati; quelli importati da un `.nbib`
# arrivano in un blocco solo, "...criteria. RESULTS: 56 incisors...".
INLINE_LABEL = re.compile(r"(?<=[.!?])\s+(?=[A-Z][A-Z0-9 ,/&()-]{2,48}:\s)")
LEADING_LABEL = re.compile(r"^([A-Z][A-Za-z0-9 ,/&()'-]{1,48}):\s+(.+)$", re.S)


def abstract_html(text, rx=None) -> str:
    """L'abstract come HTML da leggere: un paragrafo per sezione, l'etichetta
    sopra, tutto il resto escapato, e i termini di `rx` evidenziati.

    Prima passava da `st.write`, cioe' dal Markdown di Streamlit, che un
    abstract lo interpreta: `$1 M ... $780,000` diventava una formula LaTeX e
    `T2* ... L*/a*/b*` un corsivo a caso. Un abstract e' testo, non sintassi."""
    text = clean(text)
    if not text or text == "No abstract available.":
        return '<div class="abstract"><p class="none">No abstract available.</p></div>'
    paragraphs = []
    for block in text.split("\n\n"):
        paragraphs.extend(p for p in INLINE_LABEL.split(block.strip()) if p)
    out = []
    for para in paragraphs:
        m = LEADING_LABEL.match(para)
        # "Label: testo" solo se l'etichetta e' corta: una frase che contiene
        # due punti non e' un'intestazione
        if m and len(m.group(1).split()) <= 5:
            out.append(f'<p><span class="lbl">{html.escape(m.group(1))}</span>'
                       f'{highlight.mark(m.group(2), rx)}</p>')
        else:
            out.append(f"<p>{highlight.mark(para, rx)}</p>")
    return '<div class="abstract">' + "".join(out) + "</div>"


def css(title_rem: float, reading_rem: float, reading_font: str) -> str:
    """Il CSS delle schede, per le misure e il carattere scelti nelle
    impostazioni. Scritto per andare bene su tutt'e due i temi senza sapere
    quale c'e': grigi fatti di trasparenza e testo secondario fatto di
    opacita'."""
    quartile_css = " ".join(
        f".art-badges span.{q.lower()} {{ {theme.tinted(base)} "
        f"border-color: transparent; font-weight: 600; }}"
        for q, base in theme.QUARTILE_BASE.items())
    return f"""
      .art-title {{
        font-size: {title_rem}rem;
        font-weight: 650;
        line-height: 1.3;
        letter-spacing: -.005em;
        margin: 0 0 .3rem 0;
        max-width: 60rem;
        text-wrap: pretty;
      }}
      .art-meta {{ font-size: .86rem; opacity: .72; margin-bottom: .35rem;
                   line-height: 1.45; max-width: 60rem; }}
      .art-badges {{ font-size: .78rem; margin-bottom: .35rem;
                     display: flex; flex-wrap: wrap; gap: .3rem; }}
      .art-badges span {{
        display: inline-block; padding: .05rem .5rem; margin: 0;
        border-radius: 999px; background: rgba(128,128,128,.12);
        border: 1px solid rgba(128,128,128,.22);
        white-space: nowrap;
      }}
      /* Il quartile e' l'unica cosa in questa riga che si legge di colpo:
         verde Q1, rosso Q4, come un semaforo. Gli altri badge restano grigi
         apposta - se fossero colorati anche loro non si vedrebbe piu' niente. */
      {quartile_css}
      .art-badges span.oa {{ {theme.tinted(theme.QUARTILE_BASE["Q1"])}
                             border-color: transparent; font-weight: 600; }}
      .art-badges span.oa-closed {{ opacity: .75; }}
      /* L'abstract e' il testo che si legge davvero, e per questo ha regole sue.
         Una riga lunga al massimo una settantina di caratteri: oltre, l'occhio
         che torna a capo perde la riga dopo - e nella pagina larga di
         Streamlit una riga arrivava a duecento. Interlinea larga, carattere di
         lettura, e ogni sezione (BACKGROUND, METHODS...) un paragrafo suo con
         l'etichetta sopra, invece di un blocco unico da scandire a occhio. */
      .abstract {{
        font-family: {reading_font};
        font-size: {reading_rem}rem; line-height: 1.65;
        max-width: 70ch; text-wrap: pretty;
        font-variant-numeric: lining-nums;
      }}
      .abstract p {{ margin: 0 0 .8em 0; }}
      .abstract p:last-child {{ margin-bottom: .2em; }}
      .abstract .lbl {{
        display: block; font-family: {theme.UI_FONT};
        font-size: .7rem; font-weight: 700; letter-spacing: .07em;
        text-transform: uppercase; opacity: .6; margin-bottom: .1em;
      }}
      .abstract .none {{ opacity: .6; font-style: italic; }}
      /* I termini cercati. Un giallo evidenziatore trasparente, cosi' sul
         chiaro e sullo scuro il testo sotto resta il suo e resta leggibile. */
      .abstract mark, .art-title mark {{
        background: color-mix(in srgb, #f2c230 38%, transparent);
        color: inherit; border-radius: 3px; padding: 0 .08em;
      }}
    """
