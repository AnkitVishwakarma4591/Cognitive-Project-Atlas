"""
Pydantic models and schemas for Project Atlas API.
Defines typed request/response contracts according to PDF specification.
"""
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


class Citation(BaseModel):
    report_id: str = Field(..., description="Unique report identifier, e.g., R-101")
    title: str = Field(..., description="Full title of the referenced report")
    page: Optional[int] = Field(None, description="Page number where the quote or metric appears")
    text: str = Field(..., description="Exact or verbatim quote from the report")
    sector: Optional[str] = Field(None, description="Industry sector of the report")


class ConflictSource(BaseModel):
    report_id: str = Field(..., description="Report ID containing the conflicting figure")
    title: Optional[str] = None
    value: str = Field(..., description="Quoted value or metric")
    scope: str = Field(..., description="Scope or methodology explaining the boundary conditions")


class Conflict(BaseModel):
    metric: str = Field(..., description="The metric subject to conflicting data points")
    sources: List[ConflictSource] = Field(..., description="List of conflicting sources and scopes")
    explanation: str = Field(..., description="Analytical breakdown of why the figures differ")


class DerivedValue(BaseModel):
    metric: str = Field(..., description="The calculated or extrapolated metric name")
    derived_value: str = Field(..., description="The computed outcome, clearly labeled as an estimate")
    formula: str = Field(..., description="Mathematical formula applied (e.g., V_2030 = Base * (1+r)^n * share)")
    assumptions: List[str] = Field(..., description="List of assumptions, base-year notes, and caveats")


class ChatRequest(BaseModel):
    client_id: str = Field(..., min_length=1, description="Authenticated client identifier (e.g. C-01, C-02)")
    question: str = Field(..., min_length=1, max_length=1000, description="User question or research prompt")
    session_id: Optional[str] = Field(default=None, description="Optional session/conversation identifier")


class ChatResponse(BaseModel):
    answer: str = Field(..., description="Executive synthesized response with strict citations")
    citations: List[Citation] = Field(default_factory=list, description="Array of verified citations")
    confidence: float = Field(..., ge=0.0, le=1.0, description="System confidence score between 0.0 and 1.0")
    conflicts: List[Conflict] = Field(default_factory=list, description="Detected conflicts with scope explanations")
    derived_values: List[DerivedValue] = Field(default_factory=list, description="Computed metrics with formulas and assumptions")
    escalated: bool = Field(default=False, description="True if forwarded to human analyst due to low confidence or ambiguity")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Operational metadata (latency_ms, cost_usd, cached)")


class FeedbackRequest(BaseModel):
    conversation_id: int = Field(..., description="Database ID of the conversation")
    rating: Literal["up", "down"] = Field(..., description="Thumbs up or thumbs down")
    comments: Optional[str] = Field(default=None, description="Optional qualitative feedback")


class IngestResponse(BaseModel):
    status: str
    indexed_reports: int
    chunks_count: int
    message: str


class EscalationItem(BaseModel):
    id: int
    client_id: str
    question: str
    reason: str
    confidence: float
    status: str
    created_at: str


class HealthResponse(BaseModel):
    status: str
    database: str
    indexed_chunks: int
    llm_provider: str
    timestamp: str
