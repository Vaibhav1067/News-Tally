"""Pydantic request/response schemas — the API contract the frontend relies on."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

RiskLevel = Literal["HIGH MISINFORMATION RISK", "POTENTIALLY MISLEADING", "EVIDENCE SUPPORTS CLAIM",
                    "UNVERIFIED", "INSUFFICIENT EVIDENCE"]


class AnalyzeRequest(BaseModel):
    text: Optional[str] = Field(None, max_length=10_000, description="Claim, post, forward or article text")
    url: Optional[HttpUrl] = Field(None, description="Optional article URL to extract text from")
    language: Optional[str] = Field(None, max_length=12, description="Optional language hint, e.g. 'hi'")
    save_to_history: bool = Field(False, description="Store the submitted text (opt-in, purged after retention period)")

    @field_validator("text")
    @classmethod
    def strip_text(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v

    @model_validator(mode="after")
    def need_input(self):
        if not self.text and not self.url:
            raise ValueError("Provide 'text' or 'url'.")
        return self


class LanguageInfo(BaseModel):
    code: str
    name: str
    confidence: float
    is_mixed: bool
    method: str
    supported_by_model: bool
    user_hint: Optional[str] = None


class ExtractedContent(BaseModel):
    text: str
    source: Literal["text", "url", "text+url"]
    url: Optional[str] = None
    title: Optional[str] = None
    char_count: int
    truncated: bool
    urls_in_text: list[str] = []
    extraction_error: Optional[str] = None


class Prediction(BaseModel):
    available: bool
    label: Optional[str] = None
    probabilities: dict[str, float] = {}
    confidence: Optional[float] = None
    model_name: Optional[str] = None
    in_domain: bool = False
    note: str = ""


class FactCheckMatch(BaseModel):
    id: str
    claim_text: str
    title: Optional[str]
    verdict: Optional[str]
    explanation: Optional[str]
    source_name: str
    original_url: str
    language: Optional[str]
    publication_date: Optional[date]
    similarity: float
    match_strength: Literal["strong", "related", "weak"]
    age_days: Optional[int] = None


class SourceInfo(BaseModel):
    domain: Optional[str]
    name: Optional[str] = None
    source_type: Optional[str] = None
    status: Literal["no_url", "insufficient_history", "known_source", "fact_checker"]
    mentions_in_dataset: int = 0
    verdict_breakdown: dict[str, int] = {}
    example_fact_checks: list[dict] = []
    coverage_note: str = ""
    limitations: list[str] = []


class Explanation(BaseModel):
    available: bool
    method: Optional[str] = None
    target_class: Optional[str] = None
    top_features: list[dict] = []
    token_highlights: list[dict] = []
    note: str = ""
    reason: Optional[str] = None


class ScoreComponent(BaseModel):
    name: str
    value: Optional[float]
    weight: float
    available: bool
    detail: str


class RiskAssessment(BaseModel):
    level: RiskLevel
    risk_score: float = Field(..., ge=0, le=100)
    evidence_strength: float = Field(..., ge=0, le=1)
    evidence_strength_label: Literal["High", "Medium", "Low"]
    summary: str
    reasons: list[str]
    missing_evidence: list[str]
    components: list[ScoreComponent]
    formula: str


class AnalyzeResponse(BaseModel):
    analysis_id: str
    detected_language: LanguageInfo
    extracted_content: ExtractedContent
    prediction: Prediction
    confidence: Optional[float]
    risk_assessment: RiskAssessment
    matching_fact_checks: list[FactCheckMatch]
    source_information: SourceInfo
    explanation: Explanation
    retrieval_backend: str
    processing_time_ms: int
    stored: bool
    disclaimer: str


class FactCheckOut(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    claim_text: str
    claim_source: Optional[str]
    title: Optional[str]
    verdict: Optional[str]
    verdict_raw: Optional[str]
    verdict_rule: Optional[str]
    explanation: Optional[str]
    source_name: str
    original_url: str
    category: Optional[str]
    category_source: Optional[str]
    language: Optional[str]
    publication_date: Optional[date]


class FactCheckPage(BaseModel):
    items: list[FactCheckOut]
    total: int
    page: int
    page_size: int


class FeedbackIn(BaseModel):
    analysis_id: str = Field(..., max_length=36)
    feedback_type: Literal["helpful", "not_helpful", "wrong_match", "wrong_assessment", "other"]
    comments: Optional[str] = Field(None, max_length=2000)


class FeedbackOut(BaseModel):
    id: int
    analysis_id: str
    feedback_type: str
    created_at: datetime


class HistoryItem(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    text_preview: Optional[str]
    submitted_url: Optional[str]
    detected_language: Optional[str]
    predicted_class: Optional[str]
    risk_level: Optional[str]
    risk_score: Optional[float]
    created_at: datetime
