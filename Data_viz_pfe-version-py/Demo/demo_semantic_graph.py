from __future__ import annotations

import argparse
import html
import json
import traceback
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from viz_agent.main import Phase0ExtractionAgent
from viz_agent.phase0_extraction.data_source_registry import DataSourceRegistry
from viz_agent.phase1_parser.tableau_parser import TableauParser
from viz_agent.phase2_semantic.llm.mistral_client import LLMResponse
from viz_agent.phase2_semantic.mapping.semantic_mapping_engine import SemanticMappingEngine
from viz_agent.phase2_semantic.phase2_orchestrator import Phase2SemanticOrchestrator


@dataclass
class SemanticDemoCaseResult:
    input_path: str
    status: str
    phase0_mode: str
    extracted_tables: int
    live_connections: int
    worksheets: int
    dashboards: int
    semantic_nodes: int
    semantic_relationships: int
    graph_persisted: bool
    graph_error: str
    graph_json_path: str
    schema_json_path: str
    schema_html_path: str
    schema_tables: int
    schema_columns: int
    orchestration_path: str
    llm_provider: str
    orchestration_confidence: float
    confidence_heuristic: float
    confidence_profiling: float
    confidence_ontology: float
    confidence_llm: float
    metadata_sample: dict[str, Any]
    error: str


class _NoopLLMClient:
    def chat_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        _ = system_prompt
        _ = user_prompt
        return {}


def _run_phase2(workbook, use_real_llm: bool, disable_mapping_llm: bool):
    orchestrator = Phase2SemanticOrchestrator(llm_client=None if use_real_llm else _NoopLLMClient())

    if not disable_mapping_llm:
        return orchestrator.run(workbook, intent={"type": "analysis"})

    original_validate = SemanticMappingEngine._llm_validate

    def _local_validate(self, column: str, candidate: str | None) -> LLMResponse:
        _ = self
        return LLMResponse(
            column=column,
            possible_meaning=candidate,
            mapped_business_term=None,
            confidence=0.0,
            raw={"mode": "disabled_in_demo"},
            error="disabled",
        )

    SemanticMappingEngine._llm_validate = _local_validate
    try:
        return orchestrator.run(workbook, intent={"type": "analysis"})
    finally:
        SemanticMappingEngine._llm_validate = original_validate


def _collect_inputs(input_value: str) -> list[Path]:
    target = Path(input_value)
    if target.is_file():
        return [target] if target.suffix.lower() in {".twb", ".twbx"} else []

    if target.is_dir():
        files = sorted([*target.rglob("*.twbx"), *target.rglob("*.twb")])
        return [path for path in files if path.is_file()]

    base = Path(".")
    files = sorted(base.glob(input_value))
    return [path for path in files if path.is_file() and path.suffix.lower() in {".twb", ".twbx"}]


