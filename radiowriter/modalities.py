"""Le modalita' di imaging, ognuna scritta come la scrive la letteratura.

La modalita' e' uno dei tre concetti di cui e' fatta una ricerca seria - la
malattia, LA MODALITA', il tipo di studio - ed e' quello che si sbaglia piu'
facilmente, perche' ogni modalita' ha tre o quattro nomi e nessuno li usa tutti.
Chi cerca `ultrasound` perde meta' dei lavori che dicono `sonography`; chi cerca
`MRI` perde quelli che scrivono solo `magnetic resonance`; e nessuno dei due
prende quello che sta indicizzato sotto il descrittore MeSH e non lo dice mai
nell'abstract.

Quindi ogni voce ha due liste, come in `strategies`:

- `mesh`: vocabolario controllato. Preciso, ma indicizza solo quello che i
  curatori del MEDLINE hanno gia' indicizzato - un lavoro di tre mesi fa non
  c'e' ancora.
- `keywords`: le parole nel titolo e nell'abstract, tutte le varianti comprese
  quelle britanniche (`oesophageal`), le sigle (`TOE`, `CEUS`, `DECT`) e i modi
  in cui gli autori scrivono davvero.

Scegliendone piu' d'una si uniscono in **OR**: chiedere insieme TC ed ecografia
vuol dire volere l'una O l'altra. Un lavoro che le usi tutte e due esiste, ma
chiederlo in AND e' quasi sempre il modo di non trovare niente - e chi lo vuole
davvero mette due blocchi.

ATTENZIONE ALLE SIGLE CORTE. `US` per ultrasound, `MR` per magnetic resonance e
`CT` da sole sono ambigue in `[tiab]`: `US` prende ogni articolo americano che
scriva "US population", `MR` ogni "Mr Smith". Dove la sigla e' troppo corta per
stare in abstract si limita al titolo con `[ti]`, che e' molto piu' pulito, e la
copertura la recuperano il descrittore MeSH e le forme lunghe.

DA DOVE VENGONO I DESCRITTORI. Dal MeSH, e sono verificati uno per uno contro
PubMed da `check_mesh_live.py`: un descrittore inventato non da' zero
risultati, finisce in `errorlist` e non lo si vedrebbe mai.

QUI NON CI SONO SOTTOTITOLI DI MODALITA', e non e' una dimenticanza. Il MeSH
nel 2011 ha fuso `radiography`, `ultrasonography` e `radionuclide imaging` in
un solo sottotitolo, `diagnostic imaging`, e PubMed mappa i vecchi nomi su
quello: chiesti uno per uno danno tutti lo stesso insieme, 1.665.656 record, e
la differenza fra due qualunque di loro e' zero in entrambe le direzioni.
Quindi `ultrasonography[sh]` non vuol dire "ecografia": vuol dire "questo
lavoro contiene imaging", e da solo tira dentro 376.616 lavori di TC. Sembra
che restringa e invece allarga, che e' il modo peggiore di sbagliare una query.
I descrittori separano davvero - `"Ultrasonography"[Mesh]` lascia fuori la TC -
e quindi si usano solo quelli. `"diagnostic imaging"[sh]` resta, ma solo in
`Any imaging (broad)`, dove e' quello che si vuole dire.
"""

from __future__ import annotations

# Le stesse tre modalita' di `strategies`, e per la stessa ragione: le due liste
# rispondono a esigenze diverse e a volte una sola e' quella che serve.
MODES = {
    "both": "MeSH + keywords",
    "mesh": "MeSH only",
    "keywords": "Keywords only",
}

