# HaemoPulse transactional email notifications

## Scope and safety defaults

This module adds automatic email notifications to the existing FastAPI + SQLite application. It does not replace the authentication, donor eligibility, blood-request, ML, or React/Vite architecture.

**External sending is disabled by default.** Set `HAEMOPULSE_DISABLE_EXTERNAL_MESSAGES=true` for development and tests. The worker does not start when external messages are disabled. No test in this project should use a real provider account or a real recipient.

Brevo is the initial transactional provider for the emergency notification workflow. It is called only by the backend. There is no automatic SMTP/Gmail fallback for emergency notifications. The existing SMTP-backed email-verification path is a separate legacy workflow and was not rewritten by this change.

## New environment variables

Configure these only in a local/backend environment file that is excluded from source control:

- `BREVO_API_KEY`: Brevo transactional API key.
- `MAIL_FROM`: a Brevo-verified sender email address for emergency notifications.
- `MAIL_FROM_NAME`: display name for new transactional notifications.
- `SMTP_MAIL_FROM`: sender identity for the pre-existing SMTP email-verification workflow. If omitted, the backend falls back to the legacy `MAIL_FROM` value for compatibility; set it explicitly when the SMTP sender differs from the Brevo sender.
- `BREVO_WEBHOOK_BEARER_TOKEN`: long random token configured in the Brevo webhook authorization settings.
- `HAEMOPULSE_DISABLE_EXTERNAL_MESSAGES=true`: safe default; leave true until a separate single-recipient test has been expressly approved.
- `FRONTEND_URL`: existing public/local frontend URL used in application links.

Both root and `backend/.env.example` contain placeholders only. Do not put secrets in `VITE_*` variables, frontend source, tests, or ZIP archives. A verified sender/domain and an eligible Brevo account are required before a later live test. The project code does not create a provider account, verify a domain, configure DNS, or send a live test automatically.

### Provider facts checked 23 October 2026

Brevo's official Free-plan documentation states that the plan has no time limit and includes **300 email sends per day**. Once the daily limit is reached, up to **1,000 additional transactional emails** may be held in a retry queue; email beyond that queue is not delivered. The Free plan includes Brevo branding. This is a quota, not a delivery guarantee. See [Brevo Free-plan limits](https://help.brevo.com/hc/en-us/articles/208580669-FAQs-What-are-the-limits-of-the-Free-plan) and [pricing overview](https://help.brevo.com/hc/en-us/articles/208589409-About-Brevo-s-pricing-plans).

The adapter calls `POST https://api.brevo.com/v3/smtp/email` with an `api-key` header and correlates the response's `messageId`. A registered/verified sender is required; the message ID is used to associate webhook status events. See [Send a transactional email](https://developers.brevo.com/docs/send-a-transactional-email). The webhook endpoint uses the documented bearer-token authentication mode; see [Secure webhook calls](https://developers.brevo.com/docs/secured-webhooks).

## Recipient rules

### Emergency request created

`POST /api/v1/requests` keeps the existing role checks. For an emergency request:

1. A hospital-created request is linked to that authenticated hospital account.
2. An admin-created emergency request must explicitly identify a valid, active `ROLE_HOSPITAL` account.
3. A supplied assigned-admin ID must resolve to an active `ROLE_ADMIN` account; the app never chooses an arbitrary admin.
4. Donors are selected on the backend. Selection uses exact blood-group match and existing eligibility concepts: donor available, required health/age/donation-gap checks, affirmative emergency-notification consent, matching active/verified donor user linked through `donors.user_id`, and matching account/donor email. No email address or donor list supplied by the browser is trusted.
5. The request and donor events are committed in the same SQLite transaction. No eligible linked/verified/opted-in donors means the request still succeeds and reports that no eligible donors were found. Regular/high requests do not fan out automatically.

The automatic request-created notification path does not apply a distance/radius filter because `blood_requests` has no explicit notification-radius field or approved default. No radius is invented or inferred. Existing donor-search/manual alert filtering remains governed by its current server-side behavior.

### Donor accepts

`POST /api/v1/requests/{request_id}/response` still authenticates an email-verified donor and persists the donor response under the existing one-response-per-request/donor rule. For an accepted emergency request, notification events are created for the explicitly linked hospital account and assigned admin account within the same transaction as the acceptance. Missing/invalid recipient relationships create actionable `NEEDS_REVIEW` notification rows rather than rolling back a valid acceptance or substituting another recipient. Rejection remains a persisted response and does not automatically email recipients.

### Manual alert

The existing `POST /api/v1/donors/send-email-alert` API remains available. It now records a compatible manual alert and a deterministic outbox event instead of directly sending synchronously. The legacy `emergency_alerts` table remains in place and its status is synchronized from outbox/provider status updates.

## Database migration

The application invokes the idempotent migration module `backend/migrations/email_notifications_20261023.py` during existing SQLite initialization. The migration is additive:

