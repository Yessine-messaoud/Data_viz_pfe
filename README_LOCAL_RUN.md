# Execution Locale - Viz Agent (Python)

## Prerequis
- Python 3.11+
- Pip
- Cle API Mistral valide

## Installation
1. Ouvrir un terminal dans ce dossier.
2. Installer les dependances:

```bash
python -m pip install -r viz_agent/requirements.txt
```

## Lancer les tests
```bash
python -m pytest tests -q
```

## Lancer le pipeline complet
```bash
python main.py --input <chemin_fichier.twbx> --output <chemin_sortie.rdl>
```

Si `MISTRAL_API_KEY` n est pas definie, le programme la demandera en mode securise.

## Validation RDL (phase 5.1)
- Le pipeline valide le RDL avant ecriture sur disque avec 3 niveaux:
	- XML (syntaxe, namespace, structure)
	- Schema (elements requis, enums, structure RDL)
	- Semantique (references datasets/champs/parametres)
- Des auto-corrections deterministes sont appliquees quand possible.
- Si des erreurs persistent apres les tours de correction, le fichier `.rdl` n est pas ecrit.

## Variables optionnelles
- `MISTRAL_API_KEY` (obligatoire)
- `MISTRAL_MODEL` (defaut: `mistral-small-latest`)
- `MISTRAL_BASE_URL` (defaut: `https://api.mistral.ai/v1`)
- `VIZ_AGENT_RDL_CONNECTION_STRING` (connexion SQL du rapport RDL)

Valeur par defaut de la connexion RDL:

```text
Data Source=localhost\SQLEXPRESS;Initial Catalog=AdventureWorksDW2022
```

Exemple PowerShell (session courante):

```powershell
$env:VIZ_AGENT_RDL_CONNECTION_STRING = "Data Source=localhost\SQLEXPRESS;Initial Catalog=AdventureWorksDW2022"
```

Note: les cles de credentials (`User ID`, `Password`, `Integrated Security`, etc.) sont retirees automatiquement pour eviter les conflits de mode d authentification dans Report Builder/SSRS.

## Sorties
- Rapport pagine RDL: fichier passe dans `--output`
- Lineage JSON: meme nom avec suffixe `_lineage.json`
- Abstract Spec JSON: meme nom avec suffixe `_abstract_spec.json`
- Visualisation HTML du spec: meme nom avec suffixe `_abstract_spec_visualization.html`

## Visualiser le spec abstrait
1. Lancer la pipeline comme d habitude.
2. Ouvrir le fichier HTML genere.

Exemple Windows:

```powershell
start .\output\vente_par_pays_v15_abstract_spec_visualization.html
```

Le JSON du spec est aussi disponible dans:

```text
.\output\vente_par_pays_v15_abstract_spec.json
```

## Erreurs courantes
- Input introuvable: verifier le chemin `--input`
- Input invalide: le fichier doit etre un `.twbx`
- XML TWB invalide: verifier le contenu du workbook
- Hyper extraction indisponible: installer `pantab` ou `tableauhyperapi`
