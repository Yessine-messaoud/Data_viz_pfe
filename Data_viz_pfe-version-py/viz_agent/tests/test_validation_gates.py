from __future__ import annotations

from pathlib import Path

from viz_agent.orchestrator.agent_orchestrator import AgentOrchestrator
from viz_agent.orchestrator.agent_state import AgentState
from viz_agent.orchestrator.validation_gates import ValidationGates
from viz_agent.orchestrator.phase_agent import PhaseAgentResult


def test_validation_gates_phase_specific_rules() -> None:
    gates = ValidationGates()

    phase1_fail = gates.validate("parsing", {"parsed_structure": {"dashboards": [], "visuals": []}})
    assert not phase1_fail.passed

    phase2_fail = gates.validate(
        "semantic_reasoning",
        {
            "semantic_graph": {
                "columns": [{"name": "Country", "role": "dimension"}],
                "measures": [{"name": "BadMeasure", "role": "measure", "expression": "SUM(Country)"}],
            }
        },
    )
    assert not phase2_fail.passed

    phase3_fail = gates.validate(
        "specification",
        {
            "abstract_spec": {
                "dashboard_spec": {
                    "pages": [{"visuals": [{"id": "v1", "type": "chart", "data_binding": {"axes": {"x": "Country"}}}]}]
                }
            }
        },
    )
    assert not phase3_fail.passed

    phase5_pass = gates.validate(
        "export",
        {"export_result": {"validation": {"is_valid": True}, "content_bytes": 128}},
    )
    assert phase5_pass.passed


class _ParsingRetryAgent:
    name = "parsing"

    def __init__(self) -> None:
        self.calls = 0

    def execute(self, state: dict):
        self.calls += 1
        if self.calls == 1:
            return PhaseAgentResult(status="success", confidence=0.95, output={"parsed_structure": {"dashboards": [], "visuals": []}})
        return PhaseAgentResult(
            status="success",
            confidence=0.95,
            output={"parsed_structure": {"worksheets": [{"name": "ws1"}], "visuals": [{"source_worksheet": "ws1"}]}}
        )


def test_orchestrator_retries_when_validation_gate_fails(tmp_path: Path) -> None:
    orchestrator = AgentOrchestrator(
        max_retries=2,
        trace_file=tmp_path / "trace.jsonl",
        debug_snapshot_dir=tmp_path / "snapshots",
        enable_phase_cache=False,
    )
    parser = _ParsingRetryAgent()
    orchestrator.register_tool(parser)

    state = AgentState(execution_id="gates-001")
    results = orchestrator.run(state, ["parsing"])

    assert parser.calls == 2
    assert results["parsing"].status == "success"


class _ParsingNeedsFixAgent:
    name = "parsing"

    def __init__(self) -> None:
        self.calls = 0

    def execute(self, state: dict):
        self.calls += 1
        context = state.get("context", {}) if isinstance(state, dict) else {}
        fixes = ((context or {}).get("deterministic_fixes", {}) or {}).get("parsing", {})
        if fixes.get("ensure_worksheets_from_visuals"):
            return PhaseAgentResult(
                status="success",
                confidence=0.9,
                output={"parsed_structure": {"worksheets": [{"name": "ws1"}], "visuals": [{"source_worksheet": "ws1"}]}},
            )
        return PhaseAgentResult(
            status="success",
            confidence=0.9,
            output={"parsed_structure": {"dashboards": [{"name": "d1"}], "visuals": [{}]}},
        )


def test_orchestrator_applies_deterministic_fix_before_retry(tmp_path: Path) -> None:
    orchestrator = AgentOrchestrator(
        max_retries=2,
        trace_file=tmp_path / "trace_fix.jsonl",
        debug_snapshot_dir=tmp_path / "snapshots_fix",
        enable_phase_cache=False,
    )
    parser = _ParsingNeedsFixAgent()
    orchestrator.register_tool(parser)

    state = AgentState(execution_id="gates-002", context={}, artifacts={})
    results = orchestrator.run(state, ["parsing"])

    assert parser.calls == 2
    assert results["parsing"].status == "success"
    assert ((state.context.get("deterministic_fixes") or {}).get("parsing") or {}).get("ensure_worksheets_from_visuals") is True


