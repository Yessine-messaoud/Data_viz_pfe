from __future__ import annotations

import argparse
import asyncio
import html
import json
import traceback
from types import SimpleNamespace
from datetime import datetime
from pathlib import Path

import pandas as pd

from viz_agent.main import run_pipeline
from viz_agent.models.abstract_spec import AbstractSpec
from viz_agent.orchestrator.modular_planner import PlannerAgent
from viz_agent.orchestrator.pipeline_context import PipelineContext
from viz_agent.phase0_extraction.data_source_registry import DataSourceRegistry
from viz_agent.phase1_parser.tableau_parser import TableauParser
from viz_agent.phase5_rdl.rdl_generator import RDLGenerator
from viz_agent.phase5_rdl.rdl_layout_builder import RDLLayoutBuilder
from viz_agent.phase5_rdl.rdl_validator_pipeline import RDLValidatorPipeline


def _safe_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _sample_csv_tables(raw_dir: Path, max_rows: int = 5) -> str:
    if not raw_dir.exists():
        return "<p>Aucun export raw phase 0 disponible.</p>"

    csv_files = sorted(raw_dir.glob("*.csv"))
    if not csv_files:
        return "<p>Aucun CSV detecte dans le dossier raw.</p>"

    blocks = []
    for csv_path in csv_files[:2]:
        try:
            df = pd.read_csv(csv_path, nrows=max_rows)
            blocks.append(
                f"<h4>{html.escape(csv_path.name)}</h4>"
                f"<p>Rows sample: {len(df)} | Columns: {len(df.columns)}</p>"
                f"{df.to_html(index=False)}"
            )
        except Exception as exc:
            blocks.append(f"<p>Erreur lecture {html.escape(csv_path.name)}: {html.escape(str(exc))}</p>")
    return "".join(blocks)


def _sample_phase0_connections(connections_path: Path) -> str:
    payload = _safe_json(connections_path)
    connections = payload.get("connections", []) if isinstance(payload, dict) else []
    if not connections:
        return "<p>Aucune connexion live detectee.</p>"

    rows = []
    for conn in connections[:5]:
        if not isinstance(conn, dict):
            continue
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(conn.get('name', '-')))}</td>"
            f"<td>{html.escape(str(conn.get('class', '-')))}</td>"
            f"<td>{html.escape(str(conn.get('server', '-')))}</td>"
            f"<td>{html.escape(str(conn.get('database', '-')))}</td>"
            f"<td>{html.escape(str(conn.get('schema', '-')))}</td>"
            "</tr>"
        )

    if not rows:
        return "<p>Aucune connexion live detectee.</p>"

    return (
        f"<p>Connexions live detectees: {len(connections)}</p>"
        "<table><tr><th>Nom</th><th>Type</th><th>Serveur</th><th>Base</th><th>Schema</th></tr>"
        + "".join(rows)
        + "</table>"
    )


def _sample_phase0_manifest(manifest_path: Path) -> str:
    manifest = _safe_json(manifest_path)
    if not isinstance(manifest, dict) or not manifest:
        return "<p>Manifeste phase 0 indisponible.</p>"

    actions = manifest.get("actions", [])
    action_items = "".join(f"<li>{html.escape(str(item))}</li>" for item in actions) or "<li>Aucune action</li>"
    return (
        "<ul>"
        f"<li>Agent: {html.escape(str(manifest.get('agent', '-')))}</li>"
        f"<li>Mode: {html.escape(str(manifest.get('mode', '-')))}</li>"
        f"<li>Tables extraites: {html.escape(str(manifest.get('tables_extracted', 0)))}</li>"
        f"<li>Connexions detectees: {html.escape(str(manifest.get('connections_detected', 0)))}</li>"
        "</ul>"
        "<h4>Actions decidees par l'agent</h4>"
        f"<ul>{action_items}</ul>"
    )


