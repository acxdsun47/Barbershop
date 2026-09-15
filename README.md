# Barber Booking Bot — production-ready starter

Telegram booking bot designed for GitHub + Railway + PostgreSQL + Google Calendar.

## Included

### Client
- choose service;
- choose master;
- choose date/time from real free slots;
- name + phone;
- booking confirmation;
- Google Calendar event;
- list future bookings;
- cancellation with configurable notice period;
- rescheduling;
- reminders 24h and 2h before appointment.

### Admin
- `/admin` — today's bookings;
- `/admin_tomorrow` — tomorrow's bookings;
- `/masters` — active masters;
- `/services` — active services.

### Infrastructure
- Railway-compatible Docker deployment;
- Telegram webhook;
- PostgreSQL;
- health endpoint;
- Google service account authentication from Railway variable;
- no secrets in Git.

## Railway setup

1. Push this directory to GitHub.
2. Railway → New Project → Deploy from GitHub.
3. Add PostgreSQL.
4. Add these Variables:

`BOT_TOKEN`
Telegram token from BotFather.

`WEBHOOK_BASE_URL`
The public URL of this Railway service, for example `https://your-app.up.railway.app`.

`WEBHOOK_SECRET`
A random long secret. Telegram uses it to authenticate webhook requests.

`DATABASE_URL`
Use the PostgreSQL service's `DATABASE_URL` variable/reference.

`GOOGLE_CALENDAR_ID`
ID of the calendar that the bot will manage.

`GOOGLE_SERVICE_ACCOUNT_JSON`
Paste the complete Google service account JSON as one environment variable.

`TIMEZONE`
For example `Europe/Amsterdam` or `Europe/Berlin`.

`ADMIN_IDS`
Comma-separated Telegram numeric IDs, e.g. `123456789,987654321`.

Optional:
- `WORK_START=10`
- `WORK_END=19`
- `SLOT_MINUTES=30`
- `REMINDER_HOURS=24,2`
- `BOOKING_DAYS_AHEAD=60`
- `MIN_NOTICE_MINUTES=60`
- `CANCELLATION_NOTICE_HOURS=2`

## Google Calendar

1. Google Cloud project.
2. Enable Google Calendar API.
3. Create Service Account.
4. Create a JSON key.
5. Open the target Google Calendar settings.
6. Share the calendar with the service account email.
7. Give `Make changes to events`.
8. Put the Calendar ID into `GOOGLE_CALENDAR_ID`.
9. Put the JSON contents into `GOOGLE_SERVICE_ACCOUNT_JSON`.

## First deployment

Railway builds the Dockerfile and starts FastAPI.
On startup the application:
- connects to PostgreSQL;
- creates required tables;
- seeds default services/master if database is empty;
- registers Telegram webhook;
- starts reminder loop.

Check:
`GET /health`

Expected:
`{"status":"ok"}`

## Default services

On an empty database:
- Мужская стрижка — 60 min — 25 €
- Стрижка + борода — 90 min — 35 €
- Борода — 30 min — 15 €

These are stored in PostgreSQL.

## Important production note

This version is designed to be deployable, but before taking real payments or large traffic, add:
- proper admin UI with buttons;
- individual weekly schedules for every master;
- holiday calendar;
- payment/prepayment;
- rate limiting;
- structured logging/Sentry;
- GDPR privacy/retention policy;
- database migrations (Alembic) instead of startup CREATE TABLE;
- monitoring and backups.

For a single-location barber shop with a small number of masters, the included version is a solid operational base.
