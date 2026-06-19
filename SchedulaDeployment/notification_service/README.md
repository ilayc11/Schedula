# Schedula Notification Service

This service handles sending notifications via Apprise (Telegram and Email) and Telegram webhook processing for Schedula.

It owns notification channel resolution and linking persistence directly in PostgreSQL (`user_notifications` + `users`).
Backend only decides when/who to notify and publishes recipient-based events.

## Telegram Linking and Webhook Verification

This guide covers end-to-end verification where Telegram webhook URL remains on Backend and Backend forwards webhook requests to notification_service.

### Supported Telegram Commands

1. `/start <token>`: links a Telegram chat to a Schedula user. The token can also be passed as a Telegram deep-link parameter (`start=` / `startapp=`); both are recognized.
2. `/link <user_name> <user_id>`: fallback linking path when `/start` is pressed without a token. `user_id` must be exactly 9 digits; otherwise the message is rejected.

Notes:

- A `@botname` suffix on commands (for example `/start@Schedula_BotBot <token>`) is stripped before parsing.
- Unrecognized commands are accepted and silently return `200 OK` (no user-visible reply).

Global reset is now dev-only via backend route:

1. `POST /dev/user-notifications/clear-telegram-data`
2. After reset, users can relink using app deep-link flow or `/link <user_name> <user_id>`.

### Service Endpoints

1. `POST /webhooks/telegram` (called by Backend proxy): receives forwarded updates and handles `/start` and `/link`.
2. `POST /internal/telegram-webhook/set`: set webhook URL at runtime.
3. `POST /internal/telegram-webhook/delete`: delete current webhook at runtime.
4. `GET /internal/telegram-link/status/{user_internal_id}`: read current Telegram link status.
5. `POST /internal/telegram-link/start/{user_internal_id}`: create/reuse deep-link token and return link status.
6. `GET /internal/telegram-link/{user_internal_id}`: backward-compatible read endpoint that ensures token exists.
7. `POST /internal/period-notifications/preview`: build title/body for a period transition payload without sending.
8. `POST /internal/period-notifications/send`: send a period transition message to explicit `recipient_user_ids`.
9. `GET /health`: healthcheck endpoint.

The webhook handler reads `X-Telegram-Bot-Api-Secret-Token` but `TelegramNotifier.is_valid_webhook_secret` currently always returns `True`. In other words, the webhook does not actually reject mismatched secrets today; rely on the obscurity of the public webhook URL or a network-level check.

### Configuration

All settings come from environment variables (loaded by `pydantic-settings`).

Database and messaging:

- `DATABASE_URL` (default `postgresql://postgres:postgres@postgres:5432/schedula`)
- `DATABASE_POOL_MIN_SIZE` (default `2`)
- `DATABASE_POOL_MAX_SIZE` (default `10`)
- `RABBITMQ_URL` (default `amqp://rabbitmq:rabbitmq@rabbitmq:5672/`)
- `NOTIFICATION_QUEUE_NAME` (default `notifications_queue`)

Telegram:

Telegram sender credentials are sourced from `APPRISE_URLS`.
Include at least one Telegram URL, e.g. `tgram://<bot_token>/<chat_id>`.
Telegram deep-link generation settings are owned by this service via `TELEGRAM_BOT_NAME` and `TELEGRAM_LINK_TOKEN_TTL_SECONDS`.

Email:

Email sending uses Apprise `mailto://` URLs built per recipient from DB profiles.
Set these environment variables on the `notification` container:

1. `EMAIL_SENDER_USERNAME` (for example `schedulaemail` or `schedulaemail@gmail.com`)
2. `EMAIL_SENDER_APP_PASSWORD` (Gmail app password; spaces are tolerated and stripped automatically)
3. Optional overrides: `EMAIL_SENDER_DOMAIN`, `EMAIL_SMTP_HOST`, `EMAIL_SMTP_PORT`, `EMAIL_SMTP_MODE`, `EMAIL_FROM_ADDRESS`, `EMAIL_FROM_NAME`

Delivery policy for recipient-based notifications:

