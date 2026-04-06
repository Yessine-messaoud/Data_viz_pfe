from __future__ import annotations

import argparse
import json
import os
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parent
SCENARIOS_FILE = ROOT / "scenarios.json"
RESULTS_DIR = ROOT / "results"


@dataclass
class ModelConfig:
    name: str
    kind: str
    model_id: str


@dataclass
class CaseResult:
    scenario_id: str
    phase: str
    title: str
    score: float
    latency_ms: int
    passed: bool
    output: str
    notes: str


@dataclass
class ModelResult:
    model_name: str
    total_score: float
    pass_rate: float
    avg_latency_ms: float
    cases: list[CaseResult]


def load_scenarios() -> list[dict[str, Any]]:
    return json.loads(SCENARIOS_FILE.read_text(encoding="utf-8"))


def build_prompt(s: dict[str, Any]) -> str:
    payload = {
        "phase": s["phase"],
        "title": s["title"],
        "goal": s["goal"],
        "input": s["input"],
        "question": s["question"],
    }
    return (
        "You are evaluating a BI conversion pipeline decision. "
        "Answer as strict JSON with keys: decision, rationale, confidence, mapping. "
        "For semantic classification scenarios, mapping must be an object keyed by column name, "
        "each value containing at least role and business_type. "
        "Confidence is a number in [0,1].\n"
        f"Scenario:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def call_model(config: ModelConfig, prompt: str, timeout: int, simulate: bool) -> str:
    if simulate:
        return simulate_answer(config, prompt)

    if config.kind == "mistral_api":
        return call_mistral_api(config.model_id, prompt, timeout)
    if config.kind == "gemini_api":
        return call_gemini_api(config.model_id, prompt, timeout)
    if config.kind == "mistral_local":
        return call_mistral_local(config.model_id, prompt, timeout)

    raise ValueError(f"Unknown model kind: {config.kind}")


def call_mistral_api(model_id: str, prompt: str, timeout: int) -> str:
    key = os.getenv("MISTRAL_API_KEY", "").strip()
    if not key:
        raise RuntimeError("MISTRAL_API_KEY is missing")

    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def call_gemini_api(model_id: str, prompt: str, timeout: int) -> str:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY is missing")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.0},
    }
    resp = requests.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()

    candidates = data.get("candidates", [])
    if not candidates:
        return json.dumps(data)
    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        return json.dumps(candidates[0])
    return "\n".join(str(p.get("text", "")) for p in parts)


def call_mistral_local(model_id: str, prompt: str, timeout: int) -> str:
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    url = f"{base}/api/chat"
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.0},
    }
    resp = requests.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    message = data.get("message", {})
    return str(message.get("content", ""))


def simulate_answer(config: ModelConfig, prompt: str) -> str:
    lower = prompt.lower()
    # Simulate distinct behavior profiles so benchmark ranking is informative.
    profiles = {
        "mistral_api": "strong",
        "gemini_api": "strong_alt",
        "mistral_local": "mid",
    }
    profile = profiles.get(config.kind, "mid")

    if "parsing ambigu" in lower:
        if profile in {"strong", "strong_alt"}:
            decision = "line"
            rationale = "OrderDate on x suggests time trend; line is preferred over bar"
        else:
            decision = "bar"
            rationale = "bar is acceptable but less ideal for temporal trend"
        mapping = {"visual_intent": "trend_over_time"}

    elif "detection semantique" in lower:
        if profile == "strong":
            mapping = {
                "Amt": {"role": "measure", "business_type": "amount"},
                "Value": {"role": "measure", "business_type": "metric"},
                "X1": {"role": "dimension", "business_type": "code"},
                "Region": {"role": "dimension", "business_type": "geography"},
                "OrderDate": {"role": "dimension", "business_type": "date"},
            }
        elif profile == "strong_alt":
            mapping = {
                "Amt": {"role": "measure", "business_type": "amount"},
                "Value": {"role": "measure", "business_type": "count_like"},
                "X1": {"role": "dimension", "business_type": "identifier"},
                "Region": {"role": "dimension", "business_type": "region"},
                "OrderDate": {"role": "dimension", "business_type": "date"},
            }
        else:
            mapping = {
                "Amt": {"role": "dimension", "business_type": "unknown"},
                "Value": {"role": "measure", "business_type": "metric"},
                "X1": {"role": "dimension", "business_type": "code"},
                "Region": {"role": "dimension", "business_type": "region"},
                "OrderDate": {"role": "dimension", "business_type": "date"},
            }
        decision = "semantic_map"
        rationale = "Column role inference based on lexical cues and sample values"

    elif "mapping visuel intelligent" in lower:
        if profile == "strong":
            decision = "bar"
            rationale = "22 subcategories: bar is readable; pie is not appropriate"
        elif profile == "strong_alt":
            decision = "treemap"
            rationale = "Hierarchical composition (Category/SubCategory) favors treemap"
        else:
            decision = "pie"
            rationale = "simple share view"
        mapping = {"candidate_rank": [decision, "bar", "treemap", "pie"]}

    elif "traduction de calculs" in lower:
        if profile in {"strong", "strong_alt"}:
            decision = "rdl_calc"
            rationale = "Use IIF with Nothing for null-equivalent branch"
            mapping = {
                "rdl_expression": "=IIF(Fields!Sales.Value > 1000, (Fields!Sales.Value - Fields!Cost.Value) / Fields!Sales.Value, Nothing)"
            }
        else:
            decision = "rdl_calc"
            rationale = "Approximate translation"
            mapping = {"rdl_expression": "=IIF(Fields!Sales.Value > 1000, Fields!Sales.Value - Fields!Cost.Value, 0)"}

    else:
        if profile in {"strong", "strong_alt"}:
            decision = "autofix"
            rationale = "Replace text aggregation by numeric measure and update mapping"
            mapping = {"fix": "Use Total_Revenue (or Total_Profit) as Y instead of Country"}
        else:
            decision = "autofix"
            rationale = "Try to keep existing mapping"
            mapping = {"fix": "Keep Country and cast"}

    conf = 0.82 if profile == "strong" else (0.79 if profile == "strong_alt" else 0.68)
    return json.dumps(
        {
            "decision": decision,
            "rationale": rationale,
            "confidence": conf,
            "mapping": mapping,
        },
        ensure_ascii=False,
    )


