"""
Backend'i **pencere açmadan** ve **dosyaya log yazarak** çalıştıran servis girişi.

Faz 12'nin autostart'ı (`start.ps1 -InstallAutostart` ile kurulan Windows zamanlanmış görevi)
bunu `pythonw.exe run_service.py --port 8420` diye çağırır. `pythonw` konsol açmaz — oturum
açılışında ekranda bir pencere belirmez.

Neden ayrı bir giriş noktası: `pythonw`'nun konsolu olmadığı için uvicorn'un stdout'u hiçbir
yere gitmez. Bu, tam olarak bu projenin defalarca yakaladığı hata sınıfı olurdu — arka planda
sessizce ölen bir mekanizma, hiç kurulmamış olmaktan kötüdür, çünkü kullanıcı çalıştığını
sanır. Bu yüzden log burada açıkça bir dosyaya (data/logs/backend.log, döngüsel) bağlanıyor:
"otomatik tarama neden çalışmadı" sorusunun bakılacak bir yeri olsun.

Elle çalıştırırken bu dosyaya gerek yok — `start.ps1` uvicorn'u kendi penceresinde başlatır,
log zaten ekranda akar.
"""
import argparse
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import uvicorn

LOG_DIR = Path(__file__).resolve().parent.parent / "data" / "logs"
LOG_FILE = LOG_DIR / "backend.log"


def setup_logging(level: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers = [handler]
    # uvicorn kendi handler'larını kurar ve root'a yaymaz; propagate açılmazsa erişim/hata
    # logları dosyaya hiç düşmez (yine sessiz bir mekanizma olurdu).
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        log = logging.getLogger(name)
        log.handlers = []
        log.propagate = True


def main() -> int:
    parser = argparse.ArgumentParser(description="OsintLab backend — servis modu")
    # Port varsayılanı burada da 8420: start.ps1 görevi kurarken portu açıkça geçirir, ama
    # elle çağrılırsa da doğru portta açılsın (8000'e düşmek arayüzü ve vault senkronunu
    # sessizce kırıyordu — bkz. .claude/CLAUDE.md).
    parser.add_argument("--port", type=int, default=8420)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--log-level", default="info")
    args = parser.parse_args()

    setup_logging(args.log_level)
    logger = logging.getLogger("osintlab.service")
    logger.info("Servis modunda başlatılıyor — %s:%s", args.host, args.port)
    try:
        uvicorn.run(
            "app.main:app",
            host=args.host,
            port=args.port,
            # log_config=None: yukarıda kurduğumuz dosya handler'ı ezilmesin.
            log_config=None,
            access_log=False,  # tek kullanıcılı yerel araç; erişim logu gürültüden ibaret
        )
    except Exception:
        # Portun dolu olması en olası hata (kullanıcı start.ps1 ile zaten açmış). Sessizce
        # ölmesin — görev "başarısız" görünsün ve nedeni logda yazsın.
        logger.exception("Servis başlatılamadı")
        return 1
    logger.info("Servis durdu")
    return 0


if __name__ == "__main__":
    sys.exit(main())
