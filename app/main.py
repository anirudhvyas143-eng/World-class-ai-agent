# app/main.py
import os
import uvicorn
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
import json
import requests
from datetime import datetime, timedelta
from supabase import create_client, Client

# ---------------- Supabase Setup ----------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------- Environment / Other APIs ----------------
TWILIO_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
MAILCHIMP_KEY = os.getenv("MAILCHIMP_API_KEY")
CALENDLY_KEY = os.getenv("CALENDLY_API_KEY")
SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL")
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "You are RE-DealAgent")

app = FastAPI(title="RE-DealAgent")

# ---------------- Pydantic Model ----------------
class LeadIn(BaseModel):
    source: str
    campaign_id: str = None
    lead: dict
    utm: dict = None

# ---------------- Lead Persistence ----------------
def persist_lead(payload):
    lead = payload.get('lead', {})
    name = lead.get('name')
    phone = lead.get('phone')
    email = lead.get('email')
    budget = lead.get('budget')
    intent = lead.get('use_case') or lead.get('intent')
    source = payload.get('source')
    payload_json = json.dumps(payload)

    # Insert into Supabase
    response = supabase.table("leads").insert([
        {
            "source": source,
            "source_payload": payload_json,
            "name": name,
            "phone": phone,
            "email": email,
            "budget": budget,
            "intent": intent
        }
    ]).execute()

    if response.data and len(response.data) > 0:
        return response.data[0]["id"]
    return None

# ---------------- Lead Scoring ----------------
def compute_score(lead):
    score = 0
    try:
        budget = int(lead.get('budget') or 0)
    except:
        budget = 0
    ASKING_PRICE_PER_ACRE = 60000000  # adjust per property
    if budget >= ASKING_PRICE_PER_ACRE * 0.5:
        score += 40
    timeline = lead.get('timeline', '')
    if timeline:
        score += 20
    intent = (lead.get('use_case') or lead.get('intent') or '').lower()
    if 'developer' in intent:
        score += 15
    elif 'investment' in intent:
        score += 10
    if lead.get('phone'):
        score += 10
    return min(100, score)

# ---------------- Notifications ----------------
def send_slack(msg):
    if not SLACK_WEBHOOK:
        print("No SLACK_WEBHOOK set.")
        return
    try:
        requests.post(SLACK_WEBHOOK, json={'text': msg}, timeout=5)
    except Exception as e:
        print("Slack send error:", e)

def send_sms(to, body):
    if not TWILIO_SID or not TWILIO_TOKEN or not TWILIO_NUMBER:
        print("Twilio not configured.")
        return
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json"
    try:
        resp = requests.post(url, data={
            "From": TWILIO_NUMBER,
            "To": to,
            "Body": body
        }, auth=(TWILIO_SID, TWILIO_TOKEN), timeout=10)
        print("Twilio resp:", resp.status_code)
    except Exception as e:
        print("Twilio error:", e)

def create_calendly_event(name, email, phone, start_iso):
    # Placeholder; replace with Calendly API call later
    return {"booking_url":"https://calendly.com/your/slot","event_id":"evt_stub"}

# ---------------- Webhook Endpoint ----------------
@app.post("/webhook/lead")
async def webhook_lead(payload: LeadIn, background_tasks: BackgroundTasks):
    payload_dict = payload.dict()
    lead_id = persist_lead(payload_dict)
    lead = payload_dict.get('lead', {})
    score = compute_score(lead)

    # Update score in Supabase
    supabase.table("leads").update({"lead_score": score, "updated_at": datetime.utcnow().isoformat()}).eq("id", lead_id).execute()

    phone = lead.get('phone')
    name = lead.get('name','')

    if phone:
        msg = f"Hi {name}, thanks for your interest. Reply A)Dev B)Invest C)Personal"
        background_tasks.add_task(send_sms, phone, msg)

    if score >= 75:
        preferred = lead.get('preferred_visit') or (datetime.utcnow()+timedelta(days=3)).isoformat()
        background_tasks.add_task(create_calendly_event, name, lead.get('email'), phone, preferred)
        send_slack(f"🔥 HOT LEAD #{lead_id} | {name} | {phone} | score={score}")
    else:
        send_slack(f"New lead #{lead_id} | {name} | score={score} | source={payload_dict.get('source')}")

    return {"lead_id": lead_id, "score": score}

# ---------------- Health & Root ----------------
@app.get("/health")
def health():
    return {"status":"ok", "time": datetime.utcnow().isoformat()}

@app.get("/")
async def root():
    return {"message": "World Class AI Agent is running!"}

# ---------------- Run ----------------
if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
