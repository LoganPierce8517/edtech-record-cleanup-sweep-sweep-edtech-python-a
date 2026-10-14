from datetime import datetime, timezone

from edtech_cleanup import CleanupSweepRequest, CourseDelivery, DeliveryState, select_stale_records


def test_sweep_waits_for_deadline_retention_and_educator_reporting() -> None:
    request = CleanupSweepRequest(
        as_of=datetime(2026, 9, 24, tzinfo=timezone.utc),
        retention_days=30,
        records=[
            CourseDelivery(
                delivery_id="algebra-spring",
                learner_id="learner-17",
                deadline=datetime(2026, 7, 1, tzinfo=timezone.utc),
                state=DeliveryState.COMPLETED,
                educator_reported_at=datetime(2026, 7, 3, tzinfo=timezone.utc),
                storage_key="deliveries/algebra-spring.json",
            ),
            CourseDelivery(
                delivery_id="biology-summer",
                learner_id="learner-28",
                deadline=datetime(2026, 9, 1, tzinfo=timezone.utc),
                state=DeliveryState.COMPLETED,
                educator_reported_at=datetime(2026, 9, 2, tzinfo=timezone.utc),
                storage_key="deliveries/biology-summer.json",
            ),
            CourseDelivery(
                delivery_id="history-review",
                learner_id="learner-39",
                deadline=datetime(2026, 7, 1, tzinfo=timezone.utc),
                state=DeliveryState.WITHDRAWN,
                educator_reported_at=None,
                storage_key="deliveries/history-review.json",
            ),
        ],
    )

    stale, retained = select_stale_records(request)

    assert [record.delivery_id for record in stale] == ["algebra-spring"]
    assert [record.delivery_id for record in retained] == [
        "biology-summer",
        "history-review",
    ]

