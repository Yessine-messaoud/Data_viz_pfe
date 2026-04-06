from __future__ import annotations

import argparse
import html
import json
import traceback
from typing import Any
from dataclasses import asdict, dataclass
from pathlib import Path

from viz_agent.main import Phase0ExtractionAgent
from viz_agent.phase0_extraction.data_source_registry import DataSourceRegistry
from viz_agent.phase1_parser.tableau_parser import TableauParser


@dataclass
class DemoCaseResult:
    input_path: str
    status: str
    phase0_mode: str
    extracted_tables: int
    live_connections: int
    worksheets: int
    dashboards: int
    calculated_fields: int
    datasources: int
    first_worksheet: str
    first_dashboard: str
    metadata_sample: dict[str, Any]
    error: str


def _safe_text(value: Any, fallback: str = "-") -> str:
    text = str(value or "").strip()
    return text if text else fallback


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, indent=2)


def _format_score(score: Any) -> str:
    if not isinstance(score, dict):
        return "-"
    parts = []
    for key in ("visual", "encoding", "datasource_linkage", "overall"):
        if key in score:
            parts.append(f"{key}: {float(score.get(key, 0.0) or 0.0):.2f}")
    return " | ".join(parts) if parts else "-"


def _render_list(items: list[Any]) -> str:
    if not items:
        return "<span class='muted'>Aucun</span>"
    escaped = "".join(f"<li>{html.escape(_safe_text(item))}</li>" for item in items)
    return f"<ul class='inline-list'>{escaped}</ul>"


def _render_key_value_pairs(payload: dict[str, Any]) -> str:
    if not payload:
        return "<span class='muted'>Aucune donnee</span>"
    rows = []
    for key, value in payload.items():
        rows.append(
            "<div class='kv-row'>"
            f"<span class='kv-key'>{html.escape(_safe_text(key))}</span>"
            f"<span class='kv-value'>{html.escape(_safe_text(value))}</span>"
            "</div>"
        )
    return "".join(rows)


def _render_sheet_card(sheet: dict[str, Any]) -> str:
    encoding = sheet.get("visual_encoding", {}) or {}
    confidence = sheet.get("confidence", {}) or {}
    semantic_hints = sheet.get("semantic_hints", []) or []
    lineage = sheet.get("enriched_lineage", []) or []
    warnings = sheet.get("validation_warnings", []) or []
    parts = [
        "<section class='sheet-card'>",
        "<div class='sheet-card__header'>",
        f"<div><h4>{html.escape(_safe_text(sheet.get('name')))}</h4><p>{html.escape(_safe_text(sheet.get('title') or sheet.get('mark_type')))}</p></div>",
        f"<span class='badge badge--{html.escape(_safe_text(sheet.get('mark_type', 'table')).lower())}'>{html.escape(_safe_text(sheet.get('mark_type')))}</span>",
        "</div>",
        "<div class='sheet-card__grid'>",
        "<div><span class='label'>Datasource</span>",
        f"<div>{html.escape(_safe_text(sheet.get('datasource_name')))}</div></div>",
        "<div><span class='label'>Encodage</span>",
        f"<div class='mono'>{html.escape(_compact_json(encoding))}</div></div>",
        "<div><span class='label'>Confidence</span>",
        f"<div>{html.escape(_format_score(confidence))}</div></div>",
        "<div><span class='label'>Semantic hints</span>",
        f"<div class='mono'>{html.escape(_compact_json(semantic_hints[:4]))}</div></div>",
        "<div><span class='label'>Lineage</span>",
        f"<div class='mono'>{html.escape(_compact_json(lineage[:4]))}</div></div>",
        "<div><span class='label'>Warnings</span>",
        f"<div>{_render_list(warnings)}</div></div>",
        "</div>",
        "</section>",
    ]
    return "".join(parts)