def _normalize_graph_payload(graph: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(graph) if isinstance(graph, dict) else {}
    nodes_in = normalized.get("nodes", []) if isinstance(normalized.get("nodes", []), list) else []
    rels_in = normalized.get("relationships", []) if isinstance(normalized.get("relationships", []), list) else []

    nodes_out: list[dict[str, Any]] = []
    for node in nodes_in:
        if not isinstance(node, dict):
            continue
        item = dict(node)
        node_type = str(item.get("type") or item.get("label") or item.get("kind") or "Unknown").strip() or "Unknown"
        item["type"] = node_type
        nodes_out.append(item)

    rels_out: list[dict[str, Any]] = []
    for rel in rels_in:
        if not isinstance(rel, dict):
            continue
        item = dict(rel)
        rel_type = str(item.get("type") or item.get("label") or item.get("kind") or "RELATED_TO").strip() or "RELATED_TO"
        item["type"] = rel_type
        rels_out.append(item)

    normalized["nodes"] = nodes_out
    normalized["relationships"] = rels_out
    return normalized


def _build_metadata_sample(registry, workbook, graph: dict[str, Any]) -> dict[str, Any]:
    connections = getattr(registry, "connection_catalog", []) or []
    connection_sample = [
        {
            "name": str(conn.get("name", "")),
            "class": str(conn.get("class", "")),
            "database": str(conn.get("database", "")),
            "server": str(conn.get("server", "")),
        }
        for conn in connections[:3]
        if isinstance(conn, dict)
    ]

    return {
        "datasource_names": [ds.name for ds in workbook.datasources[:5]],
        "worksheet_marks": [
            {
                "worksheet": ws.name,
                "mark_type": str(ws.mark_type),
                "datasource": ws.datasource_name,
            }
            for ws in workbook.worksheets[:5]
        ],
        "connections_sample": connection_sample,
        "graph_node_types": [str(node.get("type", "Unknown")) for node in graph.get("nodes", [])[:8] if isinstance(node, dict)],
        "graph_relationship_types": [
            str(rel.get("type", "RELATED_TO")) for rel in graph.get("relationships", [])[:8] if isinstance(rel, dict)
        ],
    }


def _build_schema_payload(lineage) -> dict[str, Any]:
    tables_payload: list[dict[str, Any]] = []
    total_columns = 0

    for table in getattr(lineage, "tables", []) or []:
        columns_payload: list[dict[str, Any]] = []
        for column in getattr(table, "columns", []) or []:
            columns_payload.append(
                {
                    "name": str(getattr(column, "name", "")),
                    "role": str(getattr(column, "role", "unknown")),
                    "pbi_type": str(getattr(column, "pbi_type", "text")),
                    "label": str(getattr(column, "label", "")),
                }
            )
        total_columns += len(columns_payload)
        tables_payload.append(
            {
                "id": str(getattr(table, "id", "")),
                "name": str(getattr(table, "name", "")),
                "source_name": str(getattr(table, "source_name", "")),
                "schema": str(getattr(table, "schema", "dbo")),
                "row_count": int(getattr(table, "row_count", 0) or 0),
                "columns": columns_payload,
            }
        )

    return {
        "tables": tables_payload,
        "summary": {
            "tables": len(tables_payload),
            "columns": total_columns,
        },
    }


def _render_schema_html(output_html: Path, input_path: Path, phase0_mode: str, schema_payload: dict[str, Any]) -> None:
    table_blocks: list[str] = []
    for table in schema_payload.get("tables", []):
        if not isinstance(table, dict):
            continue

        rows: list[str] = []
        for col in table.get("columns", []):
            if not isinstance(col, dict):
                continue
            rows.append(
                "<tr>"
                f"<td>{html.escape(str(col.get('name', '')))}</td>"
                f"<td>{html.escape(str(col.get('role', '')))}</td>"
                f"<td>{html.escape(str(col.get('pbi_type', '')))}</td>"
                f"<td>{html.escape(str(col.get('label', '')))}</td>"
                "</tr>"
            )

        table_name = html.escape(str(table.get("name", "")))
        row_count = int(table.get("row_count", 0) or 0)
        table_blocks.append(
            "<section style='margin-bottom:20px;'>"
            f"<h3>{table_name}</h3>"
            f"<p>Row count estime: {row_count} | Colonnes: {len(table.get('columns', []))}</p>"
            "<table><tr><th>Colonne</th><th>Role</th><th>Type PBI</th><th>Label</th></tr>"
            + "".join(rows)
            + "</table></section>"
        )

    summary = schema_payload.get("summary", {}) if isinstance(schema_payload, dict) else {}
    content = (
        "<!doctype html><html><head><meta charset='utf-8'><title>Schema detecte</title>"
        "<style>body{font-family:Segoe UI,Arial,sans-serif;padding:20px;background:#f8fafc;}"
        "table{border-collapse:collapse;width:100%;background:#fff;}"
        "th,td{border:1px solid #cbd5e1;padding:8px;vertical-align:top;font-size:12px;}"
        "th{background:#e2e8f0;}</style></head><body>"
        "<h1>Schema detecte - Phase semantique</h1>"
        f"<p>Input: {html.escape(str(input_path))}</p>"
        f"<p>Mode phase0: {html.escape(phase0_mode)}</p>"
        f"<p>Tables: {int(summary.get('tables', 0) or 0)} | Colonnes: {int(summary.get('columns', 0) or 0)}</p>"
        + "".join(table_blocks)
        + "</body></html>"
    )

    output_html.parent.mkdir(parents=True, exist_ok=True)
    output_html.write_text(content, encoding="utf-8")


def _safe_slug(path: Path) -> str:
    stem = path.stem
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in stem)