def _sample_phase1(input_path: Path, phase1_path: Path | None = None) -> str:
    payload = _safe_json(phase1_path) if phase1_path and phase1_path.exists() else {}
    if isinstance(payload, dict) and payload.get("workbook"):
        workbook = payload.get("workbook", {})
        summary = payload.get("summary", {}) if isinstance(payload.get("summary"), dict) else {}
        worksheets = workbook.get("worksheets", []) if isinstance(workbook, dict) else []
        dashboards = workbook.get("dashboards", []) if isinstance(workbook, dict) else []
        calculated_fields = workbook.get("calculated_fields", []) if isinstance(workbook, dict) else []
        warnings = workbook.get("validation_warnings", []) if isinstance(workbook, dict) else []

        first_ws = "-"
        first_dash = "-"
        if worksheets and isinstance(worksheets[0], dict):
            first_ws = str(worksheets[0].get("name", "-"))
        if dashboards and isinstance(dashboards[0], dict):
            first_dash = str(dashboards[0].get("name", "-"))

        sheet_items = []
        for ws in worksheets[:6]:
            if not isinstance(ws, dict):
                continue
            ws_name = str(ws.get("name", "-"))
            mark_type = str(ws.get("mark_type", "-"))
            raw_mark = str(ws.get("raw_mark_type", ""))
            datasource = str(ws.get("datasource_name", "-"))
            encoding = ws.get("visual_encoding", {}) if isinstance(ws.get("visual_encoding"), dict) else {}
            confidence = ws.get("confidence", {}) if isinstance(ws.get("confidence"), dict) else {}
            hints = ws.get("semantic_hints", []) if isinstance(ws.get("semantic_hints"), list) else []
            lineage = ws.get("enriched_lineage", []) if isinstance(ws.get("enriched_lineage"), list) else []

            sheet_items.append(
                "<li>"
                f"<strong>{html.escape(ws_name)}</strong> "
                f"(mark={html.escape(mark_type)}"
                + (f", raw={html.escape(raw_mark)}" if raw_mark else "")
                + f", datasource={html.escape(datasource)})"
                + "<br/>"
                + f"encoding={html.escape(json.dumps(encoding, ensure_ascii=True))}"
                + "<br/>"
                + f"confidence={html.escape(json.dumps(confidence, ensure_ascii=True))}"
                + "<br/>"
                + f"semantic_hints={len(hints)}, enriched_lineage={len(lineage)}"
                + "</li>"
            )

        marks = "".join(sheet_items) or "<li>Aucun worksheet</li>"
        warnings_html = "".join(f"<li>{html.escape(str(item))}</li>" for item in warnings[:8]) or "<li>Aucun warning</li>"
        return (
            "<ul>"
            f"<li>Worksheets: {len(worksheets)}</li>"
            f"<li>Dashboards: {len(dashboards)}</li>"
            f"<li>Calculated fields: {len(calculated_fields)}</li>"
            f"<li>Semantic hints (global): {int(summary.get('semantic_hints', 0) or 0)}</li>"
            f"<li>Enriched lineage (global): {int(summary.get('enriched_lineage', 0) or 0)}</li>"
            f"<li>Premier worksheet: {html.escape(first_ws)}</li>"
            f"<li>Premier dashboard: {html.escape(first_dash)}</li>"
            "</ul>"
            "<h4>Worksheets enrichies</h4>"
            f"<ul>{marks}</ul>"
            "<h4>Warnings phase 1</h4>"
            f"<ul>{warnings_html}</ul>"
        )

    try:
        wb = TableauParser().parse(str(input_path), DataSourceRegistry())
    except Exception as exc:
        return f"<p>Parsing phase 1 indisponible: {html.escape(str(exc))}</p>"

    first_ws = wb.worksheets[0].name if wb.worksheets else "-"
    first_dash = wb.dashboards[0].name if wb.dashboards else "-"
    marks = "".join(
        f"<li>{html.escape(ws.name)}: {html.escape(str(ws.mark_type))}</li>"
        for ws in wb.worksheets[:10]
    ) or "<li>Aucun worksheet</li>"
    return (
        "<ul>"
        f"<li>Worksheets: {len(wb.worksheets)}</li>"
        f"<li>Dashboards: {len(wb.dashboards)}</li>"
        f"<li>Calculated fields: {len(wb.calculated_fields)}</li>"
        f"<li>Premier worksheet: {html.escape(first_ws)}</li>"
        f"<li>Premier dashboard: {html.escape(first_dash)}</li>"
        "</ul>"
        "<h4>Mark types detectes</h4>"
        f"<ul>{marks}</ul>"
    )


def _sample_phase2(semantic_path: Path) -> str:
    payload = _safe_json(semantic_path)
    semantic_model = payload.get("semantic_model", {})
    measures = semantic_model.get("measures", []) if isinstance(semantic_model, dict) else []
    fact_table = semantic_model.get("fact_table", "-") if isinstance(semantic_model, dict) else "-"

    measure_names = [m.get("name", "?") for m in measures[:5] if isinstance(m, dict)]
    items = "".join(f"<li>{html.escape(str(name))}</li>" for name in measure_names) or "<li>Aucune mesure</li>"
    return (
        "<ul>"
        f"<li>Fact table: {html.escape(str(fact_table))}</li>"
        f"<li>Nombre de mesures: {len(measures)}</li>"
        "</ul>"
        "<h4>Echantillon mesures</h4>"
        f"<ul>{items}</ul>"
    )