def _render_case_card(result: DemoCaseResult) -> str:
    meta = result.metadata_sample if isinstance(result.metadata_sample, dict) else {}
    phase0 = meta.get("phase0", {}) if isinstance(meta.get("phase0"), dict) else {}
    phase1 = meta.get("phase1", {}) if isinstance(meta.get("phase1"), dict) else {}
    worksheets = phase1.get("worksheets", []) if isinstance(phase1.get("worksheets"), list) else []
    dashboards = phase1.get("dashboards", []) if isinstance(phase1.get("dashboards"), list) else []

    sheet_cards = "".join(_render_sheet_card(sheet) for sheet in worksheets[:3])
    if not sheet_cards:
        sheet_cards = "<div class='empty'>Aucune worksheet enrichie</div>"
    parts = [
        "<details class='case-card' open>",
        "<summary>",
        f"<div class='case-title'>{html.escape(_safe_text(result.input_path))}</div>",
        f"<div class='case-badges'><span class='badge badge--{result.status.lower()}'>{html.escape(result.status)}</span><span class='badge badge--muted'>{html.escape(_safe_text(result.phase0_mode))}</span></div>",
        "</summary>",
        "<div class='case-body'>",
        "<div class='summary-grid'>",
        f"<div class='metric'><span>Tables</span><strong>{result.extracted_tables}</strong></div>",
        f"<div class='metric'><span>Connexions</span><strong>{result.live_connections}</strong></div>",
        f"<div class='metric'><span>Worksheets</span><strong>{result.worksheets}</strong></div>",
        f"<div class='metric'><span>Dashboards</span><strong>{result.dashboards}</strong></div>",
        f"<div class='metric'><span>Calc fields</span><strong>{result.calculated_fields}</strong></div>",
        f"<div class='metric'><span>Datasources</span><strong>{result.datasources}</strong></div>",
        "</div>",
        "<div class='two-columns'>",
        "<section class='panel panel--phase0'>",
        "<h3>Phase 0 - Extraction</h3>",
        f"<div class='panel-kv'>{_render_key_value_pairs(phase0)}</div>",
        f"<div class='panel-kv'><div class='kv-row'><span class='kv-key'>Connexions</span><span class='kv-value'>{html.escape(_compact_json(meta.get('connections_sample', [])))}</span></div></div>",
        "</section>",
        "<section class='panel panel--phase1'>",
        "<h3>Phase 1 - Parsing enrichi</h3>",
        f"<div class='panel-kv'>{_render_key_value_pairs(phase1.get('summary', {}))}</div>",
        f"<div class='panel-kv'><div class='kv-row'><span class='kv-key'>Dashboards</span><span class='kv-value'>{html.escape(_compact_json(dashboards))}</span></div></div>",
        "</section>",
        "</div>",
        "<section class='panel panel--sheets'>",
        "<h3>Worksheets enrichies</h3>",
        f"<div class='sheet-grid'>{sheet_cards}</div>",
        "</section>",
        "<section class='panel panel--sample'>",
        "<h3>Echantillon metadonnees</h3>",
        f"<pre>{html.escape(_compact_json(meta))}</pre>",
        "</section>",
    ]
    if result.error:
        parts.extend([
            "<section class='panel panel--error'>",
            "<h3>Erreur</h3>",
            f"<pre>{html.escape(result.error)}</pre>",
            "</section>",
        ])
    parts.extend([
        "</div>",
        "</details>",
    ])
    return "".join(parts)


def _collect_inputs(input_value: str) -> list[Path]:
    target = Path(input_value)
    if target.is_file():
        return [target] if target.suffix.lower() in {".twb", ".twbx"} else []

    if target.is_dir():
        # Include all Tableau docs found in the directory tree.
        files = sorted([*target.rglob("*.twbx"), *target.rglob("*.twb")])
        return [path for path in files if path.is_file()]

    # Fallback for glob pattern usage, ex: input/demo*.twbx
    base = Path(".")
    files = sorted(base.glob(input_value))
    return [path for path in files if path.is_file() and path.suffix.lower() in {".twb", ".twbx"}]