def _run_case(
    input_path: Path,
    output_dir: Path,
    schema_dir: Path,
    use_real_llm: bool,
    disable_mapping_llm: bool,
) -> SemanticDemoCaseResult:
    phase0_agent = Phase0ExtractionAgent()
    parser = TableauParser()
    extraction_error = ""

    try:
        registry = phase0_agent.run(str(input_path))
    except Exception as exc:
        registry = DataSourceRegistry()
        extraction_error = f"Phase0 {type(exc).__name__}: {exc}"

    try:
        workbook = parser.parse(str(input_path), registry)
    except Exception as exc:
        trace = traceback.format_exc(limit=2)
        joined_error = extraction_error.strip()
        parsing_error = f"Phase1 {type(exc).__name__}: {exc}\n{trace}"
        if joined_error:
            joined_error = joined_error + "\n" + parsing_error
        else:
            joined_error = parsing_error
        return SemanticDemoCaseResult(
            input_path=str(input_path),
            status="KO",
            phase0_mode="-",
            extracted_tables=0,
            live_connections=0,
            worksheets=0,
            dashboards=0,
            semantic_nodes=0,
            semantic_relationships=0,
            graph_persisted=False,
            graph_error="",
            graph_json_path="",
            schema_json_path="",
            schema_html_path="",
            schema_tables=0,
            schema_columns=0,
            orchestration_path="-",
            llm_provider="-",
            orchestration_confidence=0.0,
            confidence_heuristic=0.0,
            confidence_profiling=0.0,
            confidence_ontology=0.0,
            confidence_llm=0.0,
            metadata_sample={},
            error=joined_error,
        )

    try:
        semantic_model, lineage, artifacts = _run_phase2(
            workbook,
            use_real_llm=use_real_llm,
            disable_mapping_llm=disable_mapping_llm,
        )
        _ = semantic_model
        _ = lineage
        graph_raw = artifacts.get("graph", {}) if isinstance(artifacts, dict) else {}
        graph = _normalize_graph_payload(graph_raw)
        orchestration = artifacts.get("orchestration", {}) if isinstance(artifacts, dict) else {}
        confidence_components = orchestration.get("confidence_components", {}) if isinstance(orchestration, dict) else {}
        llm_provider = str(orchestration.get("llm_provider", "none")) if isinstance(orchestration, dict) else "none"
        nodes = graph.get("nodes", []) if isinstance(graph, dict) else []
        relationships = graph.get("relationships", []) if isinstance(graph, dict) else []
        persisted = bool(graph.get("persisted", False)) if isinstance(graph, dict) else False
        graph_error = str(graph.get("error", "")) if isinstance(graph, dict) else ""

        slug = _safe_slug(input_path)
        graph_json_path = output_dir / f"{slug}_semantic_graph.json"
        schema_json_path = schema_dir / f"{slug}_detected_schema.json"
        schema_html_path = schema_dir / f"{slug}_detected_schema.html"
        graph_payload = {
            "input": str(input_path),
            "phase0_mode": str((getattr(registry, "phase0_manifest", {}) or {}).get("mode", "unknown")),
            "graph": graph,
            "mappings": artifacts.get("mappings", []) if isinstance(artifacts, dict) else [],
            "orchestration": orchestration,
            "ontology_terms": [
                term.get("name", "")
                for term in (artifacts.get("ontology", {}).get("terms", []) if isinstance(artifacts, dict) else [])
                if isinstance(term, dict)
            ],
        }
        output_dir.mkdir(parents=True, exist_ok=True)
        graph_json_path.write_text(json.dumps(graph_payload, indent=2), encoding="utf-8")

        schema_payload = _build_schema_payload(lineage)
        schema_dir.mkdir(parents=True, exist_ok=True)
        schema_json_path.write_text(json.dumps(schema_payload, indent=2), encoding="utf-8")
        _render_schema_html(
            schema_html_path,
            input_path=input_path,
            phase0_mode=str((getattr(registry, "phase0_manifest", {}) or {}).get("mode", "unknown")),
            schema_payload=schema_payload,
        )

        all_frames = registry.all_frames()
        connections = getattr(registry, "connection_catalog", []) or []
        metadata_sample = _build_metadata_sample(registry, workbook, graph)

        status = "OK" if not extraction_error else "PARTIAL"
        joined_error = extraction_error

        return SemanticDemoCaseResult(
            input_path=str(input_path),
            status=status,
            phase0_mode=str((getattr(registry, "phase0_manifest", {}) or {}).get("mode", "unknown")),
            extracted_tables=len(all_frames),
            live_connections=len(connections),
            worksheets=len(workbook.worksheets),
            dashboards=len(workbook.dashboards),
            semantic_nodes=len(nodes),
            semantic_relationships=len(relationships),
            graph_persisted=persisted,
            graph_error=graph_error,
            graph_json_path=str(graph_json_path),
            schema_json_path=str(schema_json_path),
            schema_html_path=str(schema_html_path),
            schema_tables=int(schema_payload.get("summary", {}).get("tables", 0) or 0),
            schema_columns=int(schema_payload.get("summary", {}).get("columns", 0) or 0),
            orchestration_path=str(orchestration.get("selected_path", "unknown")),
            llm_provider=llm_provider,
            orchestration_confidence=float(orchestration.get("confidence", 0.0) or 0.0),
            confidence_heuristic=float(confidence_components.get("heuristic_score", 0.0) or 0.0),
            confidence_profiling=float(confidence_components.get("profiling_score", 0.0) or 0.0),
            confidence_ontology=float(confidence_components.get("ontology_score", 0.0) or 0.0),
            confidence_llm=float(confidence_components.get("llm_score", 0.0) or 0.0),
            metadata_sample=metadata_sample,
            error=joined_error,
        )
    except Exception as exc:
        trace = traceback.format_exc(limit=2)
        semantic_error = f"Phase2 {type(exc).__name__}: {exc}\n{trace}"
        joined_error = extraction_error.strip()
        if joined_error:
            joined_error = joined_error + "\n" + semantic_error
        else:
            joined_error = semantic_error

        return SemanticDemoCaseResult(
            input_path=str(input_path),
            status="KO",
            phase0_mode=str((getattr(registry, "phase0_manifest", {}) or {}).get("mode", "unknown")),
            extracted_tables=len(registry.all_frames()),
            live_connections=len(getattr(registry, "connection_catalog", []) or []),
            worksheets=len(workbook.worksheets),
            dashboards=len(workbook.dashboards),
            semantic_nodes=0,
            semantic_relationships=0,
            graph_persisted=False,
            graph_error="",
            graph_json_path="",
            schema_json_path="",
            schema_html_path="",
            schema_tables=0,
            schema_columns=0,
            orchestration_path="-",
            llm_provider="-",
            orchestration_confidence=0.0,
            confidence_heuristic=0.0,
            confidence_profiling=0.0,
            confidence_ontology=0.0,
            confidence_llm=0.0,
            metadata_sample={},
            error=joined_error,
        )


