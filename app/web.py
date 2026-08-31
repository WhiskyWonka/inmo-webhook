from fastapi import FastAPI, Request

from app.config import Settings
from app.domain.messages import parse_whatsapp_payload
from app.domain.verification import validate_verification
from app.storage.lead_log import LeadLogStore


def create_app(settings: Settings) -> FastAPI:
    """Build and return the FastAPI application wired to the given settings."""
    store = LeadLogStore(settings.leads_log_path)
    app = FastAPI()

    @app.get("/webhook")
    async def verify_webhook(request: Request):
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")
        return validate_verification(mode, token, challenge, settings.verify_token)

    @app.post("/webhook")
    async def receive_webhook(request: Request):
        data = await request.json()
        leads = parse_whatsapp_payload(data)
        for lead in leads:
            store.write(lead)
            print(f"\U0001f4e9 {lead.phone}: {lead.text}")
        return {"status": "ok"}

    return app