1. Email is attempted when `users.email` exists and `COALESCE(user_notifications.email_enabled, TRUE)` is true. Additionally, `EmailAppriseNotifier.can_send` requires both `EMAIL_SENDER_USERNAME` and `EMAIL_SENDER_APP_PASSWORD` to be set; otherwise the email channel is silently skipped (a single warning is logged at startup).
2. Telegram is attempted when `telegram_enabled` is true and a linked `telegram_chat_id` exists. Additionally, the bot token must be discoverable from a `tgram://` URL inside `APPRISE_URLS`; if no such URL is configured, the Telegram channel is skipped.

If `EMAIL_SMTP_MODE` is set to a value other than `insecure`, `starttls`, or `ssl`, the notifier falls back to `starttls`.

### Queue Contract (v2)

Notification events are consumed from `notifications_queue` as recipient-based payloads:

```json
{
   "schema_version": "2.0",
   "message_type": "schedule_published",
   "recipient_user_ids": [101, 102],
   "metadata": {
      "event_type": "schedule_published",
      "semester_year": 2026,
      "semester_number": 1,
      "status": "published",
      "schedule_id": 42
   },
   "payload": {
      "title": "Schedule Ready",
      "body": "A new schedule is available.",
      "urls": []
   }
}
```

`message_type` is a free-form string (the model defaults it to `"generic"` and the consumer does not enforce an allowlist). Types currently produced by the backend include:

- `period_transition` (period and semester-status transitions)
- `lecturer_constraint_saved`
- `lecturer_constraint_edited_by_secretary`
- `schedule_published`
- `change_start_schedule_snapshot`

Dispatch precedence inside the consumer (`src/main.py`):

1. If `payload.urls` is non-empty, the consumer fans out via Apprise URLs and **skips** per-recipient delivery. Use this only for legacy or broadcast cases; recipient-based events should leave `urls` empty.
2. Otherwise, the consumer resolves delivery profiles for `recipient_user_ids` from PostgreSQL and dispatches to email and Telegram per the policy above.

`payload.title` defaults to `"Schedula Notification"` if missing. `recipient_user_ids` defaults to `[]`. `metadata` is optional from the model's perspective but is what consumers and tests rely on for routing.

Legacy URL-based payloads (with `payload` not a dict, or a dict containing only `urls`) are still supported during migration.

Period transition payloads follow the same v2 envelope with `message_type = period_transition` and metadata fields:

```json
{
   "schema_version": "2.0",
   "message_type": "period_transition",
   "recipient_user_ids": [101, 102],
   "metadata": {
      "event_type": "period_transition",
      "semester_year": 2026,
      "semester_number": 1,
      "period_type": "constraint",
      "transition_type": "ending_soon",
      "warning_hours": 24,
      "transition_date": "2026-10-14"
   },
   "payload": {
      "title": "Constraint submission period ending soon",
      "body": "Constraint submission period for semester 2026/1 ends in about 24 hours.",
      "urls": []
   }
}
```

The `metadata` model accepts the following optional fields in addition to the period-specific ones above: `old_status`, `new_status`, `status`, `schedule_id`, `broken_constraints_count`. They are surfaced to downstream consumers (and tests) but the notification service itself does not branch on them.

The `/internal/period-notifications/preview` and `/internal/period-notifications/send` endpoints generate titles and bodies from `src/period_messages.py` using the following matrix:

| `period_type`              | `transition_type` | Title / body source                                                                  |
|----------------------------|-------------------|--------------------------------------------------------------------------------------|
| `status`                   | (any)             | "Semester Status Updated" using `old_status` / `new_status`                          |
| `constraint` or `change`   | `start`           | "<period> period started"                                                            |
| `constraint` or `change`   | `starting_soon`   | "<period> period starting soon" - `warning_hours` defaults to **48** if not provided |
| `constraint` or `change`   | `ending_soon`     | "<period> period ending soon" - `warning_hours` defaults to **24** if not provided   |
| `constraint` or `change`   | `ended`           | "<period> period ended"                                                              |
| `constraint` or `change`   | `changed` (or unknown) | Generic fallback: "Schedula Period Update"                                       |

