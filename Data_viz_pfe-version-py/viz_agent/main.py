from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, is_dataclass
import getpass
import html
import json
import os
import re
from pathlib import Path
from typing import Any

def _ensure_mistral_api_key() -> str:
    api_key = os.getenv("MISTRAL_API_KEY", "").strip()
    if api_key:
        return api_key

    entered = getpass.getpass("Mistral API Key: ").strip()
    if not entered:
        raise RuntimeError("Mistral API key is required")
    os.environ["MISTRAL_API_KEY"] = entered
    return entered


def _register_data_sources(tableau_path: str) -> DataSourceRegistry:
    from viz_agent.phase0_data.csv_loader import CSVLoader
    from viz_agent.phase0_data.data_source_registry import DataSourceRegistry, ResolvedDataSource
    from viz_agent.phase0_data.hyper_extractor import HyperExtractor

    registry = DataSourceRegistry()
    input_path = Path(tableau_path)
    suffix = input_path.suffix.lower()

    if suffix == ".twbx":
        hyper_frames = HyperExtractor().extract_from_twbx(tableau_path)
        for hyper_name, tables in hyper_frames.items():
            registry.register(
                hyper_name,
                ResolvedDataSource(name=hyper_name, source_type="hyper", frames=tables),
            )

        csv_frames = CSVLoader().extract_from_twbx(tableau_path)
        if csv_frames:
            registry.register(
                "csv_sources",
                ResolvedDataSource(name="csv_sources", source_type="csv", frames=csv_frames),
            )
    elif suffix == ".twb":
        # TWB is plain XML and does not embed Hyper/CSV extracts.
        registry.register(
            input_path.name,
            ResolvedDataSource(name=input_path.name, source_type="tableau_xml", frames={}),
        )
    else:
        raise ValueError("Input must be a .twb or .twbx file")

    return registry


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
    intent_type_override: str | None = None,
    constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    intent_type = intent_type_override or _detect_intent_type(input_path, output_path)
    constraints = constraints or {}

    return {
        "type": intent_type,
        "action": "export_rdl",
        "constraints": constraints,
        "pipeline_target": "tableau_to_rdl",
        "artifacts": {
            "input_format": input_path.suffix.lower().lstrip("."),
            "output_format": output_path.suffix.lower().lstrip("."),
        },
    }


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
    intent_type: str | None = None,
    intent_constraints: dict[str, Any] | None = None,
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
    from viz_agent.phase4_transform.rdl_dataset_mapper import RDLDatasetMapper
    from viz_agent.phase5_rdl.rdl_generator import RDLGenerator
    from viz_agent.phase5_rdl.rdl_layout_builder import RDLLayoutBuilder
    from viz_agent.phase5_rdl.rdl_validator_pipeline import RDLValidatorPipeline
    from viz_agent.phase6_lineage.lineage_service import LineageQueryService
    from viz_agent.validators.expression_validator import ExpressionValidator

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    _ensure_mistral_api_key()

    print("\nViz Agent v2 - Tableau to RDL")
    print("=" * 40)

    print("[Phase 0] Data source extraction...")
    registry = _register_data_sources(twbx_path)
    all_frames = registry.all_frames()
    print(f"  extracted tables: {len(all_frames)}")
    raw_dir, raw_index = _export_raw_select_star_views(all_frames, output_file)
    print(f"  raw select* folder: {raw_dir}")
    print(f"  raw select* index: {raw_index}")

    print("[Phase 1] Tableau parsing...")
    workbook = TableauParser().parse(twbx_path, registry)
    print(f"  worksheets={len(workbook.worksheets)}, dashboards={len(workbook.dashboards)}")

    print("[Phase 2] Hybrid semantic layer...")
    intent = _build_structured_intent(
        input_path,
        output_file,
        intent_type_override=intent_type,
        constraints=intent_constraints,
    )
    print(f"  intent_type={intent.get('type')}, target={intent.get('pipeline_target')}")
    try:
        semantic_model, lineage, phase2_artifacts = Phase2SemanticOrchestrator().run(workbook, intent)
        print("  mistral semantic_enrichment: SUCCESS")
    except Exception as exc:
        print(f"  mistral semantic_enrichment: FAILED ({exc})")
        raise
    print(f"  fact_table={semantic_model.fact_table}, measures={len(semantic_model.measures)}")

    semantic_model_path = output_file.with_name(f"{output_file.stem}_semantic_model.json")
    semantic_model_payload = {
        "semantic_model": semantic_model.model_dump(mode="json"),
        "phase2_artifacts": phase2_artifacts,
    }
    semantic_model_path.write_text(json.dumps(_to_jsonable(semantic_model_payload), indent=2), encoding="utf-8")
    print(f"  semantic model: {semantic_model_path}")

    print("[Phase 3] AbstractSpec build + validation...")
    spec = AbstractSpecBuilder.build(workbook, intent, semantic_model, lineage)
    spec.rdl_datasets = RDLDatasetMapper.build(registry, lineage)

    validation = AbstractSpecValidator().validate(spec)
    print(f"  abstract score={validation.score}/100")
    if not validation.can_proceed:
        print("\nValidation failed:")
        for issue in validation.errors:
            print(f"  [{issue.code}] {issue.message}")
        raise SystemExit(1)

    abstract_spec_path = output_file.with_name(f"{output_file.stem}_abstract_spec.json")
    abstract_spec_path.write_text(json.dumps(spec.model_dump(mode="json"), indent=2), encoding="utf-8")

    abstract_visualization_path = output_file.with_name(
        f"{output_file.stem}_abstract_spec_visualization.html"
    )
    abstract_visualization_path.write_text(_build_spec_visualization_html(spec), encoding="utf-8")
    print(f"  abstract spec json: {abstract_spec_path}")
    print(f"  abstract spec html: {abstract_visualization_path}")

    print("[Phase 4] Calc field translation...")
    translator = CalcFieldTranslator(validator=ExpressionValidator())
    for calc in workbook.calculated_fields:
        if calc.expression:
            calc.rdl_expression = translator.translate(calc.expression, semantic_model)
    print(
        "  mistral calc_translation: "
        f"calls={translator.llm_calls}, success={translator.llm_success}, failed={translator.llm_failed}"
    )

    print("[Phase 5] RDL generation + validation...")
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
        print("\nRDL validation failed:")
        for issue in rdl_report.all_issues:
            if issue.severity == "error":
                print(f"  [{issue.code}] {issue.message}")
        raise SystemExit(1)

    print("[Phase 6] Lineage export...")
    lineage_service = LineageQueryService(spec.data_lineage)

    output_file.write_text(rdl_xml, encoding="utf-8")

    lineage_path = output_file.with_name(f"{output_file.stem}_lineage.json")
    lineage_path.write_text(lineage_service.to_json(indent=2), encoding="utf-8")

    print("\nPipeline complete")
    print(f"  raw select* index: {raw_index}")
    print(f"  semantic model: {semantic_model_path}")
    print(f"  abstract spec: {abstract_spec_path}")
    print(f"  visualization: {abstract_visualization_path}")
    print(f"  rdl: {output_file}")
    print(f"  lineage: {lineage_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="VizAgent v2 - Tableau (.twb/.twbx) to RDL")
    parser.add_argument("--input", required=True, help="Path to input .twb or .twbx file")
    parser.add_argument("--output", default="output.rdl", help="Path to output .rdl file")
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
    args = parser.parse_args()

    try:
        constraints = json.loads(args.intent_constraints)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid --intent-constraints JSON: {exc}") from exc
    if not isinstance(constraints, dict):
        raise ValueError("--intent-constraints must be a JSON object")

    asyncio.run(
        run_pipeline(
            args.input,
            args.output,
            intent_type=args.intent_type,
            intent_constraints=constraints,
        )
    )


if __name__ == "__main__":
    main()