def score_output(scenario: dict[str, Any], output: str) -> tuple[float, str]:
    expected = scenario.get("expected", {})
    text = output.strip()
    lower = text.lower()

    def _extract_json_payload(raw: str) -> dict[str, Any]:
        s = str(raw or "").strip()
        if not s:
            return {}
        try:
            parsed = json.loads(s)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            pass

        start = s.find("{")
        end = s.rfind("}")
        if start >= 0 and end > start:
            try:
                parsed = json.loads(s[start : end + 1])
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
        return {}

    payload = _extract_json_payload(text)
    decision_value = str(payload.get("decision", "") or "").lower()
    mapping_value = payload.get("mapping", {})
    confidence_value = payload.get("confidence", None)

    score = 0.0
    notes: list[str] = []

    any_decisions = [d.lower() for d in expected.get("decision_any_of", [])]
    if any_decisions:
        if decision_value in any_decisions or any(d in lower for d in any_decisions):
            score += 0.4
            notes.append("decision matched")
        else:
            notes.append("decision not matched")

    must_not = [d.lower() for d in expected.get("must_not_be", [])]
    if must_not:
        forbidden_hit = False
        if decision_value and decision_value in must_not:
            forbidden_hit = True
        if not forbidden_hit and isinstance(mapping_value, dict):
            rank = mapping_value.get("candidate_rank")
            if isinstance(rank, list) and rank:
                top = str(rank[0] or "").lower()
                if top in must_not:
                    forbidden_hit = True
        if forbidden_hit:
            notes.append("forbidden decision present")
        else:
            score += 0.2
            notes.append("forbidden decision absent")

    required_keywords = [k.lower() for k in expected.get("must_include_any_keywords", [])]
    if required_keywords:
        hits = sum(1 for k in required_keywords if k in lower)
        score += min(0.3, 0.1 * hits)
        notes.append(f"keyword hits: {hits}")

    col_expect = expected.get("column_expectations", {})
    if col_expect:
        hits = 0
        if isinstance(mapping_value, dict) and mapping_value:
            for col, role in col_expect.items():
                col_key = str(col)
                expected_role = str(role).lower()
                node = mapping_value.get(col_key)
                if isinstance(node, dict):
                    role_value = str(node.get("role", "") or "").lower()
                    if role_value == expected_role:
                        hits += 1
                else:
                    role_value = str(node or "").lower()
                    if expected_role and expected_role in role_value:
                        hits += 1
            score += min(0.6, 0.12 * hits)
        else:
            for col, role in col_expect.items():
                col_l = str(col).lower()
                role_l = str(role).lower()
                pattern = rf"{re.escape(col_l)}[^\n\r]*{re.escape(role_l)}"
                if re.search(pattern, lower):
                    hits += 1
            score += min(0.4, 0.08 * hits)
        notes.append(f"column role hits: {hits}/{len(col_expect)}")

    # Scenario-specific bonus to better separate practical quality.
    scenario_id = str(scenario.get("id", ""))
    if scenario_id == "phase4_calc_translation":
        expr = ""
        if isinstance(mapping_value, dict):
            expr = str(mapping_value.get("rdl_expression", "") or "")
        source = (expr + "\n" + text).lower()
        if "iif" in source and "nothing" in source and "fields!sales" in source and "fields!cost" in source:
            score += 0.2
            notes.append("calc translation structure matched")

    if scenario_id == "phase5_autofix":
        src = lower
        if isinstance(mapping_value, dict):
            src += "\n" + json.dumps(mapping_value, ensure_ascii=False).lower()
        if ("total_revenue" in src or "total_profit" in src) and "country" in src:
            score += 0.2
            notes.append("autofix target field matched")

    # Small tie-breaker component: reward calibrated confidence without dominating task quality.
    try:
        conf = float(confidence_value)
        conf = max(0.0, min(1.0, conf))
        score += 0.03 * conf
        notes.append(f"confidence bonus: {conf:.2f}")
    except Exception:
        pass

    score = min(1.0, score)
    return score, "; ".join(notes)


