from datetime import date
from app.schemas.product import ProductInput
from app.schemas.compliance import (
    ComplianceCheckResponse,
    QCOResult,
    ComplianceRequirement,
    SourceCitation,
)
from app.services.citation_verifier import verify_response_citations

def test_valid_citations_verification():
    valid_citation = SourceCitation(
        document_id="QCO-TOYS-2020",
        clause="Clause 3.1",
        title="Toys (Quality Control) Order, 2020",
        url="https://bis.gov.in/qco/toys"
    )

    product = ProductInput(category="Toys", description="Plastic toy")
    qco_res = QCOResult(
        qco_id="QCO-TOYS-2020",
        standard_id="IS 9873 (Part 1):2019",
        applies=True,
        reasoning="Toys QCO applies",
        effective_date=date(2021, 1, 1),
        exemption_status="none",
        source=valid_citation
    )
    reqs = [
        ComplianceRequirement(
            requirement="Physical Safety Test",
            test_or_document="test",
            mandatory=True,
            source=valid_citation
        )
    ]

    response = ComplianceCheckResponse(
        product=product,
        qco_result=qco_res,
        requirements=reqs,
        recommended_labs=["NTH Kolkata"],
        unverified_claims=[]
    )

    verified_resp = verify_response_citations(response)
    assert len(verified_resp.unverified_claims) == 0

def test_invalid_and_broken_citations_verification():
    invalid_citation = SourceCitation(
        document_id="QCO-FAKE-9999",
        clause="Clause 99",
        title="Fake QCO Order",
        url="http://fake-link.com"
    )

    product = ProductInput(category="Toys", description="Plastic toy")
    qco_res = QCOResult(
        qco_id="QCO-TOYS-2020",
        standard_id="IS 9873 (Part 1):2019",
        applies=True,
        reasoning="Toys QCO applies",
        effective_date=date(2021, 1, 1),
        exemption_status="none",
        source=invalid_citation
    )
    reqs = [
        ComplianceRequirement(
            requirement="Fake Test Requirement",
            test_or_document="test",
            mandatory=True,
            source=invalid_citation
        )
    ]

    response = ComplianceCheckResponse(
        product=product,
        qco_result=qco_res,
        requirements=reqs,
        recommended_labs=[],
        unverified_claims=[]
    )

    verified_resp = verify_response_citations(response)
    assert len(verified_resp.unverified_claims) == 2
    assert any("QCO-FAKE-9999" in msg for msg in verified_resp.unverified_claims)
