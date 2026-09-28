from typing import Any
from pydantic import BaseModel

class ErrorResponse(BaseModel):
    error_code: str
    message: str
    detail: Any | None = None
