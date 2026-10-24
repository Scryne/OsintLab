import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app import doc_worker, docint, scheduler, vault as vault_module
from app.db import bump_data_version, get_connection
from app.enrichment import engine as enrichment_engine
from app.routers import (
    archive, claims, collectors, enrichment, entities, evidence, events, investigations, monitors, observations,
    search, selectors, sources, tools, vault,
)

logger = logging.getLogger(__name__)

# Faz 8: Next.js frontend'i (localhost:3000) yerel geliştirmede API'ye tarayıcıdan erişiyor.
# Tek kullanıcılı, local-first bir araç — sadece localhost origin'lerine izin veriliyor.
ALLOWED_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")

# DNS rebinding savunması: tarayıcı, saldırganın alan adını 127.0.0.1'e çözdürse bile `Host`
# başlığında o alan adını gönderir. Yalnızca yerel adlar kabul ediliyor. Ek bir ad gerekirse
# (ör. testler) `OSINTLAB_ALLOWED_HOSTS=ad1,ad2` ile genişletilir.
ALLOWED_HOSTS = ["127.0.0.1", "localhost", *(
    h.strip() for h in os.environ.get("OSINTLAB_ALLOWED_HOSTS", "").split(",") if h.strip()
)]

_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


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


@asynccontextmanager
async def lifespan(_app: FastAPI):
    asyncio.get_running_loop().set_exception_handler(_quiet_connection_reset)
    get_connection()  # KùzuDB bağlantısını açar, şemayı garanti eder
    # Faz 30: önceki süreçten RUNNING kalmış zenginleştirme koşuları kapatılır.
    enrichment_engine.recover_stale()
    # Faz 12: zamanlanmış tarama döngüsü. Backend ayakta olduğu sürece çalışır — ayrı bir
    # süreç değil, çünkü gömülü KùzuDB'yi aynı anda tek süreç açabiliyor (bkz. scheduler.py).
    scheduler.start()
    # Faz 15.1: DOCINT belge işleyicisi. Yükleme ucunda senkron çıkarma yapılamaz —
    # spike 492 sayfalık bir belgeyi 29,9 sn'de çıkardı (bkz. doc_worker.py).
    doc_worker.start()
    # Vault render'ı arka planda, birleştirilerek (bkz. vault.py `RenderWorker`).
    vault_module.start_background_renderer()
    try:
        yield
    finally:
        # Biri patlasa da diğerleri durdurulsun: eskiden zamanlayıcının durması bir istisna
        # fırlatırsa belge işçisi hiç durdurulmuyordu.
        for name, stop in (("scheduler", scheduler.stop), ("doc_worker", doc_worker.stop)):
            try:
                await stop()
            except Exception:  # noqa: BLE001
                logger.exception("%s durdurulamadı", name)
        vault_module.stop_background_renderer()


app = FastAPI(title="OsintLab API", version="0.2.0", lifespan=lifespan)


@app.middleware("http")
async def guard_and_version(request: Request, call_next):
    """İki iş, ikisi de yazan isteklerle ilgili.

    **1. Tarayıcıdan gelen sahte yazma isteklerini (CSRF) reddet.** CORS yanıtın OKUNMASINI
    engeller, isteğin GÖNDERİLMESİNİ değil: herhangi bir site `fetch(..., {mode: "no-cors"})`
    ile içerik türü vermeden POST atabilir (FastAPI gövdeyi yine JSON sayıyor), ve çok parçalı
    form gönderimi zaten "basit istek"tir. Yani açık bir sekmedeki kötü niyetli bir sayfa
    allowlist'e host ekleyebilir, kanıt yükleyebilirdi (2026-10-18 denetimi). Tarayıcılar her
    çapraz kaynaklı yazma isteğinde `Origin` başlığını gönderir; izinli olmayan bir `Origin`
    reddediliyor. Başlıksız istekler (curl, oturum-sonu hook'u, ölçüm script'i) etkilenmez —
    tarayıcı bu başlığı atlayamaz, yalnızca tarayıcı-dışı istemciler göndermez.

    **2. Graf sürümünü artır.** Pahalı türetilmiş görünümler (Promote Kuyruğu) bu sayaçla
    önbellekleniyor; başarılı her yazma isteğinden sonra önbellek geçersiz."""
    unsafe = request.method in _UNSAFE_METHODS
    if unsafe:
        origin = request.headers.get("origin")
        if origin is not None and origin not in ALLOWED_ORIGINS:
            return JSONResponse(status_code=403, content={"detail": "Bu kaynaktan yazma isteği kabul edilmiyor."})
    response = await call_next(request)
    if unsafe and response.status_code < 400:
        bump_data_version()
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=list(ALLOWED_ORIGINS),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)
app.include_router(entities.same_as_router)
app.include_router(entities.candidates_router)
app.include_router(entities.relations_router)
app.include_router(selectors.entity_router)
app.include_router(entities.router)
app.include_router(events.router)
app.include_router(sources.router)
app.include_router(evidence.router)
app.include_router(claims.mentions_router)
app.include_router(selectors.claim_router)
app.include_router(claims.router)
app.include_router(observations.router)
app.include_router(investigations.router)
app.include_router(investigations.hypotheses_router)
app.include_router(collectors.router)
app.include_router(monitors.router)
app.include_router(archive.router)
app.include_router(vault.router)
app.include_router(selectors.router)
app.include_router(enrichment.router)
app.include_router(tools.router)
app.include_router(search.router)


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
        # Vault artık arka planda render ediliyor; son render'ın hatası burada görünür olmalı.
        "vault": vault_module.render_status(),
        # Faz 15.4: OCR sistem kurulumuna bağlı. "Kurulu mu" sorusunun tek satırlık cevabı
        # burada olmalı — sessizce çalışmayan bir mekanizma, hiç kurulmamış olmaktan kötüdür.
        "ocr": _ocr_health(),
    }


def _ocr_health() -> dict:
    d = docint.ocr_status()
    return {"available": d["available"], "lang": d["lang"], "error": d["error"]}