def _sample_phase3(spec_path: Path) -> str:
    spec = _safe_json(spec_path)
    dashboard_spec = spec.get("dashboard_spec", {}) if isinstance(spec, dict) else {}
    pages = dashboard_spec.get("pages", []) if isinstance(dashboard_spec, dict) else []
    first_page = pages[0] if pages else {}
    visuals = first_page.get("visuals", []) if isinstance(first_page, dict) else []
    visual_names = [v.get("title") or v.get("id") for v in visuals[:5] if isinstance(v, dict)]

    return (
        "<ul>"
        f"<li>Pages: {len(pages)}</li>"
        f"<li>Visuals (premiere page): {len(visuals)}</li>"
        "</ul>"
        "<h4>Echantillon visuals (page 1)</h4>"
        "<ul>"
        + ("".join(f"<li>{html.escape(str(v))}</li>" for v in visual_names) or "<li>Aucun visual</li>")
        + "</ul>"
    )


def _sample_phase4_from_rdl(rdl_path: Path) -> str:
    if not rdl_path.exists():
        return "<p>RDL indisponible, echantillon phase 4 non disponible.</p>"
    content = rdl_path.read_text(encoding="utf-8", errors="ignore")
    expr_lines = [line.strip() for line in content.splitlines() if "=" in line and len(line.strip()) < 180]
    sample = expr_lines[:5]
    return (
        "<p>Proxy phase 4: expressions detectees dans le RDL final (translation calc fields).</p>"
        + "<pre>"
        + html.escape("\n".join(sample) if sample else "Aucune expression echantillon")
        + "</pre>"
    )


def _sample_phase4_tool_model(tool_model_path: Path) -> str:
    payload = _safe_json(tool_model_path)
    if not isinstance(payload, dict) or not payload:
        return "<p>Tool model phase 4 indisponible.</p>"
    visuals = payload.get("visuals", []) if isinstance(payload.get("visuals"), list) else []
    rows = []
    for visual in visuals[:6]:
        if not isinstance(visual, dict):
            continue
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(visual.get('id', '-')))}</td>"
            f"<td>{html.escape(str(visual.get('business_type', '-')))}</td>"
            f"<td>{html.escape(str(visual.get('tool_visual_type', '-')))}</td>"
            "</tr>"
        )
    table = (
        "<table><tr><th>Visual</th><th>Type metier</th><th>Type outil</th></tr>"
        + "".join(rows)
        + "</table>"
        if rows
        else "<p>Aucun visual dans le tool model.</p>"
    )
    hints = payload.get("optimization_hints", []) if isinstance(payload.get("optimization_hints"), list) else []
    hints_html = "".join(f"<li>{html.escape(str(item))}</li>" for item in hints) or "<li>Aucun hint</li>"
    return (
        f"<p>Tool model genere: {html.escape(tool_model_path.name)}</p>"
        + table
        + "<h4>Optimizations</h4><ul>"
        + hints_html
        + "</ul>"
    )


def _sample_phase5(rdl_path: Path) -> str:
    if not rdl_path.exists():
        return "<p>Fichier RDL non genere.</p>"
    content = rdl_path.read_text(encoding="utf-8", errors="ignore")
    snippet = content[:1200]
    size_kb = round(rdl_path.stat().st_size / 1024, 2)
    return (
        f"<ul><li>Taille RDL: {size_kb} KB</li></ul>"
        f"<pre>{html.escape(snippet)}</pre>"
    )


def _sample_phase6(lineage_path: Path) -> str:
    lineage = _safe_json(lineage_path)
    tables = lineage.get("tables", []) if isinstance(lineage, dict) else []
    joins = lineage.get("joins", []) if isinstance(lineage, dict) else []
    labels: list[str] = []
    for table in tables:
        if not isinstance(table, dict):
            continue
        technical_name = str(table.get("name", "?"))
        source_name = str(table.get("source_name", "") or "").strip()
        if source_name and source_name != technical_name:
            labels.append(f"{source_name} ({technical_name})")
        else:
            labels.append(technical_name)

    unique_table_names = list(dict.fromkeys(labels))
    table_names = unique_table_names[:5]
    return (
        "<ul>"
        f"<li>Tables lineages (uniques): {len(unique_table_names)}</li>"
        f"<li>Joins: {len(joins)}</li>"
        "</ul>"
        "<h4>Echantillon tables</h4>"
        "<ul>"
        + ("".join(f"<li>{html.escape(str(t))}</li>" for t in table_names) or "<li>Aucune table</li>")
        + "</ul>"
    )


