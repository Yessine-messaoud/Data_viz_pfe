from __future__ import annotations

from typing import Any

from viz_agent.validators.autofix.heuristic_fixer import HeuristicAutoFixer
from viz_agent.validators.autofix.llm_fixer_stub import LLMAutoFixerStub
from viz_agent.validators.autofix.rule_based_fixer import RuleBasedAutoFixer


class AutoFixEngine:
    def __init__(self) -> None:
        self.rule = RuleBasedAutoFixer()
        self.heuristic = HeuristicAutoFixer()
        self.llm_stub = LLMAutoFixerStub()

    def apply(self, payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        fixed, applied = self.rule.apply(payload)
        fixed, heuristic_applied = self.heuristic.apply(fixed)
        applied.extend(heuristic_applied)
        fixed, llm_applied = self.llm_stub.apply(fixed)
        applied.extend(llm_applied)
        return fixed, applied

