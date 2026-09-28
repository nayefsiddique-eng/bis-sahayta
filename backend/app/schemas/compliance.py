from datetime import date
from typing import Literal, Any
from pydantic import BaseModel, Field
from app.schemas.product import ProductInput
from app.schemas.language import LanguagePreference

class SourceCitation(BaseModel):
    document_id: str
    clause: str | None = None
    title: str
    url: str | None = None

class ComplianceRequirement(BaseModel):
    requirement: str
    test_or_document: Literal["test", "document", "marking"]
    mandatory: bool
    source: SourceCitation

class QCOResult(BaseModel):
    qco_id: str
    standard_id: str
    applies: bool
    reasoning: str
    effective_date: date
    exemption_status: Literal["none", "msme", "import", "grandfathered"]
    source: SourceCitation
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

class ComplianceCheckResponse(BaseModel):
    product: ProductInput
    qco_result: QCOResult
    qco_results: list[QCOResult] = []
    requirements: list[ComplianceRequirement]
    recommended_labs: list[str]
    unverified_claims: list[str] = []
    roadmap_available: bool = True
    low_confidence_warning: bool = False
    explanation: dict[str, Any] | None = None
    response_lang: str = "en"
    translation_unavailable: bool = False

class QueryInput(BaseModel):
    query: str
    lang: LanguagePreference = Field(default_factory=LanguagePreference)

class QueryResponse(BaseModel):
    intent: str
    message: str
    data: dict | None = None
    response_lang: str = "en"
    translation_unavailable: bool = False

class RoadmapRequest(BaseModel):
    qco_result: QCOResult
    lang: LanguagePreference = Field(default_factory=LanguagePreference)

class RoadmapStep(BaseModel):
    step_number: int
    title: str
    description: str

class RoadmapResponse(BaseModel):
    qco_id: str
    steps: list[RoadmapStep]
    response_lang: str = "en"
    translation_unavailable: bool = False
