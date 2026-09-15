import asyncpg
from app.config import settings

pool=None

async def init_db():
    global pool
    pool=await asyncpg.create_pool(settings.database_url,min_size=1,max_size=10)
    async with pool.acquire() as c:
        await c.execute("""
        CREATE TABLE IF NOT EXISTS services(
          id SERIAL PRIMARY KEY,name TEXT NOT NULL,duration_min INT NOT NULL,
          price_cents INT NOT NULL DEFAULT 0,active BOOLEAN NOT NULL DEFAULT TRUE,
          sort_order INT NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS masters(
          id SERIAL PRIMARY KEY,name TEXT NOT NULL,active BOOLEAN NOT NULL DEFAULT TRUE
        );
        CREATE TABLE IF NOT EXISTS master_days_off(
          id SERIAL PRIMARY KEY,master_id INT REFERENCES masters(id) ON DELETE CASCADE,
          day DATE NOT NULL,UNIQUE(master_id,day)
        );
        CREATE TABLE IF NOT EXISTS blocked_slots(
          id SERIAL PRIMARY KEY,master_id INT REFERENCES masters(id) ON DELETE CASCADE,
          start_at TIMESTAMPTZ NOT NULL,end_at TIMESTAMPTZ NOT NULL,reason TEXT
        );
        CREATE TABLE IF NOT EXISTS bookings(
          id SERIAL PRIMARY KEY,telegram_user_id BIGINT NOT NULL,
          client_name TEXT NOT NULL,phone TEXT NOT NULL,
          service_id INT NOT NULL REFERENCES services(id),
          master_id INT NOT NULL REFERENCES masters(id),
          start_at TIMESTAMPTZ NOT NULL,end_at TIMESTAMPTZ NOT NULL,
          google_event_id TEXT,status TEXT NOT NULL DEFAULT 'confirmed',
          reminder_24_sent BOOLEAN NOT NULL DEFAULT FALSE,
          reminder_2_sent BOOLEAN NOT NULL DEFAULT FALSE,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          cancelled_at TIMESTAMPTZ
        );
        CREATE INDEX IF NOT EXISTS bookings_range_idx ON bookings(master_id,start_at,end_at,status);
        CREATE INDEX IF NOT EXISTS reminders_idx ON bookings(status,start_at,reminder_24_sent,reminder_2_sent);
        """)
        if await c.fetchval("SELECT count(*) FROM masters")==0:
            await c.execute("INSERT INTO masters(name) VALUES('Основной мастер')")
        if await c.fetchval("SELECT count(*) FROM services")==0:
            await c.executemany(
                "INSERT INTO services(name,duration_min,price_cents,sort_order) VALUES($1,$2,$3,$4)",
                [("Мужская стрижка",60,2500,1),("Стрижка + борода",90,3500,2),("Борода",30,1500,3)]
            )

async def close_db():
    if pool: await pool.close()

async def get_services():
    async with pool.acquire() as c: return await c.fetch("SELECT * FROM services WHERE active=true ORDER BY sort_order,id")
async def get_service(sid):
    async with pool.acquire() as c: return await c.fetchrow("SELECT * FROM services WHERE id=$1 AND active=true",sid)
async def get_masters():
    async with pool.acquire() as c: return await c.fetch("SELECT * FROM masters WHERE active=true ORDER BY id")
async def get_master(mid):
    async with pool.acquire() as c: return await c.fetchrow("SELECT * FROM masters WHERE id=$1 AND active=true",mid)

async def master_day_off(mid,day):
    async with pool.acquire() as c: return await c.fetchval("SELECT 1 FROM master_days_off WHERE master_id=$1 AND day=$2",mid,day) is not None

async def busy(mid,start,end):
    async with pool.acquire() as c:
        return await c.fetch("""
        SELECT start_at,end_at FROM bookings
        WHERE master_id=$1 AND status='confirmed' AND start_at < $3 AND end_at > $2
        UNION ALL
        SELECT start_at,end_at FROM blocked_slots
        WHERE master_id=$1 AND start_at < $3 AND end_at > $2
        """,mid,start,end)

async def create_booking(user_id,name,phone,sid,mid,start,end,event_id):
    async with pool.acquire() as c:
        # Database-level overlap guard inside a transaction.
        async with c.transaction():
            conflict=await c.fetchval("""
              SELECT id FROM bookings
              WHERE master_id=$1 AND status='confirmed' AND start_at < $3 AND end_at > $2
              FOR UPDATE
            """,mid,start,end)
            if conflict: return None
            return await c.fetchrow("""
              INSERT INTO bookings(telegram_user_id,client_name,phone,service_id,master_id,start_at,end_at,google_event_id)
              VALUES($1,$2,$3,$4,$5,$6,$7,$8) RETURNING *
            """,user_id,name,phone,sid,mid,start,end,event_id)

