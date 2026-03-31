from viz_agent.phase2_semantic.mapping import SemanticMappingEngine


ONTOLOGY = {
    "terms": [
        {"name": "Customer", "aliases": ["cust"]},
        {"name": "Revenue", "aliases": []},
    ]
}


def test_heuristic_uses_alias_and_sets_details():
    engine = SemanticMappingEngine(ONTOLOGY, min_confidence=0.1)
    mapping = engine.map_columns(["cust_id"], use_llm=False)[0]
    assert mapping.mapped_business_term == "Customer"
    assert mapping.method == "heuristic"
    assert "heuristic" in mapping.details and "embedding" in mapping.details


def test_unmapped_when_below_threshold():
    engine = SemanticMappingEngine(ONTOLOGY, min_confidence=0.95)
    mapping = engine.map_columns(["unknown_field"], use_llm=False)[0]
    assert mapping.mapped_business_term is None
    assert mapping.method == "unmapped"
    assert mapping.confidence == 0.0


def test_llm_disabled_keeps_deterministic_method():
    engine = SemanticMappingEngine(ONTOLOGY, min_confidence=0.1)
    mapping = engine.map_columns(["revenue_total"], use_llm=False)[0]
    assert mapping.method == "heuristic"
    assert mapping.mapped_business_term == "Revenue"
