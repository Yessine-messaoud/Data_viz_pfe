"""
SemanticCache: Mécanisme de cache pour accélérer les transformations répétitives
"""
from typing import Any, Dict

class SemanticCache:
    def __init__(self):
        self._cache = {}

    def store(self, semantic_graph: Any, spec: Dict) -> None:
        key = self._make_key(semantic_graph)
        self._cache[key] = spec

    def get(self, semantic_graph: Any) -> Dict:
        key = self._make_key(semantic_graph)
        return self._cache.get(key)

    def _make_key(self, semantic_graph: Any) -> str:
        # TODO: Améliorer la génération de clé (hash du graphe)
        return str(hash(str(semantic_graph)))
