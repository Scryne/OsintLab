import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import doc_worker, scheduler
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


def _quiet_connection_reset(loop, context: dict) -> None:
    """Windows asyncio'nun `ConnectionResetError` gürültüsünü loga basmaz, diğer her şeyi basar.

    Faz 12 sonrası gerçek kullanımda bulundu (F55): 4 saatlik bir koşuda log'da **186 adet**
    `ConnectionResetError: [WinError 10054]` traceback'i (582 satır) ve yalnızca **3** gerçek
    tarama satırı vardı. Bu istisna, bir istemci (tarayıcı, curl) keep-alive bağlantısını
    sertçe kapattığında ProactorEventLoop'un ürettiği bilinen ve zararsız bir Windows
    davranışı — sunucuyu etkilemiyor, ama `data/logs/backend.log`'u %99 gürültüye çeviriyordu.
    Oysa o dosyanın tek varlık nedeni "otomatik tarama neden çalışmadı" sorusuna bakılacak bir
    yer olmasıydı; okunamayan bir log, olmayan logla aynı şey.

    Kapsam bilerek DAR: yalnızca bu istisna türü susturuluyor, geri kalan her şey asyncio'nun
    kendi varsayılan işleyicisine gidiyor. Tümünü susturmak (asyncio logger'ını kapatmak)
    gerçek bir hatayı da gizlerdi."""
    if isinstance(context.get("exception"), ConnectionResetError):
        logging.getLogger("app.net").debug("İstemci bağlantıyı sertçe kapattı (WinError 10054)")
        return
    loop.default_exception_handler(context)


@app.on_event("startup")
async def startup() -> None:
    asyncio.get_running_loop().set_exception_handler(_quiet_connection_reset)
    get_connection()  # KùzuDB bağlantısını açar, şemayı garanti eder
    # Faz 12: zamanlanmış tarama döngüsü. Backend ayakta olduğu sürece çalışır — ayrı bir
    # süreç değil, çünkü gömülü KùzuDB'yi aynı anda tek süreç açabiliyor (bkz. scheduler.py).
    scheduler.start()
    # Faz 15.1: DOCINT belge işleyicisi. Yükleme ucunda senkron çıkarma yapılamaz —
    # spike 492 sayfalık bir belgeyi 29,9 sn'de çıkardı (bkz. doc_worker.py).
    doc_worker.start()


@app.on_event("shutdown")
async def shutdown() -> None:
    await scheduler.stop()
    await doc_worker.stop()


@app.get("/health")
def health() -> dict:
    # Zamanlayıcının durumu health'e kondu: "otomatik tarama gerçekten çalışıyor mu"
    # sorusunun tek satırlık cevabı olsun (Faz 11'in dersi — sessiz mekanizma kurma).
    return {
        "status": "ok",
        "scheduler": scheduler.is_running(),
        # Faz 15.1: belge işleyicisi de sessiz bir mekanizma — durumu görünür olmalı.
        "docint_worker": doc_worker.is_running(),
        "docint_queue": doc_worker.queue_depth(),
    }
