# Glunova v11 - Deployment Package

Genere automatiquement par le notebook v11 le 2026-05-01.

## Contenu

| Fichier | Description |
|---------|-------------|
| glunova_predictor.py | Module Python autonome avec les 7 modeles + late fusion |
| glunova_config.json | Poids cliniques, seuils, metriques (editable) |
| glunova_api_schema.json | Contrat API (input/output JSON Schema) |
| requirements.txt | Dependances Python a installer |
| README_DEPLOYMENT.md | Ce fichier |

## Installation

```bash
python -m venv venv
source venv/bin/activate   # ou venv\Scripts\activate sur Windows
pip install -r requirements.txt
```

## Utilisation Python (backend)

```python
from glunova_predictor import GlunovaSystem

system = GlunovaSystem(config_path='glunova_config.json')

result = system.predict(
    patient_data={
        'age': 52, 'bmi': 30.5,
        'HbA1c_level': 7.2, 'blood_glucose_level': 165,
        'hypertension': 1, 'heart_disease': 0,
        'gender_enc': 0, 'smoking_enc': 2,
    },
    fundus_image_path='/uploads/eye.jpg',
)

print(result['tier'], '|', result['recommendation'])
```

## Pour le frontend

Voir `glunova_api_schema.json` pour le contrat complet.
- Champs obligatoires: age, HbA1c_level, blood_glucose_level
- Toutes les images sont OPTIONNELLES
- Plus le patient ajoute d'images, plus confidence_factor monte (50% -> 100%)

## Regles cliniques preservees

- **Cap n=1**: tier max = HIGH si seulement le tabular est fourni (ADA 2024)
- **Asymetrie**: Thermal/DFU/Cataract < 0.30 traites comme ABSENT
- **Override DR V8**: Severe/Proliferative + conf >= 0.75 -> CRITICAL FORCE
- **Boost co-occurrence**: Tabular + DR concordants -> MIN HIGH

## Modifier les poids

Editer `glunova_config.json` -> section `clinical_weights`. Pas besoin de toucher au code.

## Limitations connues

- Tongue : metriques internes encore inconnues (poids 0.09 conservateur)
- DFU : test set non encore evalue
- Cataract : F1 par classe instable (legere=0.32, severe=0.29)
- Pas de validation sur cohorte clinique reelle (phase 2)
