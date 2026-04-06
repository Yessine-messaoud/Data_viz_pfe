"""
DeterministicParser: XML/structured parsing for .twb, .rdl, etc.
"""
from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path
from typing import Dict
import xml.etree.ElementTree as ET


class DeterministicParser:
    def parse(self, artifact_path: str, metadata: Dict) -> Dict:
        path = Path(artifact_path)
        ext = path.suffix.lower()

        if ext == ".rdl":
            return self._parse_rdl(path)
        if ext == ".twb":
            return self._parse_twb(path)
        if ext == ".twbx":
            return self._parse_twbx(path)
        raise ValueError(f"Unsupported artifact format: {ext}")

    def _parse_twbx(self, twbx_path: Path) -> Dict:
        with zipfile.ZipFile(twbx_path) as archive:
            twb_files = [name for name in archive.namelist() if name.lower().endswith(".twb")]
            if not twb_files:
                raise ValueError("No .twb file found in TWBX")
            with tempfile.TemporaryDirectory() as temp_dir:
                twb_name = twb_files[0]
                archive.extract(twb_name, temp_dir)
                twb_path = Path(temp_dir) / twb_name
                return self._parse_twb(twb_path)

    def _parse_twb(self, twb_path: Path) -> Dict:
        root = ET.parse(twb_path).getroot()
        worksheets = []
        for ws in root.findall(".//worksheet"):
            ws_name = ws.get("name", "UnnamedWorksheet")
            mark = ws.find(".//mark")
            mark_type = mark.get("class", "Text") if mark is not None else "Text"
            worksheets.append({"id": ws_name, "name": ws_name, "type": mark_type.upper(), "fields": []})

        dashboards = []
        for dashboard in root.findall(".//dashboard"):
            d_name = dashboard.get("name", "UnnamedDashboard")
            sheet_names = [zone.get("name", "") for zone in dashboard.findall(".//zone") if zone.get("type") == "sheet"]
            visuals = [w for w in worksheets if w["name"] in set(sheet_names)] if sheet_names else worksheets
            dashboards.append(
                {
                    "name": d_name,
                    "pages": [{"name": d_name, "visuals": [v["name"] for v in visuals], "layout": {}}],
                    "visuals": visuals,
                    "filters": [],
                }
            )

        if not dashboards:
            dashboards.append(
                {
                    "name": "Default",
                    "pages": [{"name": "Default", "visuals": [v["name"] for v in worksheets], "layout": {}}],
                    "visuals": worksheets,
                    "filters": [],
                }
            )

        return {
            "dashboards": dashboards,
            "visuals": [v for d in dashboards for v in d.get("visuals", [])],
            "bindings": [],
            "filters": [],
            "layout": {},
            "source_format": "twb",
        }

    def _parse_rdl(self, rdl_path: Path) -> Dict:
        root = ET.parse(rdl_path).getroot()

        datasets = []
        visuals = []
        bindings = []

        for node in root.iter():
            local = self._local_name(node.tag)
            if local == "DataSet":
                ds_name = node.attrib.get("Name", "Dataset")
                datasets.append(ds_name)
            if local in {"Tablix", "Chart", "GaugePanel", "Map"}:
                v_name = node.attrib.get("Name", f"{local}_{len(visuals)+1}")
                dataset_name = self._find_child_text(node, "DataSetName")
                visual = {
                    "id": v_name,
                    "name": v_name,
                    "type": local.upper(),
                    "fields": [],
                    "dataset": dataset_name,
                }
                visuals.append(visual)
                if dataset_name:
                    bindings.append({"visual": v_name, "dataset": dataset_name})

        report_name = self._find_child_text(root, "ReportName") or rdl_path.stem
        dashboard = {
            "name": report_name,
            "pages": [{"name": report_name, "visuals": [v["name"] for v in visuals], "layout": {}}],
            "visuals": visuals,
            "filters": [],
        }

        return {
            "dashboards": [dashboard],
            "visuals": visuals,
            "bindings": bindings,
            "datasets": datasets,
            "filters": [],
            "layout": {},
            "source_format": "rdl",
        }

    @staticmethod
    def _local_name(tag: str) -> str:
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag

    def _find_child_text(self, node: ET.Element, local_name: str) -> str | None:
        for child in node.iter():
            if self._local_name(child.tag) == local_name and child.text:
                return child.text.strip()
        return None
