"""KùzuDB bağlantı yönetimi — Brain-Centric Architecture'daki Intelligence Core katmanı."""
from pathlib import Path

import kuzu

from app.schema import init_schema

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "graph" / "osintlab.kuzu"

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


def fetch_all(result) -> list[dict]:
    """Bir QueryResult'ı dict listesine çevirir. Sorgularda kolonlar her zaman `AS <isim>`
    ile açıkça isimlendirilmeli — aksi halde KùzuDB `e.id` gibi prefiksli adlar döndürür."""
    columns = result.get_column_names()
    rows = []
    while result.has_next():
        rows.append(dict(zip(columns, result.get_next())))
    return rows


def fetch_one(result) -> dict | None:
    if not result.has_next():
        return None
    columns = result.get_column_names()
    return dict(zip(columns, result.get_next()))
