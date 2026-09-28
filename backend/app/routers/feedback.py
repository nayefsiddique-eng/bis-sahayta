import json
import uuid
import datetime
from pathlib import Path
from fastapi import APIRouter
from app.schemas.feedback import FeedbackRequest, FeedbackResponse

router = APIRouter(tags=["feedback"])

LOG_FILE = Path(__file__).parent.parent / "data" / "feedback_log.json"

@router.post("/feedback", response_model=FeedbackResponse)
def submit_feedback(payload: FeedbackRequest):
    feedback_id = f"fb-{uuid.uuid4().hex[:8]}"

    entry = {
        "feedback_id": feedback_id,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "request_id": payload.request_id,
        "verdict_correct": payload.verdict_correct,
        "comment": payload.comment
    }

    logs = []
    if LOG_FILE.exists():
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                logs = json.load(f)
        except Exception:
            logs = []

    logs.append(entry)

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2)

    return FeedbackResponse(
        status="success",
        feedback_id=feedback_id,
        message="Feedback logged successfully. Thank you for helping improve the BIS compliance decision engine."
    )
