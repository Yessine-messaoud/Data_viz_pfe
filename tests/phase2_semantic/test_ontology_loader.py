from viz_agent.phase2_semantic.ontology import OntologyLoader, DEFAULT_ONTOLOGY


def test_loads_default_when_no_path():
    loader = OntologyLoader()
    data = loader.load()
    assert data["entities"] == DEFAULT_ONTOLOGY["entities"]
    assert any(term["name"] == "Sales" for term in data["terms"])


def test_merge_and_dedup(tmp_path):
    custom = {
        "entities": ["Sales", "Finance"],
        "metrics": ["Revenue", "Revenue"],
        "terms": [
            {"name": "Sales", "aliases": ["Orders", "Orders"]},
            {"name": "Finance", "aliases": ["Money"]},
        ],
    }
    path = tmp_path / "ontology.json"
    path.write_text(__import__("json").dumps(custom), encoding="utf-8")

    loader = OntologyLoader(str(path))
    data = loader.load()

    assert "Finance" in data["entities"]
    # aliases deduped and include override
    sales_term = next(t for t in data["terms"] if t["name"] == "Sales")
    assert "Orders" in sales_term["aliases"]
    assert len(set(sales_term["aliases"])) == len(sales_term["aliases"])
    # new term merged
    assert any(t["name"] == "Finance" for t in data["terms"])


def test_invalid_schema_raises(tmp_path):
    bad = {"entities": "not-a-list", "terms": [{"name": 123}]}
    path = tmp_path / "bad.json"
    path.write_text(__import__("json").dumps(bad), encoding="utf-8")
    loader = OntologyLoader(str(path))
    try:
        loader.load()
    except ValueError:
        return
    assert False, "Expected ValueError"
