"""KùzuDB bağlantı yönetimi — Brain-Centric Architecture'daki Intelligence Core katmanı."""
import os
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


def get_connection() -> kuzu.Connection:
    global _database, _connection
    if _connection is None:
        DATA_DIR.parent.mkdir(parents=True, exist_ok=True)
        _database = kuzu.Database(str(DATA_DIR))
        _connection = kuzu.Connection(_database)
        init_schema(_connection)
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
    return {c: _as_utc(v) for c, v in zip(columns, values)}


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
