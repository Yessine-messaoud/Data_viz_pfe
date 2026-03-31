from __future__ import annotations

from lxml import etree


def extract_dashboard_worksheets(dashboard_xml: etree._Element) -> list[str]:
    zones = dashboard_xml.findall(".//zone")
    names: list[str] = []
    for zone in zones:
        zone_type = (zone.get("type") or "").lower()
        name = zone.get("name")
        if not name:
            continue

        # Tableau exports are not consistent: some files mark sheet zones with type="sheet",
        # others only expose worksheet names in `name` without a `type` attribute.
        if zone_type and zone_type != "sheet":
            continue
        if name not in names:
            names.append(name)
    return names


PREFIX_MAP = {
    "CD_": "Customer Details",
    "PD_": "Product Details",
    "SO_": "Sales Overview",
}


def infer_dashboard_name_from_worksheet(worksheet_name: str) -> str | None:
    for prefix, page_name in PREFIX_MAP.items():
        if worksheet_name.startswith(prefix):
            return page_name
    return None