# nome -> {"mesh": [...], "keywords": [...]}
#
# I nomi sono quelli con cui un radiologo le chiama, non quelli del MeSH: si
# scelgono da un elenco, e un elenco che dice "Tomography, X-Ray Computed" al
# posto di "CT" costringe a tradurre mentalmente ogni voce.
MODALITIES: dict[str, dict[str, list[str]]] = {
    # --- radiologia tradizionale -------------------------------------------
    "Radiograph (plain film)": {
        "mesh": ['"Radiography"[Mesh]'],
        "keywords": [
            'radiograph*[tiab]',
            '"plain film*"[tiab]',
            '"plain radiograph*"[tiab]',
            '"x-ray*"[tiab]',
            'roentgen*[tiab]',
        ],
    },
    "Fluoroscopy": {
        "mesh": ['"Fluoroscopy"[Mesh]'],
        "keywords": [
            'fluoroscop*[tiab]',
            '"screening examination*"[tiab]',
            '"real time imaging"[tiab]',
        ],
    },
    "Barium / contrast swallow and enema": {
        "mesh": ['"Barium Sulfate"[Mesh]', '"Fluoroscopy"[Mesh]', '"Enema"[Mesh]'],
        "keywords": [
            'barium[tiab]',
            '"contrast swallow"[tiab]',
            '"barium swallow"[tiab]',
            '"barium meal"[tiab]',
            '"barium enema"[tiab]',
            'oesophagram[tiab]',
            'esophagram[tiab]',
            '"small bowel follow through"[tiab]',
            'gastrografin[tiab]',
        ],
    },
    "Bone densitometry (DXA)": {
        "mesh": ['"Absorptiometry, Photon"[Mesh]', '"Bone Density"[Mesh]'],
        "keywords": [
            'densitometr*[tiab]',
            'DXA[tiab]',
            'DEXA[tiab]',
            '"bone mineral density"[tiab]',
            'absorptiometr*[tiab]',
        ],
    },

    # --- TC -----------------------------------------------------------------
    "CT": {
        "mesh": [
            '"Tomography, X-Ray Computed"[Mesh]',
            '"Multidetector Computed Tomography"[Mesh]',
        ],
        "keywords": [
            '"computed tomography"[tiab]',
            '"computerised tomography"[tiab]',
            '"computerized tomography"[tiab]',
            'CT[ti]',
            'MDCT[tiab]',
            'MSCT[tiab]',
            '"CAT scan*"[tiab]',
        ],
    },
    "CT angiography": {
        "mesh": ['"Computed Tomography Angiography"[Mesh]'],
        "keywords": [
            '"CT angiograph*"[tiab]',
            'CTA[tiab]',
            '"computed tomography angiograph*"[tiab]',
            '"CT venograph*"[tiab]',
            'CTV[tiab]',
        ],
    },
    "Dual-energy and photon-counting CT": {
        "mesh": [
            '"Radiography, Dual-Energy Scanned Projection"[Mesh]',
            '"Tomography, X-Ray Computed"[Mesh]',
        ],
        "keywords": [
            '"dual energy"[tiab]',
            '"dual-energy"[tiab]',
            'DECT[tiab]',
            '"spectral CT"[tiab]',
            '"photon counting"[tiab]',
            '"photon-counting"[tiab]',
            '"material decomposition"[tiab]',
        ],
    },
    "Cone-beam CT": {
        "mesh": ['"Cone-Beam Computed Tomography"[Mesh]'],
        "keywords": [
            '"cone beam"[tiab]',
            '"cone-beam"[tiab]',
            'CBCT[tiab]',
        ],
    },
    "CT perfusion": {
        "mesh": ['"Perfusion Imaging"[Mesh]', '"Tomography, X-Ray Computed"[Mesh]'],
        "keywords": [
            '"CT perfusion"[tiab]',
            'CTP[tiab]',
            '"perfusion CT"[tiab]',
            '"cerebral blood flow"[tiab]',
            '"cerebral blood volume"[tiab]',
        ],
    },

    # --- RM -----------------------------------------------------------------
    "MRI": {
        "mesh": ['"Magnetic Resonance Imaging"[Mesh]'],
        "keywords": [
            'MRI[tiab]',
            '"magnetic resonance"[tiab]',
            'MR[ti]',
            '"MR imaging"[tiab]',
            'T2-weighted[tiab]',
            'T1-weighted[tiab]',
        ],
    },
    "Diffusion-weighted imaging": {
        "mesh": [
            '"Diffusion Magnetic Resonance Imaging"[Mesh]',
            '"Diffusion Tensor Imaging"[Mesh]',
        ],
        "keywords": [
            'DWI[tiab]',
            '"diffusion weighted"[tiab]',
            '"diffusion-weighted"[tiab]',
            '"apparent diffusion coefficient"[tiab]',
            'ADC[tiab]',
            'tractograph*[tiab]',
        ],
    },
    "MR angiography": {
        "mesh": ['"Magnetic Resonance Angiography"[Mesh]'],
        "keywords": [
            '"MR angiograph*"[tiab]',
            'MRA[tiab]',
            '"magnetic resonance angiograph*"[tiab]',
            '"time of flight"[tiab]',
            '"MR venograph*"[tiab]',
        ],
    },
    "MR spectroscopy": {
        "mesh": ['"Magnetic Resonance Spectroscopy"[Mesh]'],
        "keywords": [
            '"MR spectroscop*"[tiab]',
            'MRS[tiab]',
            '"magnetic resonance spectroscop*"[tiab]',
            '"N-acetylaspartate"[tiab]',
            '"choline peak"[tiab]',
        ],
    },
    "Functional MRI": {
        "mesh": ['"Magnetic Resonance Imaging"[Mesh]', '"Brain Mapping"[Mesh]'],
        "keywords": [
            'fMRI[tiab]',
            '"functional MRI"[tiab]',
            '"functional magnetic resonance"[tiab]',
            'BOLD[tiab]',
            '"resting state"[tiab]',
        ],
    },
    "MR perfusion": {
        "mesh": ['"Perfusion Imaging"[Mesh]', '"Magnetic Resonance Imaging"[Mesh]'],
        "keywords": [
            '"MR perfusion"[tiab]',
            '"perfusion weighted"[tiab]',
            '"dynamic susceptibility"[tiab]',
            'DSC[tiab]',
            'DCE[tiab]',
            '"arterial spin label*"[tiab]',
        ],
    },

    # --- ecografia ----------------------------------------------------------
    "Ultrasound": {
        "mesh": ['"Ultrasonography"[Mesh]'],
        "keywords": [
            'ultraso*[tiab]',
            'sonograph*[tiab]',
            'echograph*[tiab]',
            'US[ti]',
            'B-mode[tiab]',
        ],
    },
    "Doppler ultrasound": {
        "mesh": [
            '"Ultrasonography, Doppler"[Mesh]',
            '"Ultrasonography, Doppler, Color"[Mesh]',
            '"Ultrasonography, Doppler, Duplex"[Mesh]',
        ],
        "keywords": [
            'doppler[tiab]',
            '"colour doppler"[tiab]',
            '"color doppler"[tiab]',
            '"duplex ultraso*"[tiab]',
            '"power doppler"[tiab]',
            '"spectral waveform*"[tiab]',
            '"resistive index"[tiab]',
        ],
    },
    "Contrast-enhanced ultrasound": {
        "mesh": ['"Contrast Media"[Mesh]', '"Ultrasonography"[Mesh]'],
        "keywords": [
            'CEUS[tiab]',
            '"contrast enhanced ultraso*"[tiab]',
            '"contrast-enhanced ultraso*"[tiab]',
            'microbubble*[tiab]',
            'SonoVue[tiab]',
        ],
    },
    "Elastography": {
        "mesh": ['"Elasticity Imaging Techniques"[Mesh]'],
        "keywords": [
            'elastograph*[tiab]',
            '"shear wave"[tiab]',
            '"transient elastograph*"[tiab]',
            'fibroscan[tiab]',
            '"tissue stiffness"[tiab]',
        ],
    },
    "Echocardiography": {
        "mesh": ['"Echocardiography"[Mesh]', '"Echocardiography, Doppler"[Mesh]'],
        "keywords": [
            'echocardiograph*[tiab]',
            '"cardiac ultraso*"[tiab]',
            'TTE[tiab]',
            '"transthoracic echo*"[tiab]',
        ],
    },
    "Transoesophageal echocardiography": {
        "mesh": ['"Echocardiography, Transesophageal"[Mesh]'],
        "keywords": [
            'transoesophageal[tiab]',
            'transesophageal[tiab]',
            'TOE[tiab]',
            'TEE[tiab]',
        ],
    },
    "Endoscopic ultrasound": {
        "mesh": ['"Endosonography"[Mesh]'],
        "keywords": [
            'endosonograph*[tiab]',
            '"endoscopic ultraso*"[tiab]',
            'EUS[tiab]',
            '"endorectal ultraso*"[tiab]',
        ],
    },
    "Antenatal ultrasound": {
        "mesh": ['"Ultrasonography, Prenatal"[Mesh]'],
        "keywords": [
            'antenatal[tiab]',
            'prenatal[tiab]',
            '"obstetric ultraso*"[tiab]',
            '"fetal ultraso*"[tiab]',
            '"foetal ultraso*"[tiab]',
            '"nuchal translucency"[tiab]',
        ],
    },

    # --- medicina nucleare --------------------------------------------------
    "Nuclear medicine and scintigraphy": {
        "mesh": [
            '"Nuclear Medicine"[Mesh]',
            '"Radionuclide Imaging"[Mesh]',
        ],
        "keywords": [
            'scintigraph*[tiab]',
            '"nuclear medicine"[tiab]',
            'radiotracer*[tiab]',
            'radionuclide*[tiab]',
            'radiopharmaceutical*[tiab]',
            'technetium[tiab]',
        ],
    },
    "SPECT": {
        "mesh": ['"Tomography, Emission-Computed, Single-Photon"[Mesh]'],
        "keywords": [
            'SPECT[tiab]',
            '"single photon emission"[tiab]',
            '"SPECT/CT"[tiab]',
        ],
    },
    "PET": {
        "mesh": ['"Positron-Emission Tomography"[Mesh]'],
        "keywords": [
            'PET[tiab]',
            '"positron emission"[tiab]',
            'FDG[tiab]',
            '"standardised uptake"[tiab]',
            '"standardized uptake"[tiab]',
        ],
    },
    "PET-CT": {
        "mesh": ['"Positron Emission Tomography Computed Tomography"[Mesh]'],
        "keywords": [
            '"PET-CT"[tiab]',
            '"PET/CT"[tiab]',
            '"PET CT"[tiab]',
        ],
    },
    "PET-MRI": {
        "mesh": ['"Multimodal Imaging"[Mesh]', '"Positron-Emission Tomography"[Mesh]'],
        "keywords": [
            '"PET-MRI"[tiab]',
            '"PET/MRI"[tiab]',
            '"PET/MR"[tiab]',
            '"hybrid imaging"[tiab]',
        ],
    },

    # --- vascolare e interventistica ---------------------------------------
    "Catheter angiography (DSA)": {
        "mesh": ['"Angiography"[Mesh]', '"Angiography, Digital Subtraction"[Mesh]'],
        "keywords": [
            'angiograph*[tiab]',
            'DSA[tiab]',
            '"digital subtraction"[tiab]',
            'arteriograph*[tiab]',
            '"catheter angiograph*"[tiab]',
        ],
    },
    "Venography": {
        "mesh": ['"Phlebography"[Mesh]'],
        "keywords": [
            'venograph*[tiab]',
            'phlebograph*[tiab]',
            '"venous phase"[tiab]',
        ],
    },
    "Lymphangiography": {
        "mesh": ['"Lymphography"[Mesh]'],
        "keywords": [
            'lymphangiograph*[tiab]',
            'lymphograph*[tiab]',
            'lymphoscintigraph*[tiab]',
        ],
    },
    "Interventional radiology": {
        "mesh": [
            '"Radiology, Interventional"[Mesh]',
            '"Radiography, Interventional"[Mesh]',
            '"Embolization, Therapeutic"[Mesh]',
        ],
        "keywords": [
            '"interventional radiolog*"[tiab]',
            '"image guided"[tiab]',
            '"image-guided"[tiab]',
            'emboli[tiab]',
            'embolisation[tiab]',
            'embolization[tiab]',
            '"percutaneous"[tiab]',
        ],
    },
    "Image-guided biopsy and drainage": {
        "mesh": ['"Image-Guided Biopsy"[Mesh]', '"Drainage"[Mesh]'],
        "keywords": [
            '"image guided biops*"[tiab]',
            '"percutaneous biops*"[tiab]',
            '"core biops*"[tiab]',
            '"fine needle aspirat*"[tiab]',
            'drainage[tiab]',
        ],
    },

    # --- studi con mezzo di contrasto dedicati ------------------------------
    "Myelography": {
        "mesh": ['"Myelography"[Mesh]'],
        "keywords": [
            'myelograph*[tiab]',
            '"CT myelograph*"[tiab]',
            'intrathecal[tiab]',
        ],
    },
    "Arthrography": {
        "mesh": ['"Arthrography"[Mesh]'],
        "keywords": [
            'arthrograph*[tiab]',
            '"MR arthrograph*"[tiab]',
            '"intra articular contrast"[tiab]',
        ],
    },
    "Urography": {
        "mesh": ['"Urography"[Mesh]'],
        "keywords": [
            'urograph*[tiab]',
            '"intravenous urogram*"[tiab]',
            'IVU[tiab]',
            'IVP[tiab]',
            '"CT urograph*"[tiab]',
            'pyelograph*[tiab]',
        ],
    },
    "Cholangiography (ERCP, MRCP, PTC)": {
        "mesh": [
            '"Cholangiography"[Mesh]',
            '"Cholangiopancreatography, Endoscopic Retrograde"[Mesh]',
            '"Cholangiopancreatography, Magnetic Resonance"[Mesh]',
        ],
        "keywords": [
            'cholangiograph*[tiab]',
            'ERCP[tiab]',
            'MRCP[tiab]',
            '"percutaneous transhepatic"[tiab]',
            'cholangiopancreatograph*[tiab]',
        ],
    },
    "Sialography": {
        "mesh": ['"Sialography"[Mesh]'],
        "keywords": [
            'sialograph*[tiab]',
            '"salivary duct*"[tiab]',
        ],
    },
    "Hysterosalpingography": {
        "mesh": ['"Hysterosalpingography"[Mesh]'],
        "keywords": [
            'hysterosalpingograph*[tiab]',
            'HSG[tiab]',
            '"tubal patency"[tiab]',
            '"saline infusion sonohysterograph*"[tiab]',
        ],
    },

    # --- imaging della mammella --------------------------------------------
    "Mammography": {
        "mesh": ['"Mammography"[Mesh]'],
        "keywords": [
            'mammograph*[tiab]',
            '"BI-RADS"[tiab]',
            '"mammographic screening"[tiab]',
        ],
    },
    "Tomosynthesis": {
        "mesh": ['"Mammography"[Mesh]', '"Radiographic Image Enhancement"[Mesh]'],
        "keywords": [
            'tomosynthes*[tiab]',
            'DBT[tiab]',
            '"3D mammograph*"[tiab]',
        ],
    },

    # --- trasversali --------------------------------------------------------
    "Any imaging (broad)": {
        "mesh": ['"Diagnostic Imaging"[Mesh]', '"diagnostic imaging"[sh]'],
        "keywords": [
            'imaging[tiab]',
            'radiolog*[tiab]',
            '"imaging finding*"[tiab]',
            '"imaging feature*"[tiab]',
        ],
    },
    "Neuroimaging": {
        "mesh": ['"Neuroimaging"[Mesh]'],
        "keywords": [
            'neuroimaging[tiab]',
            '"brain imaging"[tiab]',
            '"cerebral imaging"[tiab]',
        ],
    },
}

