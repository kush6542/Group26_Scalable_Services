import uuid
import logging
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("restaurant_service")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [corr_id=%(correlation_id)s] %(name)s: %(message)s'
)

class CorrelationIdFilter(logging.Filter):
    def __init__(self, correlation_id="N/A"):
        super().__init__()
        self.correlation_id = correlation_id

    def filter(self, record):
        if not hasattr(record, "correlation_id"):
            record.correlation_id = self.correlation_id
        return True

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        corr_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        request.state.correlation_id = corr_id

        # Update root logger filter dynamically
        corr_filter = CorrelationIdFilter(corr_id)
        logger.addFilter(corr_filter)

        start_time = time.time()
        logger.info(f"Incoming {request.method} {request.url.path}", extra={"correlation_id": corr_id})

        response: Response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000
        response.headers["X-Correlation-ID"] = corr_id

        logger.info(
            f"Completed {request.method} {request.url.path} with status {response.status_code} in {duration_ms:.2f}ms",
            extra={"correlation_id": corr_id}
        )
        logger.removeFilter(corr_filter)
        return response
