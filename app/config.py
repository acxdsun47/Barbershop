import os
from dataclasses import dataclass

def env(name: str, default=None, required=False):
    value=os.getenv(name, default)
    if required and not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value

@dataclass(frozen=True)
class Settings:
    bot_token: str
    webhook_base_url: str
    webhook_secret: str
    database_url: str
    google_calendar_id: str
    google_service_account_json: str
    timezone: str
    admin_ids: tuple[int,...]
    work_start: int
    work_end: int
    slot_minutes: int
    reminder_hours: tuple[int,...]
    booking_days_ahead: int
    min_notice_minutes: int
    cancellation_notice_hours: int

def load_settings():
    admins=tuple(int(x.strip()) for x in env("ADMIN_IDS","").split(",") if x.strip())
    return Settings(
        bot_token=env("BOT_TOKEN", required=True),
        webhook_base_url=env("WEBHOOK_BASE_URL", required=True).rstrip("/"),
        webhook_secret=env("WEBHOOK_SECRET", required=True),
        database_url=env("DATABASE_URL", required=True),
        google_calendar_id=env("GOOGLE_CALENDAR_ID", required=True),
        google_service_account_json=env("GOOGLE_SERVICE_ACCOUNT_JSON", required=True),
        timezone=env("TIMEZONE","Europe/Amsterdam"),
        admin_ids=admins,
        work_start=int(env("WORK_START","10")),
        work_end=int(env("WORK_END","19")),
        slot_minutes=int(env("SLOT_MINUTES","30")),
        reminder_hours=tuple(int(x) for x in env("REMINDER_HOURS","24,2").split(",") if x),
        booking_days_ahead=int(env("BOOKING_DAYS_AHEAD","60")),
        min_notice_minutes=int(env("MIN_NOTICE_MINUTES","60")),
        cancellation_notice_hours=int(env("CANCELLATION_NOTICE_HOURS","2")),
    )
settings=load_settings()
