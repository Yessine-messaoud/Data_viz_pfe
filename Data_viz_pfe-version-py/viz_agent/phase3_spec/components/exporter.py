"""
Exporter: Exporte la spécification en différents formats (JSON, YAML, Markdown, GraphQL)
"""
import json
import yaml

class Exporter:
    def export(self, spec: dict, format: str = "json") -> str:
        if format == "json":
            return json.dumps(spec, indent=2, ensure_ascii=False)
        elif format == "yaml":
            return yaml.dump(spec, allow_unicode=True)
        elif format == "markdown":
            return self._to_markdown(spec)
        elif format == "graphql":
            return self._to_graphql_schema(spec)
        else:
            raise ValueError(f"Unsupported export format: {format}")

    def _to_markdown(self, spec: dict) -> str:
        # TODO: Implémenter la conversion Markdown
        return "# Abstract Specification\n\n..."

    def _to_graphql_schema(self, spec: dict) -> str:
        # TODO: Implémenter la conversion GraphQL schema
        return "type AbstractSpec { ... }"
