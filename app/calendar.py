import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from app.config import settings

SCOPES=["https://www.googleapis.com/auth/calendar"]

def svc():
    info=json.loads(settings.google_service_account_json)
    creds=service_account.Credentials.from_service_account_info(info,scopes=SCOPES)
    return build("calendar","v3",credentials=creds,cache_discovery=False)

def create_event(client,phone,service_name,master,start,end):
    body={"summary":f"{service_name} — {client}",
          "description":f"Клиент: {client}\nТелефон: {phone}\nМастер: {master}",
          "start":{"dateTime":start.isoformat(),"timeZone":settings.timezone},
          "end":{"dateTime":end.isoformat(),"timeZone":settings.timezone}}
    return svc().events().insert(calendarId=settings.google_calendar_id,body=body).execute()["id"]

def update_event(event_id,client,phone,service_name,master,start,end):
    s=svc(); e=s.events().get(calendarId=settings.google_calendar_id,eventId=event_id).execute()
    e.update({"summary":f"{service_name} — {client}",
              "description":f"Клиент: {client}\nТелефон: {phone}\nМастер: {master}",
              "start":{"dateTime":start.isoformat(),"timeZone":settings.timezone},
              "end":{"dateTime":end.isoformat(),"timeZone":settings.timezone}})
    s.events().update(calendarId=settings.google_calendar_id,eventId=event_id,body=e).execute()

def delete_event(event_id):
    if event_id: svc().events().delete(calendarId=settings.google_calendar_id,eventId=event_id).execute()
