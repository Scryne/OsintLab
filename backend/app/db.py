"""KùzuDB bağlantı yönetimi — Brain-Centric Architecture'daki Intelligence Core katmanı."""
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

import kuzu

from app.schema import init_schema

# Veri kökü ortam değişkeniyle taşınabilir. Varsayılan proje içindeki `data/`.
#
# Faz 15.1'de eklendi, gerekçesi Faz 13'ün canlı dersi: gerçek graf üzerinde test verisi
# üretilirken yazılan bir temizlik filtresi fazla geniş kaldı ve iki gerçek Evidence kaydını
# sildi. O turda "izole bir backend kurulmalıydı" diye not düşülmüştü, ama izolasyon her
# seferinde elle kurulduğu için kolay olan hep yanlış olan kaldı. `OSINTLAB_DATA_DIR=...`
# ile hem graf hem evidence vault tek hamlede başka bir köke taşınıyor; testin gerçek
# veriye dokunması artık kaza değil, bilinçli bir tercih olmak zorunda.
DATA_ROOT = Path(os.environ.get("OSINTLAB_DATA_DIR") or
                 (Path(__file__).resolve().parent.parent.parent / "data"))
DATA_DIR = DATA_ROOT / "graph" / "osintlab.kuzu"

_database: kuzu.Database | None = None
_connection: kuzu.Connection | None = None
_connection_lock = threading.Lock()

# Okuma-sonra-yazma adımlarının (ör. "bu gözlem claim üretmiş mi? → üretmediyse claim yarat")
# kilidi. Bağlantı tek ve paylaşılan: istek iş parçacıkları, zamanlayıcı ve belge işçisi aynı
# `kuzu.Connection`'ı kullanıyor. Tek bir sorgu güvenli, ama iki sorgunun ARASI değil — 2026-10-18
# denetiminde 4 iş parçacığıyla 200'er oku-artır döngüsü 800 yerine 262'de bitti. RLock: aynı iş
# parçacığı iç içe kilitleyebilsin (promote → create_claim → _recompute_and_store).
#
# Kapsam bilerek dar: yalnızca kontrol-sonra-yazma yapan kritik bölgeler alıyor. Ağ beklemesi
# (toplama, arşiv doğrulama) bu kilidin içinde YAPILMAZ — yoksa 45 sn'lik bir tarama arayüzdeki
# her tıklamayı bekletirdi.
graph_lock = threading.RLock()

# Grafın "sürümü": her yazma isteğinden ve arka plan yazmasından sonra artar. Pahalı türetilmiş
# görünümler (Promote Kuyruğu'nun skorlanmış listesi) bunu önbellek anahtarı olarak kullanıyor —
# grafta hiçbir şey değişmediyse aynı 3.000 gözlemi yeniden skorlamanın anlamı yok.
_data_version = 0
_version_lock = threading.Lock()


def bump_data_version() -> int:
    global _data_version
    with _version_lock:
        _data_version += 1
        return _data_version


def data_version() -> int:
    return _data_version


def atomic_write_text(path: Path, text: str) -> None:
    """Dosyayı geçici bir kardeşe yazıp yerine taşır: yazma yarıda kesilirse eski dosya
    bozulmadan kalır. `data/config/` altındaki JSON'lar (allowlist, Inbox ayarı) için — yarım
    bir JSON bir sonraki okumada ilgili özelliğin tamamını durdururdu."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def get_connection() -> kuzu.Connection:
    global _database, _connection
    if _connection is None:
        with _connection_lock:
            if _connection is None:
                DATA_DIR.parent.mkdir(parents=True, exist_ok=True)
                database = kuzu.Database(str(DATA_DIR))
                connection = kuzu.Connection(database)
                # Şema/göç bağlantı YAYINLANMADAN önce: yarıda patlayan bir göç, sonraki
                # çağrıların yarım şemalı bir bağlantıyı sessizce yeniden kullanmasına yol
                # açıyordu. Artık patlarsa global boş kalır ve bir sonraki çağrı yeniden dener.
                init_schema(connection)
                _database, _connection = database, connection
    return _connection


def _as_utc(value):
    """KùzuDB TIMESTAMP'ları saat dilimi bilgisi OLMADAN döndürür.

    Faz 12 bulgusu (F47): grafa her zaman `datetime.now(timezone.utc)` yazılıyor, ama okurken
    tzinfo düşüyor. Pydantic bunu `2026-09-04T07:06:01` diye (Z'siz) serialize ediyor,
    tarayıcıda `new Date(...)` ise saat dilimi eki olmayan bir damgayı YEREL saat sayıyor —
    yani UTC+3'te arayüzdeki her zaman damgası 3 saat geride görünüyordu. Faz 11'e kadar
    kimse yakalamamıştı çünkü zaman damgaları o güne dek yalnızca sıralama içindi; Faz 12'de
    ilk kez taşıyıcı bir bilgi oldular ("son koşu", "sıradaki koşu" — 3 saatlik bir aralıkta
    3 saatlik kayma, sıradaki koşuyu daima 'geçmiş' gösterirdi).

    Düzeltme okuma noktasında, tek yerde: yazılan değer zaten UTC, yalnızca etiketi geri
    konuyor. Karşılaştırmalar (claims.py supersede, sources.py lineage yönü) iki DB değerini
    kıyasladığı için ikisi de aware olunca bozulmuyor."""
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _row(columns, values) -> dict:
    return {c: _as_utc(v) for c, v in zip(columns, values, strict=True)}


def fetch_all(result) -> list[dict]:
    """Bir QueryResult'ı dict listesine çevirir. Sorgularda kolonlar her zaman `AS <isim>`
    ile açıkça isimlendirilmeli — aksi halde KùzuDB `e.id` gibi prefiksli adlar döndürür."""
    columns = result.get_column_names()
    rows = []
    while result.has_next():
        rows.append(_row(columns, result.get_next()))
    return rows


def fetch_one(result) -> dict | None:
    if not result.has_next():
        return None
    return _row(result.get_column_names(), result.get_next())
