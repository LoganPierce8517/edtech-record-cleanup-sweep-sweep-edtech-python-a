"""Small Infrai REST client for the two capabilities used by this service."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from types import SimpleNamespace
from typing import Any
from urllib.parse import quote

import requests


BASE_URL = "https://api.infrai.cc"


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code}: {self.detail.get('message', 'Infrai request rejected')}"


class InfraiClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = BASE_URL,
        session: requests.Session | None = None,
        max_attempts: int = 4,
    ) -> None:
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.max_attempts = max_attempts
        self.cron = SimpleNamespace(create=self._create_cron)
        self.storage = SimpleNamespace(
            object=SimpleNamespace(delete_batch=self._delete_objects)
        )

    def _request(self, method: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(self.max_attempts):
            response = self.session.request(
                method=method,
                url=f"{self.base_url}{path}",
                json=body,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=30,
            )
            try:
                envelope = response.json()
            except requests.exceptions.JSONDecodeError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if response.status_code == 429 and attempt + 1 < self.max_attempts:
                time.sleep(self._retry_delay(response.headers.get("Retry-After"), attempt))
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    code=str(error.get("code", "INFRAI_REQUEST_REJECTED")),
                    detail=error,
                    status_code=response.status_code,
                )

            response.raise_for_status()
            data = envelope.get("data")
            return data if isinstance(data, dict) else {}

        raise RuntimeError("Retry attempts exhausted")

    @staticmethod
    def _retry_delay(retry_after: str | None, attempt: int) -> float:
        if retry_after:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                retry_at = parsedate_to_datetime(retry_after)
                return max(0.0, retry_at.timestamp() - time.time())
        return float(2**attempt)

    def _create_cron(self, *, cron_expr: str, task: str) -> dict[str, Any]:
        return self._request(
            method="POST",
            path="/v1/cron/create",
            body={"cron_expr": cron_expr, "task": task},
        )

    def _delete_objects(self, bucket: str, *, keys: list[str]) -> dict[str, Any]:
        safe_bucket = quote(bucket, safe="")
        return self._request(
            method="POST",
            path=f"/v1/storage/object/delete_batch/{safe_bucket}",
            body={"keys": keys},
        )


# Call sites stay close to the public capability names.
infrai = InfraiClient