def _regenerate_rdl_from_corrected_spec(
    corrected_spec_path: Path,
    output_rdl: Path,
    *,
    include_report_filters: bool = True,
) -> tuple[bool, str]:
    payload = _safe_json(corrected_spec_path)
    if not isinstance(payload, dict) or not payload:
        return False, "Corrected spec vide ou invalide"

    try:
        spec = AbstractSpec.model_validate(payload)
    except Exception as exc:
        return False, f"Corrected spec incompatible avec AbstractSpec: {exc}"

    if not include_report_filters:
        spec.dashboard_spec.global_filters = []

    # `rdl_datasets` is typed loosely in the model and may contain dicts.
    # RDLGenerator expects attribute-style dataset/field objects.
    normalized_datasets = []
    for dataset in getattr(spec, "rdl_datasets", []) or []:
        if isinstance(dataset, dict):
            fields = []
            for field in dataset.get("fields", []) or []:
                if isinstance(field, dict):
                    fields.append(
                        SimpleNamespace(
                            name=field.get("name", ""),
                            data_field=field.get("data_field", field.get("name", "")),
                            rdl_type=field.get("rdl_type", "String"),
                        )
                    )
                else:
                    fields.append(field)
            normalized_datasets.append(
                SimpleNamespace(
                    name=dataset.get("name", ""),
                    query=dataset.get("query", ""),
                    fields=fields,
                    connection_ref=dataset.get("connection_ref", "DataSource1"),
                )
            )
        else:
            normalized_datasets.append(dataset)
    spec.rdl_datasets = normalized_datasets

    layout_builder = RDLLayoutBuilder()
    rdl_pages = layout_builder.compute_pagination(spec.dashboard_spec.pages)
    layouts: dict[str, dict] = {}
    for page in rdl_pages:
        layouts[page.name] = layout_builder.compute_layout(None, page.visuals)

    generator = RDLGenerator(llm_client=None, calc_translator=None)
    rdl_xml = generator.generate(spec, layouts, rdl_pages)
    final_rdl, report = RDLValidatorPipeline().validate_and_fix(rdl_xml, auto_fix=True)
    if not report.can_proceed:
        return False, f"Validation RDL KO depuis corrected spec: {len(report.errors)} erreurs"

    output_rdl.write_text(final_rdl, encoding="utf-8")
    return True, "RDL regenere depuis abstract_spec.corrected.json"


def _actions_from_manifest(manifest_path: Path) -> str:
    payload = _safe_json(manifest_path)
    actions = payload.get("actions", []) if isinstance(payload, dict) else []
    if not actions:
        return "Aucune action explicite"
    return " | ".join(str(action) for action in actions[:6])


def _actions_from_phase1_payload(phase1_path: Path) -> str:
    payload = _safe_json(phase1_path)
    summary = payload.get("summary", {}) if isinstance(payload, dict) else {}
    if not isinstance(summary, dict) or not summary:
        return "parse_workbook"
    return (
        "parse_worksheets"
        f" | parse_dashboards({int(summary.get('dashboards', 0) or 0)})"
        f" | enrich_semantic_hints({int(summary.get('semantic_hints', 0) or 0)})"
        f" | lineage_enrichment({int(summary.get('enriched_lineage', 0) or 0)})"
    )


def _actions_from_phase2_payload(semantic_path: Path) -> str:
    payload = _safe_json(semantic_path)
    artifacts = payload.get("phase2_artifacts", {}) if isinstance(payload, dict) else {}
    orchestration = artifacts.get("orchestration", {}) if isinstance(artifacts, dict) else {}
    selected_path = str(orchestration.get("selected_path", "unknown"))
    confidence = orchestration.get("confidence")
    mappings = artifacts.get("mappings", []) if isinstance(artifacts, dict) else []
    joins = payload.get("lineage", {}).get("joins", []) if isinstance(payload.get("lineage", {}), dict) else []
    confidence_txt = f"{float(confidence):.2f}" if isinstance(confidence, (int, float)) else "n/a"
    return (
        f"orchestrate({selected_path})"
        f" | resolve_joins({len(joins)})"
        f" | ontology_mapping({len(mappings)})"
        f" | confidence({confidence_txt})"
    )


def _actions_from_phase3_payload(spec_path: Path) -> str:
    payload = _safe_json(spec_path)
    logs = payload.get("build_log", []) if isinstance(payload, dict) else []
    warnings = payload.get("warnings", []) if isinstance(payload, dict) else []
    pages = payload.get("dashboard_spec", {}).get("pages", []) if isinstance(payload.get("dashboard_spec", {}), dict) else []
    return (
        f"build_dashboard_spec({len(pages)} pages)"
        f" | decision_engine_logs({len(logs)})"
        f" | warnings({len(warnings)})"
    )


