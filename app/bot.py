from datetime import datetime,timedelta,date
from zoneinfo import ZoneInfo
import asyncio,re
from aiogram import Router,F
from aiogram.filters import CommandStart,Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State,StatesGroup
from aiogram.types import Message,CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.config import settings
from app import db
from app.calendar import create_event,delete_event,update_event
from app.keyboards import main,cancel

router=Router(); TZ=ZoneInfo(settings.timezone)

class Book(StatesGroup):
    service=State(); master=State(); name=State(); date=State(); time=State(); phone=State()
class Move(StatesGroup):
    date=State(); time=State()

def slots(day,duration):
    s=datetime(day.year,day.month,day.day,settings.work_start,tzinfo=TZ)
    end=datetime(day.year,day.month,day.day,settings.work_end,tzinfo=TZ)
    return [s+timedelta(minutes=settings.slot_minutes*i) for i in range(int((end-s).total_seconds()/60/settings.slot_minutes))
            if s+timedelta(minutes=settings.slot_minutes*i+duration)<=end]

async def free_slots(day,mid,duration):
    if await db.master_day_off(mid,day): return []
    out=[]
    for s in slots(day,duration):
        if s < datetime.now(TZ)+timedelta(minutes=settings.min_notice_minutes): continue
        e=s+timedelta(minutes=duration)
        if not await db.busy(mid,s,e): out.append(s)
    return out

@router.message(CommandStart())
async def start(m:Message):
    await m.answer("Привет! 👋\nВыберите действие:",reply_markup=main())

@router.callback_query(F.data=="book")
async def book(c:CallbackQuery,state:FSMContext):
    await c.answer(); rows=await db.get_services()
    k=InlineKeyboardBuilder()
    for x in rows: k.button(text=f"{x['name']} — {x['price_cents']/100:.0f} €",callback_data=f"svc:{x['id']}")
    k.adjust(1); await state.set_state(Book.service); await c.message.answer("Выберите услугу:",reply_markup=k.as_markup())

@router.callback_query(Book.service,F.data.startswith("svc:"))
async def service(c:CallbackQuery,state:FSMContext):
    await c.answer(); sid=int(c.data[4:]); s=await db.get_service(sid)
    await state.update_data(service_id=sid,duration=s["duration_min"],service_name=s["name"],price=s["price_cents"])
    ms=await db.get_masters(); k=InlineKeyboardBuilder()
    for m in ms: k.button(text=m["name"],callback_data=f"master:{m['id']}")
    k.adjust(1); await state.set_state(Book.master); await c.message.answer("Выберите мастера:",reply_markup=k.as_markup())

@router.callback_query(Book.master,F.data.startswith("master:"))
async def master(c:CallbackQuery,state:FSMContext):
    await c.answer(); mid=int(c.data.split(":")[1]); m=await db.get_master(mid)
    await state.update_data(master_id=mid,master_name=m["name"]); await state.set_state(Book.name); await c.message.answer("Ваше имя:")

@router.message(Book.name)
async def name(m:Message,state:FSMContext):
    n=m.text.strip()
    if len(n)<2:return await m.answer("Укажите имя.")
    await state.update_data(name=n); await state.set_state(Book.date)
    await m.answer(f"Введите дату YYYY-MM-DD (можно записаться максимум на {settings.booking_days_ahead} дней вперёд):")

@router.message(Book.date)
async def dt(m:Message,state:FSMContext):
    try:d=date.fromisoformat(m.text.strip())
    except:return await m.answer("Неверная дата. Пример: 2026-09-20")
    now=datetime.now(TZ).date(); maxd=now+timedelta(days=settings.booking_days_ahead)
    if d<now or d>maxd:return await m.answer(f"Дата должна быть от {now} до {maxd}.")
    x=await state.get_data(); fs=await free_slots(d,x["master_id"],x["duration"])
    if not fs:return await m.answer("На эту дату свободных окон нет. Введите другую дату.")
    await state.update_data(date=d.isoformat())
    k=InlineKeyboardBuilder()
    for s in fs:k.button(text=s.strftime("%H:%M"),callback_data=f"time:{s.isoformat()}")
    k.adjust(3); await state.set_state(Book.time); await m.answer("Выберите время:",reply_markup=k.as_markup())

