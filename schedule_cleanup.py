"""Register the hosted schedule that calls the cleanup service."""

import os

from infrai import InfraiClient


def register_cleanup_schedule() -> str:
    client = InfraiClient()
    job = client.cron.create(
        cron_expr="0 2 * * *",
        task=os.environ["CLEANUP_WEBHOOK_URL"],
    )
    return str(job["job_id"])


if __name__ == "__main__":
    print(f"Scheduled cleanup job: {register_cleanup_schedule()}")

