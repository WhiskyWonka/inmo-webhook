import os
from fastapi import FastAPI, Request
from datetime import datetime

app = FastAPI()
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "")

@app.get("/webhook")
async def verificar(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return int(challenge)
    return {"error": "fallo"}

@app.post("/webhook")
async def recibir(request: Request):
    data = await request.json()
    
    if data.get("object") == "whatsapp_business_account":
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                if "messages" in value:
                    for msg in value["messages"]:
                        telefono = msg["from"]
                        texto = msg.get("text", {}).get("body", "")
                        ts = datetime.now().isoformat()
                        
                        with open("/app/data/leads.log", "a") as f:
                            f.write(f"{ts} | {telefono} | {texto}\n")
                        
                        print(f"📩 {telefono}: {texto}")
    
    return {"status": "ok"}
