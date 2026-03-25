from __future__ import annotations

import re

from viz_agent.models.validation import Issue


class RDLAutoFixer:
    def __init__(self) -> None:
        self.fix_log: list[str] = []

    def fix_all(self, rdl_content: str, issues: list[Issue]) -> tuple[str, list[str]]:
        self.fix_log = []
        current = rdl_content

        for issue in issues:
            if issue.severity != "error" and issue.code != "X006":
                continue
            fixer = self._get_fixer(issue.code)
            if fixer is None:
                continue
            updated = fixer(current, issue)
            if updated != current:
                current = updated
        return current, self.fix_log

    def _get_fixer(self, code: str):
        return {
            "X002": self._fix_namespace,
            "X005": self._fix_control_chars,
            "X006": self._fix_unescaped_attrs,
            "S007": self._fix_dimension,
        }.get(code)

    def _fix_namespace(self, rdl: str, issue: Issue) -> str:
        target = issue.auto_fix or "http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"
        replaced = re.sub(
            r'xmlns="http://schemas\.microsoft\.com/sqlserver/reporting/\d+/\d+/reportdefinition"',
            f'xmlns="{target}"',
            rdl,
            count=1,
        )
        if replaced == rdl and "<Report" in rdl and "xmlns=" not in rdl.split(">", 1)[0]:
            replaced = rdl.replace("<Report", f'<Report xmlns="{target}"', 1)

        if replaced != rdl:
            self.fix_log.append("[X002] normalized RDL namespace")
        return replaced

    def _fix_control_chars(self, rdl: str, issue: Issue) -> str:
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", rdl)
        if cleaned != rdl:
            self.fix_log.append("[X005] removed forbidden control characters")
        return cleaned

    def _fix_unescaped_attrs(self, rdl: str, issue: Issue) -> str:
        def _escape_attr(match: re.Match[str]) -> str:
            attr = match.group(0)
            return re.sub(r"&(?!amp;|lt;|gt;|apos;|quot;|#)", "&amp;", attr)

        updated = re.sub(r'="[^"]*"', _escape_attr, rdl)
        if updated != rdl:
            self.fix_log.append("[X006] escaped '&' in XML attributes")
        return updated

    def _fix_dimension(self, rdl: str, issue: Issue) -> str:
        tags = [
            "Width",
            "Height",
            "Top",
            "Left",
            "MarginTop",
            "MarginBottom",
            "MarginLeft",
            "MarginRight",
            "PageWidth",
            "PageHeight",
        ]
        current = rdl
        for tag in tags:
            current = re.sub(
                rf"<{tag}>(-?\\d+(?:\\.\\d+)?)</{tag}>",
                rf"<{tag}>\\1in</{tag}>",
                current,
            )
        if current != rdl:
            self.fix_log.append("[S007] added default 'in' unit to numeric dimensions")
        return current
