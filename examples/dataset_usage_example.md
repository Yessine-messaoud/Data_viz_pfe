# Exemple d usage dataset - Ventes par Pays

## Objectif
Executer le pipeline complet sur le workbook de demonstration `Input/Ventes par Pays.twbx` et verifier les artefacts semantiques exportes.

## Commande (Windows PowerShell)

```powershell
c:/python312/python.exe main.py --input "C:/Users/User/OneDrive/Desktop/TALAN/PFE/Coeur/Input/Ventes par Pays.twbx" --output "C:/Users/User/OneDrive/Desktop/TALAN/PFE/Coeur/version_py/output/ventes_par_pays_demo.rdl"
```

## Artefacts attendus
- `output/ventes_par_pays_demo.rdl`
- `output/ventes_par_pays_demo_lineage.json`
- `output/ventes_par_pays_demo_semantic_model.json`
- `output/ventes_par_pays_demo_abstract_spec.json`
- `output/ventes_par_pays_demo_abstract_spec_visualization.html`
- dossier `output/ventes_par_pays_demo_raw_select_star/`

## Verification rapide du semantic model

```powershell
Get-Content .\output\ventes_par_pays_demo_semantic_model.json -First 80
```

Verifier notamment:
- `semantic_model.fact_table` non vide (idealement `sales_data`)
- `phase2_artifacts.mappings` present
- `phase2_artifacts.graph.nodes` et `phase2_artifacts.graph.relationships` presents
