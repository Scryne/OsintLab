"""Faz 30 — zenginleştirme API'si. Mantık `app/enrichment/engine.py`de.

Yanıtlar modüle göre şekil değiştiren bir `summary` taşıdığı için katı bir Pydantic modeline
bağlanmadı; sabit alanlar (durum, OPSEC, hash, zaman) her koşuda aynı."""
import threading
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.enrichment import datasets, engine
from app.routers.observations import create_observation_record

router = APIRouter(prefix="/enrichment", tags=["enrichment"])


class RunRequest(BaseModel):
    module: str
    target_id: str
    force: bool = False
    confirm_active: bool = False
    # Arayüz `false` gönderir ve koşuyu yoklar; script/ajan için varsayılan sonucu beklemek.
    wait: bool = True


class ModuleToggle(BaseModel):
    enabled: bool


class BulkRequest(BaseModel):
    module: str
    kind: str
    only_missing: bool = True
    limit: int = Field(1000, ge=1, le=5000)


def _raise(exc: engine.EnrichmentError):
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/modules")
def modules() -> list[dict]:
    return engine.list_modules()


@router.patch("/modules/{name}")
def toggle(name: str, payload: ModuleToggle) -> dict:
    try:
        engine.set_enabled(name, payload.enabled)
    except engine.EnrichmentError as exc:
        _raise(exc)
    return engine.describe(engine.REGISTRY[name])


@router.get("/targets/{target_id:path}/modules")
def target_modules(target_id: str) -> list[dict]:
    try:
        return engine.modules_for(target_id)
    except engine.EnrichmentError as exc:
        _raise(exc)


@router.get("/targets/{target_id:path}/runs")
def target_runs(target_id: str) -> list[dict]:
    return engine.runs_for(target_id)


@router.post("/run")
def run(payload: RunRequest) -> dict:
    try:
        return engine.run(payload.module, payload.target_id, force=payload.force,
                          confirm_active=payload.confirm_active, wait=payload.wait)
    except engine.EnrichmentError as exc:
        _raise(exc)


@router.get("/runs")
def recent(limit: int = 100) -> list[dict]:
    return engine.recent_runs(min(max(limit, 1), 500))


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> dict:
    row = engine.get_run(run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Koşu bulunamadı")
    return row


@router.get("/runs/{run_id}/raw")
def raw(run_id: str) -> dict:
    """Ham kayıt + bütünlük kontrolü. `integrity_ok=false` dosyanın koşudan sonra değiştiği anlamına gelir."""
    found = engine.raw_record(run_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Ham kayıt bulunamadı")
    record, ok = found
    return {"integrity_ok": ok, "record": record}


def _flatten(summary: dict, prefix: str = "") -> list[str]:
    lines = []
    for key, value in summary.items():
        if key in ("caution",):
            continue
        label = f"{prefix}{key}"
        if isinstance(value, (str, int, float, bool)) and value not in ("", None):
            lines.append(f"{label}: {value}")
        elif isinstance(value, list) and value and all(isinstance(v, (str, int, float)) for v in value):
            shown = ", ".join(str(v) for v in value[:25])
            lines.append(f"{label}: {shown}{' …' if len(value) > 25 else ''}")
        elif isinstance(value, dict) and value and len(prefix) < 20:
            lines.extend(_flatten(value, f"{label}."))
    return lines


@router.post("/runs/{run_id}/observation", status_code=201)
def to_observation(run_id: str) -> dict:
    """Bir zenginleştirme sonucunu gözleme çevirir; mevcut promote hattına (kuyruk → claim →
    doğrulama) girer. Metin özetten DETERMİNİSTİK üretilir, yorum eklenmez — kaynağı modülün
    sorduğu servistir (`source_url`), `text_source=enrichment` bunu gözlemle birlikte taşır."""
    run_row = engine.get_run(run_id)
    if run_row is None:
        raise HTTPException(status_code=404, detail="Koşu bulunamadı")
    if run_row["status"] != "DONE" or not run_row.get("summary"):
        raise HTTPException(status_code=409, detail="Yalnızca başarılı bir koşu gözleme çevrilebilir.")
    module = engine.REGISTRY.get(run_row["module"])
    header = f"[{module.provider if module else run_row['module']} · {run_row['module_label']}] {run_row['target_id']}"
    body = "\n".join(_flatten(run_row["summary"]))[:18_000]
    obs = create_observation_record(
        f"{header}\n\n{body}",
        observed_at=run_row["finished_at"],
        source_url=run_row.get("request_url"),
        log_extra={"enrichment_run": run_id, "raw_sha256": run_row.get("raw_sha256")},
        text_source="enrichment",
    )
    return obs.model_dump()


# --- Veri setleri --------------------------------------------------------------------------

_dataset_errors: dict[str, str] = {}


@router.get("/datasets")
def dataset_status() -> list[dict]:
    rows = datasets.status()
    for row in rows:
        row["downloading"] = datasets._download_locks[row["name"]].locked()
        row["last_error"] = _dataset_errors.get(row["name"])
    return rows


@router.post("/datasets/{name}/download", status_code=202)
def dataset_download(name: str) -> dict:
    """Arka planda indirir — ATT&CK paketi 55 MB, isteği bekletmemeli."""
    if name not in datasets.DATASETS:
        raise HTTPException(status_code=404, detail="Bilinmeyen veri seti")
    if datasets._download_locks[name].locked():
        raise HTTPException(status_code=409, detail="Bu veri seti zaten indiriliyor")

    def work() -> None:
        try:
            datasets.download(name)
            _dataset_errors.pop(name, None)
        except Exception as exc:  # noqa: BLE001
            _dataset_errors[name] = f"{datetime.now(timezone.utc).isoformat()} — {exc}"

    threading.Thread(target=work, name=f"dataset-{name}", daemon=True).start()
    return {"name": name, "started": True}


# --- Toplu --------------------------------------------------------------------------------

@router.get("/bulk")
def bulk_status() -> dict:
    return engine.bulk_status()


@router.post("/bulk", status_code=202)
def bulk(payload: BulkRequest) -> dict:
    try:
        return engine.start_bulk(payload.module, payload.kind, only_missing=payload.only_missing, limit=payload.limit)
    except engine.EnrichmentError as exc:
        _raise(exc)


@router.post("/bulk/cancel")
def bulk_cancel() -> dict:
    return engine.cancel_bulk()