# I gruppi in cui si presentano. Sono famiglie di tecnica, non del MeSH: e' come
# le tiene in testa chi le usa, ed e' l'ordine in cui le cerca in un elenco.
#
# Ogni nome qui deve essere una chiave di MODALITIES e ogni chiave di MODALITIES
# deve stare in un gruppo: `check_search.py` lo verifica, cosi' una modalita'
# aggiunta e dimenticata qui non finisce invisibile nell'interfaccia.
GROUPS: dict[str, list[str]] = {
    "Plain radiography and fluoroscopy": [
        "Radiograph (plain film)",
        "Fluoroscopy",
        "Barium / contrast swallow and enema",
        "Bone densitometry (DXA)",
    ],
    "CT": [
        "CT",
        "CT angiography",
        "Dual-energy and photon-counting CT",
        "Cone-beam CT",
        "CT perfusion",
    ],
    "MRI": [
        "MRI",
        "Diffusion-weighted imaging",
        "MR angiography",
        "MR spectroscopy",
        "Functional MRI",
        "MR perfusion",
    ],
    "Ultrasound": [
        "Ultrasound",
        "Doppler ultrasound",
        "Contrast-enhanced ultrasound",
        "Elastography",
        "Echocardiography",
        "Transoesophageal echocardiography",
        "Endoscopic ultrasound",
        "Antenatal ultrasound",
    ],
    "Nuclear medicine": [
        "Nuclear medicine and scintigraphy",
        "SPECT",
        "PET",
        "PET-CT",
        "PET-MRI",
    ],
    "Vascular and interventional": [
        "Catheter angiography (DSA)",
        "Venography",
        "Lymphangiography",
        "Interventional radiology",
        "Image-guided biopsy and drainage",
    ],
    "Contrast studies": [
        "Myelography",
        "Arthrography",
        "Urography",
        "Cholangiography (ERCP, MRCP, PTC)",
        "Sialography",
        "Hysterosalpingography",
    ],
    "Breast imaging": [
        "Mammography",
        "Tomosynthesis",
    ],
    "Across modalities": [
        "Any imaging (broad)",
        "Neuroimaging",
    ],
}


