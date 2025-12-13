
from pydantic import BaseModel


class TechDocsEnrichment(BaseModel):
    """Enrichment schema for technical documentation."""
    summary: str | None = None
    evidence: list[str] | None = None
    truncated: bool = False  # True if any field was truncated during enrichment
