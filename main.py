import uvicorn

from app.config import Settings
from app.storage.lead_log import LeadLogStore
from app.web import create_app

settings = Settings()
store = LeadLogStore(settings.leads_log_path)
app = create_app(settings, store)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
