import logging
from fastapi import FastAPI

from routes.webhook import router as webhook_router

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = FastAPI(title="Local Health Server")


@app.get("/health")
@app.get("/")
def health() -> dict:
    return {"status": "ok"}


app.include_router(webhook_router)
