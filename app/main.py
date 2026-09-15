import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI,Request
from aiogram import Bot,Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Update
from app.config import settings
from app import db
from app.bot import router
from app.reminders import reminder_loop

bot=Bot(settings.bot_token,default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp=Dispatcher(); dp.include_router(router)
path=f"/telegram/webhook/{settings.webhook_secret}"

@asynccontextmanager
async def lifespan(app:FastAPI):
    await db.init_db()
    await bot.set_webhook(settings.webhook_base_url+path,secret_token=settings.webhook_secret,allowed_updates=dp.resolve_used_update_types())
    task=asyncio.create_task(reminder_loop(bot))
    yield
    task.cancel()
    await bot.delete_webhook()
    await db.close_db()
    await bot.session.close()

app=FastAPI(title="Barber Booking Bot",lifespan=lifespan)

@app.get("/")
async def root(): return {"status":"ok","service":"barber-booking-bot"}

@app.get("/health")
async def health(): return {"status":"ok"}

@app.post(path)
async def webhook(request:Request):
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token")!=settings.webhook_secret:
        return {"ok":False}
    update=Update.model_validate(await request.json(),context={"bot":bot})
    await dp.feed_update(bot,update)
    return {"ok":True}
