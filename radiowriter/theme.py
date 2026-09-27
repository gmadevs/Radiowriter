"""I colori e le forme dell'app, gli stessi di Radiouploader.

Le due app si usano una dopo l'altra - si scrive l'articolo qui, si carica il
caso di la' - e passare da una finestra scura con l'accento blu a una bianca
con l'accento rosso di Streamlit faceva sembrare due cose che non si
conoscono. I valori sono presi da `src/renderer/src/styles.css` di
Radiouploader, e i nomi di `TOKENS` sono le sue variabili CSS.

Stanno qui e non in un `.streamlit/config.toml` perche' Streamlit quel file lo
cerca nella cartella da cui si lancia, e chi installa il pacchetto la lancia da
dove capita: un tema che funziona solo dentro il repository non e' un tema.
`__main__` li passa al server insieme agli altri flag.
"""

from __future__ import annotations

TOKENS = {
    "bg": "#111418",
    "panel": "#191e24",
    "panel-2": "#212830",
    "border": "#2c343e",
    "text": "#e7edf3",
    "muted": "#93a1b0",
    "accent": "#4c9aff",
    "accent-ink": "#0b1220",
    "warn": "#e0a44a",
    "danger": "#e06c6c",
    "ok": "#5bc98c",
}

FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"

# Le opzioni `theme.*` di Streamlit. Il rosso, il verde e il giallo dei suoi
# avvisi sono ridefiniti anche loro: lasciati di default stonano accanto
# all'accento, e un `st.warning` giallo limone su fondo quasi nero si legge
# come un errore di disegno, non come un avviso.
OPTIONS = {
    "theme.base": "dark",
    "theme.primaryColor": TOKENS["accent"],
    "theme.backgroundColor": TOKENS["bg"],
    "theme.secondaryBackgroundColor": TOKENS["panel-2"],
    "theme.textColor": TOKENS["text"],
    "theme.borderColor": TOKENS["border"],
    "theme.linkColor": TOKENS["accent"],
    "theme.redColor": TOKENS["danger"],
    "theme.orangeColor": TOKENS["warn"],
    "theme.yellowColor": TOKENS["warn"],
    "theme.greenColor": TOKENS["ok"],
    "theme.blueColor": TOKENS["accent"],
    "theme.font": FONT,
    "theme.baseFontSize": 15,
    "theme.baseRadius": "8px",
    "theme.buttonRadius": "8px",
    "theme.showWidgetBorder": True,
    "theme.sidebar.backgroundColor": TOKENS["panel"],
    "theme.sidebar.secondaryBackgroundColor": TOKENS["panel-2"],
    "theme.sidebar.borderColor": TOKENS["border"],
    "theme.showSidebarBorder": True,
}
