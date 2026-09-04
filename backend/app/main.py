from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import scheduler
from app.db import get_connection
from app.routers import claims, collectors, entities, evidence, events, investigations, monitors, observations, sources, vault

app = FastAPI(title="OsintLab API", version="0.1.0")
# Faz 8: Next.js frontend'i (localhost:3000) yerel geliştirmede API'ye tarayıcıdan erişiyor.
# Tek kullanıcılı, local-first bir araç — sadece localhost origin'lerine izin veriliyor.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(entities.same_as_router)
app.include_router(entities.router)
app.include_router(events.router)
app.include_router(sources.router)
app.include_router(evidence.router)
app.include_router(claims.router)
app.include_router(observations.router)
app.include_router(investigations.router)
app.include_router(investigations.hypotheses_router)
app.include_router(collectors.router)
app.include_router(monitors.router)
app.include_router(vault.router)


@app.on_event("startup")
async def startup() -> None:
    get_connection()  # KùzuDB bağlantısını açar, şemayı garanti eder
    # Faz 12: zamanlanmış tarama döngüsü. Backend ayakta olduğu sürece çalışır — ayrı bir
    # süreç değil, çünkü gömülü KùzuDB'yi aynı anda tek süreç açabiliyor (bkz. scheduler.py).
    scheduler.start()


@app.on_event("shutdown")
async def shutdown() -> None:
    await scheduler.stop()


@app.get("/health")
def health() -> dict:
    # Zamanlayıcının durumu health'e kondu: "otomatik tarama gerçekten çalışıyor mu"
    # sorusunun tek satırlık cevabı olsun (Faz 11'in dersi — sessiz mekanizma kurma).
    return {"status": "ok", "scheduler": scheduler.is_running()}
