from typing import Any
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.schemas.error import ErrorResponse

class APIException(Exception):
    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        detail: Any | None = None,
        headers: dict[str, str] | None = None
    ):
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.detail = detail
        self.headers = headers
        super().__init__(message)

async def api_exception_handler(request: Request, exc: APIException) -> JSONResponse:
    content = ErrorResponse(
        error_code=exc.error_code,
        message=exc.message,
        detail=exc.detail
    ).model_dump()
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers=exc.headers
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    content = ErrorResponse(
        error_code="INVALID_PRODUCT_INPUT",
        message="Invalid request body or parameters.",
        detail=exc.errors()
    ).model_dump()
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=content
    )

async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    import logging
    logging.getLogger("bis_backend").error(
        f"Unhandled exception on {request.method} {request.url.path}: {exc}",
        exc_info=True,
    )
    content = ErrorResponse(
        error_code="INTERNAL_SERVER_ERROR",
        message="An unexpected server error occurred. Please try again.",
        detail=None  # Never expose raw exception text to users
    ).model_dump()
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=content
    )