def _render_html_report(output_html: Path, results: list[SemanticDemoCaseResult]) -> None:
    path_counts = {
        "cache": sum(1 for item in results if item.orchestration_path == "cache"),
        "fast": sum(1 for item in results if item.orchestration_path == "fast"),
        "fallback": sum(1 for item in results if item.orchestration_path == "fallback"),
        "unknown": sum(1 for item in results if item.orchestration_path not in {"cache", "fast", "fallback"}),
    }
    llm_counts = {
        "mistral": sum(1 for item in results if item.llm_provider == "mistral"),
        "gemini": sum(1 for item in results if item.llm_provider == "gemini"),
        "ollama": sum(1 for item in results if item.llm_provider == "ollama"),
        "none": sum(1 for item in results if item.llm_provider == "none"),
        "unknown": sum(1 for item in results if item.llm_provider not in {"mistral", "gemini", "ollama", "none"}),
    }

    rows = []
    for result in results:
        rows.append(
            "<tr>"
            f"<td>{html.escape(result.input_path)}</td>"
            f"<td>{result.status}</td>"
            f"<td>{html.escape(result.phase0_mode)}</td>"
            f"<td>{result.extracted_tables}</td>"
            f"<td>{result.live_connections}</td>"
            f"<td>{result.worksheets}</td>"
            f"<td>{result.dashboards}</td>"
            f"<td>{result.semantic_nodes}</td>"
            f"<td>{result.semantic_relationships}</td>"
            f"<td>{result.graph_persisted}</td>"
            f"<td>{html.escape(result.graph_error)}</td>"
            f"<td>{html.escape(result.graph_json_path)}</td>"
            f"<td>{html.escape(result.schema_json_path)}</td>"
            f"<td>{html.escape(result.schema_html_path)}</td>"
            f"<td>{result.schema_tables}</td>"
            f"<td>{result.schema_columns}</td>"
            f"<td>{html.escape(result.orchestration_path)}</td>"
            f"<td>{html.escape(result.llm_provider)}</td>"
            f"<td>{result.orchestration_confidence:.3f}</td>"
            f"<td>{result.confidence_heuristic:.3f}</td>"
            f"<td>{result.confidence_profiling:.3f}</td>"
            f"<td>{result.confidence_ontology:.3f}</td>"
            f"<td>{result.confidence_llm:.3f}</td>"
            f"<td><pre>{html.escape(json.dumps(result.metadata_sample, ensure_ascii=True, indent=2))}</pre></td>"
            f"<td><pre>{html.escape(result.error)}</pre></td>"
            "</tr>"
        )

    content = (
        "<!doctype html><html><head><meta charset='utf-8'><title>Semantic Graph Demo</title>"
        "<style>body{font-family:Segoe UI,Arial,sans-serif;padding:20px;background:#f8fafc;}"
        "table{border-collapse:collapse;width:100%;background:#fff;}"
        "th,td{border:1px solid #cbd5e1;padding:8px;vertical-align:top;font-size:12px;}"
        "th{background:#e2e8f0;} .ok{color:#166534;font-weight:700;} .ko{color:#991b1b;font-weight:700;}"
        "pre{margin:0;white-space:pre-wrap;max-width:480px;}</style></head><body>"
        "<h1>Demo Semantic Graph</h1>"
        "<p>Ce rapport couvre phase 0 (extraction), phase 1 (parsing), et phase 2 (semantic graph).</p>"
        f"<p>Paths utilises: cache={path_counts['cache']}, fast={path_counts['fast']}, fallback={path_counts['fallback']}, unknown={path_counts['unknown']}</p>"
        f"<p>LLM utilises: mistral={llm_counts['mistral']}, gemini={llm_counts['gemini']}, ollama={llm_counts['ollama']}, none={llm_counts['none']}, unknown={llm_counts['unknown']}</p>"
        "<table><tr>"
        "<th>Input</th><th>Status</th><th>Mode P0</th><th>Tables</th><th>Connexions</th>"
        "<th>Worksheets</th><th>Dashboards</th><th>Nodes</th><th>Relationships</th>"
        "<th>Persisted</th><th>Graph Error</th><th>Graph JSON</th><th>Schema JSON</th><th>Schema HTML</th>"
        "<th>Schema Tables</th><th>Schema Colonnes</th><th>Path</th><th>LLM</th><th>Confidence</th>"
        "<th>Heuristic</th><th>Profiling</th><th>Ontology</th><th>LLM</th>"
        "<th>Echantillon metadonnees</th><th>Erreur</th>"
        "</tr>"
        + "".join(rows)
        + "</table></body></html>"
    )

    content = content.replace("<td>OK</td>", "<td class='ok'>OK</td>")
    content = content.replace("<td>PARTIAL</td>", "<td style='color:#92400e;font-weight:700;'>PARTIAL</td>")
    content = content.replace("<td>KO</td>", "<td class='ko'>KO</td>")

    output_html.parent.mkdir(parents=True, exist_ok=True)
    output_html.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Demo phase 0 + phase 1 + phase 2 (semantic graph output)")
    parser.add_argument(
        "--input",
        default="input",
        help="Fichier, dossier, ou pattern glob (*.twbx/*.twb). Exemple: input ou input/demo*.twbx",
    )
    parser.add_argument(
        "--graph-dir",
        default="output/semantic_graph",
        help="Dossier de sortie des semantic graph JSON par input",
    )
    parser.add_argument(
        "--schema-dir",
        default="output/semantic_schema",
        help="Dossier de sortie des schemas detectes (JSON + HTML) par input",
    )
    parser.add_argument(
        "--report-json",
        default="output/semantic_graph_report.json",
        help="Chemin du rapport JSON",
    )
    parser.add_argument(
        "--report-html",
        default="output/semantic_graph_report.html",
        help="Chemin du rapport HTML",
    )
    parser.add_argument(
        "--use-real-llm",
        action="store_true",
        help="Utiliser les appels LLM reels pour l'enrichissement semantique (plus lent).",
    )
    parser.add_argument(
        "--allow-mapping-llm",
        action="store_true",
        help="Autoriser les appels LLM du mapping ontologique (reseau).",
    )
    args = parser.parse_args()

    inputs = _collect_inputs(args.input)
    if not inputs:
        raise FileNotFoundError(f"Aucun fichier .twb/.twbx trouve pour: {args.input}")

    graph_dir = Path(args.graph_dir)
    schema_dir = Path(args.schema_dir)

    print("=" * 72)
    print("DEMO SEMANTIC GRAPH (PHASE 0 + PHASE 1 + PHASE 2)")
    print("=" * 72)
    print(f"Inputs detectes: {len(inputs)}")

    results: list[SemanticDemoCaseResult] = []
    for input_path in inputs:
        print(f"\n[RUN] {input_path}")
        result = _run_case(
            input_path,
            graph_dir,
            schema_dir,
            use_real_llm=args.use_real_llm,
            disable_mapping_llm=not args.allow_mapping_llm,
        )
        results.append(result)
        print(
            "  "
            f"status={result.status} | mode={result.phase0_mode} | "
            f"nodes={result.semantic_nodes} | relationships={result.semantic_relationships} | "
            f"path={result.orchestration_path} | llm={result.llm_provider} | conf={result.orchestration_confidence:.3f} | "
            f"graph={result.graph_json_path or '-'} | schema={result.schema_html_path or '-'}"
        )
        if result.error:
            first_line = result.error.splitlines()[0]
            print(f"  error={first_line}")

    ok_count = sum(1 for item in results if item.status == "OK")
    partial_count = sum(1 for item in results if item.status == "PARTIAL")
    ko_count = len(results) - ok_count - partial_count

    report_json = Path(args.report_json)
    report_json.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "summary": {
            "total": len(results),
            "ok": ok_count,
            "partial": partial_count,
            "ko": ko_count,
            "total_nodes": sum(item.semantic_nodes for item in results),
            "total_relationships": sum(item.semantic_relationships for item in results),
            "total_schema_tables": sum(item.schema_tables for item in results),
            "total_schema_columns": sum(item.schema_columns for item in results),
            "path_counts": {
                "cache": sum(1 for item in results if item.orchestration_path == "cache"),
                "fast": sum(1 for item in results if item.orchestration_path == "fast"),
                "fallback": sum(1 for item in results if item.orchestration_path == "fallback"),
                "unknown": sum(
                    1
                    for item in results
                    if item.orchestration_path not in {"cache", "fast", "fallback"}
                ),
            },
            "llm_counts": {
                "mistral": sum(1 for item in results if item.llm_provider == "mistral"),
                "gemini": sum(1 for item in results if item.llm_provider == "gemini"),
                "ollama": sum(1 for item in results if item.llm_provider == "ollama"),
                "none": sum(1 for item in results if item.llm_provider == "none"),
                "unknown": sum(
                    1
                    for item in results
                    if item.llm_provider not in {"mistral", "gemini", "ollama", "none"}
                ),
            },
        },
        "cases": [asdict(item) for item in results],
    }
    report_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report_html = Path(args.report_html)
    _render_html_report(report_html, results)

    print("\n" + "=" * 72)
    print(
        f"Termine: OK={ok_count} | PARTIAL={partial_count} | KO={ko_count} | "
        f"nodes={payload['summary']['total_nodes']} | rels={payload['summary']['total_relationships']}"
    )
    print(f"Graph dir: {graph_dir}")
    print(f"Schema dir: {schema_dir}")
    print(f"Rapport JSON: {report_json}")
    print(f"Rapport HTML: {report_html}")


if __name__ == "__main__":
    main()
