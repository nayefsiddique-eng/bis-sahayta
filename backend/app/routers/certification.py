"""
Certification router.
POST /certification/analyze  — analyze a product for certification requirements
POST /certification/roadmap  — generate a step-by-step certification roadmap
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.compliance_engine import check_qco_applicability, resolve_requirements
from app.services.roadmap import generate_roadmap
from app.services.llm_service import LLMService
from app.services.rag_service import RAGService
from app.services.cache_service import get_cache, make_cache_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/certification", tags=["certification"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CertificationAnalyzeRequest(BaseModel):
    product_name: str = Field(..., min_length=1, max_length=300)
    category: str = Field(..., min_length=1, max_length=200)
    description: str = Field("", max_length=1000)
    manufacturer_scale: str = Field("large", description="msme | large | startup")
    is_imported: bool = False
    target_market: str = Field("domestic", description="domestic | export | both")


class CertificationStep(BaseModel):
    step_number: int
    phase: str
    title: str
    description: str
    estimated_days: Optional[int] = None
    cost_inr_approx: Optional[str] = None


class CertificationAnalyzeResponse(BaseModel):
    product_name: str
    category: str
    qco_applicable: bool
    qco_id: Optional[str]
    standard_id: Optional[str]
    certification_type: str
    mandatory: bool
    summary: str
    requirements: list[dict]
    recommended_labs: list[str]


class RoadmapRequestCert(BaseModel):
    qco_id: str
    category: str = ""
    manufacturer_scale: str = "large"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/analyze", response_model=CertificationAnalyzeResponse)
async def analyze_certification(body: CertificationAnalyzeRequest):
    """
    Analyze a product to determine certification requirements and applicable QCOs.
    Returns applicable standards, requirements, and recommended testing labs.
    """
    from app.schemas.product import ProductInput
    from app.schemas.language import LanguagePreference

    cache_key = make_cache_key(
        body.category, body.description, body.manufacturer_scale, body.is_imported,
        prefix="cert_analyze",
    )
    cached = get_cache().get(cache_key)
    if cached:
        return CertificationAnalyzeResponse(**cached)

    # Run compliance engine
    product = ProductInput(
        category=body.category,
        description=body.description or body.product_name,
        manufacturer_scale=body.manufacturer_scale,
        is_imported=body.is_imported,
        lang=LanguagePreference(lang_code="en"),
    )
    primary_qco, qco_results, _ = check_qco_applicability(product)
    all_requirements = []
    all_labs = set()
    for qco_res in qco_results:
        reqs, labs = resolve_requirements(qco_res)
        all_requirements.extend(reqs)
        all_labs.update(labs)

    # Generate contextual summary via LLM
    rag_context = ""
    if RAGService.is_available():
        chunks = RAGService.retrieve_texts(f"{body.category} BIS certification requirements", k=3)
        rag_context = "\n".join(chunks)

    summary_prompt = (
        f"Summarize in 2-3 sentences the BIS certification requirements for:\n"
        f"Product: {body.product_name}\nCategory: {body.category}\n"
        f"Manufacturer scale: {body.manufacturer_scale}\nImported: {body.is_imported}\n"
        f"QCO applicable: {primary_qco.applies}, QCO ID: {primary_qco.qco_id}\n"
        f"{'Context: ' + rag_context if rag_context else ''}"
    )
    summary = await LLMService.complete(summary_prompt, max_tokens=256)

    response = CertificationAnalyzeResponse(
        product_name=body.product_name,
        category=body.category,
        qco_applicable=primary_qco.applies,
        qco_id=primary_qco.qco_id if primary_qco.applies else None,
        standard_id=primary_qco.standard_id if primary_qco.applies else None,
        certification_type="BIS ISI Mark" if primary_qco.applies else "Voluntary / Not Mandatory",
        mandatory=primary_qco.applies,
        summary=summary,
        requirements=[r.model_dump() for r in all_requirements],
        recommended_labs=list(all_labs),
    )
    get_cache().set(cache_key, response.model_dump(), ttl=600)
    return response


@router.post("/roadmap")
async def certification_roadmap(body: RoadmapRequestCert):
    """
    Generate a step-by-step certification roadmap for a given QCO ID.
    """
    from app.schemas.compliance import QCOResult, SourceCitation
    from app.services.compliance_engine import load_qco_data
    from datetime import date

    # Look up QCO data
    qco_list = load_qco_data()
    matched = next(
        (q for q in qco_list if q.get("qco_id", "").lower() == body.qco_id.lower()), None
    )
    if not matched:
        from app.core.exceptions import APIException
        raise APIException(
            status_code=404,
            error_code="QCO_NOT_FOUND",
            message=f"QCO ID '{body.qco_id}' not found in database.",
        )

    # Build SourceCitation from QCO data
    source_citation = SourceCitation(
        document_id=matched.get("qco_id", "UNKNOWN"),
        title=matched.get("title", ""),
        clause=None,
        url=None,
    )

    # Parse effective_date — fall back to today if missing/invalid
    raw_date = matched.get("effective_date", "")
    try:
        from datetime import datetime
        eff_date = datetime.strptime(raw_date, "%Y-%m-%d").date() if raw_date else date.today()
    except ValueError:
        eff_date = date.today()

    qco_result = QCOResult(
        applies=True,
        qco_id=matched["qco_id"],
        standard_id=matched.get("standard_id", ""),
        exemption_status=body.manufacturer_scale if body.manufacturer_scale == "msme" else "none",
        confidence=1.0,
        reasoning=f"Direct lookup for QCO ID {body.qco_id}",
        effective_date=eff_date,
        source=source_citation,
    )

    steps = generate_roadmap(qco_result)
    cache_key = make_cache_key(body.qco_id, prefix="cert_roadmap")
    result = {
        "qco_id": body.qco_id,
        "title": matched.get("title", ""),
        "steps": [s.model_dump() for s in steps],
        "total_steps": len(steps),
    }
    get_cache().set(cache_key, result, ttl=3600)
    return result
