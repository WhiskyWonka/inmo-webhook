import os
from datetime import datetime

from fastapi import FastAPI, Request

app = FastAPI()
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "")
LEADS_LOG_PATH = os.getenv("LEADS_LOG_PATH", "/app/data/leads.log")


def _ensure_log_dir() -> None:
    """Create the directory that holds the leads log if it does not exist."""
    directory = os.path.dirname(LEADS_LOG_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)


@app.get("/webhook")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return int(challenge)
    return {"error": "fallo"}


@app.post("/webhook")
async def receive_webhook(request: Request):
    data = await request.json()

    if data.get("object") == "whatsapp_business_account":
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                if "messages" in value:
                    for msg in value["messages"]:
                        phone = msg["from"]
                        text = msg.get("text", {}).get("body", "")
                        ts = datetime.now().isoformat()

                        _ensure_log_dir()
                        with open(LEADS_LOG_PATH, "a") as f:
                            f.write(f"{ts} | {phone} | {text}\n")

                        print(f"📩 {phone}: {text}")

    return {"status": "ok"}
