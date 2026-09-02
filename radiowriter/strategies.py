"""Da un titolo di sezione Radiopaedia a un pezzo di ricerca PubMed.

Gli heading di un articolo Radiopaedia sono gia' una scaletta della ricerca da
fare: `Epidemiology` vuol dire cercare prevalenza e incidenza, `Treatment and
prognosis` vuol dire cercare terapia e sopravvivenza, `MRI` vuol dire cercare
risonanza. Quello che manca e' tradurre ognuno di quei titoli nei termini con
cui la letteratura ne parla davvero - e quello e' un lavoro che si fa una volta
e si riusa, non uno da rifare a ogni articolo.

Ogni voce ha due liste, tenute distinte perche' rispondono a due esigenze
diverse:

- `mesh`: vocabolario controllato - descrittori MeSH e sottotitoli. Preciso,
  ma indicizza solo quello che i curatori del MEDLINE hanno gia' indicizzato:
  un lavoro di tre mesi fa non c'e' ancora.
- `keywords`: parole nel titolo e nell'abstract. Prende anche il non ancora
  indicizzato e il modo in cui gli autori scrivono davvero, al prezzo di
  qualche falso positivo.

Le due insieme (`both`) sono lo standard: e' come si costruisce un blocco di
una strategia di ricerca seria.

I titoli si riconoscono attraverso `structure`, quindi valgono anche i modi in
cui la gente li scrive negli articoli veri: `etiology` trova `Aetiology`,
`CT scan` trova `CT`, `x-ray` trova `Plain radiograph`.
"""

from __future__ import annotations

from radiowriter import structure as sx

MODES = {
    "both": "MeSH + keywords",
    "mesh": "MeSH only",
    "keywords": "Keywords only",
}