class _HeuristicRecoveryAgent:
    name = "parsing"

    def __init__(self) -> None:
        self.calls = 0

    def execute(self, state: dict):
        self.calls += 1
        context = state.get("context", {}) if isinstance(state, dict) else {}
        hfix = ((context or {}).get("heuristic_fixes", {}) or {}).get("parsing", {})
        if hfix.get("infer_dashboards_from_visuals"):
            return PhaseAgentResult(
                status="success",
                confidence=0.92,
                output={"parsed_structure": {"worksheets": [{"name": "ws1"}], "dashboards": [{"name": "AutoDashboard"}], "visuals": [{"source_worksheet": "ws1"}]}},
            )
        return PhaseAgentResult(
            status="low_confidence",
            confidence=0.65,
            output={"parsed_structure": {"worksheets": [{"name": "ws1"}], "dashboards": [], "visuals": [{"source_worksheet": "ws1"}]}},
        )


def test_orchestrator_applies_heuristic_fix_before_retry(tmp_path: Path) -> None:
    orchestrator = AgentOrchestrator(
        max_retries=2,
        trace_file=tmp_path / "trace_heuristic.jsonl",
        debug_snapshot_dir=tmp_path / "snapshots_heuristic",
        enable_phase_cache=False,
    )
    parser = _HeuristicRecoveryAgent()
    orchestrator.register_tool(parser)

    state = AgentState(execution_id="gates-003", context={}, artifacts={})
    results = orchestrator.run(state, ["parsing"])

    assert parser.calls == 2
    assert results["parsing"].status == "success"
    assert ((state.context.get("heuristic_fixes") or {}).get("parsing") or {}).get("infer_dashboards_from_visuals") is True


class _FakeLLMClient:
    def __init__(self) -> None:
        self.calls = 0

    def chat_json(self, system_prompt: str, user_prompt: str):
        self.calls += 1
        return {
            "fix_name": "llm_force_minimal_valid_structure",
            "hints": {"force_minimal_valid_structure": True},
            "notes": ["Ensure minimal parsed structure"],
        }


class _LLMOnlyRecoveryAgent:
    name = "parsing"

    def __init__(self) -> None:
        self.calls = 0

    def execute(self, state: dict):
        self.calls += 1
        context = state.get("context", {}) if isinstance(state, dict) else {}
        llm_fix = ((context or {}).get("llm_fixes", {}) or {}).get("parsing", {})
        if llm_fix.get("force_minimal_valid_structure"):
            return PhaseAgentResult(
                status="success",
                confidence=0.9,
                output={"parsed_structure": {"worksheets": [{"name": "ws_llm"}], "dashboards": [{"name": "db_llm"}], "visuals": [{"source_worksheet": "ws_llm"}]}},
            )
        return PhaseAgentResult(
            status="error",
            confidence=0.2,
            output={"parsed_structure": {"dashboards": [{"name": "d1"}], "visuals": [{}]}},
            errors=["still invalid after deterministic and heuristic fixes"],
        )


def test_llm_fallback_applies_only_after_previous_fix_layers(tmp_path: Path) -> None:
    orchestrator = AgentOrchestrator(
        max_retries=2,
        trace_file=tmp_path / "trace_llm.jsonl",
        debug_snapshot_dir=tmp_path / "snapshots_llm",
        enable_llm_fallback=True,
        enable_phase_cache=False,
    )
    parser = _LLMOnlyRecoveryAgent()
    orchestrator.register_tool(parser)

    fake_llm = _FakeLLMClient()
    orchestrator._llm_fallbacks._llm_client = fake_llm

    state = AgentState(execution_id="gates-004", context={}, artifacts={})
    results = orchestrator.run(state, ["parsing"])

    # attempt1 fail -> deterministic+heuristic ; attempt2 fail -> LLM fix ; attempt3 success
    assert parser.calls == 3
    assert fake_llm.calls == 1
    assert results["parsing"].status == "success"
    assert ((state.context.get("llm_fixes") or {}).get("parsing") or {}).get("force_minimal_valid_structure") is True