def covered() -> list[str]:
    """Le modalita', nell'ordine dei gruppi.

    Non in ordine alfabetico: `CT angiography` accanto a `CT` dice qualcosa,
    fra `Cone-beam CT` e `Contrast-enhanced ultrasound` no."""
    return [name for names in GROUPS.values() for name in names]


def has(name: str) -> bool:
    return name in MODALITIES


def group_of(name: str) -> str:
    """La famiglia di tecnica a cui appartiene, o '' se non e' una modalita'.

    Serve all'interfaccia: in un elenco di quaranta voci `Doppler ultrasound`
    da sola non dice a quale famiglia appartiene, e `Ultrasound > Doppler
    ultrasound` si a colpo d'occhio."""
    for group, names in GROUPS.items():
        if name in names:
            return group
    return ""


def terms_for(name: str, mode: str = "both") -> list[str]:
    """I singoli pezzi di una modalita', gia' in sintassi PubMed."""
    entry = MODALITIES.get(name)
    if entry is None:
        return []
    if mode == "mesh":
        return list(entry["mesh"])
    if mode == "keywords":
        return list(entry["keywords"])
    out = list(entry["mesh"])
    for term in entry["keywords"]:
        if term not in out:
            out.append(term)
    return out


def fragment(name: str, mode: str = "both") -> str:
    """Una modalita' sola, pronta da mettere in un blocco."""
    terms = terms_for(name, mode)
    return "(" + " OR ".join(terms) + ")" if terms else ""


def clause(names: list[str] | None, mode: str = "both") -> str:
    """Le modalita' scelte, in OR, come un pezzo unico di query.

    I doppioni si tolgono: `"Magnetic Resonance Imaging"[Mesh]` sta sia in
    `MRI` sia in `MR perfusion`, e chiedendo tutt'e due comparirebbe due volte -
    non cambierebbe il risultato, ma una query in cui lo stesso termine torna
    due volte fa dubitare di averla composta male, ed e' l'unica cosa che uno
    legge prima di premere invio.
    """
    if not names:
        return ""
    terms: list[str] = []
    for name in names:
        for term in terms_for(name, mode):
            if term not in terms:
                terms.append(term)
    return "(" + " OR ".join(terms) + ")" if terms else ""
