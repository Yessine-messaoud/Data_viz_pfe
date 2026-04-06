# Benchmark LLM Comparative Study

This folder provides a comparative benchmark between:

- mistral_api (Mistral with API key)
- gemini_api (Gemini with API key)
- mistral_local (local Mistral via Ollama)

The benchmark simulates the following pipeline scenarios:

1. Parsing ambigu (Phase 1)
2. Detection semantique (Phase 2)
3. Mapping visuel intelligent (Phase 3)
4. Traduction de calculs (Phase 4)
5. Auto-fix intelligent (Phase 5)

## Files

- scenarios.json: scenario definitions and expected checks
- run_benchmark.py: runner and scorer
- results/: generated JSON and Markdown reports

## Environment variables

Set only what you need:

- MISTRAL_API_KEY
- GEMINI_API_KEY
- OLLAMA_BASE_URL (optional, default: http://localhost:11434)

## Run

Simulated mode (safe, no provider calls):

python benchmark/run_benchmark.py --simulate

Live mode with defaults:

python benchmark/run_benchmark.py

Custom models:

python benchmark/run_benchmark.py --models mistral_api:mistral-large-latest,gemini_api:gemini-1.5-pro,mistral_local:mistral

## Output

Each run writes:

- benchmark/results/benchmark_YYYYMMDD_HHMMSS.json
- benchmark/results/benchmark_YYYYMMDD_HHMMSS.md

The report includes:

- leaderboard (score, pass rate, latency)
- per-scenario details
- winner model

## Notes

- Scoring is heuristic by design for rapid comparative analysis.
- You can tighten scoring rules in scenarios.json for stricter evaluation.