- Adds nullable `blood_requests.hospital_user_id` and `blood_requests.assigned_admin_user_id` foreign-key columns referencing `users(id)`.
- Creates `notification_outbox` and its due/request/provider indexes.
- Creates `notification_provider_events` for webhook idempotency and correlation.
- Does not backfill historical assignments or drop/recreate application tables.

The application makes a dedicated SQLite online backup before applying this migration to an existing non-empty database, using a `.pre_email_notifications_backup.sqlite3` name and a timestamped variant when needed. Keep backups outside a distributable ZIP and protect them as sensitive runtime data.

### Rollback

The migration is intentionally additive. A code rollback can stop using the new fields/tables without deleting them. Prefer this non-destructive rollback if any production writes occurred after migration.

If a full database restore is necessary, stop all application/worker processes, preserve the current database separately, confirm the selected backup is the correct one, and restore it only during a maintenance window. Restoring a pre-migration backup loses every write since that backup, so do not do so merely to remove new columns. Do not issue `DROP TABLE` or delete notification records ad hoc. Historical hospital/admin assignment values remain NULL unless set through the authorized application workflow.

## Outbox, idempotency, retries, and status

Outbox rows are written in the same transaction as their business event. Stable unique keys prevent duplicate logical events:

- `request-created:<request-id>:<donor-id>` for a donor request alert.
- `acceptance:<request-id>:<donor-id>:<recipient-user-id>` for acceptance recipients.
- `manual-alert:<existing-idempotency-key>` for manual alerts.

A bounded worker processes due rows in batches and claims them under a SQLite `BEGIN IMMEDIATE` transaction with an expiring lease. Sends happen after the claim transaction commits. Retryable provider failures use bounded exponential backoff with jitter and a maximum of six automatic attempts. HTTP 429/quota responses use a longer wait by default, and a provider `Retry-After` hint is treated as a minimum delay (capped at 24 hours). Permanent errors stop retrying. Ambiguous timeouts become `NEEDS_REVIEW` so the app does not blindly re-send an email that may already have been accepted. Stale `PROCESSING` claims also go to review rather than being automatically resent.

`SUBMITTED` means the provider accepted the API submission; it is **not** proof that an email reached an inbox. `DELIVERED` is set only after a valid provider webhook reports delivery. Bounce/block events are recorded as `BOUNCED`. Provider events are deduplicated using stable event identity and out-of-order timestamps are guarded. A `DELIVERED` status is never downgraded by a later bounce or a timestamp-less event; a `BOUNCED` event is only upgraded to `DELIVERED` if the provider event has an explicit strictly newer timestamp.

Brevo webhooks use the documented bearer authorization mode configured for the webhook. Endpoint: `POST /api/v1/webhooks/brevo/transactional`. Protect the token as a secret. Events with unknown provider message IDs are stored safely as unmatched events; webhook payloads and recipient details are not written to logs.

## Relevant API surface

- `POST /api/v1/requests`: create request; emergency requests enqueue donor notifications.
- `POST /api/v1/requests/{request_id}/response`: donor accept/reject; accepted emergency request enqueues authorized recipient events.
- `GET /api/v1/notification-assignees`: return allowed account choices for assignment UI.
- `PUT /api/v1/requests/{request_id}/notification-assignments`: admin-only update of explicit recipient relationships; validates role and account activity.
- `GET /api/v1/notifications/requests/{request_id}`: authorized request notification state, without recipient email addresses.
- `POST /api/v1/notifications/{notification_id}/retry`: authorized retry for eligible exhausted, retryable events only.
- `POST /api/v1/webhooks/brevo/transactional`: authenticated provider-status webhook.
- `POST /api/v1/donors/send-email-alert`: existing manual donor alert, now queued using the shared provider/outbox route.

## Local setup and testing

1. Create/activate the backend virtual environment and install existing dependencies from `backend/requirements.txt`.
2. Keep external delivery disabled and configure no real provider keys for automated tests.
3. From `Major-project/backend`, run `python3 -m pytest -q`.
4. Run frontend dependency installation from `Major-project/frontend` and `npm run build`. A successful frontend build requires installed npm packages; it cannot run when package installation is blocked.
5. Use the existing application startup command to start FastAPI. With external sending disabled the worker remains stopped and all notifications remain queued. Only configure the live provider and change the flag after separate explicit authorization for a single-recipient test.

## Operational limitations

- The SQLite worker model is intended for this project's single-instance deployment. Use a database/queue architecture review before running multiple independent app instances across machines.
- The provider and database cannot offer exactly-once external email delivery. Deterministic event keys, leases, provider message IDs, status webhooks, and ambiguous-timeout review reduce duplicate risk but do not eliminate all provider-side uncertainty.
- Free provider allowances may change. Re-check current Brevo account terms, quotas, sender requirements, and event behavior before any live deployment.
