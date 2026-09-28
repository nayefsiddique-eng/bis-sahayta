from enum import Enum
import re

class Intent(str, Enum):
    GENERAL_QA = "general_qa"
    COMPLIANCE_CHECK = "compliance_check"
    CERTIFICATION_PROCESS = "certification_process"
    HYBRID = "hybrid"

COMPLIANCE_PATTERNS = [
    r"\bapplies?\b", r"\bmandatory\b", r"\bqco\b", r"\bis\s+\d{4,5}\b",
    r"\bexemption\b", r"\bexempt\b", r"\bmsme\b", r"\bimported?\b",
    r"\bis bis required\b", r"\bcompulsory\b", r"\bcompliance\b"
]

PROCESS_PATTERNS = [
    r"\bprocess\b", r"\bsteps?\b", r"\broadmap\b", r"\bapplications?\b",
    r"\blicense\b", r"\bhow to get\b", r"\bprocedure\b", r"\baudit\b",
    r"\btesting process\b", r"\bfee\b", r"\bcost\b", r"\bmanakonline\b",
    r"\brenewal\b", r"\bsample submission\b", r"\blab testing\b"
]

QA_PATTERNS = [
    r"\bwhat is bis\b", r"\bwho is\b", r"\bdefinition\b", r"\boverview\b",
    r"\babout bis\b", r"\bfaq\b", r"\bcontact\b", r"\baddress\b",
    r"\bhistory\b", r"\bgeneral information\b"
]

def classify_intent(query: str) -> Intent:
    """
    Classifies a user query string into one of the four Intent categories:
    general_qa, compliance_check, certification_process, or hybrid.
    Designed as a swappable interface so an LLM classifier can replace it seamlessly.
    """
    query_lower = query.lower()

    has_compliance = any(re.search(pat, query_lower) for pat in COMPLIANCE_PATTERNS)
    has_process = any(re.search(pat, query_lower) for pat in PROCESS_PATTERNS)
    has_qa = any(re.search(pat, query_lower) for pat in QA_PATTERNS)

    categories_triggered = sum([has_compliance, has_process, has_qa])

    if categories_triggered >= 2:
        return Intent.HYBRID
    elif has_compliance:
        return Intent.COMPLIANCE_CHECK
    elif has_process:
        return Intent.CERTIFICATION_PROCESS
    elif has_qa:
        return Intent.GENERAL_QA
    else:
        return Intent.GENERAL_QA
