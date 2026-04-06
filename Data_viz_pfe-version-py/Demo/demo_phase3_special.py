from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


ALLOWED_VISUAL_TYPES = {"bar", "line", "pie", "treemap", "scatter", "kpi", "table", "map", "gantt"}


def _safe_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _safe_text(value: Any, fallback: str = "-") -> str:
    text = str(value or "").strip()
    return text if text else fallback


def _axis_name(ref: Any) -> str:
    if isinstance(ref, dict):
        return _safe_text(ref.get("column") or ref.get("name"))
    if hasattr(ref, "column"):
        return _safe_text(getattr(ref, "column", ""))
    if hasattr(ref, "name"):
        return _safe_text(getattr(ref, "name", ""))
    return _safe_text(ref)


def _render_list(items: list[Any]) -> str:
    if not items:
        return "<span class='muted'>Aucun</span>"
    return "<ul>" + "".join(f"<li>{html.escape(_safe_text(item))}</li>" for item in items) + "</ul>"


def _render_visual_card(visual: dict[str, Any]) -> str:
    binding = visual.get("data_binding", {}) if isinstance(visual.get("data_binding", {}), dict) else {}
    axes = binding.get("axes", {}) if isinstance(binding.get("axes", {}), dict) else {}
    measures = binding.get("measures", []) if isinstance(binding.get("measures", []), list) else []
    corrections = [line for line in visual.get("build_log", []) if isinstance(line, str)]
    warnings = visual.get("warnings", []) if isinstance(visual.get("warnings", []), list) else []
    type_name = _safe_text(visual.get("type"), "table").lower()
    rdl_type = _safe_text(visual.get("rdl_type"), "tablix")
    contract_ok = type_name in ALLOWED_VISUAL_TYPES and rdl_type.lower() != "chart" and type_name != "chart"
    status_class = "good" if contract_ok else "warn"

    axis_rows = []
    for axis_name in ("x", "y", "color", "size", "detail"):
        axis_rows.append(
            f"<div class='kv'><span>{axis_name}</span><strong>{html.escape(_axis_name(axes.get(axis_name)))}</strong></div>"
        )

    return (
        f"<section class='visual-card {status_class}'>"
        f"<div class='visual-head'>"
        f"<div><h4>{html.escape(_safe_text(visual.get('title') or visual.get('id')))}</h4>"
        f"<p>{html.escape(_safe_text(visual.get('source_worksheet')))}</p></div>"
        f"<span class='pill'>{html.escape(_safe_text(visual.get('type')))} / {html.escape(rdl_type)}</span>"
        f"</div>"
        f"<div class='visual-grid'>"
        f"<div><span class='label'>Binding</span>{''.join(axis_rows)}</div>"
        f"<div><span class='label'>Measures</span>{_render_list([m.get('name') if isinstance(m, dict) else getattr(m, 'name', m) for m in measures])}</div>"
        f"<div><span class='label'>Group By</span>{_render_list(visual.get('data_binding', {}).get('group_by', []))}</div>"
        f"<div><span class='label'>Hierarchy</span>{_render_list(visual.get('data_binding', {}).get('hierarchy', []))}</div>"
        f"<div><span class='label'>Aggregation</span><div class='mono'>{html.escape(_safe_text(visual.get('data_binding', {}).get('aggregation')))}</div></div>"
        f"<div><span class='label'>Warnings</span>{_render_list(warnings)}</div>"
        f"</div>"
        f"<div class='footer'><span>Contract</span><strong>{'OK' if contract_ok else 'A verifier'}</strong></div>"
        f"</section>"
    )


def _render_page(page: dict[str, Any]) -> str:
    visuals = page.get("visuals", []) if isinstance(page.get("visuals", []), list) else []
    cards = "".join(_render_visual_card(v) for v in visuals if isinstance(v, dict))
    if not cards:
        cards = "<p class='muted'>Aucun visual.</p>"
    return (
        f"<section class='page'>"
        f"<div class='page-head'><h3>{html.escape(_safe_text(page.get('name')))}</h3>"
        f"<span class='page-meta'>{len(visuals)} visual(s)</span></div>"
        f"<div class='visual-list'>{cards}</div>"
        f"</section>"
    )


