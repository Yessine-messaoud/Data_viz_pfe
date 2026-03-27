from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:  # pragma: no cover - external binary dependency
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except Exception as exc:  # pragma: no cover - environment dependent
    TfidfVectorizer = None  # type: ignore
    cosine_similarity = None  # type: ignore
    logger.warning("scikit-learn unavailable, embedding similarity disabled: %s", exc)

from viz_agent.phase2_semantic.llm import call_mistral, LLMResponse
from viz_agent.phase2_semantic.semantic_model import SemanticMappingModel


class SemanticMappingEngine:
    def __init__(self, ontology: Dict[str, Any], min_confidence: float = 0.2) -> None:
        self.ontology = ontology or {"terms": []}
        self.terms = [t["name"] for t in self.ontology.get("terms", []) if isinstance(t.get("name"), str)]
        if self.terms and TfidfVectorizer:
            try:
                self._vectorizer = TfidfVectorizer().fit(self.terms)
            except Exception as exc:  # pragma: no cover - runtime env dependent
                logger.warning("Embedding vectorizer disabled: %s", exc)
                self._vectorizer = None
        else:
            self._vectorizer = None
        self.min_confidence = min_confidence

    def _heuristic_match(self, column: str) -> Tuple[Optional[str], float]:
        name = column.lower()
        best_term: Optional[str] = None
        best_score = 0.0
        for term in self.terms:
            term_lower = term.lower()
            aliases = [a.lower() for a in self._aliases(term)]

            if term_lower in name:
                score = 0.9
            elif any(alias in name for alias in aliases):
                score = 0.8
            else:
                score = 0.0

            if score > best_score:
                best_term = term
                best_score = score

        return best_term, best_score

    def _aliases(self, term: str) -> List[str]:
        for t in self.ontology.get("terms", []):
            if t.get("name") == term:
                aliases = t.get("aliases") or []
                return [a for a in aliases if isinstance(a, str)]
        return []

    def _embedding_match(self, column: str) -> Tuple[Optional[str], float]:
        if not self._vectorizer or not self.terms or not cosine_similarity:
            return None, 0.0
        vec_terms = self._vectorizer.transform(self.terms)
        vec_col = self._vectorizer.transform([column])
        sims = cosine_similarity(vec_col, vec_terms).flatten()
        if sims.size == 0:
            return None, 0.0
        best_idx = sims.argmax()
        return self.terms[best_idx], float(sims[best_idx])

    def _llm_validate(self, column: str, candidate: Optional[str]) -> LLMResponse:
        prompt = (
            '{"column": "' + column + '", "possible_meaning": "' + (candidate or "") + '", '
            '"mapped_business_term": "' + (candidate or "") + '", "confidence": 0.5}'
        )
        return call_mistral(prompt)

    def _pick_best(self, heur: Tuple[Optional[str], float], emb: Tuple[Optional[str], float]) -> Tuple[Optional[str], float, str]:
        candidates = [
            (heur[0], heur[1], "heuristic"),
            (emb[0], emb[1], "embedding"),
        ]
        candidates = [(t, s, m) for (t, s, m) in candidates if t]
        if not candidates:
            return None, 0.0, "unmapped"
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0]

    def map_columns(self, columns: List[str], use_llm: bool = True) -> List[SemanticMappingModel]:
        mappings: List[SemanticMappingModel] = []
        for col in columns:
            heur_term, heur_score = self._heuristic_match(col)
            emb_term, emb_score = self._embedding_match(col)

            best_term, best_score, best_method = self._pick_best((heur_term, heur_score), (emb_term, emb_score))

            llm_conf = 0.0
            llm_term = None
            if use_llm and best_term:
                llm_resp = self._llm_validate(col, best_term)
                llm_term = llm_resp.mapped_business_term
                llm_conf = llm_resp.confidence or 0.0

            final_term = llm_term or best_term
            final_conf = max(best_score, llm_conf)

            method = best_method if llm_conf == 0 else f"{best_method}+llm"
            if not final_term or final_conf < self.min_confidence:
                method = "unmapped"
                final_term = None
                final_conf = 0.0

            mappings.append(
                SemanticMappingModel(
                    column=col,
                    mapped_business_term=final_term,
                    confidence=final_conf,
                    method=method,
                    details={
                        "heuristic": {"term": heur_term, "score": heur_score},
                        "embedding": {"term": emb_term, "score": emb_score},
                        "llm": {"term": llm_term, "score": llm_conf},
                    },
                )
            )

            logger.info(
                "Mapped column '%s' -> '%s' (confidence=%.2f, method=%s)",
                col,
                final_term,
                final_conf,
                method,
            )

        return mappings