@router.callback_query(Book.time,F.data.startswith("time:"))
async def tm(c:CallbackQuery,state:FSMContext):
    await c.answer(); await state.update_data(start=c.data[5:]); await state.set_state(Book.phone)
    await c.message.answer("Номер телефона:")

@router.message(Book.phone)
async def phone(m:Message,state:FSMContext):
    p=m.text.strip()
    if len(re.sub(r"\D","",p))<7:return await m.answer("Проверьте номер телефона.")
    x=await state.get_data(); start=datetime.fromisoformat(x["start"]).astimezone(TZ); end=start+timedelta(minutes=x["duration"])
    if await db.master_day_off(x["master_id"],start.date()) or await db.busy(x["master_id"],start,end):
        await state.clear(); return await m.answer("Это время уже заняли. Начните заново: /start")
    try:
        eid=await asyncio.to_thread(create_event,x["name"],p,x["service_name"],x["master_name"],start,end)
        row=await db.create_booking(m.from_user.id,x["name"],p,x["service_id"],x["master_id"],start,end,eid)
        if not row:
            await asyncio.to_thread(delete_event,eid)
            await state.clear(); return await m.answer("Это время уже заняли. Выберите другое: /start")
    except Exception:
        return await m.answer("Ошибка при создании записи. Попробуйте ещё раз.")
    await state.clear()
    await m.answer(f"✅ <b>Запись подтверждена</b>\n\n✂️ {x['service_name']}\n👤 {x['master_name']}\n📅 {start:%d.%m.%Y}\n🕐 {start:%H:%M}–{end:%H:%M}\n💶 {x['price']/100:.0f} €\n📞 {p}",reply_markup=main())

@router.callback_query(F.data=="mine")
async def mine(c:CallbackQuery):
    await c.answer(); rows=await db.user_bookings(c.from_user.id)
    if not rows:return await c.message.answer("Активных записей нет.",reply_markup=main())
    for r in rows:
        s=r["start_at"].astimezone(TZ)
        await c.message.answer(f"✂️ <b>{r['service_name']}</b>\n👤 {r['master_name']}\n📅 {s:%d.%m.%Y %H:%M}\n📞 {r['phone']}",reply_markup=cancel(r["id"]))

@router.callback_query(F.data.startswith("cancel:"))
async def cancel_cb(c:CallbackQuery):
    bid=int(c.data.split(":")[1]); row=await db.get_booking(bid)
    if not row or row["telegram_user_id"]!=c.from_user.id:return await c.answer("Запись не найдена.",show_alert=True)
    if row["start_at"]-datetime.now(TZ)<timedelta(hours=settings.cancellation_notice_hours):
        return await c.answer(f"Отменять можно минимум за {settings.cancellation_notice_hours} ч.",show_alert=True)
    row=await db.cancel_booking(bid,c.from_user.id)
    try: await asyncio.to_thread(delete_event,row["google_event_id"])
    except: pass
    await c.answer("Запись отменена"); await c.message.edit_text("❌ Запись отменена.")

@router.callback_query(F.data.startswith("move:"))
async def move(c:CallbackQuery,state:FSMContext):
    bid=int(c.data.split(":")[1]); row=await db.get_booking(bid)
    if not row or row["telegram_user_id"]!=c.from_user.id:return await c.answer("Запись не найдена.",show_alert=True)
    if row["start_at"]-datetime.now(TZ)<timedelta(hours=settings.cancellation_notice_hours):
        return await c.answer(f"Перенос возможен минимум за {settings.cancellation_notice_hours} ч.",show_alert=True)
    await state.update_data(booking_id=bid,duration=row["end_at"].replace(tzinfo=None)-row["start_at"].replace(tzinfo=None),master_id=row["master_id"],service_name=row["service_name"],master_name=row["master_name"])
    await state.set_state(Move.date); await c.answer(); await c.message.answer("Новая дата YYYY-MM-DD:")

