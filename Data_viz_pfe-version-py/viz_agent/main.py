from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, is_dataclass
from dataclasses import dataclass, field
import getpass
import html
import json
import os
import re
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any
import zipfile

from lxml import etree
from viz_agent.models.abstract_spec import DataLineageSpec, ParsedWorkbook, SemanticModel
from viz_agent.orchestrator.agent_orchestrator import AgentOrchestrator
from viz_agent.orchestrator.agent_state import AgentState
from viz_agent.orchestrator.modular_planner import PlannerAgent
from viz_agent.orchestrator.pipeline_context import PipelineContext
from viz_agent.orchestrator.pipeline_runtime import (
    PipelinePhaseCache,
    PipelineTrace,
    aggregate_confidence,
    build_phase_fingerprint,
    fingerprint_file,
)
from viz_agent.orchestrator.user_intent_detection_agent import UserIntentDetectionAgent
from viz_agent.phase2_semantic.llm_fallback_client import load_llm_keys_from_file

if TYPE_CHECKING:
    from viz_agent.phase0_extraction.data_source_registry import DataSourceRegistry


@dataclass
class PipelinePhaseResult:
    phase: str
    ok: bool
    retry_hint: str = ""
    confidence: float = 0.0
    artifacts: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

def _ensure_mistral_api_key() -> str:
    api_key = os.getenv("MISTRAL_API_KEY", "").strip()
    if api_key:
        return api_key

    entered = getpass.getpass("Mistral API Key: ").strip()
    if not entered:
        raise RuntimeError("Mistral API key is required")
    os.environ["MISTRAL_API_KEY"] = entered
    return entered