def default_models(args: argparse.Namespace) -> list[ModelConfig]:
    if args.models:
        items = []
        for raw in args.models.split(","):
            raw = raw.strip()
            if not raw:
                continue
            if ":" not in raw:
                raise ValueError(
                    "Each model must be declared as kind:model_id, e.g. mistral_api:mistral-large-latest"
                )
            kind, model_id = raw.split(":", 1)
            items.append(ModelConfig(name=f"{kind}:{model_id}", kind=kind, model_id=model_id))
        return items

    return [
        ModelConfig(name="mistral_api", kind="mistral_api", model_id="mistral-large-latest"),
        ModelConfig(name="gemini_api", kind="gemini_api", model_id="gemini-1.5-pro"),
        ModelConfig(name="mistral_local", kind="mistral_local", model_id="mistral"),
    ]


def run_benchmark(models: list[ModelConfig], timeout: int, simulate: bool) -> dict[str, Any]:
    scenarios = load_scenarios()
    all_results: list[ModelResult] = []

    for model in models:
        case_results: list[CaseResult] = []

        for scenario in scenarios:
            prompt = build_prompt(scenario)
            start = time.perf_counter()
            try:
                output = call_model(model, prompt, timeout=timeout, simulate=simulate)
                latency = int((time.perf_counter() - start) * 1000)
                score, notes = score_output(scenario, output)
            except Exception as exc:
                latency = int((time.perf_counter() - start) * 1000)
                output = f"ERROR: {exc}"
                score = 0.0
                notes = "request failed"

            case_results.append(
                CaseResult(
                    scenario_id=scenario["id"],
                    phase=scenario["phase"],
                    title=scenario["title"],
                    score=score,
                    latency_ms=latency,
                    passed=score >= 0.6,
                    output=output,
                    notes=notes,
                )
            )

        total = sum(c.score for c in case_results) / max(1, len(case_results))
        pass_rate = sum(1 for c in case_results if c.passed) / max(1, len(case_results))
        avg_latency = sum(c.latency_ms for c in case_results) / max(1, len(case_results))

        all_results.append(
            ModelResult(
                model_name=model.name,
                total_score=round(total, 4),
                pass_rate=round(pass_rate, 4),
                avg_latency_ms=round(avg_latency, 2),
                cases=case_results,
            )
        )

    ranked = sorted(all_results, key=lambda r: (r.total_score, r.pass_rate), reverse=True)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "simulate": simulate,
        "models": [
            {
                "model_name": m.model_name,
                "total_score": m.total_score,
                "pass_rate": m.pass_rate,
                "avg_latency_ms": m.avg_latency_ms,
                "cases": [asdict(c) for c in m.cases],
            }
            for m in ranked
        ],
        "winner": ranked[0].model_name if ranked else None,
    }


def render_markdown_report(result: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Benchmark LLM Comparative Study")
    lines.append("")
    lines.append(f"- Timestamp: {result['timestamp']}")
    lines.append(f"- Simulate mode: {result['simulate']}")
    lines.append(f"- Winner: {result['winner']}")
    lines.append("")
    lines.append("## Leaderboard")
    lines.append("")
    lines.append("| Model | Score | Pass rate | Avg latency (ms) |")
    lines.append("|---|---:|---:|---:|")
    for m in result["models"]:
        lines.append(
            f"| {m['model_name']} | {m['total_score']:.3f} | {100*m['pass_rate']:.1f}% | {m['avg_latency_ms']:.1f} |"
        )

    lines.append("")
    lines.append("## Scenario Details")
    lines.append("")
    for m in result["models"]:
        lines.append(f"### {m['model_name']}")
        lines.append("")
        lines.append("| Scenario | Phase | Score | Pass | Latency (ms) | Notes |")
        lines.append("|---|---|---:|---:|---:|---|")
        for c in m["cases"]:
            lines.append(
                f"| {c['scenario_id']} | {c['phase']} | {c['score']:.2f} | {str(c['passed'])} | {c['latency_ms']} | {c['notes']} |"
            )
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark study for Mistral API, Gemini API, and Mistral local")
    parser.add_argument(
        "--models",
        default="",
        help="Comma-separated kind:model_id items. Example: mistral_api:mistral-large-latest,gemini_api:gemini-1.5-pro,mistral_local:mistral",
    )
    parser.add_argument("--timeout", type=int, default=45, help="HTTP timeout in seconds")
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Do not call providers. Use deterministic simulated outputs.",
    )
    args = parser.parse_args()

    models = default_models(args)
    benchmark = run_benchmark(models=models, timeout=args.timeout, simulate=args.simulate)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = RESULTS_DIR / f"benchmark_{ts}.json"
    md_path = RESULTS_DIR / f"benchmark_{ts}.md"

    json_path.write_text(json.dumps(benchmark, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_markdown_report(benchmark), encoding="utf-8")

    print("Benchmark complete")
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")
    print(f"Winner: {benchmark['winner']}")


if __name__ == "__main__":
    main()
