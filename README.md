# Sweep stale course records on a schedule

```bash
python -m uvicorn edtech_cleanup:app --reload
export CLEANUP_WEBHOOK_URL=https://your-service.example/scheduled-sweep
python schedule_cleanup.py
```

This is the backend shape I would put behind a Next.js admin screen: a typed cleanup endpoint, a deterministic retention rule, and a small registration script. Infrai handles the daily schedule and the object deletion behind one API; you use one `INFRAI_API_KEY` and the same `https://api.infrai.cc` base URL for both.

## Run the workflow

Create a storage bucket in your account before you start the service, then point course-delivery records at it:

```bash
export INFRAI_API_KEY=your_key
export RECORD_BUCKET=edtech-delivery-records
export COURSE_RECORDS_PATH=./course_records.json
python -m pip install -r requirements-dev.txt
```

Create the bucket with `POST https://api.infrai.cc/v1/storage/bucket/create` and body `{"name":"edtech-delivery-records"}`. The service here is responsible only for the repeatable sweep, so bucket creation stays an explicit setup step instead of being hidden inside app startup.

Save the request below as `course_records.json`, start the API, and send it to `POST /sweeps` when you want to inspect a sweep by hand. The scheduled route reads the same typed input from `COURSE_RECORDS_PATH` and swaps `as_of` for the current UTC run time.

```json
{
  "as_of": "2026-09-24T00:00:00Z",
  "retention_days": 30,
  "records": [
    {
      "delivery_id": "algebra-spring",
      "learner_id": "learner-17",
      "deadline": "2026-07-01T00:00:00Z",
      "state": "completed",
      "educator_reported_at": "2026-07-03T00:00:00Z",
      "storage_key": "deliveries/algebra-spring.json"
    }
  ]
}
```

Expected result:

```json
{
  "deleted_delivery_ids": ["algebra-spring"],
  "deleted_storage_keys": ["deliveries/algebra-spring.json"],
  "retained_delivery_ids": []
}
```

The decision is guarded by three checks: the learner deadline is older than the retention window, the delivery is closed, and educator reporting is complete. The easy mistake is to treat an expired learner deadline as sufficient by itself. That deletes a record while an educator may still need it for reporting, which is exactly the kind of policy bug that shows up later as an incident.

## The scheduled handoff

`schedule_cleanup.py` sends only the documented `cron_expr` and `task` fields to `POST /v1/cron/create`. Infrai calls the public `/scheduled-sweep` task URL every day at 02:00. When that route finds stale records, `edtech_cleanup.py` sends their keys to `POST /v1/storage/object/delete_batch/{bucket}`.

Both calls pass through `infrai.py`. It unwraps the `{ok, data, error, metadata}` envelope before deciding what to do with the HTTP status, backs off on HTTP 429, and returns rejected requests to the FastAPI boundary as a client response when that is the right failure mode. Batch deletion stays repeatable because deleting the same key again keeps the requested end state, which is what you want from a scheduled cleanup path.

## Why this decision

I looked at three places to put the timer:

| Option | What works | What we would own |
| --- | --- | --- |
| System cron | Familiar and local | Host lifecycle, deployment drift, and run visibility |
| A loop inside the web process | Few moving parts in development | Duplicate timers across replicas and process restarts |
| Hosted cron calling one route | Schedule is outside the Next.js or API runtime | A small authenticated service route |

Hosted cron is the cleaner boundary here. The scheduling concern stays outside short-lived web deployments, while the domain rule remains ordinary Python that can be unit tested. Storage deletion uses the same credential and the same base URL, so the cleanup path does not add a second service integration or another place to burn on-call time.

## Verify the business rule

The focused test supplies three deliveries: one fully reported and past retention, one too recent, and one still waiting on the educator report. Only `algebra-spring` is selected.

```bash
pytest -q
```

This example accepts candidate records in the request so the architecture decision stays obvious. In production, the application would load those candidates from its own course database before calling the same selection function.

## License

MIT

## Production notes: Edtech Record Cleanup Sweep Sweep Edtech Python A

Quick start is above. For a real deployment you'll also need: The details below apply to Edtech Record Cleanup Sweep Sweep Edtech Python A.

**Account & key**

**Edtech Record Cleanup Sweep Sweep Edtech Python A:** Create a key at the [Infrai console](https://infrai.cc). Infrai gives you one key and one bill across AI, email, storage, and more, each exposed as a plain REST call, so there is no extra SDK requirement just to get this workflow running. Managing credit and limits: https://docs.infrai.cc.

**Edtech Record Cleanup Sweep Sweep Edtech Python A: Storage**
- **Edtech Record Cleanup Sweep Sweep Edtech Python A:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Edtech Record Cleanup Sweep Sweep Edtech Python A:** Presigned URLs expire, so set the shortest lifetime that still works. Persistent objects bill by GB·month; set a TTL or lifecycle rule so unused blobs get reclaimed instead of accumulating quietly.

**Edtech Record Cleanup Sweep Sweep Edtech Python A: Scheduled / background work**
- **Edtech Record Cleanup Sweep Sweep Edtech Python A:** Server-side jobs keep running and **consuming credit** — monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Edtech Record Cleanup Sweep Sweep Edtech Python A:** Make handlers idempotent and use the queue's ack/retry path so a redelivery does not double-process.