import uvicorn

from app.config import Settings
from app.web import create_app

settings = Settings()
app = create_app(settings)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
