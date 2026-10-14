"""HTTP entry point for deciding and deleting stale course-delivery records."""

from __future__ import annotations

import os
import json
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from infrai import InfraiClient, InfraiError


class DeliveryState(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    WITHDRAWN = "withdrawn"


class CourseDelivery(BaseModel):
    delivery_id: str
    learner_id: str
    deadline: datetime
    state: DeliveryState
    educator_reported_at: datetime | None = None
    storage_key: str


class CleanupSweepRequest(BaseModel):
    as_of: datetime
    retention_days: Annotated[int, Field(ge=0, le=3650)] = 30
    records: list[CourseDelivery]


class CleanupSweepResult(BaseModel):
    deleted_delivery_ids: list[str]
    deleted_storage_keys: list[str]
    retained_delivery_ids: list[str]


def select_stale_records(request: CleanupSweepRequest) -> tuple[list[CourseDelivery], list[CourseDelivery]]:
    """Delete only closed deliveries whose deadline aged out after educator reporting."""
    cutoff = request.as_of - timedelta(days=request.retention_days)
    stale: list[CourseDelivery] = []
    retained: list[CourseDelivery] = []

    for record in request.records:
        report_complete = (
            record.educator_reported_at is not None
            and record.educator_reported_at <= request.as_of
        )
        deadline_expired = record.deadline <= cutoff
        delivery_closed = record.state in {DeliveryState.COMPLETED, DeliveryState.WITHDRAWN}
        (stale if report_complete and deadline_expired and delivery_closed else retained).append(record)

    return stale, retained


def get_infrai() -> InfraiClient:
    return InfraiClient()


app = FastAPI(title="Edtech cleanup sweep")


def delete_stale_records(request: CleanupSweepRequest, client: InfraiClient) -> CleanupSweepResult:
    stale, retained = select_stale_records(request)
    keys = [record.storage_key for record in stale]

    if keys:
        try:
            # Batch deletion is safe to repeat: deleting an already absent key keeps it absent.
            client.storage.object.delete_batch(os.environ["RECORD_BUCKET"], keys=keys)
        except InfraiError as error:
            status = error.status_code if 400 <= error.status_code < 500 else 502
            raise HTTPException(status_code=status, detail=error.detail) from error

    return CleanupSweepResult(
        deleted_delivery_ids=[record.delivery_id for record in stale],
        deleted_storage_keys=keys,
        retained_delivery_ids=[record.delivery_id for record in retained],
    )


@app.post("/sweeps", response_model=CleanupSweepResult)
def run_cleanup_sweep(
    request: CleanupSweepRequest,
    client: Annotated[InfraiClient, Depends(get_infrai)],
) -> CleanupSweepResult:
    return delete_stale_records(request, client)


@app.post("/scheduled-sweep", response_model=CleanupSweepResult)
def run_scheduled_sweep(
    client: Annotated[InfraiClient, Depends(get_infrai)],
) -> CleanupSweepResult:
    with open(os.environ["COURSE_RECORDS_PATH"], encoding="utf-8") as records_file:
        saved_request = json.load(records_file)
    saved_request["as_of"] = datetime.now(timezone.utc).isoformat()
    return delete_stale_records(CleanupSweepRequest.model_validate(saved_request), client)