def _build_metadata_sample(registry, workbook) -> dict[str, Any]:
    frames = registry.all_frames()
    table_names = list(frames.keys())
    connections = getattr(registry, "connection_catalog", []) or []

    worksheet_marks = [
        {
            "worksheet": ws.name,
            "mark_type": str(ws.mark_type),
            "datasource": ws.datasource_name,
        }
        for ws in workbook.worksheets[:5]
    ]

    datasource_names = [ds.name for ds in workbook.datasources[:5]]
    datasource_captions = [ds.caption for ds in workbook.datasources[:5]]
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

    worksheet_samples = []
    for ws in workbook.worksheets[:5]:
        worksheet_samples.append(
            {
                "name": ws.name,
                "title": ws.title,
                "mark_type": str(ws.mark_type),
                "raw_mark_type": str(getattr(ws, "raw_mark_type", "")),
                "datasource_name": ws.datasource_name,
                "visual_encoding": ws.visual_encoding.model_dump() if hasattr(ws.visual_encoding, "model_dump") else {},
                "confidence": ws.confidence.model_dump() if hasattr(ws.confidence, "model_dump") else {},
                "semantic_hints": [
                    hint.model_dump() if hasattr(hint, "model_dump") else hint
                    for hint in ws.semantic_hints[:3]
                ],
                "enriched_lineage": [
                    lineage.model_dump() if hasattr(lineage, "model_dump") else lineage
                    for lineage in ws.enriched_lineage[:3]
                ],
                "validation_warnings": list(ws.validation_warnings),
            }
        )

    phase0_payload = {
        "tables_sample": table_names[:5],
        "datasource_names": datasource_names,
        "datasource_captions": datasource_captions,
        "worksheet_marks": worksheet_marks,
        "dashboard_names": [dash.name for dash in workbook.dashboards[:5]],
        "parameters_sample": [param.name for param in workbook.parameters[:5]],
        "filters_sample": [flt.field for flt in workbook.filters[:5]],
        "connections_sample": connection_sample,
    }

    phase1_payload = {
        "summary": {
            "worksheets": len(workbook.worksheets),
            "dashboards": len(workbook.dashboards),
            "semantic_hints": len(workbook.semantic_hints),
            "enriched_lineage": len(workbook.enriched_lineage),
        },
        "worksheets": worksheet_samples,
        "dashboards": [
            {
                "name": dash.name,
                "worksheets": dash.worksheets,
                "count": len(dash.worksheets),
            }
            for dash in workbook.dashboards[:5]
        ],
        "validation_warnings": list(workbook.validation_warnings[:10]),
    }

    return {
        "phase0": phase0_payload,
        "phase1": phase1_payload,
    }


def _run_case(input_path: Path) -> DemoCaseResult:
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
        manifest = getattr(registry, "phase0_manifest", {}) or {}
        connections = getattr(registry, "connection_catalog", []) or []
        all_frames = registry.all_frames()
        metadata_sample = _build_metadata_sample(registry, workbook)
        status = "OK" if not extraction_error else "PARTIAL"

        return DemoCaseResult(
            input_path=str(input_path),
            status=status,
            phase0_mode=str(manifest.get("mode", "unknown" if not extraction_error else "failed")),
            extracted_tables=len(all_frames),
            live_connections=len(connections),
            worksheets=len(workbook.worksheets),
            dashboards=len(workbook.dashboards),
            calculated_fields=len(workbook.calculated_fields),
            datasources=len(workbook.datasources),
            first_worksheet=workbook.worksheets[0].name if workbook.worksheets else "-",
            first_dashboard=workbook.dashboards[0].name if workbook.dashboards else "-",
            metadata_sample=metadata_sample,
            error=extraction_error,
        )
    except Exception as exc:
        trace = traceback.format_exc(limit=2)
        joined_error = extraction_error.strip()
        parsing_error = f"Phase1 {type(exc).__name__}: {exc}\n{trace}"
        if joined_error:
            joined_error = joined_error + "\n" + parsing_error
        else:
            joined_error = parsing_error
        return DemoCaseResult(
            input_path=str(input_path),
            status="KO",
            phase0_mode="-",
            extracted_tables=0,
            live_connections=0,
            worksheets=0,
            dashboards=0,
            calculated_fields=0,
            datasources=0,
            first_worksheet="-",
            first_dashboard="-",
            metadata_sample={},
            error=joined_error,
        )


