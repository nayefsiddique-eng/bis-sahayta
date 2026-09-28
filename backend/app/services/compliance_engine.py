import json
from pathlib import Path
from datetime import date, datetime
from typing import Any
from app.schemas.product import ProductInput
from app.schemas.compliance import QCOResult, SourceCitation, ComplianceRequirement

DATA_FILE = Path(__file__).parent.parent / "data" / "mock_qco.json"

def load_qco_data() -> list[dict]:
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def evaluate_qco_matches(product: ProductInput, today_date: date) -> tuple[list[QCOResult], dict[str, Any]]:
    """
    Evaluates product against ALL QCO entries in mock_qco.json.
    Returns list of matching QCOResult objects sorted by confidence,
    along with an explanation audit dict.
    """
    qco_list = load_qco_data()
    prod_cat = product.category.lower().strip()
    prod_subcat = (product.sub_category or "").lower().strip()
    prod_desc = product.description.lower().strip()
    prod_materials = [m.lower().strip() for m in (product.materials or [])]

    results: list[QCOResult] = []
    candidates_evaluated = []
    rejected_candidates = []

    for qco in qco_list:
        qco_cat = qco.get("category", "").lower()
        qco_subcat = qco.get("sub_category", "").lower()
        qco_id = qco["qco_id"]

        confidence = 0.0
        match_reason = ""

        # Exact category match
        if prod_cat == qco_cat:
            confidence = 0.95
            match_reason = f"Exact match on product category '{product.category}'."
        # Sub-category exact match
        elif prod_subcat and prod_subcat == qco_subcat:
            confidence = 0.85
            match_reason = f"Sub-category match on '{product.sub_category}'."
        # Category partial/substring match
        elif qco_cat in prod_cat or prod_cat in qco_cat:
            confidence = 0.75
            match_reason = f"Partial category match between '{product.category}' and '{qco.get('category')}'."
        # Material or description mention match
        elif qco_cat in prod_desc or any(qco_cat in m for m in prod_materials) or (qco_subcat and qco_subcat in prod_desc):
            confidence = 0.55  # Below 0.6 threshold for fuzzy match test
            match_reason = f"Secondary match on material/description keyword for '{qco.get('category')}'."

        candidates_evaluated.append({
            "qco_id": qco_id,
            "category": qco.get("category"),
            "evaluated_confidence": confidence,
            "match_reason": match_reason or "No criteria matched"
        })

        if confidence > 0.0:
            citation_data = qco.get("citation", {})
            citation = SourceCitation(
                document_id=citation_data.get("document_id", qco_id),
                clause=citation_data.get("clause"),
                title=citation_data.get("title", qco["title"]),
                url=citation_data.get("url")
            )

            eff_date_str = qco.get("effective_date", "2000-01-01")
            effective_date = datetime.strptime(eff_date_str, "%Y-%m-%d").date()

            reason_parts = [match_reason]
            if today_date < effective_date:
                reason_parts.append(
                    f"QCO '{qco['title']}' applies but is not yet mandatory. Effective date: {eff_date_str}."
                )
            else:
                reason_parts.append(
                    f"QCO '{qco['title']}' applies and is mandatory as of {eff_date_str}."
                )

            exemption_status = "none"
            if product.manufacturer_scale == "msme" and qco.get("msme_exemption"):
                exemption_status = "msme"
                reason_parts.append(f"Exemption Status: MSME exemption applies ({qco.get('exemption_notes', '')}).")
            elif product.is_imported and qco.get("import_exemption"):
                exemption_status = "import"
                reason_parts.append(f"Exemption Status: Import exemption applies ({qco.get('exemption_notes', '')}).")
            else:
                reason_parts.append(f"Exemption Status: No exemption applies ({qco.get('exemption_notes', '')}).")

            qco_res = QCOResult(
                qco_id=qco_id,
                standard_id=qco["standard_id"],
                applies=True,
                reasoning=" ".join(reason_parts),
                effective_date=effective_date,
                exemption_status=exemption_status,
                source=citation,
                confidence=confidence
            )
            results.append(qco_res)
        else:
            rejected_candidates.append({
                "qco_id": qco_id,
                "reason": f"Category '{product.category}' and description did not match QCO category '{qco.get('category')}'."
            })

    # Sort results by confidence descending
    results.sort(key=lambda r: r.confidence, reverse=True)

    # Fallback if no QCO matches at all
    if not results:
        default_citation = SourceCitation(document_id="N/A", clause=None, title="BIS QCO Database", url=None)
        fallback_res = QCOResult(
            qco_id="N/A",
            standard_id="N/A",
            applies=False,
            reasoning=f"No Quality Control Order (QCO) currently applies to product category '{product.category}'.",
            effective_date=today_date,
            exemption_status="none",
            source=default_citation,
            confidence=0.0
        )
        results = [fallback_res]

    explanation = {
        "candidates_evaluated": candidates_evaluated,
        "rejected_candidates": rejected_candidates,
        "matched_qcos_count": len([r for r in results if r.applies]),
        "primary_match_confidence": results[0].confidence
    }

    return results, explanation

def check_qco_applicability(product: ProductInput, today_date: date | None = None) -> tuple[QCOResult, list[QCOResult], dict[str, Any]]:
    if today_date is None:
        today_date = date.today()

    qco_results, explanation = evaluate_qco_matches(product, today_date)
    primary_result = qco_results[0]
    return primary_result, qco_results, explanation

def resolve_requirements(qco_result: QCOResult) -> tuple[list[ComplianceRequirement], list[str]]:
    if not qco_result.applies or qco_result.qco_id == "N/A":
        return [], []

    qco_list = load_qco_data()
    qco_entry = next((q for q in qco_list if q["qco_id"] == qco_result.qco_id), None)
    if not qco_entry:
        return [], []

    citation = qco_result.source
    requirements: list[ComplianceRequirement] = []

    for test in qco_entry.get("required_tests", []):
        req_title = test["name"] if isinstance(test, dict) else str(test)
        clause = test.get("standard_clause") if isinstance(test, dict) else citation.clause
        req_citation = SourceCitation(
            document_id=citation.document_id,
            clause=clause,
            title=citation.title,
            url=citation.url
        )
        requirements.append(
            ComplianceRequirement(
                requirement=req_title,
                test_or_document="test",
                mandatory=True,
                source=req_citation
            )
        )

    for doc in qco_entry.get("required_documents", []):
        requirements.append(
            ComplianceRequirement(
                requirement=doc,
                test_or_document="document",
                mandatory=True,
                source=citation
            )
        )

    labs = qco_entry.get("recommended_labs", [])
    return requirements, labs