@router.message(Move.date)
async def move_date(m:Message,state:FSMContext):
    try:d=date.fromisoformat(m.text.strip())
    except:return await m.answer("Неверная дата.")
    x=await state.get_data(); duration=int(x["duration"].total_seconds()/60)
    fs=await free_slots(d,x["master_id"],duration)
    if not fs:return await m.answer("Свободных окон нет.")
    await state.update_data(date=d.isoformat())
    k=InlineKeyboardBuilder()
    for s in fs:k.button(text=s.strftime("%H:%M"),callback_data=f"movetime:{s.isoformat()}")
    k.adjust(3); await state.set_state(Move.time); await m.answer("Новое время:",reply_markup=k.as_markup())

@router.callback_query(Move.time,F.data.startswith("movetime:"))
async def move_time(c:CallbackQuery,state:FSMContext):
    await c.answer(); x=await state.get_data(); bid=x["booking_id"]
    row=await db.get_booking(bid); start=datetime.fromisoformat(c.data[8:]).astimezone(TZ)
    end=start+timedelta(minutes=int(x["duration"].total_seconds()/60))
    if await db.busy(x["master_id"],start,end):return await c.answer("Время уже заняли.",show_alert=True)
    try:
        row=await db.reschedule_booking(bid,c.from_user.id,start,end)
        if not row:return await c.answer("Время уже заняли.",show_alert=True)
        await asyncio.to_thread(update_event,row["google_event_id"],row["client_name"],row["phone"],x["service_name"],x["master_name"],start,end)
    except Exception:
        return await c.answer("Не удалось перенести запись.",show_alert=True)
    await state.clear(); await c.message.answer(f"✅ Перенесено на {start:%d.%m.%Y %H:%M}.",reply_markup=main())

@router.message(Command("admin"))
async def admin(m:Message):
    if m.from_user.id not in settings.admin_ids:return
    d=datetime.now(TZ).date(); a=datetime(d.year,d.month,d.day,tzinfo=TZ); rows=await db.list_day(a,a+timedelta(days=1))
    if not rows:return await m.answer("Сегодня записей нет.")
    text=["📋 <b>Сегодня</b>"]
    for r in rows:text.append(f"{r['start_at'].astimezone(TZ):%H:%M} — {r['client_name']} — {r['service_name']} — {r['master_name']} — {r['phone']}")
    await m.answer("\n".join(text))

@router.message(Command("admin_tomorrow"))
async def admin_tomorrow(m:Message):
    if m.from_user.id not in settings.admin_ids:return
    d=datetime.now(TZ).date()+timedelta(days=1); a=datetime(d.year,d.month,d.day,tzinfo=TZ); rows=await db.list_day(a,a+timedelta(days=1))
    if not rows:return await m.answer("Завтра записей нет.")
    await m.answer("\n".join([f"{r['start_at'].astimezone(TZ):%H:%M} — {r['client_name']} — {r['service_name']} — {r['master_name']} — {r['phone']}" for r in rows]))

@router.message(Command("masters"))
async def masters_cmd(m:Message):
    if m.from_user.id not in settings.admin_ids:return
    rows=await db.get_masters(); await m.answer("\n".join([f"{x['id']}: {x['name']}" for x in rows]))

@router.message(Command("services"))
async def services_cmd(m:Message):
    if m.from_user.id not in settings.admin_ids:return
    rows=await db.get_services(); await m.answer("\n".join([f"{x['id']}: {x['name']} — {x['duration_min']} мин — {x['price_cents']/100:.0f} €" for x in rows]))
