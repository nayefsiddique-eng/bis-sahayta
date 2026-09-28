import time
from typing import Dict, Tuple
from app.core.exceptions import APIException

class RateLimiter:
    def __init__(self, requests_per_window: int = 10, window_seconds: int = 60):
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        # key -> (count, reset_time)
        self._store: Dict[str, Tuple[int, float]] = {}

    def check_rate_limit(self, identifier: str):
        now = time.time()
        if identifier in self._store:
            count, reset_time = self._store[identifier]
            if now < reset_time:
                if count >= self.requests_per_window:
                    retry_after = int(reset_time - now) + 1
                    raise APIException(
                        status_code=429,
                        error_code="RATE_LIMITED",
                        message="Rate limit exceeded. Please try again later.",
                        headers={"Retry-After": str(retry_after)}
                    )
                self._store[identifier] = (count + 1, reset_time)
            else:
                self._store[identifier] = (1, now + self.window_seconds)
        else:
            self._store[identifier] = (1, now + self.window_seconds)

rate_limiter = RateLimiter(requests_per_window=10, window_seconds=60)
