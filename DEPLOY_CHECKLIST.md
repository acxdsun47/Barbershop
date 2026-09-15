# Deployment checklist

## Before GitHub
- [ ] No `.env` committed
- [ ] No Google JSON committed
- [ ] `BOT_TOKEN` is not in source code
- [ ] `ADMIN_IDS` set in Railway

## Google
- [ ] Calendar API enabled
- [ ] Service Account created
- [ ] Calendar shared with Service Account
- [ ] Make changes to events enabled
- [ ] Calendar ID copied

## Railway
- [ ] GitHub repo connected
- [ ] PostgreSQL attached
- [ ] all variables configured
- [ ] deployment successful
- [ ] `/health` returns `{"status":"ok"}`

## Telegram
- [ ] `/start` works
- [ ] service list appears
- [ ] master list appears
- [ ] free slots appear
- [ ] booking creates Google event
- [ ] cancellation deletes Google event
- [ ] reschedule updates Google event
- [ ] `/admin` works for admin
- [ ] reminder test completed

## Recommended test
Create a test booking 25 hours ahead and verify:
1. Telegram confirmation
2. Google Calendar event
3. `/admin`
4. cancellation
5. rescheduling
6. reminder delivery
