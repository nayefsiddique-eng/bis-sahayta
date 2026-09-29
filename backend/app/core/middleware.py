import uuid
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import settings
from app.core.exceptions import APIException
from app.core.rate_limiter import rate_limiter

logger = logging.getLogger("bis_backend")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [req_id=%(request_id)s] %(message)s"
)

# Custom Filter to inject request_id into log records
class RequestIDLogFilter(logging.Filter):
    def __init__(self, request_id: str = "N/A"):
        super().__init__()
        self.request_id = request_id

    def filter(self, record):
        if not hasattr(record, "request_id"):
            record.request_id = self.request_id
        return True

class RequestTracingAndAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # 1. Correlation ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        log_filter = RequestIDLogFilter(request_id)
        logger.addFilter(log_filter)

        logger.info(f"Incoming Request: {request.method} {request.url.path}")

        # Bypass auth & rate-limit for health, readiness, and OpenAPI docs
        path = request.url.path
        is_public = path in ["/health", "/api/health", "/ready", "/docs", "/openapi.json", "/redoc"]

        try:
            # 2. API Key Auth (Step 10)
            if not is_public:
                api_key = request.headers.get("X-API-Key")
                if not api_key or api_key != settings.API_KEY:
                    raise APIException(
                        status_code=401,
                        error_code="UNAUTHORIZED",
                        message="Invalid or missing X-API-Key header."
                    )

            # 3. Rate Limiting (Step 4)
            if not is_public and path in ["/compliance/check", "/translate/text", "/voice/stream"]:
                client_ip = request.client.host if request.client else "unknown"
                rate_limit_key = f"{request.headers.get('X-API-Key', client_ip)}:{path}"
                rate_limiter.check_rate_limit(rate_limit_key)

            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            logger.info(f"Request Completed: {request.method} {path} -> Status {response.status_code}")
            return response

        except APIException as exc:
            logger.warning(f"API Exception ({exc.error_code}): {exc.message}")
            from app.core.exceptions import api_exception_handler
            resp = await api_exception_handler(request, exc)
            resp.headers["X-Request-ID"] = request_id
            return resp
        finally:
            logger.removeFilter(log_filter)
