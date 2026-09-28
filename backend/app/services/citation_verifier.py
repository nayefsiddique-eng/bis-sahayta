import json
from pathlib import Path
from app.schemas.compliance import ComplianceCheckResponse

DATA_FILE = Path(__file__).parent.parent / "data" / "mock_qco.json"

def get_valid_document_ids() -> set[str]:
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        qco_data = json.load(f)

    doc_ids = set()
    for entry in qco_data:
        if "qco_id" in entry:
            doc_ids.add(entry["qco_id"])
        citation = entry.get("citation", {})
        if "document_id" in citation:
            doc_ids.add(citation["document_id"])
    return doc_ids

def verify_response_citations(response: ComplianceCheckResponse) -> ComplianceCheckResponse:
    """
    Walks every field in ComplianceCheckResponse carrying a SourceCitation.
    Confirms non-null and resolution to a valid document_id in mock_qco.json.
    Unverified claims are added to response.unverified_claims.
    """
    valid_ids = get_valid_document_ids()
    unverified: list[str] = list(response.unverified_claims or [])

    # Verify QCOResult citation
    qco_src = response.qco_result.source
    if response.qco_result.applies and response.qco_result.qco_id != "N/A":
        if not qco_src or not qco_src.document_id or qco_src.document_id not in valid_ids:
            unverified.append(
                f"Unverified citation in QCO Result: document_id '{qco_src.document_id if qco_src else None}' not found in QCO registry."
            )

    # Verify requirements citations
    for idx, req in enumerate(response.requirements):
        req_src = req.source
        if not req_src or not req_src.document_id or req_src.document_id not in valid_ids:
            unverified.append(
                f"Unverified citation in requirement '{req.requirement}': document_id '{req_src.document_id if req_src else None}' not found in QCO registry."
            )

    response.unverified_claims = unverified
    return response
