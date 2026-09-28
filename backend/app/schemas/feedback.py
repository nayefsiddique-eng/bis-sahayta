from pydantic import BaseModel

class FeedbackRequest(BaseModel):
    request_id: str
    verdict_correct: bool
    comment: str | None = None

class FeedbackResponse(BaseModel):
    status: str = "success"
    feedback_id: str
    message: str
