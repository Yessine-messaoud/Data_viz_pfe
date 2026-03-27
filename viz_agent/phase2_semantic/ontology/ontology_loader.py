from __future__ import annotations

import json
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

DEFAULT_ONTOLOGY: Dict[str, Any] = {
    "entities": ["Sales", "Product", "Customer", "Geography", "Time"],
    "metrics": ["Revenue", "Quantity", "Profit"],
    "terms": [
        {"name": "Sales", "aliases": ["Sale", "Orders", "Order"]},
        {"name": "Product", "aliases": ["Item", "SKU"]},
        {"name": "Customer", "aliases": ["Client", "Buyer"]},
        {"name": "Geography", "aliases": ["Country", "Region", "City"]},
        {"name": "Time", "aliases": ["Date", "Year", "Month"]},
        {"name": "Revenue", "aliases": ["SalesAmount", "Turnover"]},
        {"name": "Quantity", "aliases": ["Qty", "Units"]},
        {"name": "Profit", "aliases": ["Margin"]},
    ],
}


class OntologyLoader:
    def __init__(self, ontology_path: str | None = None, base_ontology: Dict[str, Any] | None = None) -> None:
        self.ontology_path = ontology_path
        self.base_ontology = deepcopy(base_ontology) if base_ontology else deepcopy(DEFAULT_ONTOLOGY)

    def load(self) -> Dict[str, Any]:
        """Load ontology from disk if provided, otherwise return defaults.

        Merges user ontology with defaults (dedup terms/entities/metrics) and
        validates basic schema to fail fast on malformed files.
        """

        ontology = deepcopy(self.base_ontology)
        if not self.ontology_path:
            logger.info("Loading default ontology (in-code)")
            return ontology

        path = Path(self.ontology_path)
        if not path.exists():
            raise FileNotFoundError(f"Ontology file not found: {self.ontology_path}")

        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        self._validate_schema(data)
        merged = self._merge_ontology(ontology, data)
        logger.info("Ontology loaded from %s", self.ontology_path)
        return merged

    def _validate_schema(self, data: Dict[str, Any]) -> None:
        if not isinstance(data, dict):
            raise ValueError("Ontology must be a JSON object")

        def _validate_list_of_str(key: str) -> List[str]:
            value = data.get(key, [])
            if value is None:
                return []
            if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
                raise ValueError(f"Ontology field '{key}' must be a list of strings")
            return value

        _validate_list_of_str("entities")
        _validate_list_of_str("metrics")

        terms = data.get("terms", [])
        if terms is None:
            terms = []
        if not isinstance(terms, list):
            raise ValueError("Ontology field 'terms' must be a list")
        for term in terms:
            if not isinstance(term, dict):
                raise ValueError("Each term must be an object")
            if "name" not in term or not isinstance(term["name"], str):
                raise ValueError("Each term must have a string 'name'")
            aliases = term.get("aliases", [])
            if aliases is None:
                aliases = []
            if not isinstance(aliases, list) or any(not isinstance(a, str) for a in aliases):
                raise ValueError("Term 'aliases' must be a list of strings")

    def _merge_ontology(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        merged = deepcopy(base)

        def _dedup(values: List[str]) -> List[str]:
            seen = set()
            result = []
            for val in values:
                if val not in seen:
                    seen.add(val)
                    result.append(val)
            return result

        merged_entities = _dedup((merged.get("entities") or []) + (override.get("entities") or []))
        merged_metrics = _dedup((merged.get("metrics") or []) + (override.get("metrics") or []))

        merged_terms: Dict[str, Dict[str, Any]] = {t["name"]: deepcopy(t) for t in merged.get("terms", [])}
        for term in override.get("terms", []) or []:
            name = term.get("name")
            aliases = term.get("aliases") or []
            if name in merged_terms:
                merged_terms[name]["aliases"] = _dedup(merged_terms[name].get("aliases", []) + aliases)
            else:
                merged_terms[name] = {"name": name, "aliases": aliases}

        return {
            "entities": merged_entities,
            "metrics": merged_metrics,
            "terms": list(merged_terms.values()),
        }
