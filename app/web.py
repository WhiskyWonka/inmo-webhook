import json

from fastapi import FastAPI, Request, Response

from app.config import Settings
from app.domain.messages import parse_whatsapp_payload
from app.domain.signature import verify_signature
from app.domain.verification import validate_verification
from app.storage.base import LeadStore


def create_app(settings: Settings, store: LeadStore) -> FastAPI:
    """Build and return the FastAPI application wired to the given settings.

    The storage backend is injected through the ``store`` argument, so the
    web layer depends on the ``LeadStore`` abstraction rather than a concrete
    implementation (Dependency Inversion Principle).
    """
    app = FastAPI()

    @app.get("/webhook")
    async def verify_webhook(request: Request):
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")
        result = validate_verification(mode, token, challenge, settings.verify_token)
        if result is None:
            return Response(status_code=400)
        return Response(content=result, media_type="text/plain", status_code=200)

    @app.post("/webhook")
    async def receive_webhook(request: Request):
        raw = await request.body()
        header = request.headers.get("X-Hub-Signature-256")
        if not verify_signature(header, settings.app_secret, raw):
            return Response(status_code=403)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return Response(status_code=400)

        leads = parse_whatsapp_payload(data)
        for lead in leads:
            store.write(lead)
            print(f"\U0001f4e9 {lead.phone}: {lead.text}")
        return {"status": "ok"}

    return app
