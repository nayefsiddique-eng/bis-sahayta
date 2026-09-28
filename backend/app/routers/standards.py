"""
Standards router.
GET /standards              — list/search all QCO entries
GET /standards/{id}         — get specific standard details
GET /standards/{id}/history — amendment history
"""
from fastapi import APIRouter, Query
from app.services.compliance_engine import load_qco_data
from app.core.exceptions import APIException

router = APIRouter(prefix="/standards", tags=["standards"])


@router.get("")
def list_standards(
    search: str = Query("", description="Search term to filter by title, category, or QCO ID"),
    limit: int = Query(50, ge=1, le=200),
):
    """List all QCO standards, optionally filtered by a search term."""
    qco_list = load_qco_data()
    if search:
        term = search.lower()
        qco_list = [
            q for q in qco_list
            if (
                term in q.get("title", "").lower()
                or term in q.get("qco_id", "").lower()
                or term in q.get("standard_id", "").lower()
                or term in " ".join(q.get("categories", [])).lower()
            )
        ]
    results = [
        {
            "qco_id": q.get("qco_id"),
            "standard_id": q.get("standard_id"),
            "title": q.get("title"),
            "categories": q.get("categories", []),
            "scope": q.get("scope", ""),
        }
        for q in qco_list[:limit]
    ]
    return {"total": len(results), "standards": results}


@router.get("/{standard_id}")
def get_standard(standard_id: str):
    """Get full details for a specific standard by QCO ID or standard ID."""
    qco_list = load_qco_data()
    target = standard_id.lower().strip()
    matched = next(
        (
            q for q in qco_list
            if q.get("standard_id", "").lower().strip() == target
            or q.get("qco_id", "").lower().strip() == target
        ),
        None,
    )
    if not matched:
        raise APIException(
            status_code=404,
            error_code="STANDARD_NOT_FOUND",
            message=f"Standard '{standard_id}' not found in QCO database.",
        )
    return matched


@router.get("/{standard_id}/history")
def get_standard_history(standard_id: str):
    """Get amendment history for a standard."""
    qco_list = load_qco_data()
    target = standard_id.lower().strip()
    matched = next(
        (
            q for q in qco_list
            if q.get("standard_id", "").lower().strip() == target
            or q.get("qco_id", "").lower().strip() == target
        ),
        None,
    )
    if not matched:
        raise APIException(
            status_code=404,
            error_code="NO_MATCHING_QCO",
            message=f"Standard ID or QCO ID '{standard_id}' not found in QCO database.",
        )
    history = matched.get("amendment_history", [])
    return {
        "standard_id": matched["standard_id"],
        "qco_id": matched["qco_id"],
        "title": matched["title"],
        "history": history,
    }
