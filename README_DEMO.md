# README Demo

Ce document explique comment executer la demo end-to-end avec LLM cloud (Mistral), fallback local (llama3), sortie RDL, et validation stricte optionnelle.

## Prerequis

- Node.js 20+
- npm
- Un fichier `.twb` ou `.twbx` dans `Input/` (ou `input/`)

## Installation

```bash
npm install
npm run build
```

## Variables d'environnement LLM

Cloud LLM principal: Mistral

- `MISTRAL_API_KEY`: cle API Mistral (obligatoire pour le cloud)
- `MISTRAL_MODEL`: modele Mistral (optionnel, defaut: `mistral-small-latest`)
- `MISTRAL_BASE_URL`: endpoint API (optionnel, defaut: `https://api.mistral.ai/v1`)

Fallback local:

- `LOCAL_LLM_BASE_URL` (optionnel, defaut: `http://127.0.0.1:11434`)
- `LOCAL_LLM_MODEL` (optionnel, defaut: `llama3`)

## Executer la demo complete

```powershell
$env:MISTRAL_API_KEY="<votre_cle_mistral>"
npm run demo:full
```

Sorties principales:

- `output/abstract-visualization.json`
- `output/abstract-visualization.html`
- `output/abstract-spec.json`
- `output/lineage.json`
- `output/powerbi-paginated-report.rdl`
- `output/powerbi-paginated-report.rdl.validation.json`

## Pipeline execute

Le pipeline complet execute par `npm run demo:full` suit cet ordre:

1. Parse Tableau (.twb/.twbx)
2. Semantic layer (deterministe + LLM)
3. Build AbstractSpec (pivot)
4. Transformation engine (M, DAX, schema)
5. Export artefact cible (RDL)
6. Generation lineage + rapport HTML

Marqueurs de verification dans `output/abstract-spec.json`:

- `semantic_enrichment_mode`
- `semantic_llm_called`
- `calc_translation_llm_calls`
- `calc_translation_llm_success`
- `calc_translation_provider_mistral`
- `calc_translation_provider_local_llama3`
- `calc_translation_provider_failed`

Verification rapide:

```powershell
$spec = Get-Content -Raw output/abstract-spec.json | ConvertFrom-Json
$spec.build_log | ForEach-Object { $_.message } | Where-Object { $_ -match 'semantic_enrichment_mode|calc_translation_provider_mistral|calc_translation_provider_local_llama3|calc_translation_provider_failed' }
```

## Verifier que le LLM a ete utilise

```powershell
$spec = Get-Content -Raw output/abstract-spec.json | ConvertFrom-Json
$msgs = $spec.build_log | ForEach-Object { $_.message }
$msgs | Where-Object {
  $_ -match 'semantic_enrichment_mode|semantic_llm_called|calc_translation_llm_calls|calc_translation_llm_success|calc_translation_provider_mistral|calc_translation_provider_local_llama3|calc_translation_provider_failed'
}
```

Interpretation rapide:

- `calc_translation_provider_mistral>0`: appel cloud Mistral effectif
- `calc_translation_provider_local_llama3>0`: fallback local active
- `calc_translation_provider_failed>0`: echec de traduction pour une partie des calculs

## Mode strict RDL (contraintes metier)

Le mode strict peut imposer:

- noms de datasets obligatoires
- sections XML obligatoires
- conventions de nommage (dataset/textbox/tablix)

Activation au niveau code (API TypeScript):

- `strictMode: true`
- `businessConstraints: { ... }`

Exemple de contraintes:

```ts
{
  strictMode: true,
  businessConstraints: {
    requiredDatasetNames: ["MainDataset"],
    requiredSections: ["PageHeader", "PageFooter", "ReportItems"],
    datasetNamePattern: "^MainDataset$",
    textboxNamePattern: "^tb[A-Z][A-Za-z0-9_]*$",
    tablixNamePattern: "^tablix[A-Za-z0-9_]+$"
  }
}
```

En cas de violation, la generation echoue avec des codes `RDL-BIZ-*`.

## Tests utiles

```bash
npm run build
node --test dist/tests/adapter/paginated-report-builder.test.js
node --test dist/tests/demo/run-full-pipeline-demo.test.js
```