# titolo del canone -> {"mesh": [...], "keywords": [...]}
#
# Chi non e' qui dentro non ha una strategia: `See also`, `Reference article`,
# `Practical points` e simili sono sezioni dell'articolo, non angoli di
# ricerca, e offrirne una sarebbe offrire rumore.
STRATEGIES: dict[str, dict[str, list[str]]] = {
    "Terminology": {
        "mesh": ['"Terminology as Topic"[Mesh]', 'classification[sh]'],
        "keywords": ['terminolog*[tiab]', 'nomenclature[tiab]', 'definition*[tiab]',
                     'synonym*[tiab]', '"named after"[tiab]'],
    },
    "Epidemiology": {
        "mesh": ['"Epidemiology"[Mesh]', '"Prevalence"[Mesh]', '"Incidence"[Mesh]',
                 'epidemiology[sh]'],
        "keywords": ['epidemiolog*[tiab]', 'prevalence[tiab]', 'incidence[tiab]',
                     'frequency[tiab]', '"population based"[tiab]'],
    },
    "Aetiology": {
        "mesh": ['etiology[sh]', '"Causality"[Mesh]'],
        "keywords": ['aetiolog*[tiab]', 'etiolog*[tiab]', 'pathogenes*[tiab]', 'cause[tiab]',
                     'causes[tiab]', 'mechanism*[tiab]'],
    },
    "Risk factors": {
        "mesh": ['"Risk Factors"[Mesh]', '"Causality"[Mesh]'],
        "keywords": ['"risk factor*"[tiab]', 'predispos*[tiab]', 'predictor*[tiab]',
                     'associated with[tiab]'],
    },
    "Associations": {
        "mesh": ['"Comorbidity"[Mesh]', '"Syndrome"[Mesh]'],
        "keywords": ['association*[tiab]', 'associated[tiab]', 'syndrom*[tiab]',
                     'coexist*[tiab]', 'concurrent[tiab]'],
    },
    "Clinical presentation": {
        "mesh": ['"Signs and Symptoms"[Mesh]', 'diagnosis[sh]'],
        "keywords": ['"clinical presentation*"[tiab]', '"clinical feature*"[tiab]',
                     'symptom*[tiab]', '"signs and symptoms"[tiab]',
                     '"clinical manifestation*"[tiab]'],
    },
    "Pathology": {
        "mesh": ['"Pathology"[Mesh]', 'pathology[sh]'],
        "keywords": ['patholog*[tiab]', 'histopatholog*[tiab]', 'pathogenes*[tiab]'],
    },
    "Genetics": {
        "mesh": ['"Genetics"[Mesh]', 'genetics[sh]', '"Mutation"[Mesh]'],
        "keywords": ['genetic*[tiab]', 'mutation*[tiab]', 'variant*[tiab]',
                     '"gene"[tiab]', 'inherit*[tiab]', 'autosomal[tiab]'],
    },
    "Macroscopic appearance": {
        "mesh": ['pathology[sh]', '"Autopsy"[Mesh]'],
        "keywords": ['macroscop*[tiab]', '"gross appearance"[tiab]', '"gross '
                     'pathology"[tiab]', 'specimen*[tiab]'],
    },
    "Microscopic appearance": {
        "mesh": ['"Histology"[Mesh]', 'pathology[sh]', '"Immunohistochemistry"[Mesh]'],
        "keywords": ['microscop*[tiab]', 'histolog*[tiab]', 'histopatholog*[tiab]',
                     '"h&e"[tiab]', 'biops*[tiab]'],
    },
    "Histology": {
        "mesh": ['"Histology"[Mesh]', '"anatomy and histology"[sh]'],
        "keywords": ['histolog*[tiab]', 'microscop*[tiab]', '"cell type*"[tiab]'],
    },
    "Immunophenotype": {
        "mesh": ['"Immunophenotyping"[Mesh]', '"Immunohistochemistry"[Mesh]',
                 '"Biomarkers, Tumor"[Mesh]'],
        "keywords": ['immunophenotyp*[tiab]', 'immunohistochem*[tiab]',
                     '"immunostain*"[tiab]', 'CD[tiab]'],
    },
    "Markers": {
        "mesh": ['"Biomarkers"[Mesh]', '"Biomarkers, Tumor"[Mesh]'],
        "keywords": ['biomarker*[tiab]', '"tumour marker*"[tiab]', '"tumor marker*"[tiab]',
                     'marker*[tiab]'],
    },
    "Classification": {
        "mesh": ['"Classification"[Mesh]', 'classification[sh]',
                 '"Severity of Illness Index"[Mesh]', '"Neoplasm Staging"[Mesh]'],
        "keywords": ['classification*[tiab]', 'grading[tiab]', 'staging[tiab]',
                     '"scoring system*"[tiab]', '"score"[tiab]', 'subtype*[tiab]'],
    },
    "Radiographic features": {
        "mesh": ['"Diagnostic Imaging"[Mesh]', '"diagnostic imaging"[sh]'],
        "keywords": ['imaging[tiab]', 'radiolog*[tiab]', '"imaging feature*"[tiab]',
                     '"imaging finding*"[tiab]', '"imaging appearance*"[tiab]'],
    },
    "Role of imaging": {
        "mesh": ['"Diagnostic Imaging"[Mesh]', '"Sensitivity and Specificity"[Mesh]',
                 '"diagnostic imaging"[sh]'],
        "keywords": ['"role of imaging"[tiab]', '"diagnostic accuracy"[tiab]',
                     'sensitivit*[tiab]', 'specificit*[tiab]', '"diagnostic '
                     'performance"[tiab]'],
    },
    "Plain radiograph": {
        "mesh": ['"Radiography"[Mesh]', 'radiography[sh]'],
        "keywords": ['radiograph*[tiab]', '"plain film*"[tiab]', '"x-ray*"[tiab]',
                     '"plain radiograph*"[tiab]'],
    },
    "CT": {
        "mesh": ['"Tomography, X-Ray Computed"[Mesh]',
                 '"Multidetector Computed Tomography"[Mesh]'],
        "keywords": ['"computed tomography"[tiab]', 'CT[tiab]', 'MDCT[tiab]',
                     'MSCT[tiab]', '"CT angiograph*"[tiab]'],
    },
    "Dual-energy CT": {
        "mesh": ['"Tomography, X-Ray Computed"[Mesh]', '"Radiography, Dual-Energy '
                 'Scanned Projection"[Mesh]'],
        "keywords": ['"dual energy"[tiab]', '"dual-energy"[tiab]', 'DECT[tiab]',
                     '"spectral CT"[tiab]', '"photon counting"[tiab]'],
    },
    "MRI": {
        "mesh": ['"Magnetic Resonance Imaging"[Mesh]',
                 '"Diffusion Magnetic Resonance Imaging"[Mesh]'],
        "keywords": ['MRI[tiab]', '"magnetic resonance"[tiab]', 'MR[ti]',
                     'DWI[tiab]', '"diffusion weighted"[tiab]'],
    },
    "CT/MRI": {
        "mesh": ['"Tomography, X-Ray Computed"[Mesh]', '"Magnetic Resonance Imaging"[Mesh]'],
        "keywords": ['"computed tomography"[tiab]', 'CT[tiab]', 'MRI[tiab]',
                     '"magnetic resonance"[tiab]'],
    },
    "Ultrasound": {
        "mesh": ['"Ultrasonography"[Mesh]', 'ultrasonography[sh]',
                 '"Ultrasonography, Doppler"[Mesh]'],
        "keywords": ['ultraso*[tiab]', 'sonograph*[tiab]', 'echograph*[tiab]',
                     'doppler[tiab]', '"US"[ti]'],
    },
    "Antenatal ultrasound": {
        "mesh": ['"Ultrasonography, Prenatal"[Mesh]', '"Prenatal Diagnosis"[Mesh]'],
        "keywords": ['antenatal[tiab]', 'prenatal[tiab]', 'foetal[tiab]', 'fetal[tiab]',
                     '"obstetric ultraso*"[tiab]'],
    },
    "Transoesophageal echocardiography": {
        "mesh": ['"Echocardiography, Transesophageal"[Mesh]', '"Echocardiography"[Mesh]'],
        "keywords": ['transoesophageal[tiab]', 'transesophageal[tiab]', 'TOE[tiab]', 'TEE[tiab]',
                     'echocardiograph*[tiab]'],
    },
    "Angiography (DSA)": {
        "mesh": ['"Angiography"[Mesh]', '"Angiography, Digital Subtraction"[Mesh]'],
        "keywords": ['angiograph*[tiab]', 'DSA[tiab]', '"digital subtraction"[tiab]',
                     'arteriograph*[tiab]'],
    },
    "Nuclear medicine": {
        "mesh": ['"Nuclear Medicine"[Mesh]', '"Radionuclide Imaging"[Mesh]',
                 '"Tomography, Emission-Computed, Single-Photon"[Mesh]'],
        "keywords": ['scintigraph*[tiab]', '"nuclear medicine"[tiab]', 'SPECT[tiab]',
                     'radiotracer*[tiab]', 'radionuclide*[tiab]'],
    },
    "PET-CT": {
        "mesh": ['"Positron Emission Tomography Computed Tomography"[Mesh]',
                 '"Positron-Emission Tomography"[Mesh]'],
        "keywords": ['"PET-CT"[tiab]', '"PET/CT"[tiab]', '"positron emission"[tiab]',
                     'FDG[tiab]', 'SUV[tiab]'],
    },
    "PET-MRI": {
        "mesh": ['"Positron-Emission Tomography"[Mesh]', '"Multimodal Imaging"[Mesh]',
                 '"Magnetic Resonance Imaging"[Mesh]'],
        "keywords": ['"PET-MRI"[tiab]', '"PET/MRI"[tiab]', '"PET/MR"[tiab]',
                     '"hybrid imaging"[tiab]'],
    },
    "Mammography": {
        "mesh": ['"Mammography"[Mesh]', '"Breast Neoplasms/diagnostic imaging"[Mesh]'],
        "keywords": ['mammograph*[tiab]', 'tomosynthes*[tiab]', '"BI-RADS"[tiab]'],
    },
    "Normal appearance": {
        "mesh": ['"Reference Values"[Mesh]', '"anatomy and histology"[sh]'],
        "keywords": ['"normal appearance*"[tiab]', '"normal anatomy"[tiab]',
                     '"normal finding*"[tiab]', '"healthy volunteer*"[tiab]'],
    },
    "Diagnostic criteria": {
        "mesh": ['"Sensitivity and Specificity"[Mesh]', '"Clinical Decision Rules"[Mesh]',
                 'diagnosis[sh]'],
        "keywords": ['"diagnostic criteri*"[tiab]', 'criteri*[ti]',
                     '"diagnostic rule*"[tiab]', 'consensus[tiab]'],
    },
    "Diagnostic clues": {
        "mesh": ['diagnosis[sh]', '"Diagnosis, Differential"[Mesh]'],
        "keywords": ['"diagnostic clue*"[tiab]', '"key finding*"[tiab]',
                     '"pathognomonic"[tiab]', '"sign"[ti]'],
    },
    "Diagnosis": {
        "mesh": ['diagnosis[sh]', '"Diagnostic Techniques and Procedures"[Mesh]',
                 '"Sensitivity and Specificity"[Mesh]'],
        "keywords": ['diagnos*[tiab]', '"diagnostic accuracy"[tiab]',
                     'sensitivit*[tiab]', 'specificit*[tiab]'],
    },
    "Radiology report": {
        "mesh": ['"Research Report"[Mesh]', 'standards[sh]'],
        "keywords": ['"structured report*"[tiab]', '"radiology report*"[tiab]',
                     '"reporting template*"[tiab]', '"synoptic report*"[tiab]'],
    },
    "Treatment and prognosis": {
        "mesh": ['therapy[sh]', '"Prognosis"[Mesh]', '"Therapeutics"[Mesh]',
                 '"Treatment Outcome"[Mesh]'],
        "keywords": ['treatment*[tiab]', 'therap*[tiab]', 'management[tiab]',
                     'prognos*[tiab]', 'surviv*[tiab]', 'outcome*[tiab]'],
    },
    "Outcomes": {
        "mesh": ['"Treatment Outcome"[Mesh]', '"Prognosis"[Mesh]',
                 '"Survival Analysis"[Mesh]'],
        "keywords": ['outcome*[tiab]', 'surviv*[tiab]', '"follow up"[tiab]',
                     'recurrence[tiab]', 'mortalit*[tiab]'],
    },
    "Complications": {
        "mesh": ['complications[sh]', '"Postoperative Complications"[Mesh]',
                 '"adverse effects"[sh]'],
        "keywords": ['complication*[tiab]', '"adverse event*"[tiab]',
                     '"adverse effect*"[tiab]', 'morbidit*[tiab]'],
    },
    "Differential diagnosis": {
        "mesh": ['"Diagnosis, Differential"[Mesh]'],
        "keywords": ['"differential diagnos*"[tiab]', 'mimic*[tiab]',
                     '"differentiating"[tiab]', '"distinguish*"[tiab]'],
    },
    "Clinical differential diagnosis": {
        "mesh": ['"Diagnosis, Differential"[Mesh]', '"Signs and Symptoms"[Mesh]'],
        "keywords": ['"differential diagnos*"[tiab]', 'mimic*[tiab]',
                     '"clinical differential*"[tiab]'],
    },
    "History and etymology": {
        "mesh": ['history[sh]', '"History of Medicine"[Mesh]', '"Eponyms"[Mesh]'],
        "keywords": ['histor*[tiab]', 'eponym*[tiab]', 'etymolog*[tiab]',
                     '"first described"[tiab]', '"named after"[tiab]'],
    },
    "History": {
        "mesh": ['history[sh]', '"History of Medicine"[Mesh]'],
        "keywords": ['histor*[tiab]', '"first described"[tiab]', 'origin*[tiab]'],
    },
    "Early life": {
        "mesh": ['"History of Medicine"[Mesh]', '"Biography"[pt]'],
        "keywords": ['biograph*[tiab]', '"early life"[tiab]', '"born"[tiab]',
                     'education[tiab]'],
    },
    "Later life": {
        "mesh": ['"History of Medicine"[Mesh]', '"Biography"[pt]'],
        "keywords": ['biograph*[tiab]', 'obituar*[tiab]', '"later life"[tiab]',
                     '"in memoriam"[tiab]'],
    },
    "Legacy": {
        "mesh": ['"History of Medicine"[Mesh]', '"Eponyms"[Mesh]', '"Biography"[pt]'],
        "keywords": ['legacy[tiab]', 'eponym*[tiab]', 'contribution*[tiab]',
                     'tribute[tiab]'],
    },
    "Accolades": {
        "mesh": ['"Awards and Prizes"[Mesh]', '"Biography"[pt]'],
        "keywords": ['award*[tiab]', 'prize*[tiab]', 'honour*[tiab]', 'honor*[tiab]',
                     '"nobel"[tiab]'],
    },
    "Gross anatomy": {
        "mesh": ['"Anatomy"[Mesh]', '"anatomy and histology"[sh]'],
        "keywords": ['anatom*[tiab]', '"gross anatomy"[tiab]', 'morpholog*[tiab]',
                     'cadaver*[tiab]'],
    },
    "Variant anatomy": {
        "mesh": ['"Anatomic Variation"[Mesh]', 'abnormalities[sh]'],
        "keywords": ['"anatomic* variant*"[tiab]', '"anatomic* variation*"[tiab]',
                     '"normal variant*"[tiab]', 'variant*[tiab]', 'accessory[tiab]'],
    },
    "Development": {
        "mesh": ['"Embryonic Development"[Mesh]', 'embryology[sh]',
                 '"growth and development"[sh]'],
        "keywords": ['embryolog*[tiab]', 'development*[tiab]', 'ontogen*[tiab]',
                     'morphogenes*[tiab]'],
    },
    "Function": {
        "mesh": ['physiology[sh]', '"Physiological Phenomena"[Mesh]'],
        "keywords": ['function*[tiab]', 'physiolog*[tiab]', 'role[tiab]'],
    },
    "Biological function": {
        "mesh": ['physiology[sh]', '"Physiological Phenomena"[Mesh]', 'metabolism[sh]'],
        "keywords": ['"biological function*"[tiab]', 'physiolog*[tiab]',
                     'metabolis*[tiab]', 'cofactor*[tiab]'],
    },
    "Location": {
        "mesh": ['"anatomy and histology"[sh]', '"Anatomic Landmarks"[Mesh]'],
        "keywords": ['location[tiab]', 'topograph*[tiab]', '"anatomic* landmark*"[tiab]',
                     'position[tiab]'],
    },
    "Relations and/or Boundaries": {
        "mesh": ['"anatomy and histology"[sh]', '"Anatomic Landmarks"[Mesh]'],
        "keywords": ['boundar*[tiab]', 'relation*[tiab]', 'adjacent[tiab]',
                     'border*[tiab]', 'compartment*[tiab]'],
    },
    "Contents": {
        "mesh": ['"anatomy and histology"[sh]'],
        "keywords": ['content*[tiab]', 'contain*[tiab]', 'traverse*[tiab]',
                     'compartment*[tiab]'],
    },
    "Arterial supply": {
        "mesh": ['"blood supply"[sh]', '"Arteries"[Mesh]'],
        "keywords": ['"arterial suppl*"[tiab]', '"blood suppl*"[tiab]', 'arter*[tiab]',
                     'vascular*[tiab]', 'perfusion[tiab]'],
    },
    "Venous drainage": {
        "mesh": ['"blood supply"[sh]', '"Veins"[Mesh]'],
        "keywords": ['"venous drainage"[tiab]', 'vein*[tiab]', 'venous[tiab]',
                     'tributar*[tiab]'],
    },
    "Lymphatic drainage": {
        "mesh": ['"Lymphatic System"[Mesh]', '"Lymph Nodes"[Mesh]',
                 '"Lymphatic Metastasis"[Mesh]'],
        "keywords": ['"lymphatic drainage"[tiab]', 'lymphatic*[tiab]',
                     '"lymph node*"[tiab]', '"sentinel node*"[tiab]'],
    },
    "Innervation": {
        "mesh": ['innervation[sh]', '"Peripheral Nerves"[Mesh]'],
        "keywords": ['innervat*[tiab]', '"nerve suppl*"[tiab]', 'nerve*[tiab]',
                     'neural[tiab]'],
    },
    "Supply": {
        "mesh": ['"blood supply"[sh]', '"Arteries"[Mesh]'],
        "keywords": ['"blood suppl*"[tiab]', 'vascular*[tiab]', 'perfusion[tiab]'],
    },
    "Supply/drainage": {
        "mesh": ['"blood supply"[sh]', '"Arteries"[Mesh]', '"Veins"[Mesh]'],
        "keywords": ['"blood suppl*"[tiab]', '"venous drainage"[tiab]', 'vascular*[tiab]'],
    },
    "Branches": {
        "mesh": ['"anatomy and histology"[sh]', '"Arteries"[Mesh]'],
        "keywords": ['branch*[tiab]', 'ramus[tiab]', 'rami[tiab]', 'division*[tiab]'],
    },
    "Branches/tributaries": {
        "mesh": ['"anatomy and histology"[sh]', '"Veins"[Mesh]'],
        "keywords": ['branch*[tiab]', 'tributar*[tiab]', 'confluence*[tiab]'],
    },
    "Course": {
        "mesh": ['"anatomy and histology"[sh]'],
        "keywords": ['course[tiab]', 'trajector*[tiab]', 'pathway*[tiab]',
                     '"runs"[tiab]'],
    },
    "Origin": {
        "mesh": ['"anatomy and histology"[sh]'],
        "keywords": ['origin*[tiab]', 'arise*[tiab]', 'arising[tiab]',
                     '"proximal attachment*"[tiab]'],
    },
    "Insertion": {
        "mesh": ['"anatomy and histology"[sh]', '"Tendons"[Mesh]'],
        "keywords": ['insertion*[tiab]', '"distal attachment*"[tiab]', 'enthes*[tiab]'],
    },
    "Termination": {
        "mesh": ['"anatomy and histology"[sh]'],
        "keywords": ['terminat*[tiab]', '"drains into"[tiab]', 'ends[tiab]'],
    },
    "Attachments": {
        "mesh": ['"anatomy and histology"[sh]', '"Tendons"[Mesh]', '"Ligaments"[Mesh]'],
        "keywords": ['attachment*[tiab]', 'insertion*[tiab]', 'origin*[tiab]',
                     'enthes*[tiab]'],
    },
    "Articulations": {
        "mesh": ['"Joints"[Mesh]', '"anatomy and histology"[sh]'],
        "keywords": ['articulat*[tiab]', 'joint*[tiab]', '"synovial"[tiab]'],
    },
    "Osteology": {
        "mesh": ['"Bone and Bones"[Mesh]', '"anatomy and histology"[sh]'],
        "keywords": ['osteolog*[tiab]', 'bone*[tiab]', 'cortical[tiab]',
                     'trabecular[tiab]'],
    },
    "Ligaments": {
        "mesh": ['"Ligaments"[Mesh]'],
        "keywords": ['ligament*[tiab]', 'ligamentous[tiab]', 'capsul*[tiab]'],
    },
    "Ligamentous": {
        "mesh": ['"Ligaments"[Mesh]', '"Joint Capsule"[Mesh]'],
        "keywords": ['ligament*[tiab]', 'ligamentous[tiab]', 'stabiliser*[tiab]'],
    },
    "Tendons": {
        "mesh": ['"Tendons"[Mesh]'],
        "keywords": ['tendon*[tiab]', 'tendinous[tiab]', '"musculotendinous"[tiab]'],
    },
    "Musculotendinous": {
        "mesh": ['"Tendons"[Mesh]', '"Muscle, Skeletal"[Mesh]'],
        "keywords": ['musculotendinous[tiab]', 'tendon*[tiab]', 'muscle*[tiab]'],
    },
    "Movement": {
        "mesh": ['"Range of Motion, Articular"[Mesh]', '"Biomechanical Phenomena"[Mesh]',
                 '"Movement"[Mesh]'],
        "keywords": ['movement*[tiab]', '"range of motion"[tiab]', 'kinematic*[tiab]',
                     'biomechanic*[tiab]'],
    },
    "Action": {
        "mesh": ['physiology[sh]', '"Muscle Contraction"[Mesh]'],
        "keywords": ['action*[tiab]', 'function*[tiab]', 'contract*[tiab]',
                     'flexion[tiab]', 'extension[tiab]'],
    },
    "Structure": {
        "mesh": ['"anatomy and histology"[sh]', '"Anatomy"[Mesh]'],
        "keywords": ['structure*[tiab]', 'architectur*[tiab]', 'morpholog*[tiab]',
                     'composition[tiab]'],
    },
    "Size": {
        "mesh": ['"Organ Size"[Mesh]', '"Reference Values"[Mesh]'],
        "keywords": ['size[tiab]', 'dimension*[tiab]', 'diameter*[tiab]',
                     'volume*[tiab]', 'length[tiab]'],
    },
    "Measurement": {
        "mesh": ['"Reference Values"[Mesh]', '"Anthropometry"[Mesh]',
                 '"Reproducibility of Results"[Mesh]'],
        "keywords": ['measurement*[tiab]', 'measur*[tiab]', 'threshold*[tiab]',
                     '"cut off"[tiab]', 'reproducib*[tiab]'],
    },
    "Normal values": {
        "mesh": ['"Reference Values"[Mesh]', '"Reference Standards"[Mesh]'],
        "keywords": ['"normal value*"[tiab]', '"reference value*"[tiab]',
                     '"normal range*"[tiab]', 'percentile*[tiab]'],
    },
    "Interpretation": {
        "mesh": ['"Observer Variation"[Mesh]', '"Sensitivity and Specificity"[Mesh]'],
        "keywords": ['interpretation[tiab]', '"inter observer"[tiab]',
                     '"interobserver"[tiab]', 'agreement[tiab]', 'reliabilit*[tiab]'],
    },
    "Indications": {
        "mesh": ['"Patient Selection"[Mesh]', '"Practice Guidelines as Topic"[Mesh]'],
        "keywords": ['indication*[tiab]', '"appropriate use"[tiab]',
                     '"patient selection"[tiab]', 'criteri*[tiab]'],
    },
    "Contraindications": {
        "mesh": ['"Contraindications"[Mesh]', '"Contraindications, Drug"[Mesh]'],
        "keywords": ['contraindicat*[tiab]', '"not recommended"[tiab]',
                     'safety[tiab]', 'risk*[tiab]'],
    },
    "Technique": {
        "mesh": ['methods[sh]', '"Clinical Protocols"[Mesh]'],
        "keywords": ['technique*[tiab]', 'method*[tiab]', 'protocol*[tiab]',
                     '"step by step"[tiab]'],
    },
    "Procedure": {
        "mesh": ['methods[sh]', '"Surgical Procedures, Operative"[Mesh]',
                 '"Radiology, Interventional"[Mesh]'],
        "keywords": ['procedur*[tiab]', 'technique*[tiab]', 'intervention*[tiab]',
                     'percutaneous[tiab]'],
    },
    "Approach": {
        "mesh": ['methods[sh]', '"Surgical Procedures, Operative"[Mesh]'],
        "keywords": ['approach*[tiab]', 'access[tiab]', 'route*[tiab]',
                     'transjugular[tiab]', 'transfemoral[tiab]'],
    },
    "Planning": {
        "mesh": ['methods[sh]', '"Patient Care Planning"[Mesh]'],
        "keywords": ['planning[tiab]', '"pre procedural"[tiab]', '"work up"[tiab]',
                     'workup[tiab]'],
    },
    "Preprocedural evaluation": {
        "mesh": ['"Preoperative Care"[Mesh]', '"Preoperative Period"[Mesh]'],
        "keywords": ['preprocedur*[tiab]', 'preoperativ*[tiab]', '"work up"[tiab]',
                     'baseline[tiab]'],
    },
    "Patient preparation": {
        "mesh": ['"Preoperative Care"[Mesh]', '"Patient Education as Topic"[Mesh]'],
        "keywords": ['preparation[tiab]', 'fasting[tiab]', 'premedicat*[tiab]',
                     'consent[tiab]'],
    },
    "Patient positioning": {
        "mesh": ['"Patient Positioning"[Mesh]', '"Posture"[Mesh]'],
        "keywords": ['position*[tiab]', 'supine[tiab]', 'prone[tiab]', 'decubitus[tiab]'],
    },
    "Postprocedural care": {
        "mesh": ['"Postoperative Care"[Mesh]', '"Aftercare"[Mesh]'],
        "keywords": ['postprocedur*[tiab]', 'postoperativ*[tiab]', 'aftercare[tiab]',
                     '"follow up"[tiab]'],
    },
    "Postprocedural evaluation": {
        "mesh": ['"Postoperative Care"[Mesh]', '"Treatment Outcome"[Mesh]'],
        "keywords": ['postprocedur*[tiab]', '"follow up"[tiab]', 'surveillance[tiab]',
                     '"technical success"[tiab]'],
    },
    "Equipment": {
        "mesh": ['instrumentation[sh]', '"Equipment and Supplies"[Mesh]',
                 '"Equipment Design"[Mesh]'],
        "keywords": ['equipment[tiab]', 'device*[tiab]', 'catheter*[tiab]',
                     'system*[tiab]'],
    },
    "Protocol": {
        "mesh": ['"Clinical Protocols"[Mesh]', 'methods[sh]', 'standards[sh]'],
        "keywords": ['protocol*[tiab]', '"acquisition parameter*"[tiab]',
                     '"scan protocol*"[tiab]', 'optimis*[tiab]', 'optimiz*[tiab]'],
    },
    "Sequences": {
        "mesh": ['"Magnetic Resonance Imaging"[Mesh]', 'methods[sh]'],
        "keywords": ['sequence*[tiab]', '"T1 weighted"[tiab]', '"T2 weighted"[tiab]',
                     'FLAIR[tiab]', 'SWI[tiab]'],
    },
    "Standard sequences": {
        "mesh": ['"Magnetic Resonance Imaging"[Mesh]', 'standards[sh]'],
        "keywords": ['"standard sequence*"[tiab]', '"routine protocol*"[tiab]',
                     'sequence*[tiab]'],
    },
    "Optional sequences": {
        "mesh": ['"Magnetic Resonance Imaging"[Mesh]', 'methods[sh]'],
        "keywords": ['"additional sequence*"[tiab]', '"optional sequence*"[tiab]',
                     '"problem solving"[tiab]'],
    },
    "Coil": {
        "mesh": ['instrumentation[sh]', '"Magnetic Resonance Imaging"[Mesh]'],
        "keywords": ['coil*[tiab]', '"phased array"[tiab]', '"signal to noise"[tiab]'],
    },
    "1.5 vs 3 tesla": {
        "mesh": ['"Magnetic Resonance Imaging"[Mesh]', 'instrumentation[sh]'],
        "keywords": ['"3 tesla"[tiab]', '"1.5 tesla"[tiab]', '"3T"[tiab]',
                     '"field strength"[tiab]'],
    },
    "Technical parameters": {
        "mesh": ['instrumentation[sh]', 'standards[sh]', 'methods[sh]'],
        "keywords": ['parameter*[tiab]', '"technical factor*"[tiab]',
                     '"acquisition"[tiab]', '"reconstruction"[tiab]'],
    },
    "Technical factors": {
        "mesh": ['instrumentation[sh]', 'methods[sh]'],
        "keywords": ['"technical factor*"[tiab]', 'parameter*[tiab]', 'exposure[tiab]'],
    },
    "Scan geometry": {
        "mesh": ['methods[sh]', '"Tomography, X-Ray Computed"[Mesh]'],
        "keywords": ['"scan geometry"[tiab]', 'collimation[tiab]', 'pitch[tiab]',
                     '"slice thickness"[tiab]', '"field of view"[tiab]'],
    },
    "kVp": {
        "mesh": ['"Radiation Dosage"[Mesh]', '"Tomography, X-Ray Computed"[Mesh]'],
        "keywords": ['kVp[tiab]', '"tube voltage"[tiab]', '"tube current"[tiab]',
                     'mAs[tiab]', '"dose reduction"[tiab]'],
    },
    "Post-processing": {
        "mesh": ['"Image Processing, Computer-Assisted"[Mesh]',
                 '"Imaging, Three-Dimensional"[Mesh]'],
        "keywords": ['"post processing"[tiab]', 'postprocessing[tiab]',
                     'reconstruction*[tiab]', '"MPR"[tiab]', '"MIP"[tiab]'],
    },
    "Image technical evaluation": {
        "mesh": ['standards[sh]', '"Quality Control"[Mesh]',
                 '"Radiographic Image Enhancement"[Mesh]'],
        "keywords": ['"image quality"[tiab]', '"technical adequacy"[tiab]',
                     '"quality criteri*"[tiab]', 'exposure[tiab]'],
    },
    "Projections": {
        "mesh": ['methods[sh]', '"Radiography"[Mesh]', '"Patient Positioning"[Mesh]'],
        "keywords": ['projection*[tiab]', 'view*[tiab]', 'oblique[tiab]',
                     '"antero posterior"[tiab]', 'lateral[tiab]'],
    },
    "Standard projections": {
        "mesh": ['"Radiography"[Mesh]', 'standards[sh]'],
        "keywords": ['"standard projection*"[tiab]', '"routine view*"[tiab]',
                     'projection*[tiab]'],
    },
    "Additional projections": {
        "mesh": ['"Radiography"[Mesh]', 'methods[sh]'],
        "keywords": ['"additional projection*"[tiab]', '"supplementary view*"[tiab]',
                     '"special view*"[tiab]'],
    },
    "Modified trauma projections": {
        "mesh": ['"Radiography"[Mesh]', '"Wounds and Injuries"[Mesh]'],
        "keywords": ['trauma[tiab]', '"modified projection*"[tiab]',
                     '"trauma series"[tiab]', 'immobilis*[tiab]'],
    },
    "Pitfalls and artifacts": {
        "mesh": ['"Artifacts"[Mesh]', '"Diagnostic Errors"[Mesh]',
                 '"False Positive Reactions"[Mesh]'],
        "keywords": ['artifact*[tiab]', 'artefact*[tiab]', 'pitfall*[tiab]',
                     '"false positive*"[tiab]', 'mimic*[tiab]'],
    },
    "Limitations": {
        "mesh": ['"Sensitivity and Specificity"[Mesh]', '"Diagnostic Errors"[Mesh]'],
        "keywords": ['limitation*[tiab]', 'drawback*[tiab]', 'shortcoming*[tiab]',
                     '"false negative*"[tiab]'],
    },
    "Clinical importance": {
        "mesh": ['"Clinical Relevance"[Mesh]', '"Prognosis"[Mesh]'],
        "keywords": ['"clinical significance"[tiab]', '"clinical relevance"[tiab]',
                     '"clinical importance"[tiab]', '"clinical impact"[tiab]'],
    },
    "Radiological importance": {
        "mesh": ['"Diagnostic Imaging"[Mesh]', '"Clinical Relevance"[Mesh]'],
        "keywords": ['"radiological significance"[tiab]', '"imaging significance"[tiab]',
                     '"clinical relevance"[tiab]'],
    },
    "Clinical applications": {
        "mesh": ['"Diagnostic Imaging"[Mesh]', 'utilization[sh]'],
        "keywords": ['"clinical application*"[tiab]', '"clinical use*"[tiab]',
                     '"clinical utility"[tiab]'],
    },
    "Clinical information": {
        "mesh": ['"Medical History Taking"[Mesh]', '"Referral and Consultation"[Mesh]'],
        "keywords": ['"clinical information"[tiab]', '"clinical history"[tiab]',
                     '"request form*"[tiab]', 'referral*[tiab]'],
    },
    "Related pathology": {
        "mesh": ['"Comorbidity"[Mesh]', 'complications[sh]'],
        "keywords": ['"related patholog*"[tiab]', 'associated[tiab]',
                     '"associated condition*"[tiab]'],
    },
    "Mechanism": {
        "mesh": ['"Biomechanical Phenomena"[Mesh]', 'etiology[sh]'],
        "keywords": ['mechanism*[tiab]', '"mechanism of injury"[tiab]',
                     'biomechanic*[tiab]', 'pathophysiolog*[tiab]'],
    },
    "Purpose": {
        "mesh": ['"Goals"[Mesh]', 'utilization[sh]'],
        "keywords": ['purpose[tiab]', 'rationale[tiab]', 'aim*[tiab]',
                     '"intended use"[tiab]'],
    },
    "Usage": {
        "mesh": ['utilization[sh]', '"Drug Utilization"[Mesh]'],
        "keywords": ['usage[tiab]', 'utilis*[tiab]', 'utiliz*[tiab]', 'dose[tiab]',
                     'administration[tiab]'],
    },
    "Chemistry": {
        "mesh": ['chemistry[sh]', '"Chemical Phenomena"[Mesh]'],
        "keywords": ['chemistr*[tiab]', '"chemical structure*"[tiab]',
                     'compound*[tiab]', 'molecul*[tiab]'],
    },
    "Physical chemistry": {
        "mesh": ['"Chemistry, Physical"[Mesh]', 'chemistry[sh]'],
        "keywords": ['"physical chemistr*"[tiab]', 'solubilit*[tiab]',
                     'osmolalit*[tiab]', 'viscosit*[tiab]', '"molecular weight"[tiab]'],
    },
    "Radiochemistry": {
        "mesh": ['"Radiochemistry"[Mesh]', '"Radiopharmaceuticals"[Mesh]',
                 '"Isotope Labeling"[Mesh]'],
        "keywords": ['radiochemistr*[tiab]', 'radiolabel*[tiab]',
                     'radiopharmaceutic*[tiab]', '"half life"[tiab]'],
    },
    "Absorption": {
        "mesh": ['pharmacokinetics[sh]', '"Absorption, Physiological"[Mesh]',
                 '"Intestinal Absorption"[Mesh]'],
        "keywords": ['absorption[tiab]', 'uptake[tiab]', 'bioavailabilit*[tiab]'],
    },
    "Transport": {
        "mesh": ['"Biological Transport"[Mesh]', 'metabolism[sh]'],
        "keywords": ['transport*[tiab]', 'carrier*[tiab]', 'binding[tiab]',
                     'circulat*[tiab]'],
    },
    "Storage": {
        "mesh": ['metabolism[sh]', '"Biological Transport"[Mesh]'],
        "keywords": ['storage[tiab]', 'stored[tiab]', 'reserve*[tiab]', 'depot*[tiab]'],
    },
    "Nutrition": {
        "mesh": ['"Nutritional Requirements"[Mesh]', '"Nutritional Status"[Mesh]',
                 '"Diet"[Mesh]'],
        "keywords": ['nutrition*[tiab]', 'diet*[tiab]', 'intake[tiab]',
                     'supplement*[tiab]'],
    },
    "Nutrition, absorption, transport and storage": {
        "mesh": ['"Nutritional Requirements"[Mesh]', 'pharmacokinetics[sh]',
                 '"Biological Transport"[Mesh]', 'metabolism[sh]'],
        "keywords": ['nutrition*[tiab]', 'absorption[tiab]', 'transport*[tiab]',
                     'storage[tiab]', 'metabolis*[tiab]'],
    },
    "Deficiency": {
        "mesh": ['deficiency[sh]', '"Deficiency Diseases"[Mesh]',
                 '"Malnutrition"[Mesh]'],
        "keywords": ['deficien*[tiab]', 'depletion[tiab]', 'hypovitamin*[tiab]',
                     'insufficien*[tiab]'],
    },
    "Toxicity": {
        "mesh": ['toxicity[sh]', '"adverse effects"[sh]', '"Drug-Related Side Effects '
                 'and Adverse Reactions"[Mesh]'],
        "keywords": ['toxicit*[tiab]', 'overdose[tiab]', '"adverse reaction*"[tiab]',
                     'nephrotoxic*[tiab]'],
    },
}


