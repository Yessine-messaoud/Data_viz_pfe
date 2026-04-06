from __future__ import annotations

from lxml import etree

from viz_agent.models.validation import Issue, ValidationReport
from viz_agent.phase5_rdl.rdl_auto_fixer import RDLAutoFixer
from viz_agent.phase5_rdl.rdl_dataset_validator import RDLDatasetValidator
from viz_agent.phase5_rdl.rdl_schema_validator import RDLSchemaValidator
from viz_agent.phase5_rdl.rdl_semantic_validator import RDLSemanticValidator
from viz_agent.phase5_rdl.rdl_xml_validator import RDLXMLValidator


class RDLFullReport:
    def __init__(
        self,
        level1: ValidationReport | None,
        level2: ValidationReport | None,
        level3: ValidationReport | None,
        can_proceed: bool,
        dataset_level: ValidationReport | None = None,
    ) -> None:
        self.level1 = level1
        self.level2 = level2
        self.level3 = level3
        self.dataset_level = dataset_level
        self.can_proceed = can_proceed
        self.auto_fixes_applied: list[str] = []
        self.fix_rounds: int = 0

    @property
    def all_issues(self) -> list[Issue]:
        out: list[Issue] = []
        for lvl in (self.level1, self.level2, self.dataset_level, self.level3):
            if lvl:
                out.extend(lvl.errors)
                out.extend(lvl.warnings)
        return out

    @property
    def error_count(self) -> int:
        return sum(len(lvl.errors) for lvl in (self.level1, self.level2, self.dataset_level, self.level3) if lvl)

    @property
    def warning_count(self) -> int:
        return sum(len(lvl.warnings) for lvl in (self.level1, self.level2, self.dataset_level, self.level3) if lvl)

    @property
    def score(self) -> int:
        levels = [lvl for lvl in (self.level1, self.level2, self.dataset_level, self.level3) if lvl]
        if not levels:
            return 0
        return int(sum(l.score for l in levels) / len(levels))

    def summary(self) -> str:
        status = "OK" if self.can_proceed else "FAILED"
        lines = [
            f"RDL Validation - {status}",
            f"  Errors    : {self.error_count}",
            f"  Warnings  : {self.warning_count}",
            f"  Auto-fixes: {len(self.auto_fixes_applied)} in {self.fix_rounds} round(s)",
        ]
        return "\n".join(lines)


class RDLValidatorPipeline:
    def __init__(self) -> None:
        self.xml_validator = RDLXMLValidator()
        self.schema_validator = RDLSchemaValidator()
        self.dataset_validator = RDLDatasetValidator()
        self.semantic_validator = RDLSemanticValidator()
        self.auto_fixer = RDLAutoFixer()

    def validate_and_fix(
        self,
        rdl_content: str,
        auto_fix: bool = True,
        max_fix_rounds: int = 3,
    ) -> tuple[str, RDLFullReport]:
        current_rdl = rdl_content
        auto_fixes_applied: list[str] = []
        report: RDLFullReport | None = None

        for round_idx in range(max_fix_rounds):
            report = self._run_all_levels(current_rdl)
            if report.error_count == 0:
                break
            if not auto_fix:
                break

            fixable = [
                i
                for i in report.all_issues
                if i.auto_fix
                or i.code in {"X002", "X006", "S007", "S005", "S005c", "S005d", "S005e", "S005f", "S003f", "S008c", "S008d", "S008e", "S009"}
            ]
            if not fixable:
                break

            fixed_rdl, fixes = self.auto_fixer.fix_all(current_rdl, fixable)
            if not fixes or fixed_rdl == current_rdl:
                break

            current_rdl = fixed_rdl
            auto_fixes_applied.extend(fixes)

        final_report = self._run_all_levels(current_rdl)
        final_report.auto_fixes_applied = auto_fixes_applied
        final_report.fix_rounds = (round_idx + 1) if report is not None else 0
        return current_rdl, final_report

    def _run_all_levels(self, rdl_content: str) -> RDLFullReport:
        level1 = self.xml_validator.validate(rdl_content)
        if not level1.can_proceed:
            return RDLFullReport(level1=level1, level2=None, level3=None, can_proceed=False, dataset_level=None)

        parser = etree.XMLParser(recover=False)
        root = etree.fromstring(rdl_content.encode("utf-8"), parser=parser)

        level2 = self.schema_validator.validate(root)
        if not level2.can_proceed:
            return RDLFullReport(level1=level1, level2=level2, level3=None, can_proceed=False, dataset_level=None)

        dataset_level = self.dataset_validator.validate_rendering_contract(root)

        level3 = self.semantic_validator.validate(root)
        can_proceed = dataset_level.can_proceed and level3.can_proceed
        return RDLFullReport(level1=level1, level2=level2, level3=level3, can_proceed=can_proceed, dataset_level=dataset_level)
