from __future__ import annotations

from typing import Any


class ConfidenceEngine:
    def __init__(self, threshold: float = 0.75) -> None:
        self.threshold = float(threshold)

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    def compute(
        self,
        heuristic_score: float,
        profiling_score: float,
        ontology_score: float,
        llm_score: float,
        path: str,
    ) -> dict[str, Any]:
        h = self._clamp(heuristic_score)
        p = self._clamp(profiling_score)
        o = self._clamp(ontology_score)
        l = self._clamp(llm_score)

        llm_used = l > 0.0

        if llm_used:
            weights = {
                "heuristic": 0.35,
                "profiling": 0.25,
                "ontology": 0.15,
                "llm": 0.25,
            }
        else:
            weights = {
                "heuristic": 0.45,
                "profiling": 0.35,
                "ontology": 0.20,
            }

        if o < 0.40 and "ontology" in weights:
            weights["ontology"] = weights["ontology"] * max(0.25, o)

        components = {
            "heuristic": h,
            "profiling": p,
            "ontology": o,
            "llm": l,
        }

        active_keys = [key for key, value in components.items() if key in weights and value > 0.0]
        if not active_keys:
            return {
                "confidence": 0.0,
                "confidence_components": {
                    "heuristic_score": h,
                    "profiling_score": p,
                    "ontology_score": o,
                    "llm_score": l,
                },
                "confidence_detail": {
                    "final": 0.0,
                    "heuristic": h,
                    "profiling": p,
                    "ontology": o,
                    "llm": l,
                    "path": path,
                },
            }

        weight_sum = sum(weights[key] for key in active_keys)
        normalized = {key: (weights[key] / weight_sum) for key in active_keys}
        final = sum(components[key] * normalized[key] for key in active_keys)

        return {
            "confidence": self._clamp(final),
            "confidence_components": {
                "heuristic_score": h,
                "profiling_score": p,
                "ontology_score": o,
                "llm_score": l,
            },
            "confidence_detail": {
                "final": self._clamp(final),
                "heuristic": h,
                "profiling": p,
                "ontology": o,
                "llm": l,
                "path": path,
            },
        }