def _actions_from_phase4_payload(tool_model_path: Path) -> str:
    payload = _safe_json(tool_model_path)
    if not isinstance(payload, dict) or not payload:
        return "translate_calculations | map_visuals"
    datasets = payload.get("datasets", []) if isinstance(payload.get("datasets"), list) else []
    visuals = payload.get("visuals", []) if isinstance(payload.get("visuals"), list) else []
    validation = payload.get("validation_results", []) if isinstance(payload.get("validation_results"), list) else []
    return (
        f"build_tool_model({len(datasets)} datasets)"
        f" | map_visuals({len(visuals)})"
        f" | validate_transform({len(validation)} issues)"
    )


def _actions_from_phase6_payload(lineage_path: Path) -> str:
    payload = _safe_json(lineage_path)
    tables = payload.get("tables", []) if isinstance(payload, dict) else []
    joins = payload.get("joins", []) if isinstance(payload, dict) else []
    return f"build_lineage_tables({len(tables)}) | build_lineage_joins({len(joins)})"


def _render_dashboard(
    dashboard_path: Path,
    phase_rows: list[dict],
    input_path: Path,
    output_rdl: Path,
) -> None:
    rows_html = []
    for row in phase_rows:
        status = row["status"]
        color = "#e8f5e9" if status == "OK" else "#ffebee"
        rows_html.append(
            f"<tr style='background:{color}'>"
            f"<td>{html.escape(row['phase'])}</td>"
            f"<td>{html.escape(status)}</td>"
            f"<td>{html.escape(row.get('actions', '-'))}</td>"
            f"<td>{html.escape(row['summary'])}</td>"
            "</tr>"
        )
    details_html = "".join(
        f"<section><h3>{html.escape(r['phase'])}</h3>{r['details']}</section>" for r in phase_rows
    )

    doc = f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Demo Pipeline Phases</title>
  <style>
    body {{ font-family: Segoe UI, Arial, sans-serif; margin: 24px; background: #f7f7f4; color: #1b1b1b; }}
    .meta {{ margin-bottom: 18px; color: #444; }}
    table {{ border-collapse: collapse; width: 100%; background: white; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; vertical-align: top; }}
    th {{ background: #ecebe6; text-align: left; }}
    section {{ margin-top: 20px; padding: 14px; background: white; border: 1px solid #ddd; border-radius: 8px; }}
    pre {{ background: #111; color: #d3ffd4; padding: 10px; border-radius: 6px; overflow-x: auto; }}
  </style>
</head>
<body>
    <h1>Demo Pipeline Complet - Etat et Actions par Phase</h1>
  <div class="meta">
    <div>Input: {html.escape(str(input_path))}</div>
    <div>Output RDL: {html.escape(str(output_rdl))}</div>
        <div>Genere le: {html.escape(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}</div>
        <div><a href="{html.escape(output_rdl.name)}">Ouvrir le RDL genere</a></div>
  </div>
  <table>
        <tr><th>Phase</th><th>Status</th><th>Actions</th><th>Resume</th></tr>
    {''.join(rows_html)}
  </table>
  {details_html}
</body>
</html>
"""
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard_path.write_text(doc, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Demo pipeline complet avec dashboard des phases")
    parser.add_argument("--input", default="input/demo_ssms.twbx", help="Chemin .twbx de demo")
    parser.add_argument("--output", default="", help="Fichier RDL cible (optionnel)")
    parser.add_argument(
        "--dashboard",
        default="",
        help="Dashboard HTML de synthese",
    )
    parser.add_argument(
        "--output-dir",
        default="output/vendredi03",
        help="Dossier de sortie pour la demo complete",
    )
    parser.add_argument(
        "--prefer-corrected-spec",
        action="store_true",
        default=True,
        help="Regenerer le RDL final depuis _abstract_spec.corrected.json si present",
    )
    parser.add_argument(
        "--with-report-filters",
        action="store_true",
        help="Inclure les filtres globaux dans le RDL (ReportParameters). Par defaut: desactive.",
    )
    parser.add_argument("--sample-rows", type=int, default=5, help="Nombre de lignes pour les echantillons")
    parser.add_argument(
        "--modular-agentic",
        action="store_true",
        help="Executer la demo via PlannerAgent modulaire (avec runtime validation).",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_rdl = Path(args.output) if args.output else output_dir / "demo_complet_vendredi03.rdl"
    dashboard_path = Path(args.dashboard) if args.dashboard else output_dir / "dashboard_demo_complet_vendredi03.html"

    semantic_path = output_rdl.with_name(f"{output_rdl.stem}_semantic_model.json")
    phase1_path = output_rdl.with_name(f"{output_rdl.stem}_phase1_parsed_workbook.json")
    spec_path = output_rdl.with_name(f"{output_rdl.stem}_abstract_spec.json")
    corrected_spec_path = output_rdl.with_name(f"{output_rdl.stem}_abstract_spec.corrected.json")
    lineage_path = output_rdl.with_name(f"{output_rdl.stem}_lineage.json")
    tool_model_path = output_rdl.with_name(f"{output_rdl.stem}_tool_model.json")
    raw_dir = output_rdl.with_name(f"{output_rdl.stem}_raw_select_star")
    connections_path = output_rdl.with_name(f"{output_rdl.stem}_phase0_connections.json")
    phase0_manifest_path = output_rdl.with_name(f"{output_rdl.stem}_phase0_manifest.json")

    phase_rows: list[dict] = [
        {"phase": "Phase 0 - Extraction", "status": "KO", "actions": "", "summary": "", "details": ""},
        {"phase": "Phase 1 - Parsing", "status": "KO", "actions": "", "summary": "", "details": ""},
        {"phase": "Phase 2 - Semantic", "status": "KO", "actions": "", "summary": "", "details": ""},
        {"phase": "Phase 3 - Spec", "status": "KO", "actions": "", "summary": "", "details": ""},
        {"phase": "Phase 4 - Transform", "status": "KO", "actions": "", "summary": "", "details": ""},
        {"phase": "Phase 5 - RDL", "status": "KO", "actions": "", "summary": "", "details": ""},
        {"phase": "Phase 5b - Runtime Validation", "status": "KO", "actions": "", "summary": "", "details": ""},
        {"phase": "Phase 6 - Lineage", "status": "KO", "actions": "", "summary": "", "details": ""},
    ]

    modular_results_path = output_rdl.with_name(f"{output_rdl.stem}_modular_agentic_results.json")
    modular_trace_path = output_rdl.with_name(f"{output_rdl.stem}_modular_agentic_phase_trace.jsonl")
    modular_snapshots = output_rdl.with_name(f"{output_rdl.stem}_modular_agentic_snapshots")

    try:
        if args.modular_agentic:
            context = PipelineContext(
                execution_id=f"demo_modular_{output_rdl.stem}",
                runtime_context={"intent": {"type": "conversion", "constraints": {}}},
                artifacts={"source_path": str(input_path), "output_path": str(output_rdl)},
            )
            planner = PlannerAgent(max_retries=2, trace_file=modular_trace_path, debug_snapshot_dir=modular_snapshots)
            run = planner.run(context)
            summary = {
                "status": run.status,
                "errors": list(run.errors),
                "retries": dict(run.retries),
                "phase_results": {name: result.normalized().__dict__ for name, result in run.phase_results.items()},
                "confidence_history": list(context.confidence_history),
                "react_history": list(context.react_history),
            }
            modular_results_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
            pipeline_ok = run.status == "success"
        else:
            asyncio.run(
                run_pipeline(
                    str(input_path),
                    str(output_rdl),
                    intent_type="conversion",
                    include_report_filters=args.with_report_filters,
                )
            )
            pipeline_ok = True
    except BaseException as exc:
        pipeline_ok = False
        err = f"{type(exc).__name__}: {exc}"
        trace = traceback.format_exc(limit=2)
        phase_rows[0]["summary"] = "Pipeline interrompu"
        phase_rows[0]["actions"] = "run_pipeline"
        phase_rows[0]["details"] = f"<pre>{html.escape(err + chr(10) + trace)}</pre>"

    if args.modular_agentic:
        payload = _safe_json(modular_results_path)
        phase_results = payload.get("phase_results", {}) if isinstance(payload, dict) else {}
        mapping = {
            "parsing": 1,
            "semantic_reasoning": 2,
            "specification": 3,
            "transformation": 4,
            "export": 5,
            "runtime_validation": 6,
            "validation": 7,
        }
        for phase_name, idx in mapping.items():
            result = phase_results.get(phase_name, {}) if isinstance(phase_results, dict) else {}
            if not isinstance(result, dict) or not result:
                continue
            status = str(result.get("status", "error")).lower()
            conf = float(result.get("confidence", 0.0) or 0.0)
            errors = result.get("errors", []) if isinstance(result.get("errors"), list) else []
            phase_rows[idx]["status"] = "OK" if status == "success" else "KO"
            phase_rows[idx]["actions"] = "modular_planner_execute"
            phase_rows[idx]["summary"] = f"status={status}, confidence={conf:.2f}"
            phase_rows[idx]["details"] = (
                f"<pre>{html.escape(json.dumps(result.get('output', {}), indent=2, ensure_ascii=True))}</pre>"
                if not errors
                else f"<pre>{html.escape(json.dumps({'errors': errors, 'output': result.get('output', {})}, indent=2, ensure_ascii=True))}</pre>"
            )

        phase_rows[0]["status"] = "OK" if input_path.exists() else "KO"
        phase_rows[0]["actions"] = "resolve_source_path"
        phase_rows[0]["summary"] = "Mode modulaire: extraction externalisee" if input_path.exists() else "Input introuvable"
        phase_rows[0]["details"] = (
            "<p>La phase 0 n'est pas executee dans ce mode de demo; les agents commencent en phase parsing.</p>"
        )

        if phase_rows[7]["summary"] == "":
            phase_rows[7]["status"] = "OK" if pipeline_ok else "KO"
            phase_rows[7]["actions"] = "global_validation"
            phase_rows[7]["summary"] = "Validation globale executee" if pipeline_ok else "Validation globale en echec"
            phase_rows[7]["details"] = "<p>Resultat derive du planner modulaire.</p>"

        if modular_trace_path.exists() and not phase_rows[6]["details"]:
            phase_rows[6]["details"] = f"<p>Trace runtime: {html.escape(str(modular_trace_path.name))}</p>"

        _render_dashboard(dashboard_path, phase_rows, input_path, output_rdl)
        print(f"Pipeline status: {'OK' if pipeline_ok else 'KO'}")
        print(f"RDL: {output_rdl}")
        print(f"Modular results: {modular_results_path}")
        print(f"Modular trace: {modular_trace_path}")
        print(f"Dashboard demo: {dashboard_path}")
        return

    # Phase 0
    csv_present = raw_dir.exists() and any(raw_dir.glob("*.csv"))
    connections_payload = _safe_json(connections_path) if connections_path.exists() else {}
    live_connections = connections_payload.get("connections", []) if isinstance(connections_payload, dict) else []
    has_live_connection = bool(live_connections)
    manifest_payload = _safe_json(phase0_manifest_path) if phase0_manifest_path.exists() else {}
    phase0_mode = str(manifest_payload.get("mode", "") or "").strip()

    if csv_present or has_live_connection:
        phase_rows[0]["status"] = "OK"
        phase_rows[0]["actions"] = _actions_from_manifest(phase0_manifest_path) if phase0_manifest_path.exists() else "extract_raw | detect_connections"
        if phase0_mode:
            phase_rows[0]["summary"] = f"Agent phase 0 ({phase0_mode})"
        elif csv_present and has_live_connection:
            phase_rows[0]["summary"] = f"Raw CSV + connexions live detectes ({raw_dir.name})"
        elif csv_present:
            phase_rows[0]["summary"] = f"Dossier raw detecte ({raw_dir.name})"
        else:
            phase_rows[0]["summary"] = "Connexion live detectee (SSMS) - pas d'extract CSV local"

        details = []
        if phase0_manifest_path.exists():
            details.append(_sample_phase0_manifest(phase0_manifest_path))
        if csv_present:
            details.append("<h4>Echantillon raw extract</h4>")
            details.append(_sample_csv_tables(raw_dir, max_rows=max(1, args.sample_rows)))
        if has_live_connection:
            details.append("<h4>Connexions live (phase 0)</h4>")
            details.append(_sample_phase0_connections(connections_path))
        phase_rows[0]["details"] = "".join(details) if details else "<p>Aucun detail phase 0.</p>"
    elif not phase_rows[0]["summary"]:
        phase_rows[0]["actions"] = "extract_raw"
        phase_rows[0]["summary"] = "Aucun artefact raw"
        phase_rows[0]["details"] = "<p>Le dossier raw n'a pas ete trouve.</p>"

    # Phase 1
    try:
        phase_rows[1]["details"] = _sample_phase1(input_path, phase1_path)
        phase_rows[1]["status"] = "OK"
        phase_rows[1]["actions"] = _actions_from_phase1_payload(phase1_path) if phase1_path.exists() else "parse_workbook"
        phase_rows[1]["summary"] = (
            f"Structure workbook analysee ({phase1_path.name})" if phase1_path.exists() else "Structure workbook analysee"
        )
    except Exception as exc:
        phase_rows[1]["actions"] = "parse_workbook"
        phase_rows[1]["summary"] = "Erreur parsing"
        phase_rows[1]["details"] = f"<pre>{html.escape(str(exc))}</pre>"

    # Phase 2
    if semantic_path.exists():
        phase_rows[2]["status"] = "OK"
        phase_rows[2]["actions"] = _actions_from_phase2_payload(semantic_path)
        phase_rows[2]["summary"] = f"Semantic model genere ({semantic_path.name})"
        phase_rows[2]["details"] = _sample_phase2(semantic_path)
    else:
        phase_rows[2]["actions"] = "enrich_semantics"
        phase_rows[2]["summary"] = "Semantic model absent"
        phase_rows[2]["details"] = "<p>Le fichier semantic model n'a pas ete genere.</p>"

    # Phase 3
    if spec_path.exists():
        phase_rows[3]["status"] = "OK"
        phase_rows[3]["actions"] = _actions_from_phase3_payload(spec_path)
        phase_rows[3]["summary"] = f"Abstract spec genere ({spec_path.name})"
        phase_rows[3]["details"] = _sample_phase3(spec_path)
    else:
        phase_rows[3]["actions"] = "build_abstract_spec"
        phase_rows[3]["summary"] = "Abstract spec absent"
        phase_rows[3]["details"] = "<p>Le fichier abstract spec n'a pas ete genere.</p>"

    # Phase 4
    if tool_model_path.exists():
        phase_rows[4]["status"] = "OK"
        phase_rows[4]["actions"] = _actions_from_phase4_payload(tool_model_path)
        phase_rows[4]["summary"] = f"Tool model transforme ({tool_model_path.name})"
        phase_rows[4]["details"] = _sample_phase4_tool_model(tool_model_path)
    else:
        phase_rows[4]["actions"] = "translate_calculations | map_visuals"
        phase_rows[4]["details"] = _sample_phase4_from_rdl(output_rdl)
        if output_rdl.exists():
            phase_rows[4]["status"] = "OK"
            phase_rows[4]["summary"] = "Proxy translation calc fields echantillonnee depuis le RDL"
        else:
            phase_rows[4]["summary"] = "RDL absent, impossible d'echantillonner la phase 4"

    # Phase 5
    corrected_applied = False
    corrected_msg = ""
    if args.prefer_corrected_spec and corrected_spec_path.exists():
        corrected_applied, corrected_msg = _regenerate_rdl_from_corrected_spec(
            corrected_spec_path,
            output_rdl,
            include_report_filters=args.with_report_filters,
        )

    if output_rdl.exists():
        phase_rows[5]["status"] = "OK"
        phase_rows[5]["actions"] = "build_rdl_xml | validate_xml | validate_schema | validate_semantic"
        if corrected_applied:
            phase_rows[5]["summary"] = f"RDL genere depuis corrected spec ({output_rdl.name})"
        else:
            phase_rows[5]["summary"] = f"RDL genere ({output_rdl.name})"
        extra = f"<p>{html.escape(corrected_msg)}</p>" if corrected_msg else ""
        phase_rows[5]["details"] = extra + _sample_phase5(output_rdl)
    else:
        phase_rows[5]["actions"] = "build_rdl_xml"
        phase_rows[5]["summary"] = "RDL non genere"
        phase_rows[5]["details"] = "<p>La phase 5 n'a pas produit de fichier.</p>"

    # Phase 6
    if lineage_path.exists():
        phase_rows[7]["status"] = "OK"
        phase_rows[7]["actions"] = _actions_from_phase6_payload(lineage_path)
        phase_rows[7]["summary"] = f"Lineage genere ({lineage_path.name})"
        phase_rows[7]["details"] = _sample_phase6(lineage_path)
    else:
        phase_rows[7]["actions"] = "build_lineage"
        phase_rows[7]["summary"] = "Lineage absent"
        phase_rows[7]["details"] = "<p>Le fichier lineage n'a pas ete genere.</p>"

    # Phase 5b - Runtime validation (standard mode)
    phase5_results_path = output_rdl.with_name(f"{output_rdl.stem}_phase_results.json")
    phase5_results = _safe_json(phase5_results_path)
    phase_entries = phase5_results.get("phases", []) if isinstance(phase5_results, dict) else []
    runtime_entry = None
    for entry in phase_entries:
        if isinstance(entry, dict) and str(entry.get("phase", "")).lower() == "runtime_validation":
            runtime_entry = entry
            break
    if runtime_entry is not None:
        ok = bool(runtime_entry.get("ok", False))
        conf = float(runtime_entry.get("confidence", 0.0) or 0.0)
        phase_rows[6]["status"] = "OK" if ok else "KO"
        phase_rows[6]["actions"] = "runtime_validation"
        phase_rows[6]["summary"] = f"status={'success' if ok else 'failure'}, confidence={conf:.2f}"
        phase_rows[6]["details"] = f"<pre>{html.escape(json.dumps(runtime_entry, indent=2, ensure_ascii=True))}</pre>"
    else:
        phase_rows[6]["status"] = "OK"
        phase_rows[6]["actions"] = "runtime_validation"
        phase_rows[6]["summary"] = "Non execute dans le pipeline standard"
        phase_rows[6]["details"] = "<p>RuntimeValidationAgent est active en mode planner modulaire.</p>"

    _render_dashboard(dashboard_path, phase_rows, input_path, output_rdl)
    print(f"Pipeline status: {'OK' if pipeline_ok else 'KO'}")
    print(f"RDL: {output_rdl}")
    print(f"Dashboard demo: {dashboard_path}")


if __name__ == "__main__":
    main()
