"""Phase-one request validation and source-tool policy.

The policy is deliberately independent of an agent framework.  An adapter can
translate the returned tool names into the runtime's actual tool registry.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Literal

Language = Literal["English"]
Structure = Literal["standard_analysis", "comparative_analysis"]
Style = Literal["formal_analytical", "concise_briefing", "detailed_explanatory"]
Depth = Literal["brief", "standard", "detailed"]
SourceMode = Literal["uploaded_only", "web_only", "hybrid"]

UPLOAD_TOOLS = frozenset({"upload_document", "list_uploaded_documents", "retrieve_uploaded_documents"})
NETWORK_TOOLS = frozenset({"web_search", "financial_source_search"})


@dataclass(frozen=True)
class ReportRequest:
    task: str
    language: Language = "English"
    structure: Structure = "standard_analysis"
    style: Style = "formal_analytical"
    depth: Depth = "standard"
    source_mode: SourceMode = "uploaded_only"
    output_format: Literal["markdown"] = "markdown"
    min_words: int | None = None
    max_words: int | None = None

    def validate(self) -> None:
        if not self.task.strip():
            raise ValueError("task must not be empty")
        if self.language != "English":
            raise ValueError("phase one supports English output only")
        if self.structure not in {"standard_analysis", "comparative_analysis"}:
            raise ValueError(f"unsupported structure: {self.structure}")
        if self.style not in {"formal_analytical", "concise_briefing", "detailed_explanatory"}:
            raise ValueError(f"unsupported style: {self.style}")
        if self.depth not in {"brief", "standard", "detailed"}:
            raise ValueError(f"unsupported depth: {self.depth}")
        if self.source_mode not in {"uploaded_only", "web_only", "hybrid"}:
            raise ValueError(f"unsupported source mode: {self.source_mode}")
        if self.output_format != "markdown":
            raise ValueError("phase one supports Markdown output only")
        for value in (self.min_words, self.max_words):
            if value is not None and (type(value) is not int or value <= 0):
                raise ValueError('Word limits must be positive integers')
        limits = word_limits(self)
        if limits and any(value is not None and value <= 0 for value in (limits['min'], limits['max'])):
            raise ValueError('Word limits must be positive integers')
        if limits and limits['min'] is not None and limits['max'] is not None and limits['min'] > limits['max']:
            raise ValueError('Minimum words exceeds maximum words')


def word_limits(request):
    """Only explicit numeric requirements; depth/style never imply a word limit."""
    if request.min_words is not None or request.max_words is not None:
        return {'min': request.min_words, 'max': request.max_words, 'origin': 'explicit_fields'}
    task = request.task
    unit = r'(?:words?\b|(?:个)?(?:英文)?(?:单词|词))'
    between = re.search(r'(?:between\s+)?(\d+)\s*(?:[-–—至到]|and)\s*(\d+)\s*' + unit, task, re.I)
    if between:
        return {'min': int(between[1]), 'max': int(between[2]), 'origin': 'explicit_task_range'}
    upper = re.search(r'(?:at most|no more than|up to|maximum(?: of)?|within|不超过|最多|上限(?:为)?)\s*(\d+)\s*' + unit, task, re.I)
    if not upper:
        upper = re.search(r'(\d+)\s*' + unit + r'\s*(?:以内|以下)', task, re.I)
    if upper:
        return {'min': None, 'max': int(upper[1]), 'origin': 'explicit_task_maximum'}
    strict_upper = re.search(r'(?:under|less than|少于)\s*(\d+)\s*' + unit, task, re.I)
    if strict_upper:
        return {'min': None, 'max': int(strict_upper[1])-1, 'origin': 'explicit_task_strict_maximum'}
    exact = re.search(r'(?:exactly|恰好|严格为)\s*(\d+)\s*' + unit, task, re.I)
    if exact:
        return {'min': int(exact[1]), 'max': int(exact[1]), 'origin': 'explicit_task_exact'}
    lower = re.search(r'(?:at least|no fewer than|不少于|至少)\s*(\d+)\s*' + unit, task, re.I)
    if lower:
        return {'min': int(lower[1]), 'max': None, 'origin': 'explicit_task_minimum'}
    target = re.search(r'(\d+)[-–]word\s+(?:report|summary|brief|analysis)\b', task, re.I)
    if target:
        return {'min': None, 'max': int(target[1]), 'origin': 'explicit_task_target_as_ceiling'}
    return None


def allowed_tools(source_mode: SourceMode) -> frozenset[str]:
    """Return the runtime allowlist; callers must enforce it at tool dispatch."""
    if source_mode == "uploaded_only":
        return UPLOAD_TOOLS
    if source_mode == "web_only":
        return NETWORK_TOOLS
    if source_mode == "hybrid":
        return UPLOAD_TOOLS | NETWORK_TOOLS
    raise ValueError(f"unsupported source mode: {source_mode}")


STANDARD_HEADINGS = (
    "Executive Summary", "Scope and Information Sources", "Background and Context",
    "Key Findings", "Detailed Analysis", "Risks and Limitations", "Conclusion", "Sources",
)
COMPARATIVE_HEADINGS = (
    "Executive Summary", "Comparison Scope and Criteria", "Source Overview",
    "Comparison by Dimension", "Areas of Agreement and Disagreement", "Integrated Findings",
    "Limitations", "Sources",
)


def required_headings(structure: Structure) -> tuple[str, ...]:
    if structure == "standard_analysis":
        return STANDARD_HEADINGS
    if structure == "comparative_analysis":
        return COMPARATIVE_HEADINGS
    raise ValueError(f"unsupported structure: {structure}")


def policy_snapshot(request: ReportRequest) -> dict:
    request.validate()
    return {
        "request": asdict(request),
        "allowed_tools": sorted(allowed_tools(request.source_mode)),
        "required_headings": list(required_headings(request.structure)),
    }


if __name__ == "__main__":
    request = ReportRequest(task="Summarise the NVIDIA annual report")
    print(json.dumps(policy_snapshot(request), indent=2))