Where `<period>` is `Constraint submission` for `period_type = constraint` and `Schedule changes` for `period_type = change`.

Tunnel options:

1. Any custom/stable tunnel you manage externally (for example a named Cloudflare tunnel).
2. (Historical) An in-compose `cloudflared-backend` quick-tunnel service. The block exists in `docker-compose.yml` but is currently commented out; running it requires un-commenting that service first.

### Runtime Webhook Setup

Preferred: call backend dev delegation route (notification_service remains internal):

1. `POST http://localhost:8000/dev/telegram-webhook/set`
2. JSON body:

```json
{
   "public_url": "https://<your-tunnel-url>",
   "secret_token": "<optional-secret>"
}
```

Backend forwards to notification_service, which appends `/webhooks/telegram`, calls Telegram `setWebhook`, and returns webhook status.

To remove the current webhook during runtime, call:

1. `POST http://localhost:8000/dev/telegram-webhook/delete`
2. Optional query: `?drop_pending_updates=true`

Direct internal notification_service routes can still be used for diagnostics.

### 1) Quick Tunnel (CPU or GPU)

The compose file ships with a `cloudflared-backend` block that is **commented out**. Un-comment it in `docker-compose.yml` if you want a quick ephemeral tunnel.

1. Start stack (CPU or GPU) so Backend is running on `8000` and notification_service on `8001`.
2. After un-commenting `cloudflared-backend`, read tunnel logs:
   - `docker compose logs cloudflared-backend --tail 120`
3. Copy the `https://...trycloudflare.com` URL from logs.
4. Call `POST /dev/telegram-webhook/set` on `http://localhost:8000` with `{"public_url":"<quick_url>"}`.

Notes:

1. Quick tunnel URLs change on restart.
2. You must set Telegram webhook again each time the URL changes.

### 2) Stable URL Tunnel (External)

If you need a stable webhook URL, create/manage a named tunnel externally and provide its public URL to:

1. `POST http://localhost:8000/dev/telegram-webhook/set`

The current compose file does not include a dedicated `tunnel-named` profile/service.

### 3) End-to-End Smoke Test

1. Open frontend and click "Link to Telegram".
2. Telegram opens bot with `/start <token>`.
3. Tap Start in Telegram.
4. Return to frontend and confirm card transitions to Connected.

Useful checks:

1. `docker compose logs cloudflared-backend --tail 120`
2. `docker compose --profile cpu logs backend --tail 120` (CPU mode)
3. `docker compose --profile gpu logs backend-gpu --tail 120` (GPU mode)
4. `docker compose logs notification --tail 120`
5. `curl http://localhost:8001/health`

### 4) Automation Script (Manual Chat ID)

Use this script for fast automation when you already know a Telegram chat ID:

1. `automation_script.ps1`

What it does:

1. Asks for webhook URL first.
2. Optionally starts/rebuilds Docker stack.
3. Waits for backend and notification health.
4. Calls `/dev/telegram-webhook/set`.
5. Creates dev lecturer/course/offering/link data.
6. Upserts `user_notifications` with Telegram chat ID.
7. Sends preview + send requests through `/dev/period-notifications/*`.

Run example:

1. `cd notification_service`
2. `./automation_script.ps1`

### 5) App-Based Script (Guided User Flow)

Use this script to test the same Telegram linking flow real users perform in the frontend (no manual chat ID entry):

1. `app_based_script.ps1`

What it does:

1. Asks for webhook URL before creating the test user.
2. Optionally starts/rebuilds Docker stack.
3. Waits for backend and notification health.
4. Calls `/dev/telegram-webhook/set`.
5. Creates dev lecturer/course/offering/link data.
6. Creates/reuses Telegram link token using notification_service internal start endpoint.
7. Prints step-by-step guidance for login with `user_name` + `user_id` and Telegram linking in the app.
8. Polls Telegram link status and then sends preview + send requests through `/dev/period-notifications/*`.

Run example:

1. `cd notification_service`
2. `./app_based_script.ps1`