def _render_html_report(output_html: Path, results: list[DemoCaseResult]) -> None:
    cards = "".join(_render_case_card(result) for result in results)

    total = len(results)
    ok_count = sum(1 for item in results if item.status == "OK")
    partial_count = sum(1 for item in results if item.status == "PARTIAL")
    ko_count = total - ok_count - partial_count
    worksheet_total = sum(item.worksheets for item in results)
    dashboard_total = sum(item.dashboards for item in results)
    table_total = sum(item.extracted_tables for item in results)
    connection_total = sum(item.live_connections for item in results)

    content = (
        "<!doctype html><html><head><meta charset='utf-8'><title>Extraction + Parsing Demo</title>"
        "<style>"
        ":root{--bg:#eef2ff;--panel:#ffffff;--panel-alt:#f8fafc;--text:#0f172a;--muted:#64748b;--line:#dbe4f0;--accent:#0f766e;--accent-2:#1d4ed8;--warn:#92400e;--error:#991b1b;}"
        "*{box-sizing:border-box;} body{margin:0;font-family:Segoe UI,Arial,sans-serif;background:linear-gradient(180deg,#eef2ff 0%,#f8fafc 35%,#ffffff 100%);color:var(--text);padding:24px;}"
        ".shell{max-width:1400px;margin:0 auto;}"
        ".hero{display:flex;justify-content:space-between;gap:24px;align-items:flex-end;margin-bottom:20px;flex-wrap:wrap;}"
        ".hero h1{margin:0;font-size:32px;letter-spacing:-0.03em;} .hero p{margin:8px 0 0;color:var(--muted);max-width:760px;}"
        ".summary-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px;margin:18px 0 24px;}"
        ".metric{background:rgba(255,255,255,0.88);backdrop-filter:blur(8px);border:1px solid var(--line);border-radius:18px;padding:14px 16px;box-shadow:0 10px 30px rgba(15,23,42,0.06);}"
        ".metric span{display:block;font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;} .metric strong{display:block;margin-top:6px;font-size:26px;line-height:1.1;}"
        ".section-title{margin:24px 0 12px;font-size:18px;}"
        ".case-list{display:flex;flex-direction:column;gap:16px;}"
        ".case-card{background:var(--panel);border:1px solid var(--line);border-radius:22px;overflow:hidden;box-shadow:0 14px 35px rgba(15,23,42,0.08);}"
        ".case-card summary{list-style:none;cursor:pointer;display:flex;justify-content:space-between;gap:16px;padding:18px 20px;background:linear-gradient(90deg,rgba(29,78,216,0.06),rgba(15,118,110,0.04));}"
        ".case-card summary::-webkit-details-marker{display:none;}"
        ".case-title{font-weight:700;font-size:16px;} .case-badges{display:flex;gap:8px;align-items:center;flex-wrap:wrap;}"
        ".case-body{padding:20px;}"
        ".badge{display:inline-flex;align-items:center;border-radius:999px;padding:4px 10px;font-size:11px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;border:1px solid transparent;}"
        ".badge--ok{background:#dcfce7;color:#166534;border-color:#bbf7d0;} .badge--partial{background:#fef3c7;color:#92400e;border-color:#fde68a;} .badge--ko{background:#fee2e2;color:#991b1b;border-color:#fecaca;} .badge--muted{background:#e2e8f0;color:#334155;border-color:#cbd5e1;}"
        ".badge--bar,.badge--line,.badge--pie,.badge--treemap,.badge--scatter,.badge--map,.badge--table,.badge--kpi,.badge--gantt{background:#e0f2fe;color:#075985;border-color:#bae6fd;}"
        ".two-columns{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-top:14px;}"
        ".panel{background:var(--panel-alt);border:1px solid var(--line);border-radius:18px;padding:16px;} .panel h3{margin:0 0 12px;font-size:15px;}"
        ".panel-kv{display:flex;flex-direction:column;gap:8px;} .kv-row{display:flex;gap:12px;justify-content:space-between;padding:8px 10px;border-radius:12px;background:#fff;border:1px solid #e5e7eb;}"
        ".kv-key{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;} .kv-value{font-size:13px;text-align:right;max-width:70%;overflow-wrap:anywhere;}"
        ".sheet-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;}"
        ".sheet-card{background:#fff;border:1px solid var(--line);border-radius:16px;padding:14px;min-height:100%;box-shadow:0 8px 24px rgba(15,23,42,0.05);}"
        ".sheet-card__header{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:10px;}"
        ".sheet-card__header h4{margin:0;font-size:14px;} .sheet-card__header p{margin:4px 0 0;color:var(--muted);font-size:12px;}"
        ".sheet-card__grid{display:grid;grid-template-columns:1fr;gap:8px;}"
        ".label{display:block;font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:3px;}"
        ".mono{font-family:ui-monospace,SFMono-Regular,Consolas,Monaco,monospace;font-size:11px;white-space:pre-wrap;word-break:break-word;}"
        ".inline-list{margin:6px 0 0;padding-left:18px;color:var(--text);} .inline-list li{margin:2px 0;}"
        ".empty{color:var(--muted);font-style:italic;} .muted{color:var(--muted);}"
        ".overview{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:18px 0 8px;}"
        ".overview .metric{background:rgba(255,255,255,0.96);}"
        "pre{margin:0;white-space:pre-wrap;word-break:break-word;font-size:11px;line-height:1.45;}"
        "@media (max-width:1200px){.summary-grid,.overview,.sheet-grid{grid-template-columns:repeat(2,minmax(0,1fr));}.two-columns{grid-template-columns:1fr;}}"
        "@media (max-width:720px){body{padding:14px;}.summary-grid,.overview,.sheet-grid{grid-template-columns:1fr;}.hero h1{font-size:26px;}}"
        "</style></head><body><div class='shell'>"
        "<div class='hero'><div><h1>Demo Extraction + Parsing</h1><p>Vue structurée de la phase 0 et de la phase 1 avec extraction, parsing enrichi, encodage visuel, confidence et lineage.</p></div></div>"
        "<div class='summary-grid'>"
        f"<div class='metric'><span>Fichiers</span><strong>{total}</strong></div>"
        f"<div class='metric'><span>OK</span><strong>{ok_count}</strong></div>"
        f"<div class='metric'><span>PARTIAL</span><strong>{partial_count}</strong></div>"
        f"<div class='metric'><span>KO</span><strong>{ko_count}</strong></div>"
        f"<div class='metric'><span>Tables P0</span><strong>{table_total}</strong></div>"
        f"<div class='metric'><span>Connexions</span><strong>{connection_total}</strong></div>"
        f"<div class='metric'><span>Worksheets P1</span><strong>{worksheet_total}</strong></div>"
        f"<div class='metric'><span>Dashboards P1</span><strong>{dashboard_total}</strong></div>"
        "</div>"
        "<h2 class='section-title'>Cases</h2>"
        f"<div class='case-list'>{cards}</div>"
        "</div></body></html>"
    )
    output_html.parent.mkdir(parents=True, exist_ok=True)
    output_html.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Demo phase 0 + phase 1 uniquement (extraction/parsing)")
    parser.add_argument(
        "--input",
        default="input",
        help="Fichier, dossier, ou pattern glob (*.twbx/*.twb). Exemple: input ou input/demo*.twbx",
    )
    parser.add_argument(
        "--report-json",
        default="output/extraction_parsing_report.json",
        help="Chemin du rapport JSON",
    )
    parser.add_argument(
        "--report-html",
        default="output/extraction_parsing_report.html",
        help="Chemin du rapport HTML",
    )
    args = parser.parse_args()

    inputs = _collect_inputs(args.input)
    if not inputs:
        raise FileNotFoundError(f"Aucun fichier .twb/.twbx trouve pour: {args.input}")

    print("=" * 72)
    print("DEMO EXTRACTION + PARSING (PHASE 0 + PHASE 1)")
    print("=" * 72)
    print(f"Inputs detectes: {len(inputs)}")

    results: list[DemoCaseResult] = []
    for input_path in inputs:
        print(f"\n[RUN] {input_path}")
        result = _run_case(input_path)
        results.append(result)
        print(
            "  "
            f"status={result.status} | mode={result.phase0_mode} | "
            f"tables={result.extracted_tables} | connections={result.live_connections} | "
            f"worksheets={result.worksheets} | dashboards={result.dashboards}"
        )
        if result.metadata_sample:
            print(f"  metadata_sample={json.dumps(result.metadata_sample, ensure_ascii=True)}")
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
        },
        "cases": [asdict(item) for item in results],
    }
    report_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report_html = Path(args.report_html)
    _render_html_report(report_html, results)

    print("\n" + "=" * 72)
    print(f"Termine: OK={ok_count} | PARTIAL={partial_count} | KO={ko_count}")
    print(f"Rapport JSON: {report_json}")
    print(f"Rapport HTML: {report_html}")


if __name__ == "__main__":
    main()