def test_llm_fallback_disabled_remains_inactive(tmp_path: Path) -> None:
    orchestrator = AgentOrchestrator(
        max_retries=2,
        trace_file=tmp_path / "trace_llm_disabled.jsonl",
        debug_snapshot_dir=tmp_path / "snapshots_llm_disabled",
        enable_llm_fallback=False,
        enable_phase_cache=False,
    )
    parser = _LLMOnlyRecoveryAgent()
    orchestrator.register_tool(parser)

    fake_llm = _FakeLLMClient()
    orchestrator._llm_fallbacks._llm_client = fake_llm

    state = AgentState(execution_id="gates-005", context={}, artifacts={})
    try:
        orchestrator.run(state, ["parsing"])
        assert False, "Expected failure without LLM fallback"
    except RuntimeError:
        pass

    assert fake_llm.calls == 0


class _SelfEvalMock:
    def __init__(self, phase3_scores: list[float] | None = None, phase5_scores: list[float] | None = None):
        self.phase3_scores = list(phase3_scores or [0.95])
        self.phase5_scores = list(phase5_scores or [0.95])
        self.phase3_calls = 0
        self.phase5_calls = 0

    def evaluate_phase3(self, output: dict):
        from viz_agent.orchestrator.llm_self_evaluator import SelfEvalResult

        score = self.phase3_scores[min(self.phase3_calls, len(self.phase3_scores) - 1)]
        self.phase3_calls += 1
        return SelfEvalResult(score=score, issues=[] if score >= 0.7 else ["low phase3"], dimensions={}, provider="mock")

    def evaluate_phase5(self, output: dict):
        from viz_agent.orchestrator.llm_self_evaluator import SelfEvalResult

        score = self.phase5_scores[min(self.phase5_calls, len(self.phase5_scores) - 1)]
        self.phase5_calls += 1
        return SelfEvalResult(score=score, issues=[] if score >= 0.75 else ["low phase5"], dimensions={}, provider="mock")

    def is_below_threshold(self, phase_name: str, result) -> bool:
        if phase_name == "specification":
            return result.score < 0.7
        if phase_name == "export":
            return result.score < 0.75
        return False


class _SimpleSpecAgent:
    name = "specification"

    def __init__(self) -> None:
        self.calls = 0

    def execute(self, state: dict):
        self.calls += 1
        return PhaseAgentResult(
            status="success",
            confidence=0.9,
            output={
                "abstract_spec": {
                    "dashboard_spec": {
                        "pages": [
                            {
                                "visuals": [
                                    {
                                        "id": "v1",
                                        "type": "columnchart",
                                        "data_binding": {"axes": {"x": "Country", "y": "Sales"}},
                                    }
                                ]
                            }
                        ]
                    }
                }
            },
        )


class _SimpleExportAgent:
    name = "export"

    def __init__(self) -> None:
        self.calls = 0

    def execute(self, state: dict):
        self.calls += 1
        return PhaseAgentResult(
            status="success",
            confidence=0.9,
            output={"export_result": {"validation": {"is_valid": True, "errors": [], "warnings": []}, "content_bytes": 120}},
        )


def test_llm_self_eval_phase3_triggers_retry(tmp_path: Path) -> None:
    orchestrator = AgentOrchestrator(
        max_retries=2,
        trace_file=tmp_path / "trace_self_eval_p3.jsonl",
        debug_snapshot_dir=tmp_path / "snapshots_self_eval_p3",
        enable_llm_self_eval=True,
        enable_phase_cache=False,
    )
    spec_agent = _SimpleSpecAgent()
    orchestrator.register_tool(spec_agent)
    orchestrator._self_evaluator = _SelfEvalMock(phase3_scores=[0.5, 0.85])

    state = AgentState(execution_id="selfeval-001")
    results = orchestrator.run(state, ["specification"])

    assert spec_agent.calls == 2
    assert results["specification"].status == "success"


def test_llm_self_eval_phase5_triggers_retry(tmp_path: Path) -> None:
    orchestrator = AgentOrchestrator(
        max_retries=2,
        trace_file=tmp_path / "trace_self_eval_p5.jsonl",
        debug_snapshot_dir=tmp_path / "snapshots_self_eval_p5",
        enable_llm_self_eval=True,
        enable_phase_cache=False,
    )
    export_agent = _SimpleExportAgent()
    orchestrator.register_tool(export_agent)
    orchestrator._self_evaluator = _SelfEvalMock(phase5_scores=[0.6, 0.9])

    state = AgentState(execution_id="selfeval-002")
    results = orchestrator.run(state, ["export"])

    assert export_agent.calls == 2
    assert results["export"].status == "success"


