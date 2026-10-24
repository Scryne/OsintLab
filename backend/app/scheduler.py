"""
Faz 12 — zamanlayıcı: "bir tarama ne zaman çalışır" sorusunun cevabı. Taramanın kendisi
`app/scanning.py` içinde.

**Neden uvicorn süreci içinde bir asyncio görevi, Windows Task Scheduler değil?**
Roadmap her iki seçeneği de açık bırakmıştı. Belirleyici olan KùzuDB'nin gömülü olması:
veritabanı dosyasını aynı anda tek bir süreç açabiliyor (Faz 14 / F14 bu kilidi zaten
canlı bir bug olarak gösterdi — öksüz kalan bir uvicorn işçisi kilidi tutuyordu). Ayrı bir
süreç grafa doğrudan yazamaz; yapabileceği tek şey HTTP'den API'yi çağırmak olurdu, o da
backend'in zaten ayakta olmasını gerektirir. Yani ayrı süreç hiçbir şey kazandırmayıp bir
hareketli parça daha eklerdi.

**Kabul edilen sınır:** taramalar yalnızca backend ayaktayken çalışır (`start.ps1`). Bu,
local-first ve tek kullanıcılı bir araç için bilinçli bir karar. Telafisi: açılışta zamanı
geçmiş taramalar hemen çalışır (`scanning.next_run_at`, hiç çalışmamış tarama için
`created_at` döner), yani bilgisayar kapalıyken kaçırılan tur bir sonraki açılışta kapanır.

Ölçek notu: tur başına iş, "zamanı gelmiş var mı" diye bakan tek bir KùzuDB sorgusu. Bir
tarama gerçekten çalıştığında ağ G/Ç ve DB yazması olduğu için tüm koşu `asyncio.to_thread`
ile ayrı bir iş parçacığına atılıyor — aksi halde 10 saniyelik bir feed zaman aşımı boyunca
API'nin tamamı donardı.
"""
import asyncio
import logging
import os

from app.scanning import run_due_schedules
from app.selectorwatch import run_due_watches

logger = logging.getLogger(__name__)

# Aralıklar dakika ölçeğinde (asgari 15 dk), dolayısıyla dakikada bir bakmak fazlasıyla
# yeterli — daha sık uyanmak yalnızca boşa dönen sorgu üretir.
TICK_SECONDS = 60

# Zamanlayıcıyı kapatmak için: `OSINTLAB_SCHEDULER=0`. Hata ayıklarken ya da bir taramanın
# ortasında elle deney yaparken işe yarıyor.
ENV_FLAG = "OSINTLAB_SCHEDULER"

_task: asyncio.Task | None = None


def enabled() -> bool:
    return os.environ.get(ENV_FLAG, "1").strip().lower() not in ("0", "false", "off", "no")


# Faz 36: altyapı izleme günde bir koşuyor; "zamanı geldi mi" kontrolü 10 dakikada bir yeter.
WATCH_EVERY_TICKS = 10


async def _loop() -> None:
    tick = 0
    while True:
        if tick % WATCH_EVERY_TICKS == 0:
            try:
                notices = await asyncio.to_thread(run_due_watches)
                if notices:
                    logger.info("Altyapı izleme: %s değişiklik bildirildi", len(notices))
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 — izleme taramayı durdurmamalı
                logger.exception("Altyapı izleme turu beklenmedik şekilde çöktü")
        tick += 1
        try:
            results = await asyncio.to_thread(run_due_schedules)
            for r in results:
                if r["status"] == "OK":
                    logger.info(
                        "Zamanlanmış tarama tamam (%s): %s yeni gözlem",
                        r["schedule_id"][:8],
                        r["observations_created"],
                    )
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — döngü hiçbir hatada ölmemeli
            logger.exception("Zamanlayıcı turu beklenmedik şekilde çöktü")
        await asyncio.sleep(TICK_SECONDS)


def start() -> bool:
    global _task
    if not enabled():
        logger.info("Zamanlayıcı %s ile kapatıldı — otomatik tarama çalışmayacak", ENV_FLAG)
        return False
    if _task is not None and not _task.done():
        return True
    _task = asyncio.create_task(_loop(), name="osintlab-scan-scheduler")
    logger.info("Zamanlayıcı başladı (her %s sn'de bir kontrol)", TICK_SECONDS)
    return True


async def stop() -> None:
    global _task
    if _task is None:
        return
    _task.cancel()
    try:
        await _task
    except asyncio.CancelledError:
        pass
    finally:
        _task = None


def is_running() -> bool:
    return _task is not None and not _task.done()
