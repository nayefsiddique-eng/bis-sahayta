from fastapi import APIRouter, Query
from app.schemas.product import ProductInput
from app.schemas.compliance import (
    ComplianceCheckResponse,
    RoadmapRequest,
    RoadmapResponse,
)
from app.services.compliance_engine import check_qco_applicability, resolve_requirements
from app.services.citation_verifier import verify_response_citations
from app.services.roadmap import generate_roadmap
from app.services.translation import translate_text, BhashiniUnavailableError
from app.core.cache import response_cache

router = APIRouter(prefix="/compliance", tags=["compliance"])

@router.post("/check", response_model=ComplianceCheckResponse)
async def check_compliance(
    product: ProductInput,
    explain: bool = Query(default=False, description="Enable explainability mode detailing evaluated QCO candidates")
):
    # 1. Check in-memory response cache (Step 3) - only if explain mode is false
    if not explain:
        cached_resp = response_cache.get(product)
        if cached_resp:
            return ComplianceCheckResponse(**cached_resp)

    target_lang = product.lang.lang_code
    translation_unavailable = False

    # 2. Translate incoming product category & description to English if needed
    product_en = product.model_copy()
    if target_lang != "en":
        try:
            product_en.category = await translate_text(product.category, source_lang=target_lang, target_lang="en")
            if product.sub_category:
                product_en.sub_category = await translate_text(product.sub_category, source_lang=target_lang, target_lang="en")
            product_en.description = await translate_text(product.description, source_lang=target_lang, target_lang="en")
        except BhashiniUnavailableError:
            translation_unavailable = True

    # 3. Run compliance engine for primary & multi-standard QCO results + confidence + explanation audit
    primary_qco_result, qco_results, explanation_audit = check_qco_applicability(product_en)

    # 4. Resolve requirements across matched QCOs
    all_requirements = []
    all_labs = set()
    for qco_res in qco_results:
        reqs, labs = resolve_requirements(qco_res)
        all_requirements.extend(reqs)
        all_labs.update(labs)

    # Low confidence warning flag if primary match confidence < 0.6
    low_confidence = primary_qco_result.confidence < 0.6

    response = ComplianceCheckResponse(
        product=product,
        qco_result=primary_qco_result,
        qco_results=qco_results,
        requirements=all_requirements,
        recommended_labs=list(all_labs),
        unverified_claims=[],
        roadmap_available=primary_qco_result.applies,
        low_confidence_warning=low_confidence,
        explanation=explanation_audit if explain else None,
        response_lang="en",
        translation_unavailable=translation_unavailable
    )

    # 5. Citation verification
    verified_response = verify_response_citations(response)

    # 6. Translate human-readable fields back to target_lang if requested
    if target_lang != "en" and not translation_unavailable:
        try:
            verified_response.qco_result.reasoning = await translate_text(
                verified_response.qco_result.reasoning, source_lang="en", target_lang=target_lang
            )
            for res in verified_response.qco_results:
                res.reasoning = await translate_text(res.reasoning, source_lang="en", target_lang=target_lang)

            for req in verified_response.requirements:
                req.requirement = await translate_text(req.requirement, source_lang="en", target_lang=target_lang)

            verified_response.response_lang = target_lang
        except BhashiniUnavailableError:
            verified_response.translation_unavailable = True
            verified_response.response_lang = "en"

    # Save to response cache if unverified_claims is empty and not explain mode
    if not explain and not verified_response.unverified_claims:
        response_cache.set(product, verified_response.model_dump(mode="json"))

    return verified_response

@router.post("/roadmap", response_model=RoadmapResponse)
async def get_roadmap(request: RoadmapRequest):
    target_lang = request.lang.lang_code
    translation_unavailable = False

    steps = generate_roadmap(request.qco_result)

    if target_lang != "en":
        try:
            for step in steps:
                step.title = await translate_text(step.title, source_lang="en", target_lang=target_lang)
                step.description = await translate_text(step.description, source_lang="en", target_lang=target_lang)
        except BhashiniUnavailableError:
            translation_unavailable = True

    return RoadmapResponse(
        qco_id=request.qco_result.qco_id,
        steps=steps,
        response_lang=target_lang if not translation_unavailable else "en",
        translation_unavailable=translation_unavailable
    )
