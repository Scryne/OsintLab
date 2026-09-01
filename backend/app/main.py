from fastapi import FastAPI

from app.db import get_connection
from app.routers import claims, entities, evidence, events, observations, sources

app = FastAPI(title="OsintLab API", version="0.1.0")
app.include_router(entities.router)
app.include_router(events.router)
app.include_router(sources.router)
app.include_router(evidence.router)
app.include_router(claims.router)
app.include_router(observations.router)


@app.on_event("startup")
def startup() -> None:
    get_connection()  # KùzuDB bağlantısını açar, şemayı garanti eder


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
