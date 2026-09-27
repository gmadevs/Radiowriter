"""I colori e i caratteri dell'app: uno scuro e uno chiaro, scelti per leggere.

L'app si tiene aperta ore a leggere abstract, e la scelta giusta dipende dalla
stanza: di sera lo scuro affatica meno, di giorno e con molta luce il chiaro si
legge meglio - e chi ha un po' di astigmatismo vede il testo chiaro su fondo
scuro "sbavare". Quindi tutt'e due, e di partenza segue il sistema operativo;
si cambia dal menu in alto a destra, Settings.

Lo scuro viene da Radiouploader (le due app si usano una dopo l'altra) ma e'
ammorbidito per la lettura lunga: il fondo e' un filo meno nero e il testo un
filo meno bianco, perche' il contrasto massimo e' quello che abbaglia. Resta
13,6:1 - il minimo WCAG per il testo e' 4,5. Il chiaro non e' bianco puro ma
carta: #fcfbf9, con il testo quasi nero.

L'accento e' un blu piu' scuro di quello di Radiouploader: il testo dei
pulsanti primari Streamlit lo scrive in bianco, e bianco su #4c9aff fa 2,9:1,
illeggibile. Su #2563eb fa 5,2:1. I link invece hanno un blu loro per tema,
chiaro sullo scuro e scuro sul chiaro, perche' nessun blu solo va bene su
tutt'e due i fondi.

Stanno qui e non in un `.streamlit/config.toml` perche' Streamlit quel file lo
cerca nella cartella da cui si lancia, e chi installa il pacchetto la lancia da
dove capita. `__main__` li passa al server insieme agli altri flag.
"""

from __future__ import annotations

UI_FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"

# Il carattere di lettura, per gli abstract. Un serif da schermo: Charter su
# macOS, Sitka o Cambria su Windows, Georgia dappertutto. Nessun font scaricato
# - l'app funziona anche senza rete, e un font che arriva da Google la
# obbligherebbe a chiedere.
READING_FONTS = {
    "serif": "Charter, 'Bitstream Charter', 'Sitka Text', Cambria, Georgia, serif",
    "sans": UI_FONT,
}

PRIMARY = "#2563eb"

DARK = {
    "bg": "#15181c",
    "sidebar": "#1b1f24",
    "widget": "#242a31",
    "border": "#2f363e",
    "text": "#dce2e8",
    "link": "#7ab4ff",
    "red": "#f07171",
    "orange": "#e3a64f",
    "yellow": "#e3c14f",
    "green": "#58c48a",
    "blue": "#7ab4ff",
}

LIGHT = {
    "bg": "#fcfbf9",
    "sidebar": "#f4f2ee",
    "widget": "#efede9",
    "border": "#dedad3",
    "text": "#1d2127",
    "link": "#1d5fd1",
    "red": "#b93434",
    "orange": "#9a5b00",
    "yellow": "#8a6d00",
    "green": "#1b7f45",
    "blue": "#1d5fd1",
}

# I quartili, verde Q1 e rosso Q4. Un tono base solo, che il CSS mescola al
# colore del testo (`color-mix(... currentColor)`): sul fondo scuro il testo e'
# chiaro e il verde si schiarisce, sul fondo chiaro si scurisce. Serve che lo
# faccia il browser: il tema lo si cambia dal menu, e lo script lo viene a
# sapere solo al clic dopo - per un attimo i badge avrebbero i colori dell'altro
# tema. Con il 60% di tono base tutti stanno sopra 4,5:1 su tutt'e due i fondi.
QUARTILE_BASE = {
    "Q1": "#2f9e63",
    "Q2": "#8a9a2a",
    "Q3": "#c98a2a",
    "Q4": "#d9534f",
}


def tinted(base: str) -> str:
    """Le due dichiarazioni CSS di un badge colorato: testo e fondo."""
    return (f"color: color-mix(in srgb, {base} 60%, currentColor); "
            f"background: color-mix(in srgb, {base} 14%, transparent);")


def _palette(prefix: str, p: dict) -> dict:
    return {
        f"{prefix}.primaryColor": PRIMARY,
        f"{prefix}.backgroundColor": p["bg"],
        f"{prefix}.secondaryBackgroundColor": p["widget"],
        f"{prefix}.textColor": p["text"],
        f"{prefix}.borderColor": p["border"],
        f"{prefix}.linkColor": p["link"],
        f"{prefix}.redColor": p["red"],
        f"{prefix}.orangeColor": p["orange"],
        f"{prefix}.yellowColor": p["yellow"],
        f"{prefix}.greenColor": p["green"],
        f"{prefix}.blueColor": p["blue"],
        f"{prefix}.sidebar.backgroundColor": p["sidebar"],
        f"{prefix}.sidebar.secondaryBackgroundColor": p["widget"],
        f"{prefix}.sidebar.borderColor": p["border"],
    }


# Le opzioni `theme.*` di Streamlit. Quelle senza tema (carattere, raggi) valgono
# per tutt'e due. Il corpo e' 16px e non 15: e' la misura a cui un paragrafo si
# legge senza avvicinarsi allo schermo.
OPTIONS = {
    "theme.font": UI_FONT,
    "theme.baseFontSize": 16,
    "theme.baseRadius": "8px",
    "theme.buttonRadius": "8px",
    "theme.showWidgetBorder": True,
    "theme.showSidebarBorder": True,
    **_palette("theme.light", LIGHT),
    **_palette("theme.dark", DARK),
}
