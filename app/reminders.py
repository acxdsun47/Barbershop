import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from app import db
from app.config import settings

async def reminder_loop(bot):
    while True:
        try:
            now=datetime.now(ZoneInfo(settings.timezone))
            for hours in settings.reminder_hours:
                for row in await db.pending_reminders(now,hours):
                    s=row["start_at"].astimezone(ZoneInfo(settings.timezone))
                    try:
                        await bot.send_message(row["telegram_user_id"],
                          f"⏰ Напоминание: через {hours} ч. у вас запись.\n\n"
                          f"✂️ {row['service_name']}\n👤 {row['master_name']}\n"
                          f"📅 {s:%d.%m.%Y %H:%M}")
                        await db.mark_reminder(row["id"],hours)
                    except Exception:
                        # Do not mark if Telegram failed; retry next cycle.
                        pass
        except Exception:
            pass
        await asyncio.sleep(60)