def _render_html(spec: dict[str, Any], output_path: Path) -> None:
    dashboard = spec.get("dashboard_spec", {}) if isinstance(spec.get("dashboard_spec", {}), dict) else {}
    pages = dashboard.get("pages", []) if isinstance(dashboard.get("pages", []), list) else []
    build_log = spec.get("build_log", []) if isinstance(spec.get("build_log", []), list) else []
    warnings = spec.get("warnings", []) if isinstance(spec.get("warnings", []), list) else []

    all_visuals: list[dict[str, Any]] = []
    for page in pages:
        if isinstance(page, dict):
            all_visuals.extend([v for v in page.get("visuals", []) if isinstance(v, dict)])

    contract_ok = 0
    contract_warn = 0
    for visual in all_visuals:
        type_name = _safe_text(visual.get("type"), "table").lower()
        rdl_type = _safe_text(visual.get("rdl_type"), "tablix").lower()
        if type_name in ALLOWED_VISUAL_TYPES and type_name != "chart" and rdl_type != "chart":
            contract_ok += 1
        else:
            contract_warn += 1

    build_info = [item.get("message", "") for item in build_log if isinstance(item, dict) and item.get("message")]
    output_path.parent.mkdir(parents=True, exist_ok=True)

    page_html = "".join(_render_page(page) for page in pages if isinstance(page, dict)) or "<p>Aucune page.</p>"

    html_doc = f"""<!doctype html>
<html lang='fr'>
<head>
  <meta charset='utf-8' />
  <meta name='viewport' content='width=device-width, initial-scale=1' />
  <title>Phase 3 Special Demo</title>
  <style>
    :root {{ --bg: #f3efe8; --panel: #ffffff; --ink: #181612; --muted: #646058; --line: #ddd6c9; --accent: #0f766e; --warn: #b45309; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Segoe UI, Helvetica, Arial, sans-serif; color: var(--ink); background: radial-gradient(circle at top right, #efe6d1, var(--bg)); }}
    .wrap {{ max-width: 1320px; margin: 0 auto; padding: 24px; }}
    .hero {{ display: flex; justify-content: space-between; gap: 16px; align-items: flex-end; flex-wrap: wrap; margin-bottom: 18px; }}
    .hero h1 {{ margin: 0; font-size: 34px; letter-spacing: -0.03em; }}
    .hero p {{ margin: 8px 0 0; max-width: 920px; color: var(--muted); }}
    .metrics {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 18px 0 24px; }}
    .metric {{ background: rgba(255,255,255,0.92); border: 1px solid var(--line); border-radius: 18px; padding: 14px 16px; box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06); }}
    .metric span {{ display: block; font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: .08em; }}
    .metric strong {{ display: block; margin-top: 6px; font-size: 28px; line-height: 1.1; }}
    .section {{ margin: 22px 0; }}
    .section h2 {{ margin: 0 0 12px; font-size: 18px; }}
    .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 22px; padding: 18px; box-shadow: 0 14px 35px rgba(15, 23, 42, 0.06); }}
    .page {{ margin-top: 14px; padding: 16px; border: 1px solid var(--line); border-radius: 18px; background: #faf9f6; }}
    .page-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: center; margin-bottom: 12px; }}
    .page-head h3 {{ margin: 0; }}
    .page-meta {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }}
    .visual-list {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }}
    .visual-card {{ background: #fff; border: 1px solid var(--line); border-radius: 18px; padding: 14px; }}
    .visual-card.good {{ box-shadow: inset 0 0 0 1px rgba(15, 118, 110, 0.08); }}
    .visual-card.warn {{ box-shadow: inset 0 0 0 1px rgba(180, 83, 9, 0.10); }}
    .visual-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; margin-bottom: 10px; }}
    .visual-head h4 {{ margin: 0; font-size: 15px; }}
    .visual-head p {{ margin: 4px 0 0; color: var(--muted); font-size: 12px; }}
    .pill {{ display: inline-flex; align-items: center; border-radius: 999px; padding: 4px 10px; font-size: 11px; font-weight: 700; border: 1px solid #cbd5e1; background: #e0f2fe; color: #075985; }}
    .visual-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
    .label {{ display: block; font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; margin-bottom: 6px; }}
    .kv {{ display: flex; justify-content: space-between; gap: 10px; padding: 6px 8px; border: 1px solid #e5e7eb; border-radius: 10px; margin-bottom: 6px; background: #fcfcfc; }}
    .kv span {{ color: var(--muted); font-size: 12px; text-transform: uppercase; }}
    .kv strong {{ font-size: 12px; }}
    .mono {{ font-family: ui-monospace, SFMono-Regular, Consolas, Monaco, monospace; font-size: 12px; }}
    .footer {{ margin-top: 10px; display: flex; justify-content: space-between; color: var(--muted); font-size: 12px; }}
    .build-log {{ display: grid; gap: 8px; }}
    .log-item {{ padding: 10px 12px; border-radius: 12px; background: #fcfcfb; border: 1px solid var(--line); }}
    .log-item strong {{ display: block; margin-bottom: 4px; }}
    .muted {{ color: var(--muted); }}
    ul {{ margin: 6px 0 0; padding-left: 18px; }}
    pre {{ margin: 0; white-space: pre-wrap; word-break: break-word; background: #111; color: #d3ffd4; padding: 12px; border-radius: 14px; }}
    @media (max-width: 1000px) {{ .metrics, .visual-list, .visual-grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class='wrap'>
    <div class='hero'>
      <div>
        <h1>Phase 3 Special Demo</h1>
        <p>Démo centrée sur la couche contractuelle de l'Abstract Spec: décision visuelle, validation des bindings, corrections et traçabilité du build log.</p>
      </div>
      <div class='pill'>{html.escape(_safe_text(spec.get('version', '2.0.0')))}</div>
    </div>

    <div class='metrics'>
      <div class='metric'><span>Pages</span><strong>{len(pages)}</strong></div>
      <div class='metric'><span>Visuals</span><strong>{len(all_visuals)}</strong></div>
      <div class='metric'><span>Contrats OK</span><strong>{contract_ok}</strong></div>
      <div class='metric'><span>A vérifier</span><strong>{contract_warn}</strong></div>
    </div>

    <section class='section panel'>
      <h2>Pages et Visuals</h2>
      {page_html}
    </section>

    <section class='section panel'>
      <h2>Build Log</h2>
      <div class='build-log'>
        {''.join(f"<div class='log-item'><strong>{html.escape(item.split(':', 1)[0])}</strong><div>{html.escape(item)}</div></div>" for item in build_info) if build_info else '<p class="muted">Aucune entrée build log.</p>'}
      </div>
    </section>

    <section class='section panel'>
      <h2>Warnings</h2>
      {_render_list(warnings)}
    </section>

    <section class='section panel'>
      <h2>Abstract Spec JSON</h2>
      <pre>{html.escape(json.dumps(spec, ensure_ascii=True, indent=2))}</pre>
    </section>
  </div>
</body>
</html>
"""

    output_path.write_text(html_doc, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Demo speciale de la phase 3 (contract layer / visual decision engine)")
    parser.add_argument(
        "--spec",
        default="output/DEMO_Complete/demo_ssms_demo_abstract_spec.json",
        help="Chemin vers un AbstractSpec JSON genere par le pipeline",
    )
    parser.add_argument(
        "--output",
        default="output/DEMO_Complete/demo_phase3_special.html",
        help="Chemin du rapport HTML a generer",
    )
    args = parser.parse_args()

    spec_path = Path(args.spec)
    output_path = Path(args.output)
    spec = _safe_json(spec_path)
    if not spec:
        raise FileNotFoundError(f"AbstractSpec introuvable ou invalide: {spec_path}")

    _render_html(spec, output_path)
    print(f"Phase 3 special demo generated: {output_path}")


if __name__ == "__main__":
    main()