class _CacheablePhaseAgent:
    def __init__(self, name: str, output: dict):
        self.name = name
        self.output = output
        self.calls = 0

    def execute(self, state: dict):
        self.calls += 1
        return PhaseAgentResult(status="success", confidence=0.95, output=self.output)


def test_phase_cache_hit_skips_rerun(tmp_path: Path) -> None:
    cache_dir = tmp_path / "phase_cache"
    parsing_output = {"parsed_structure": {"worksheets": [{"name": "ws1"}], "visuals": [{"source_worksheet": "ws1"}]}}

    agent = _CacheablePhaseAgent("parsing", parsing_output)

    orchestrator1 = AgentOrchestrator(
        max_retries=1,
        trace_file=tmp_path / "trace_cache_1.jsonl",
        debug_snapshot_dir=tmp_path / "snapshots_cache_1",
        enable_phase_cache=True,
        cache_dir=cache_dir,
    )
    orchestrator1.register_tool(agent)
    state1 = AgentState(execution_id="cache-001", artifacts={"source_path": "demo.twbx"}, context={"intent": {"type": "conversion"}})
    orchestrator1.run(state1, ["parsing"])
    assert agent.calls == 1

    orchestrator2 = AgentOrchestrator(
        max_retries=1,
        trace_file=tmp_path / "trace_cache_2.jsonl",
        debug_snapshot_dir=tmp_path / "snapshots_cache_2",
        enable_phase_cache=True,
        cache_dir=cache_dir,
    )
    orchestrator2.register_tool(agent)
    state2 = AgentState(execution_id="cache-002", artifacts={"source_path": "demo.twbx"}, context={"intent": {"type": "conversion"}})
    result = orchestrator2.run(state2, ["parsing"])

    # Must stay 1 call: second run should be served from cache.
    assert agent.calls == 1
    assert result["parsing"].status == "success"


def test_cache_persists_metadata_parsed_spec_artifacts(tmp_path: Path) -> None:
    cache_dir = tmp_path / "phase_cache_artifacts"

    phase0 = _CacheablePhaseAgent("data_extraction", {"metadata": {"tables": [{"name": "sales"}]}})
    phase1 = _CacheablePhaseAgent("parsing", {"parsed_structure": {"worksheets": [{"name": "ws1"}], "visuals": [{"source_worksheet": "ws1"}]}})
    phase3 = _CacheablePhaseAgent(
        "specification",
        {
            "abstract_spec": {
                "dashboard_spec": {
                    "pages": [
                        {
                            "visuals": [
                                {
                                    "id": "v1",
                                    "type": "columnchart",
                                    "data_binding": {"axes": {"x": "Country", "y": "Sales"}},
                                }
                            ]
                        }
                    ]
                }
            }
        },
    )

    orchestrator = AgentOrchestrator(
        max_retries=1,
        trace_file=tmp_path / "trace_cache_artifacts.jsonl",
        debug_snapshot_dir=tmp_path / "snapshots_cache_artifacts",
        enable_phase_cache=True,
        cache_dir=cache_dir,
    )
    orchestrator.register_tool(phase0)
    orchestrator.register_tool(phase1)
    orchestrator.register_tool(phase3)

    state = AgentState(execution_id="cache-003", artifacts={"source_path": "demo.twbx"}, context={"intent": {"type": "conversion"}})
    orchestrator.run(state, ["data_extraction", "parsing", "specification"])

    cached = state.context.get("cached_artifacts") or {}
    assert "data_extraction" in cached and "metadata" in (cached.get("data_extraction") or {})
    assert "parsing" in cached and "parsed_structure" in (cached.get("parsing") or {})
    assert "specification" in cached and "abstract_spec" in (cached.get("specification") or {})

    assert Path((cached.get("data_extraction") or {}).get("metadata", "")).exists()
    assert Path((cached.get("parsing") or {}).get("parsed_structure", "")).exists()
    assert Path((cached.get("specification") or {}).get("abstract_spec", "")).exists()