async def get_booking(bid):
    async with pool.acquire() as c:
        return await c.fetchrow("""SELECT b.*,s.name service_name,s.duration_min,m.name master_name
        FROM bookings b JOIN services s ON s.id=b.service_id JOIN masters m ON m.id=b.master_id WHERE b.id=$1""",bid)

async def user_bookings(uid):
    async with pool.acquire() as c:
        return await c.fetch("""SELECT b.*,s.name service_name,m.name master_name
        FROM bookings b JOIN services s ON s.id=b.service_id JOIN masters m ON m.id=b.master_id
        WHERE b.telegram_user_id=$1 AND b.status='confirmed' AND b.start_at>now()
        ORDER BY b.start_at""",uid)

async def cancel_booking(bid,uid=None):
    async with pool.acquire() as c:
        if uid is None:
            return await c.fetchrow("UPDATE bookings SET status='cancelled',cancelled_at=now() WHERE id=$1 AND status='confirmed' RETURNING *",bid)
        return await c.fetchrow("UPDATE bookings SET status='cancelled',cancelled_at=now() WHERE id=$1 AND telegram_user_id=$2 AND status='confirmed' RETURNING *",bid,uid)

async def reschedule_booking(bid,uid,start,end):
    async with pool.acquire() as c:
        async with c.transaction():
            row=await c.fetchrow("SELECT * FROM bookings WHERE id=$1 AND telegram_user_id=$2 AND status='confirmed' FOR UPDATE",bid,uid)
            if not row: return None
            conflict=await c.fetchval("""SELECT id FROM bookings WHERE master_id=$1 AND status='confirmed' AND id<>$4
              AND start_at<$3 AND end_at>$2 FOR UPDATE""",row["master_id"],start,end,bid)
            if conflict: return None
            return await c.fetchrow("UPDATE bookings SET start_at=$2,end_at=$3 WHERE id=$1 RETURNING *",bid,start,end)

async def list_day(start,end,mid=None):
    async with pool.acquire() as c:
        if mid:
            return await c.fetch("""SELECT b.*,s.name service_name,m.name master_name FROM bookings b
            JOIN services s ON s.id=b.service_id JOIN masters m ON m.id=b.master_id
            WHERE b.start_at>=$1 AND b.start_at<$2 AND b.master_id=$3 ORDER BY b.start_at""",start,end,mid)
        return await c.fetch("""SELECT b.*,s.name service_name,m.name master_name FROM bookings b
            JOIN services s ON s.id=b.service_id JOIN masters m ON m.id=b.master_id
            WHERE b.start_at>=$1 AND b.start_at<$2 ORDER BY b.start_at,m.id""",start,end)

async def admin_cancel(bid):
    return await cancel_booking(bid,None)

async def pending_reminders(now, hours):
    async with pool.acquire() as c:
        if hours==24:
            return await c.fetch("""SELECT b.*,s.name service_name,m.name master_name FROM bookings b
            JOIN services s ON s.id=b.service_id JOIN masters m ON m.id=b.master_id
            WHERE b.status='confirmed' AND b.reminder_24_sent=false
            AND b.start_at > $1 + interval '23 hours' AND b.start_at <= $1 + interval '25 hours'""",now)
        return await c.fetch("""SELECT b.*,s.name service_name,m.name master_name FROM bookings b
            JOIN services s ON s.id=b.service_id JOIN masters m ON m.id=b.master_id
            WHERE b.status='confirmed' AND b.reminder_2_sent=false
            AND b.start_at > $1 + interval '1 hour' AND b.start_at <= $1 + interval '3 hours'""",now)

async def mark_reminder(bid,hours):
    async with pool.acquire() as c:
        col="reminder_24_sent" if hours==24 else "reminder_2_sent"
        await c.execute(f"UPDATE bookings SET {col}=true WHERE id=$1",bid)

async def add_master(name):
    async with pool.acquire() as c: return await c.fetchrow("INSERT INTO masters(name) VALUES($1) RETURNING *",name)
async def deactivate_master(mid):
    async with pool.acquire() as c: return await c.execute("UPDATE masters SET active=false WHERE id=$1",mid)
async def add_service(name,duration,price):
    async with pool.acquire() as c: return await c.fetchrow("INSERT INTO services(name,duration_min,price_cents) VALUES($1,$2,$3) RETURNING *",name,duration,price)
async def deactivate_service(sid):
    async with pool.acquire() as c: return await c.execute("UPDATE services SET active=false WHERE id=$1",sid)
async def add_day_off(mid,day):
    async with pool.acquire() as c: return await c.execute("INSERT INTO master_days_off(master_id,day) VALUES($1,$2) ON CONFLICT DO NOTHING",mid,day)
async def block_slot(mid,start,end,reason):
    async with pool.acquire() as c: return await c.fetchrow("INSERT INTO blocked_slots(master_id,start_at,end_at,reason) VALUES($1,$2,$3,$4) RETURNING *",mid,start,end,reason)
