"""
Schema-validated enrichment output for technical documentation.

This schema enforces field budgets and provides stable IDs for TE/MCP consumption.
See SDD_Domain_RAG_Tech_Docs.md Section 5.3 for design rationale.
"""

from __future__ import annotations

import hashlib
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

# Field budgets (from SDD Phase 3)
MAX_SUMMARY_WORDS = 60
MAX_LIST_ITEMS = 10
MAX_CONCEPT_LENGTH = 50
MAX_PARAM_DESCRIPTION = 200


def _truncate_words(text: str, max_words: int) -> tuple[str, bool]:
    """Truncate text with ellipsis, return (text, was_truncated)."""
    words = text.split()
    truncated = len(words) > max_words
    result = " ".join(words[:max_words]) + ("…" if truncated else "")
    return result, truncated


class ParameterDoc(BaseModel):
    """A documented parameter extracted from tech docs."""

    name: str = Field(..., max_length=100)
    type: str | None = Field(None, max_length=50)
    description: str = Field(..., max_length=MAX_PARAM_DESCRIPTION)

    @field_validator("description", mode="before")
    @classmethod
    def truncate_description(cls, v: str) -> str:
        if v and len(v) > MAX_PARAM_DESCRIPTION:
            return v[: MAX_PARAM_DESCRIPTION - 1] + "…"
        return v


class TechDocsEnrichment(BaseModel):
    """Schema-validated enrichment output for tech docs.

    All fields have strict budgets to prevent context bloat.
    The `truncated` flag indicates if any field was cut during enrichment.
    """

    # Stable ID: hash(file_path + section_path)
    span_id: str = Field(..., description="Stable identifier for this span")

    # Core fields
    summary: str = Field(
        ...,
        max_length=500,
        description="One sentence describing what this section explains",
    )
    key_concepts: list[str] = Field(
        default_factory=list, description="Main concepts covered"
    )
    parameters: list[ParameterDoc] = Field(
        default_factory=list, description="Documented parameters"
    )

    # Boolean flags
    code_examples: bool = Field(
        False, description="Whether section contains code examples"
    )

    # List fields with budgets
    prerequisites: list[str] = Field(
        default_factory=list, description="Required prior knowledge"
    )
    warnings: list[str] = Field(default_factory=list, description="Cautions or notes")
    related_topics: list[str] = Field(
        default_factory=list, description="Cross-references"
    )

    # Audience classification
    audience: str = Field("mixed", pattern=r"^(developer|admin|user|mixed)$")

    # Evidence tracking
    evidence: list[dict[str, Any]] = Field(
        default_factory=list, description="Source evidence for extraction"
    )

    # Truncation tracking
    truncated: bool = Field(
        False, description="True if any field was truncated during enrichment"
    )
    truncated_fields: list[str] = Field(
        default_factory=list, description="Which fields were truncated"
    )

    @field_validator(
        "key_concepts", "prerequisites", "warnings", "related_topics", mode="before"
    )
    @classmethod
    def limit_list_length(cls, v: list | None) -> list:
        """Guard against injection of massive lists."""
        if v is None:
            return []
        return v[:MAX_LIST_ITEMS]

    @field_validator("summary", mode="before")
    @classmethod
    def truncate_summary(cls, v: str | None) -> str:
        """Enforce summary word budget."""
        if v is None:
            return ""
        text, was_truncated = _truncate_words(v, MAX_SUMMARY_WORDS)
        # Note: truncation tracking is handled in model_validator
        return text

    @model_validator(mode="before")
    @classmethod
    def track_truncations(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Track which fields were truncated."""
        truncated_fields = []

        # Check summary
        if "summary" in data and data["summary"]:
            words = data["summary"].split()
            if len(words) > MAX_SUMMARY_WORDS:
                truncated_fields.append("summary")

        # Check list lengths
        for field_name in [
            "key_concepts",
            "prerequisites",
            "warnings",
            "related_topics",
        ]:
            if field_name in data and isinstance(data[field_name], list):
                if len(data[field_name]) > MAX_LIST_ITEMS:
                    truncated_fields.append(field_name)

        if truncated_fields:
            data["truncated"] = True
            data["truncated_fields"] = truncated_fields

        return data

    class Config:
        extra = "forbid"  # Reject unexpected keys (injection guard)

    @classmethod
    def make_span_id(cls, file_path: str, section_path: str) -> str:
        """Generate stable ID from file + section."""
        return hashlib.sha256(f"{file_path}::{section_path}".encode()).hexdigest()[:16]

    @classmethod
    def from_llm_response(
        cls, llm_output: dict[str, Any], file_path: str, section_path: str
    ) -> TechDocsEnrichment:
        """Create enrichment from LLM response with automatic span_id generation.

        This is the primary factory method for creating enrichments from LLM output.
        It handles missing fields gracefully and generates stable IDs.
        """
        span_id = cls.make_span_id(file_path, section_path)

        # Build parameters list
        params = []
        if "parameters" in llm_output and isinstance(llm_output["parameters"], list):
            for p in llm_output["parameters"][:MAX_LIST_ITEMS]:
                if isinstance(p, dict) and "name" in p:
                    params.append(
                        ParameterDoc(
                            name=p.get("name", "")[:100],
                            type=p.get("type"),
                            description=p.get("description", "")[
                                :MAX_PARAM_DESCRIPTION
                            ],
                        )
                    )

        return cls(
            span_id=span_id,
            summary=llm_output.get("summary", ""),
            key_concepts=llm_output.get("key_concepts", []),
            parameters=params,
            code_examples=bool(llm_output.get("code_examples", False)),
            prerequisites=llm_output.get("prerequisites", []),
            warnings=llm_output.get("warnings", []),
            related_topics=llm_output.get("related_topics", []),
            audience=llm_output.get("audience", "mixed"),
            evidence=llm_output.get("evidence", []),
        )


# Enrichment prompt for tech docs (from SDD Section 5.1)
TECH_DOCS_ENRICHMENT_PROMPT = """You are analyzing technical documentation. Extract structured information.

DOCUMENT SECTION:
{content}

EXTRACT (JSON):
{{
  "summary": "One sentence describing what this section explains",
  "key_concepts": ["list", "of", "main", "concepts"],
  "parameters": [
    {{"name": "param_name", "type": "string", "description": "what it does"}}
  ],
  "code_examples": true/false,
  "prerequisites": ["any", "required", "prior", "knowledge"],
  "warnings": ["any", "cautions", "or", "notes"],
  "related_topics": ["cross-references", "see also"],
  "audience": "developer" | "admin" | "user" | "mixed"
}}

Only include fields that are present in the content. Be concise.
"""
