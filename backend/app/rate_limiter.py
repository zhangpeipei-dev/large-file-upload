import asyncio
import time
from dataclasses import dataclass
from threading import Lock


@dataclass
class Bucket:
    tokens: float
    updated_at: float


class PerUserRateLimiter:
    def __init__(self):
        self._buckets: dict[str, Bucket] = {}
        self._lock = Lock()

    async def consume(self, user_id: str, amount: int, rate_bytes_sec: int):
        if rate_bytes_sec <= 0 or amount <= 0:
            return

        capacity = float(rate_bytes_sec)
        remaining = float(amount)
        while remaining > 0:
            step = min(remaining, capacity)
            await self._consume_once(user_id, step, rate_bytes_sec, capacity)
            remaining -= step

    async def _consume_once(self, user_id: str, amount: float, rate_bytes_sec: int, capacity: float):
        while True:
            now = time.monotonic()
            wait_sec = 0.0
            with self._lock:
                bucket = self._buckets.get(user_id)
                if bucket is None:
                    bucket = Bucket(tokens=capacity, updated_at=now)
                    self._buckets[user_id] = bucket

                elapsed = max(now - bucket.updated_at, 0.0)
                bucket.tokens = min(capacity, bucket.tokens + elapsed * rate_bytes_sec)
                bucket.updated_at = now

                if bucket.tokens >= amount:
                    bucket.tokens -= amount
                    return

                missing = amount - bucket.tokens
                wait_sec = missing / rate_bytes_sec

            await asyncio.sleep(wait_sec)


rate_limiter = PerUserRateLimiter()