def _resolve(title: str) -> str | None:
    """Il titolo del canone che questo titolo scritto a mano vuol dire.

    Si prova prima cosi' com'e', poi attraverso i sinonimi di `structure`:
    `etiology` e `CT scan` sono i modi in cui i titoli si trovano scritti negli
    articoli veri, e sono gia' mappati li'.
    """
    key = sx.normalise(title)
    if not key:
        return None
    by_norm = {sx.normalise(name): name for name in STRATEGIES}
    if key in by_norm:
        return by_norm[key]
    try:
        target = sx.canon().synonyms.get(key)
    except sx.StructureError:
        return None
    if target and sx.normalise(target) in by_norm:
        return by_norm[sx.normalise(target)]
    return None


def has(title: str) -> bool:
    return _resolve(title) is not None


def terms_for(title: str, mode: str = "both") -> list[str]:
    """I singoli pezzi, gia' scritti in sintassi PubMed. [] se non c'e' nulla."""
    name = _resolve(title)
    if not name:
        return []
    entry = STRATEGIES[name]
    if mode == "mesh":
        return list(entry["mesh"])
    if mode == "keywords":
        return list(entry["keywords"])
    out = list(entry["mesh"])
    for term in entry["keywords"]:
        if term not in out:
            out.append(term)
    return out


def fragment(title: str, mode: str = "both") -> str:
    """La strategia di un titolo, pronta da mettere in un blocco di ricerca."""
    terms = terms_for(title, mode)
    return "(" + " OR ".join(terms) + ")" if terms else ""


def suggest(titles: list[str], mode: str = "both") -> list[tuple[str, str]]:
    """(titolo del canone, strategia) per i titoli che ne hanno una.

    Nell'ordine in cui sono arrivati - cioe' l'ordine in cui stanno
    nell'articolo - e senza doppioni: `CT` scritto due volte e' una strategia
    sola.
    """
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for title in titles:
        name = _resolve(title)
        if not name or name in seen:
            continue
        seen.add(name)
        out.append((name, fragment(name, mode)))
    return out


def covered() -> list[str]:
    """I titoli per cui una strategia c'e'."""
    return sorted(STRATEGIES)