def _ensure_llm_api_keys() -> None:
    load_llm_keys_from_file()
    mistral_key = os.getenv("MISTRAL_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not mistral_key and not gemini_key:
        raise RuntimeError("At least one LLM API key is required (MISTRAL_API_KEY or GEMINI_API_KEY)")


class Phase0ExtractionAgent:
    """Single orchestrator for phase 0 source detection and extraction choices."""

    def run(self, tableau_path: str):
        from viz_agent.phase0_extraction.csv_loader import CSVLoader
        from viz_agent.phase0_extraction.data_source_registry import DataSourceRegistry, ResolvedDataSource
        from viz_agent.phase0_extraction.hyper_extractor import HyperExtractor

        registry = DataSourceRegistry()
        input_path = Path(tableau_path)
        suffix = input_path.suffix.lower()
        actions: list[str] = []

        if suffix not in {".twbx", ".twb"}:
            raise ValueError("Input must be a .twb or .twbx file")

        connections = _extract_tableau_connections(tableau_path)
        extracted_hyper_tables = 0
        extracted_csv_tables = 0

        if suffix == ".twbx":
            hyper_frames = HyperExtractor().extract_from_twbx(tableau_path)
            for hyper_name, tables in hyper_frames.items():
                registry.register(
                    hyper_name,
                    ResolvedDataSource(name=hyper_name, source_type="hyper", frames=tables),
                )
                extracted_hyper_tables += len(tables)
            if extracted_hyper_tables:
                actions.append(f"extract_hyper:{extracted_hyper_tables}")

            csv_frames = CSVLoader().extract_from_twbx(tableau_path)
            if csv_frames:
                registry.register(
                    "csv_sources",
                    ResolvedDataSource(name="csv_sources", source_type="csv", frames=csv_frames),
                )
                extracted_csv_tables = len(csv_frames)
                actions.append(f"extract_csv:{extracted_csv_tables}")
        else:
            registry.register(
                input_path.name,
                ResolvedDataSource(name=input_path.name, source_type="tableau_xml", frames={}),
            )
            actions.append("parse_twb_xml")

        live_connections: list[dict[str, str]] = []
        for idx, conn in enumerate(connections, start=1):
            conn_type = str(conn.get("class", "")).strip().lower()
            if not conn_type:
                continue
            registry.register(
                f"live_connection_{idx}",
                ResolvedDataSource(
                    name=str(conn.get("name", f"live_connection_{idx}")),
                    source_type="db",
                    frames={},
                    connection_config=conn,
                ),
            )
            live_connections.append(conn)
        if live_connections:
            actions.append(f"detect_live_connections:{len(live_connections)}")

        all_frames = registry.all_frames()
        has_extract_data = bool(all_frames)
        has_live_data = bool(live_connections)

        if has_extract_data and has_live_data:
            mode = "hybrid"
        elif has_extract_data:
            mode = "extract"
        elif has_live_data:
            mode = "live_sql"
        else:
            mode = "xml_only"

        manifest = {
            "agent": "phase0_extraction_agent",
            "input": str(input_path),
            "source_extension": suffix,
            "mode": mode,
            "tables_extracted": len(all_frames),
            "connections_detected": len(live_connections),
            "actions": actions,
        }

        setattr(registry, "connection_catalog", live_connections)
        setattr(registry, "phase0_manifest", manifest)
        return registry


def _register_data_sources(tableau_path: str) -> DataSourceRegistry:
    return Phase0ExtractionAgent().run(tableau_path)


def _extract_tableau_connections(tableau_path: str) -> list[dict[str, str]]:
    input_path = Path(tableau_path)
    suffix = input_path.suffix.lower()
    parser = etree.XMLParser(recover=True)

    try:
        if suffix == ".twbx":
            with zipfile.ZipFile(input_path) as archive:
                twb_files = [name for name in archive.namelist() if name.endswith(".twb")]
                if not twb_files:
                    return []
                with tempfile.TemporaryDirectory() as temp_dir:
                    twb_name = twb_files[0]
                    archive.extract(twb_name, temp_dir)
                    twb_path = Path(temp_dir) / twb_name
                    root = etree.parse(str(twb_path), parser).getroot()
        elif suffix == ".twb":
            root = etree.parse(str(input_path), parser).getroot()
        else:
            return []
    except Exception:
        return []

    connections: list[dict[str, str]] = []

    for index, named_connection in enumerate(root.findall(".//named-connection"), start=1):
        conn = named_connection.find(".//connection")
        if conn is None:
            continue
        connection_class = str(conn.get("class", "")).strip()
        name = str(named_connection.get("caption", "") or named_connection.get("name", "") or f"connection_{index}")
        server = str(conn.get("server", "") or conn.get("host", "") or "").strip()
        database = str(conn.get("dbname", "") or conn.get("database", "") or "").strip()
        schema = str(conn.get("schema", "") or "").strip()
        connections.append(
            {
                "name": name,
                "class": connection_class,
                "server": server,
                "database": database,
                "schema": schema,
            }
        )

    if not connections:
        for index, datasource in enumerate(root.findall(".//datasource"), start=1):
            conn = datasource.find(".//connection")
            if conn is None:
                continue
            connection_class = str(conn.get("class", "")).strip()
            name = str(datasource.get("caption", "") or datasource.get("name", "") or f"datasource_{index}")
            server = str(conn.get("server", "") or conn.get("host", "") or "").strip()
            database = str(conn.get("dbname", "") or conn.get("database", "") or "").strip()
            schema = str(conn.get("schema", "") or "").strip()
            connections.append(
                {
                    "name": name,
                    "class": connection_class,
                    "server": server,
                    "database": database,
                    "schema": schema,
                }
            )

    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for conn in connections:
        key = (
            str(conn.get("name", "")),
            str(conn.get("class", "")),
            str(conn.get("server", "")),
            str(conn.get("database", "")),
            str(conn.get("schema", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(conn)
    return deduped


def _detect_intent_type(input_path: Path, output_path: Path) -> str:
    output_ext = output_path.suffix.lower()
    input_ext = input_path.suffix.lower()

    if input_ext in {".twbx", ".twb"} and output_ext == ".rdl":
        return "conversion"
    if output_ext in {".json", ".yaml", ".yml"}:
        return "analysis"
    return "generation"


def _build_structured_intent(
    input_path: Path,
    output_path: Path,
    user_request: str | None = None,
    intent_type_override: str | None = None,
    constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    detector = UserIntentDetectionAgent()
    return detector.detect(
        user_request or "",
        input_path=input_path,
        output_path=output_path,
        intent_type_override=intent_type_override,
        constraints=constraints,
    )


def _matching_dashboard_for_page(workbook, page_name: str):
    for dashboard in workbook.dashboards:
        if dashboard.name == page_name:
            return dashboard
    return workbook.dashboards[0] if workbook.dashboards else None


def _to_jsonable(value):
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(v) for v in value]
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump(mode="json")
        except TypeError:
            return value.model_dump()
    return value

def _slugify_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")
    return safe or "table"


def _export_raw_select_star_views(all_frames: dict, output_file: Path) -> tuple[Path, Path]:
    raw_dir = output_file.with_name(f"{output_file.stem}_raw_select_star")
    raw_dir.mkdir(parents=True, exist_ok=True)

    links: list[str] = []
    for table_name, frame in all_frames.items():
        slug = _slugify_name(str(table_name))
        csv_path = raw_dir / f"{slug}.csv"
        html_path = raw_dir / f"{slug}.html"

        frame.to_csv(csv_path, index=False, encoding="utf-8")

        table_html = frame.to_html(index=False)
        html_path.write_text(
            """<!doctype html>
<html lang=\"fr\">
<head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>Raw SELECT * - """
            + html.escape(str(table_name))
            + """</title>
    <style>
        body { font-family: Segoe UI, Arial, sans-serif; margin: 20px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 6px; font-size: 12px; }
        th { background: #f2f2f2; position: sticky; top: 0; }
        .meta { color: #444; margin-bottom: 12px; }
    </style>
</head>
<body>
    <h1>SELECT * - """
            + html.escape(str(table_name))
            + """</h1>
    <p class=\"meta\">Rows: """
            + str(len(frame))
            + """ | Columns: """
            + str(len(frame.columns))
            + """</p>
    """
            + table_html
            + """
</body>
</html>
""",
            encoding="utf-8",
        )

        links.append(
            "<li><strong>"
            + html.escape(str(table_name))
            + "</strong> - "
            + f"<a href=\"{csv_path.name}\">CSV</a> | "
            + f"<a href=\"{html_path.name}\">HTML</a>"
            + "</li>"
        )

    index_path = raw_dir / "index.html"
    index_path.write_text(
        """<!doctype html>
<html lang=\"fr\">
<head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>Raw SELECT * - Index</title>
    <style>
        body { font-family: Segoe UI, Arial, sans-serif; margin: 20px; }
        li { margin: 8px 0; }
    </style>
</head>
<body>
    <h1>Visualisation des donnees extraites (mode SELECT *)</h1>
    <p>Toutes les tables extraites depuis Hyper/CSV sont disponibles ci-dessous.</p>
    <ul>
"""
        + "\n".join(links)
        + """
    </ul>
</body>
</html>
""",
        encoding="utf-8",
    )
    return raw_dir, index_path

def _build_spec_visualization_html(spec) -> str:
        pages = spec.dashboard_spec.pages
        tables = spec.data_lineage.tables
        measures = spec.semantic_model.measures
        visuals_count = sum(len(page.visuals) for page in pages)

        pages_html = ""
        for page in pages:
                visuals_html = "".join(
                        (
                                "<li>"
                                f"<strong>{html.escape(visual.title)}</strong>"
                                f" ({html.escape(visual.type)})"
                                f" - source: {html.escape(visual.source_worksheet)}"
                                "</li>"
                        )
                        for visual in page.visuals
                )
                pages_html += (
                        "<section class='page'>"
                        f"<h3>{html.escape(page.name)}</h3>"
                        f"<p>{len(page.visuals)} visual(s)</p>"
                        f"<ul>{visuals_html}</ul>"
                        "</section>"
                )

        tables_html = "".join(
                f"<li>{html.escape(table.name)} ({len(table.columns)} colonne(s))</li>"
                for table in tables
        )
        measures_html = "".join(f"<li>{html.escape(measure.name)}</li>" for measure in measures)

        spec_json = json.dumps(spec.model_dump(mode="json"), indent=2)
        return f"""<!doctype html>
<html lang=\"fr\">
<head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>Abstract Spec - Viz Agent</title>
    <style>
        :root {{
            --bg: #f5f4ef;
            --card: #ffffff;
            --ink: #1c1c1a;
            --muted: #5b5b56;
            --line: #dfddd3;
            --accent: #0d7a5f;
        }}
        body {{
            margin: 0;
            font-family: Segoe UI, Helvetica, Arial, sans-serif;
            color: var(--ink);
            background: radial-gradient(circle at top right, #efe8d1, var(--bg));
        }}
        .wrap {{ max-width: 1100px; margin: 0 auto; padding: 24px; }}
        .header {{ margin-bottom: 18px; }}
        .header h1 {{ margin: 0 0 8px; }}
        .header p {{ margin: 0; color: var(--muted); }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; margin: 14px 0 24px; }}
        .kpi {{ background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 12px; }}
        .kpi .label {{ color: var(--muted); font-size: 12px; }}
        .kpi .value {{ font-size: 24px; font-weight: 700; }}
        .card {{ background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 14px; margin-bottom: 12px; }}
        h2 {{ margin-top: 0; }}
        ul {{ margin-top: 8px; }}
        .page {{ border-top: 1px solid var(--line); padding-top: 12px; margin-top: 12px; }}
        pre {{
            background: #141414;
            color: #dbf8d3;
            border-radius: 10px;
            padding: 12px;
            overflow-x: auto;
            white-space: pre;
        }}
        .badge {{
            display: inline-block;
            margin-left: 8px;
            background: #def4ec;
            color: var(--accent);
            border: 1px solid #badfd3;
            border-radius: 999px;
            padding: 2px 10px;
            font-size: 12px;
            font-weight: 600;
        }}
    </style>
</head>
<body>
    <div class=\"wrap\">
        <header class=\"header\">
            <h1>Abstract Spec</h1>
            <p>Version {html.escape(spec.version)} <span class=\"badge\">{html.escape(spec.id)}</span></p>
        </header>

        <section class=\"grid\">
            <article class=\"kpi\"><div class=\"label\">Pages</div><div class=\"value\">{len(pages)}</div></article>
            <article class=\"kpi\"><div class=\"label\">Visuals</div><div class=\"value\">{visuals_count}</div></article>
            <article class=\"kpi\"><div class=\"label\">Tables</div><div class=\"value\">{len(tables)}</div></article>
            <article class=\"kpi\"><div class=\"label\">Measures</div><div class=\"value\">{len(measures)}</div></article>
        </section>

        <section class=\"card\">
            <h2>Pages et Visuals</h2>
            {pages_html}
        </section>

        <section class=\"card\">
            <h2>Tables</h2>
            <ul>{tables_html}</ul>
        </section>

        <section class=\"card\">
            <h2>Measures</h2>
            <ul>{measures_html}</ul>
        </section>

        <section class=\"card\">
            <h2>JSON Complet</h2>
            <pre>{html.escape(spec_json)}</pre>
        </section>
    </div>
</body>
</html>
"""


async def run_pipeline(
    twbx_path: str,
    output_path: str,
    *,
    user_request: str | None = None,
    intent_type: str | None = None,
    intent_constraints: dict[str, Any] | None = None,
    include_report_filters: bool = True,
) -> None:
    input_path = Path(twbx_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {twbx_path}")
    if input_path.suffix.lower() not in {".twbx", ".twb"}:
        raise ValueError("Input must be a .twb or .twbx file")

    from viz_agent.phase1_parser.tableau_parser import TableauParser
    from viz_agent.phase2_semantic.phase2_orchestrator import Phase2SemanticOrchestrator
    from viz_agent.phase3_spec.abstract_spec_builder import AbstractSpecBuilder
    from viz_agent.phase3b_validator.abstract_spec_validator import AbstractSpecValidator
    from viz_agent.phase4_transform.calc_field_translator import CalcFieldTranslator
    from viz_agent.phase4_transform.agent.transformation_agent import TransformationAgent
    from viz_agent.phase4_transform.rdl_dataset_mapper import RDLDatasetMapper
    from viz_agent.phase5_rdl.rdl_generator import RDLGenerator
    from viz_agent.phase5_rdl.rdl_layout_builder import RDLLayoutBuilder
    from viz_agent.phase5_rdl.rdl_validator_pipeline import RDLValidatorPipeline
    from viz_agent.phase6_lineage.lineage_service import LineageQueryService
    from viz_agent.validators.expression_validator import ExpressionValidator
    from viz_agent.validators.validation_engine import ValidationEngine

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    phase_results: list[PipelinePhaseResult] = []
    phase_cache = PipelinePhaseCache()
    trace_path = output_file.with_name(f"{output_file.stem}_phase_trace.jsonl")
    tracer = PipelineTrace(trace_path)
    agent_state = AgentState(execution_id=f"run_{output_file.stem}")
    agent_snapshot_dir = output_file.with_name(f"{output_file.stem}_agentic_snapshots")
    agent_state.snapshot(agent_snapshot_dir, "pipeline_start")

    _ensure_llm_api_keys()

    print("\nViz Agent v2 - Tableau to RDL")
    print("=" * 40)

    pipeline_base_fingerprint = fingerprint_file(input_path)

    print("[Phase 0] Data source extraction...")
    agent_state.set_phase("phase0_extraction")
    tracer.emit("phase0_extraction", "start", {"input": str(input_path)})
    registry = _register_data_sources(twbx_path)
    all_frames = registry.all_frames()
    connection_catalog = getattr(registry, "connection_catalog", [])
    phase0_manifest = getattr(registry, "phase0_manifest", {})
    print(f"  extracted tables: {len(all_frames)}")
    print(f"  detected live connections: {len(connection_catalog)}")
    if phase0_manifest:
        print(f"  phase0 mode: {phase0_manifest.get('mode', 'unknown')}")
        print(f"  phase0 agent: {phase0_manifest.get('agent', 'phase0_extraction_agent')}")
    raw_dir, raw_index = _export_raw_select_star_views(all_frames, output_file)
    print(f"  raw select* folder: {raw_dir}")
    print(f"  raw select* index: {raw_index}")
    connections_path = output_file.with_name(f"{output_file.stem}_phase0_connections.json")
    connections_payload = {"connections": connection_catalog}
    connections_path.write_text(json.dumps(connections_payload, indent=2), encoding="utf-8")
    print(f"  phase0 connections: {connections_path}")
    manifest_path = output_file.with_name(f"{output_file.stem}_phase0_manifest.json")
    manifest_path.write_text(json.dumps(phase0_manifest, indent=2), encoding="utf-8")
    print(f"  phase0 manifest: {manifest_path}")
    tracer.emit(
        "phase0_extraction",
        "ok",
        {
            "tables_extracted": len(all_frames),
            "connections_detected": len(connection_catalog),
            "mode": phase0_manifest.get("mode", "unknown") if isinstance(phase0_manifest, dict) else "unknown",
        },
    )
    phase_results.append(
        PipelinePhaseResult(
            phase="phase0_extraction",
            ok=True,
            retry_hint="Verifier le fichier source TWBX/TWB et les dependances d extraction Hyper/CSV.",
            confidence=1.0 if (all_frames or connection_catalog) else 0.5,
            artifacts={
                "mode": phase0_manifest.get("mode", "unknown") if isinstance(phase0_manifest, dict) else "unknown",
                "tables_extracted": len(all_frames),
                "connections_detected": len(connection_catalog),
                "manifest": str(manifest_path),
            },
        )
    )
    agent_state.record_output(
        "phase0_extraction",
        {
            "mode": phase0_manifest.get("mode", "unknown") if isinstance(phase0_manifest, dict) else "unknown",
            "tables_extracted": len(all_frames),
            "connections_detected": len(connection_catalog),
        },
    )

    print("[Phase 1] Tableau parsing...")
    agent_state.set_phase("phase1_parser")
    tracer.emit("phase1_parser", "start", {})
    phase1_fp = build_phase_fingerprint(pipeline_base_fingerprint, "phase1_parser")
    phase1_cached = phase_cache.get("phase1_parser", phase1_fp)
    if phase1_cached:
        workbook = ParsedWorkbook.model_validate(phase1_cached.get("workbook", {}))
        workbook.data_registry = registry
        phase1_summary = phase1_cached.get("summary", {}) if isinstance(phase1_cached, dict) else {}
        phase1_hints = int(phase1_summary.get("semantic_hints", 0) or 0)
        phase1_lineage = int(phase1_summary.get("enriched_lineage", 0) or 0)
        phase1_warnings = int(phase1_summary.get("validation_warnings", 0) or 0)
        print("  cache: HIT (phase1_parser)")
    else:
        workbook = TableauParser().parse(twbx_path, registry)
        phase1_hints = len(getattr(workbook, "semantic_hints", []) or [])
        phase1_lineage = len(getattr(workbook, "enriched_lineage", []) or [])
        phase1_warnings = len(getattr(workbook, "validation_warnings", []) or [])
        phase_cache.set(
            "phase1_parser",
            phase1_fp,
            {
                "summary": {
                    "worksheets": len(workbook.worksheets),
                    "dashboards": len(workbook.dashboards),
                    "calculated_fields": len(workbook.calculated_fields),
                    "datasources": len(workbook.datasources),
                    "semantic_hints": phase1_hints,
                    "enriched_lineage": phase1_lineage,
                    "validation_warnings": phase1_warnings,
                },
                "workbook": workbook.model_dump(mode="json", exclude={"data_registry"}),
            },
        )
        print("  cache: MISS (phase1_parser)")
    print(
        "  "
        f"worksheets={len(workbook.worksheets)}, dashboards={len(workbook.dashboards)}, "
        f"semantic_hints={phase1_hints}, enriched_lineage={phase1_lineage}, warnings={phase1_warnings}"
    )
    phase1_path = output_file.with_name(f"{output_file.stem}_phase1_parsed_workbook.json")
    phase1_payload = {
        "summary": {
            "worksheets": len(workbook.worksheets),
            "dashboards": len(workbook.dashboards),
            "calculated_fields": len(workbook.calculated_fields),
            "datasources": len(workbook.datasources),
            "semantic_hints": phase1_hints,
            "enriched_lineage": phase1_lineage,
            "validation_warnings": phase1_warnings,
        },
        "workbook": workbook.model_dump(mode="json", exclude={"data_registry"}),
    }
    phase1_path.write_text(json.dumps(_to_jsonable(phase1_payload), indent=2), encoding="utf-8")
    print(f"  phase1 parsed workbook: {phase1_path}")
    tracer.emit(
        "phase1_parser",
        "ok",
        {
            "worksheets": len(workbook.worksheets),
            "dashboards": len(workbook.dashboards),
            "warnings": phase1_warnings,
            "cache": "hit" if phase1_cached else "miss",
        },
    )
    phase_results.append(
        PipelinePhaseResult(
            phase="phase1_parser",
            ok=True,
            retry_hint="Verifier la structure XML TWB/TWBX et les references datasource.",
            confidence=1.0 if len(workbook.worksheets) > 0 else 0.6,
            artifacts={
                "worksheets": len(workbook.worksheets),
                "dashboards": len(workbook.dashboards),
                "warnings": phase1_warnings,
                "artifact": str(phase1_path),
            },
        )
    )
    agent_state.record_output(
        "phase1_parser",
        {
            "worksheets": len(workbook.worksheets),
            "dashboards": len(workbook.dashboards),
            "validation_warnings": phase1_warnings,
        },
    )

    print("[Phase 2] Hybrid semantic layer...")
    agent_state.set_phase("phase2_semantic")
    tracer.emit("phase2_semantic", "start", {})
    intent = _build_structured_intent(
        input_path,
        output_file,
        user_request=user_request,
        intent_type_override=intent_type,
        constraints=intent_constraints,
    )
    intent_meta = intent.get("intent_detection") if isinstance(intent, dict) else None
    print(f"  intent_type={intent.get('type')}, action={intent.get('action')}, target={intent.get('pipeline_target')}")
    if isinstance(intent_meta, dict):
        print(
            "  intent_detection: "
            f"agent={intent_meta.get('agent')}, "
            f"supervision={intent_meta.get('supervised_by')}, "
            f"lang={intent_meta.get('language')}, "
            f"confidence={intent_meta.get('confidence')}"
        )
    phase2_fp = build_phase_fingerprint(
        pipeline_base_fingerprint,
        "phase2_semantic",
        upstream_fingerprint=phase1_fp + json.dumps(intent, sort_keys=True),
    )
    phase2_cached = phase_cache.get("phase2_semantic", phase2_fp)
    if phase2_cached:
        semantic_model = SemanticModel.model_validate(phase2_cached.get("semantic_model", {}))
        lineage = DataLineageSpec.model_validate(phase2_cached.get("lineage", {}))
        phase2_artifacts = phase2_cached.get("phase2_artifacts", {}) if isinstance(phase2_cached, dict) else {}
        phase2_result = PipelinePhaseResult(
            phase="phase2_semantic",
            ok=True,
            retry_hint="",
            confidence=float((phase2_cached.get("phase_result") or {}).get("confidence", 0.0) or 0.0),
            artifacts=(phase2_cached.get("phase_result") or {}).get("artifacts", {}),
            errors=[],
        )
        print("  cache: HIT (phase2_semantic)")
    else:
        semantic_model, lineage, phase2_artifacts, phase2_result = Phase2SemanticOrchestrator().run_with_result(workbook, intent)
        print("  cache: MISS (phase2_semantic)")

    if phase2_result.ok:
        print("  mistral semantic_enrichment: SUCCESS")
        phase_cache.set(
            "phase2_semantic",
            phase2_fp,
            {
                "semantic_model": semantic_model.model_dump(mode="json"),
                "lineage": lineage.model_dump(mode="json"),
                "phase2_artifacts": _to_jsonable(phase2_artifacts),
                "phase_result": {
                    "confidence": phase2_result.confidence,
                    "artifacts": _to_jsonable(phase2_result.artifacts),
                },
            },
        )
        tracer.emit(
            "phase2_semantic",
            "ok",
            {
                "fact_table": getattr(semantic_model, "fact_table", ""),
                "measure_count": len(getattr(semantic_model, "measures", []) or []),
                "cache": "hit" if phase2_cached else "miss",
            },
        )
    else:
        print(f"  mistral semantic_enrichment: FAILED ({'; '.join(phase2_result.errors)})")
        agent_state.record_error("phase2_semantic", "; ".join(phase2_result.errors), attempt=1)
        tracer.emit("phase2_semantic", "error", {"errors": phase2_result.errors})
        phase_results.append(
            PipelinePhaseResult(
                phase=phase2_result.phase,
                ok=False,
                retry_hint=phase2_result.retry_hint,
                confidence=phase2_result.confidence,
                artifacts=phase2_result.artifacts,
                errors=phase2_result.errors,
            )
        )
        raise RuntimeError(phase2_result.retry_hint)
    phase_results.append(
        PipelinePhaseResult(
            phase=phase2_result.phase,
            ok=phase2_result.ok,
            retry_hint=phase2_result.retry_hint,
            confidence=phase2_result.confidence,
            artifacts=phase2_result.artifacts,
            errors=phase2_result.errors,
        )
    )
    agent_state.record_output(
        "phase2_semantic",
        {
            "fact_table": semantic_model.fact_table,
            "measures": len(semantic_model.measures),
            "confidence": phase2_result.confidence,
        },
    )
    agent_state.record_confidence("phase2_semantic", phase2_result.confidence, "success" if phase2_result.ok else "error")
    print(f"  fact_table={semantic_model.fact_table}, measures={len(semantic_model.measures)}")

    semantic_model_path = output_file.with_name(f"{output_file.stem}_semantic_model.json")
    semantic_model_payload = {
        "semantic_model": semantic_model.model_dump(mode="json"),
        "phase2_artifacts": phase2_artifacts,
    }
    semantic_model_path.write_text(json.dumps(_to_jsonable(semantic_model_payload), indent=2), encoding="utf-8")
    print(f"  semantic model: {semantic_model_path}")

    print("[Phase 3] AbstractSpec build + validation...")
    agent_state.set_phase("phase3_spec")
    tracer.emit("phase3_spec", "start", {})
    spec = AbstractSpecBuilder.build(workbook, intent, semantic_model, lineage)
    disable_filters_env = os.getenv("VIZ_AGENT_DISABLE_REPORT_FILTERS", "").strip().lower() in {"1", "true", "yes", "on"}
    if (not include_report_filters) or disable_filters_env:
        spec.dashboard_spec.global_filters = []
    spec.rdl_datasets = RDLDatasetMapper.build(registry, lineage)

    validation = AbstractSpecValidator().validate(spec)
    print(f"  abstract score={validation.score}/100")
    if not validation.can_proceed:
        print("\nValidation failed:")
        for issue in validation.errors:
            print(f"  [{issue.code}] {issue.message}")
        raise SystemExit(1)

    engine_payload = spec.model_dump(mode="json")
    engine_context = {
        "semantic_model": spec.semantic_model.model_dump(mode="json"),
        "rdl_datasets": [_to_jsonable(dataset) for dataset in spec.rdl_datasets],
    }
    v2_report = ValidationEngine(max_retries=2).validate_phase("phase3_spec", engine_payload, engine_context)
    print(
        "  validation_v2: "
        f"global={v2_report.score.global_score:.2f}, "
        f"syntax={v2_report.score.syntax_score:.2f}, "
        f"semantic={v2_report.score.semantic_score:.2f}, "
        f"structural={v2_report.score.structural_score:.2f}, "
        f"errors={v2_report.error_count}, warnings={v2_report.warning_count}, retries={v2_report.retries}"
    )
    for fix in v2_report.fixes_applied:
        spec.build_log.append({"level": "info", "message": f"validation_v2 auto-fix: {fix}"})
    if v2_report.fixed_output:
        try:
            fixed_spec = type(spec).model_validate(v2_report.fixed_output)
            fixed_spec.rdl_datasets = spec.rdl_datasets
            spec = fixed_spec
        except Exception:
            pass
    if not v2_report.can_proceed:
        print("\nValidation v2 failed:")
        for issue in v2_report.issues:
            if issue.severity == "error":
                code = issue.code or "V2"
                print(f"  [{code}] {issue.message} @ {issue.location}")
        raise SystemExit(1)
    abstract_spec_path = output_file.with_name(f"{output_file.stem}_abstract_spec.json")
    abstract_spec_path.write_text(json.dumps(spec.model_dump(mode="json"), indent=2), encoding="utf-8")

    abstract_visualization_path = output_file.with_name(
        f"{output_file.stem}_abstract_spec_visualization.html"
    )
    abstract_visualization_path.write_text(_build_spec_visualization_html(spec), encoding="utf-8")
    print(f"  abstract spec json: {abstract_spec_path}")
    print(f"  abstract spec html: {abstract_visualization_path}")
    tracer.emit(
        "phase3_spec",
        "ok",
        {
            "score": float(v2_report.score.global_score),
            "errors": v2_report.error_count,
            "warnings": v2_report.warning_count,
        },
    )
    phase_results.append(
        PipelinePhaseResult(
            phase="phase3_spec",
            ok=True,
            retry_hint="Verifier le mapping de roles semantiques et le contrat visual/data-binding.",
            confidence=max(0.0, min(1.0, float(v2_report.score.global_score))),
            artifacts={
                "validation_score": float(v2_report.score.global_score),
                "errors": v2_report.error_count,
                "warnings": v2_report.warning_count,
                "artifact": str(abstract_spec_path),
            },
        )
    )
    agent_state.record_output(
        "phase3_spec",
        {
            "validation_score": float(v2_report.score.global_score),
            "errors": v2_report.error_count,
            "warnings": v2_report.warning_count,
        },
    )

    print("[Phase 4] Calc field translation...")
    agent_state.set_phase("phase4_transform")
    tracer.emit("phase4_transform", "start", {})
    translator = CalcFieldTranslator(validator=ExpressionValidator())
    for calc in workbook.calculated_fields:
        if calc.expression:
            calc.rdl_expression = translator.translate(calc.expression, semantic_model)
    print(
        "  mistral calc_translation: "
        f"calls={translator.llm_calls}, success={translator.llm_success}, failed={translator.llm_failed}"
    )

    print("[Phase 4.1] Tool model transformation...")
    transform_agent = TransformationAgent()
    tool_model = transform_agent.transform(
        _to_jsonable(spec.model_dump(mode="json")),
        target_tool="RDL",
        context={"intent": intent},
        intent=intent,
    )
    tool_model_path = output_file.with_name(f"{output_file.stem}_tool_model.json")
    tool_model_path.write_text(json.dumps(_to_jsonable(tool_model), indent=2), encoding="utf-8")
    validation_results = tool_model.get("validation_results", []) if isinstance(tool_model, dict) else []
    p4_errors = [issue for issue in validation_results if isinstance(issue, dict) and issue.get("severity") == "error"]
    print(
        "  tool_model: "
        f"datasets={len(tool_model.get('datasets', [])) if isinstance(tool_model, dict) else 0}, "
        f"visuals={len(tool_model.get('visuals', [])) if isinstance(tool_model, dict) else 0}, "
        f"validation_errors={len(p4_errors)}"
    )
    print(f"  tool model: {tool_model_path}")
    if p4_errors:
        tracer.emit("phase4_transform", "error", {"errors": p4_errors})
        raise SystemExit("Phase 4.1 validation failed")
    tracer.emit(
        "phase4_transform",
        "ok",
        {
            "llm_calls": translator.llm_calls,
            "llm_success": translator.llm_success,
            "validation_errors": len(p4_errors),
        },
    )
    phase_results.append(
        PipelinePhaseResult(
            phase="phase4_transform",
            ok=True,
            retry_hint="Verifier les expressions calc fields et la coherence du tool model.",
            confidence=1.0 if not p4_errors else 0.0,
            artifacts={
                "llm_calls": translator.llm_calls,
                "llm_success": translator.llm_success,
                "tool_model": str(tool_model_path),
            },
        )
    )
    agent_state.record_output(
        "phase4_transform",
        {
            "llm_calls": translator.llm_calls,
            "llm_success": translator.llm_success,
            "validation_errors": len(p4_errors),
        },
    )

    print("[Phase 5] RDL generation + validation...")
    agent_state.set_phase("phase5_rdl")
    tracer.emit("phase5_rdl", "start", {})
    layout_builder = RDLLayoutBuilder()
    rdl_pages = layout_builder.compute_pagination(spec.dashboard_spec.pages)

    layouts: dict[str, dict] = {}
    for page in spec.dashboard_spec.pages:
        dashboard = _matching_dashboard_for_page(workbook, page.name)
        visuals = page.visuals
        layouts[page.name] = layout_builder.compute_layout(dashboard, visuals)

    rdl_xml = RDLGenerator(llm_client=translator.llm, calc_translator=translator).generate(spec, layouts, rdl_pages)

    print("[Phase 5.1] RDL 3-level validation + auto-fix...")
    rdl_xml, rdl_report = RDLValidatorPipeline().validate_and_fix(
        rdl_xml,
        auto_fix=True,
        max_fix_rounds=3,
    )
    print(f"  rdl score={rdl_report.score}/100")
    print(
        "  validation: "
        f"errors={rdl_report.error_count}, warnings={rdl_report.warning_count}, "
        f"auto-fixes={len(rdl_report.auto_fixes_applied)}"
    )

    if rdl_report.auto_fixes_applied:
        for fix in rdl_report.auto_fixes_applied:
            spec.build_log.append({"level": "info", "message": fix})
            print(f"    fix: {fix}")

    if not rdl_report.can_proceed:
        tracer.emit(
            "phase5_rdl",
            "error",
            {"errors": [issue.model_dump(mode="json") for issue in rdl_report.all_issues if issue.severity == "error"]},
        )
        print("\nRDL validation failed:")
        for issue in rdl_report.all_issues:
            if issue.severity == "error":
                print(f"  [{issue.code}] {issue.message}")
        raise SystemExit(1)
    tracer.emit(
        "phase5_rdl",
        "ok",
        {
            "score": rdl_report.score,
            "errors": rdl_report.error_count,
            "warnings": rdl_report.warning_count,
            "auto_fixes": len(rdl_report.auto_fixes_applied),
        },
    )
    phase_results.append(
        PipelinePhaseResult(
            phase="phase5_rdl",
            ok=True,
            retry_hint="Verifier dataset-field mapping, schema RDL et coherence semantique chart/tablix.",
            confidence=max(0.0, min(1.0, float(rdl_report.score) / 100.0)),
            artifacts={
                "score": rdl_report.score,
                "errors": rdl_report.error_count,
                "warnings": rdl_report.warning_count,
                "auto_fixes": list(rdl_report.auto_fixes_applied),
            },
        )
    )
    agent_state.record_output(
        "phase5_rdl",
        {
            "score": rdl_report.score,
            "errors": rdl_report.error_count,
            "warnings": rdl_report.warning_count,
        },
    )
    agent_state.record_confidence("phase5_rdl", float(rdl_report.score) / 100.0, "success")

    print("[Phase 6] Lineage export...")
    agent_state.set_phase("phase6_lineage")
    tracer.emit("phase6_lineage", "start", {})
    lineage_service = LineageQueryService(spec.data_lineage)

    output_file.write_text(rdl_xml, encoding="utf-8")

    lineage_path = output_file.with_name(f"{output_file.stem}_lineage.json")
    lineage_path.write_text(lineage_service.to_json(indent=2), encoding="utf-8")
    phase_results.append(
        PipelinePhaseResult(
            phase="phase6_lineage",
            ok=True,
            retry_hint="Verifier les joins lineage et la stabilite du graphe semantique.",
            confidence=1.0,
            artifacts={
                "tables": len(spec.data_lineage.tables),
                "joins": len(spec.data_lineage.joins),
                "artifact": str(lineage_path),
            },
        )
    )
    tracer.emit(
        "phase6_lineage",
        "ok",
        {"tables": len(spec.data_lineage.tables), "joins": len(spec.data_lineage.joins)},
    )
    agent_state.record_output(
        "phase6_lineage",
        {"tables": len(spec.data_lineage.tables), "joins": len(spec.data_lineage.joins)},
    )

    phase_results_path = output_file.with_name(f"{output_file.stem}_phase_results.json")
    global_confidence = aggregate_confidence(phase_results)
    phase_results_path.write_text(
        json.dumps(
            {
                "global_confidence": global_confidence,
                "phases": [_to_jsonable(result) for result in phase_results],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    summary_path = output_file.with_name(f"{output_file.stem}_pipeline_summary.json")
    summary_path.write_text(
        json.dumps(
            {
                "global_confidence": global_confidence,
                "phase_count": len(phase_results),
                "ok_count": sum(1 for p in phase_results if p.ok),
                "trace": str(trace_path),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\nPipeline complete")
    print(f"  raw select* index: {raw_index}")
    print(f"  phase0 connections: {connections_path}")
    print(f"  phase0 manifest: {manifest_path}")
    print(f"  phase1 parsed workbook: {phase1_path}")
    print(f"  semantic model: {semantic_model_path}")
    print(f"  abstract spec: {abstract_spec_path}")
    print(f"  tool model: {tool_model_path}")
    print(f"  visualization: {abstract_visualization_path}")
    print(f"  rdl: {output_file}")
    print(f"  lineage: {lineage_path}")
    print(f"  phase results: {phase_results_path}")
    print(f"  pipeline summary: {summary_path}")
    print(f"  phase trace: {trace_path}")
    agent_snapshot = agent_state.snapshot(agent_snapshot_dir, "pipeline_end")
    print(f"  agent state snapshot: {agent_snapshot}")


def main() -> None:
    parser = argparse.ArgumentParser(description="VizAgent v2 - Tableau (.twb/.twbx) to RDL")
    parser.add_argument("--input", required=True, help="Path to input .twb or .twbx file")
    parser.add_argument("--output", default="output.rdl", help="Path to output .rdl file")
    parser.add_argument(
        "--user-request",
        default="",
        help="Natural-language user request (FR/EN) for agentic intent detection.",
    )
    parser.add_argument(
        "--intent-type",
        choices=["conversion", "generation", "analysis", "optimization"],
        default=None,
        help="Override detected intent type for orchestration metadata.",
    )
    parser.add_argument(
        "--intent-constraints",
        default="{}",
        help='JSON object of intent constraints (example: \'{"strict_mode": true}\').',
    )
    parser.add_argument(
        "--no-report-filters",
        action="store_true",
        help="Disable global filters propagation to ReportParameters in generated RDL.",
    )
    parser.add_argument(
        "--agentic-conversion-only",
        action="store_true",
        help="Run Sprint-2 agentic conversion flow (Phase0->Phase5 tools) and stop.",
    )
    parser.add_argument(
        "--modular-agentic-conversion-only",
        action="store_true",
        help="Run Sprint-3 modular planner flow with retries/fallbacks/cache and stop.",
    )
    args = parser.parse_args()

    try:
        constraints = json.loads(args.intent_constraints)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid --intent-constraints JSON: {exc}") from exc
    if not isinstance(constraints, dict):
        raise ValueError("--intent-constraints must be a JSON object")

    if args.agentic_conversion_only:
        trace = Path(args.output).with_name(f"{Path(args.output).stem}_agentic_phase_trace.jsonl")
        snapshots = Path(args.output).with_name(f"{Path(args.output).stem}_agentic_snapshots")
        state = AgentState(
            execution_id=f"agentic_{Path(args.output).stem}",
            context={
                "intent": {
                    "type": args.intent_type or "conversion",
                    "constraints": constraints,
                }
            },
            artifacts={"source_path": args.input, "output_path": args.output},
        )
        orchestrator = AgentOrchestrator(max_retries=2, trace_file=trace, debug_snapshot_dir=snapshots)
        orchestrator.register_default_phase_tools()
        results = orchestrator.run_conversion_flow(state)
        summary = {name: result.normalized().__dict__ for name, result in results.items()}
        Path(args.output).with_name(f"{Path(args.output).stem}_agentic_results.json").write_text(
            json.dumps(summary, indent=2),
            encoding="utf-8",
        )
        print("Agentic conversion flow complete")
        print(f"  trace: {trace}")
        print(f"  snapshots: {snapshots}")
        return

    if args.modular_agentic_conversion_only:
        trace = Path(args.output).with_name(f"{Path(args.output).stem}_modular_agentic_phase_trace.jsonl")
        snapshots = Path(args.output).with_name(f"{Path(args.output).stem}_modular_agentic_snapshots")
        phase_results_path = Path(args.output).with_name(f"{Path(args.output).stem}_phase_results.json")
        context = PipelineContext(
            execution_id=f"modular_agentic_{Path(args.output).stem}",
            runtime_context={
                "intent": {
                    "type": args.intent_type or "conversion",
                    "constraints": constraints,
                }
            },
            artifacts={"source_path": args.input, "output_path": args.output},
        )
        planner = PlannerAgent(
            max_retries=2,
            trace_file=trace,
            debug_snapshot_dir=snapshots,
            enable_phase_cache=True,
        )
        run = planner.run(context)
        summary = {
            "status": run.status,
            "errors": list(run.errors),
            "retries": dict(run.retries),
            "phase_results": {name: result.normalized().__dict__ for name, result in run.phase_results.items()},
            "confidence_history": list(context.confidence_history),
            "react_history": list(context.react_history),
        }
        phase_result_items = []
        for name, result in run.phase_results.items():
            normalized = result.normalized()
            phase_result_items.append(
                {
                    "phase": name,
                    "ok": normalized.status == "success",
                    "confidence": normalized.confidence,
                    "errors": list(normalized.errors),
                    "artifacts": dict(normalized.output or {}),
                    "retry_hint": normalized.retry_hint,
                }
            )
        Path(args.output).with_name(f"{Path(args.output).stem}_modular_agentic_results.json").write_text(
            json.dumps(summary, indent=2),
            encoding="utf-8",
        )
        phase_results_path.write_text(
            json.dumps(
                {
                    "global_confidence": aggregate_confidence(phase_result_items),
                    "phases": phase_result_items,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print("Modular agentic conversion flow complete")
        print(f"  trace: {trace}")
        print(f"  snapshots: {snapshots}")
        print(f"  phase results: {phase_results_path}")
        return

    asyncio.run(
        run_pipeline(
            args.input,
            args.output,
            user_request=args.user_request,
            intent_type=args.intent_type,
            intent_constraints=constraints,
            include_report_filters=not args.no_report_filters,
        )
    )


if __name__ == "__main__":
    main()
