import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app import archive, docint, pivot, triage
from app.db import DATA_ROOT, bump_data_version, fetch_all, fetch_one, get_connection, graph_lock
from app.models import (
    Claim,
    ClaimCreate,
    Observation,
    ObservationCreate,
    ObservationDismiss,
    ObservationDismissResult,
    ObservationFromEvidence,
    ObservationPromote,
    ObservationPromoteBatch,
    ObservationPromoteBatchItem,
    ObservationPromoteBatchResult,
    ObservationQueue,
    QueueCount,
)
from app.monitoring import claim_headline
from app.recall import entity_recall, event_recall
from app.recall import why_matters as compute_why_matters
from app.routers.claims import _claim_about, _gather_confidence_inputs, create_claim_record, get_claim
from app.vault import safe_render_vault

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/observations", tags=["observations"])

_FIELDS = (
    "o.id AS id, o.raw_content AS raw_content, o.observed_at AS observed_at, "
    "o.promoted AS promoted, o.source_url AS source_url, o.created_at AS created_at, "
    "o.injection_hits AS injection_hits, o.text_source AS text_source, "
    # Faz 16 — "degerlendirildi, bilgiye donusturulmedi" isareti. `promoted=false` tek basina
    # iki ayri hali anlatmak zorundaydi; bu alan olmadan elenen gozlem ertesi gun yine
    # kuyrugun icinde durur.
    "o.dismissed AS dismissed, o.dismissed_at AS dismissed_at, "
    "o.dismiss_reason AS dismiss_reason"
)

# F32: OPTIONAL MATCH ile üretilmiş claim'in id'si. Ayrı bir sorgu yerine aynı sorguya
# eklendi — liste uçları N+1 sorgu yapmasın diye.
_FIELDS_WITH_CLAIM = _FIELDS + ", c.id AS produced_claim_id"
_PRODUCED = "OPTIONAL MATCH (o)-[:PRODUCED]->(c:Claim) "

# Faz 15.2 — gözlem bir belgeden geldiyse hangi belgenin hangi sayfalarından geldiği. Aynı
# sorguya eklendi (ayrı sorgu N+1 olurdu, F58'de collector tarafında öğrenilen ders).
_FROM_EVIDENCE = "OPTIONAL MATCH (o)-[ef:EXTRACTED_FROM]->(ev:Evidence) "
_FIELDS_FULL = (
    _FIELDS_WITH_CLAIM
    + ", ev.id AS ev_id, ev.file_path AS ev_file_path, "
    "ef.page_from AS ev_page_from, ef.page_to AS ev_page_to"
)


def _observation_from_row(row: dict) -> Observation:
    """Sorgu satırını modele çevirir; belge provenance'ı varsa iç nesneye toplar."""
    from_evidence = None
    if row.get("ev_id"):
        file_path = row.get("ev_file_path") or ""
        # Depolanan ad "<hash16>-<özgün ad>"; kullanıcıya özgün adı gösteriyoruz.
        name = file_path.split("/")[-1]
        from_evidence = ObservationFromEvidence(
            evidence_id=row["ev_id"],
            page_from=row.get("ev_page_from") or 1,
            page_to=row.get("ev_page_to") or 1,
            file_name=name.split("-", 1)[-1] or name or None,
        )
    plain = {k: v for k, v in row.items() if not k.startswith("ev_")}
    plain["injection_hits"] = docint.hits_from_json(plain.get("injection_hits"))
    # ALTER TABLE ile eklenen kolon, Faz 16'dan onceki kayitlarda NULL gelir — model bool
    # bekliyor. Varsayilan "elenmemis": eski kayitlarin hepsi hala degerlendirilmeyi bekliyor.
    plain["dismissed"] = bool(plain.get("dismissed"))
    return Observation(**plain, from_evidence=from_evidence)

# vault.VAULT_DIR ile aynı düzeltme (Faz 16): sabit proje yolu, izole veri köküyle çalışan
# bir test koşusunun append-only GERÇEK günlüğüne yazmasına yol açıyordu.
DAILY_LOG_DIR = DATA_ROOT / "daily"

# Q1/Q8: Knowledge Graph'a promote edilmek için bir observation'dan türeyen claim'in
# ulaşması gereken minimum confidence eşiği. Altında kalan bilgi silinmez, sadece
# Observation olarak (promoted=false) ham log'da kalır.
PROMOTION_THRESHOLD = 0.45


def _append_daily_log(
    observation_id: str,
    raw_content: str,
    observed_at: datetime,
    created_at: datetime,
    source_url: str | None,
    extra: dict | None = None,
) -> None:
    """AvenoxBeyin'in daily/ katmanına paralel: her observation, değiştirilemez (append-only)
    bir JSONL günlük dosyasına da düşer — Knowledge Graph'tan bağımsız, kalıcı bir ham kayıt."""
    DAILY_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = DAILY_LOG_DIR / f"{created_at.date().isoformat()}.jsonl"
    entry = {
        "id": observation_id,
        "raw_content": raw_content,
        "observed_at": observed_at.isoformat(),
        "source_url": source_url,
        "created_at": created_at.isoformat(),
    }
    if extra:
        entry.update(extra)
    with log_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def create_observation_record(
    raw_content: str,
    observed_at: datetime | None = None,
    source_url: str | None = None,
    log_extra: dict | None = None,
    text_source: str | None = None,
) -> Observation:
    """create_observation'ın altındaki paylaşılan mantık — collector router'ı da bunu kullanır.

    `log_extra` (Faz 15.2): append-only günlüğe eklenecek ek provenance. Belge tabanlı
    gözlemlerin URL'i yoktur; `source_url`'e uydurma bir değer yazmak yerine "hangi belgenin
    hangi sayfası" bilgisi günlüğe böyle düşüyor. Graf'taki karşılığı EXTRACTED_FROM kenarı,
    ama günlük graf'tan bağımsız ve kalıcı olmalı (AvenoxBeyin daily/ katmanının amacı bu)."""
    conn = get_connection()
    observation_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)
    observed_at = observed_at or created_at
    # Q22 (Faz 15.2): her gözlemin ham metni güvenilmeyen veridir — kaynağı belge de olsa
    # RSS de olsa. Tarama burada, ortak yaratma noktasında yapılıyor ki uyarı metinle
    # BİRLİKTE seyahat etsin: promote kararı gözlem üzerinde veriliyor, uyarı yalnızca
    # kaynak belgede dursaydı kullanıcı bir iddiayı grafa yükseltirken onu görmeyebilirdi.
    hits = docint.find_instruction_like(raw_content, where="gözlem metni")
    conn.execute(
        "CREATE (:Observation {id: $id, raw_content: $raw_content, observed_at: $observed_at, "
        "promoted: false, source_url: $source_url, created_at: $created_at, "
        "injection_hits: $injection_hits, text_source: $text_source, dismissed: false})",
        {
            "id": observation_id,
            "raw_content": raw_content,
            "observed_at": observed_at,
            "source_url": source_url,
            "created_at": created_at,
            "injection_hits": docint.hits_to_json(hits),
            "text_source": text_source,
        },
    )
    _append_daily_log(observation_id, raw_content, observed_at, created_at, source_url, log_extra)
    # Faz 29: seçiciler (CVE, alan adı, IP...) gözlem yaratılırken çıkarılır — geriye dönük tarama
    # tek seferlik, bundan sonrası kendiliğinden. İndeksleme hatası gözlemi DÜŞÜRMEZ: gözlem ham
    # kayıttır, indeks türetilmiş bir görünüm ve `/selectors/reindex` ile her an yeniden kurulur.
    try:
        pivot.index_observation(observation_id, raw_content, source_url)
    except Exception:  # noqa: BLE001
        logger.exception("Gözlem %s seçici indekslemesi başarısız", observation_id)
    # Zamanlanmış tarama HTTP dışından yazıyor; kuyruk önbelleği (triage) bunu da görmeli.
    bump_data_version()
    return Observation(
        id=observation_id, promoted=False, created_at=created_at,
        raw_content=raw_content, observed_at=observed_at, source_url=source_url,
        injection_hits=hits, text_source=text_source,
    )


@router.post("", response_model=Observation, status_code=201)
def create_observation(payload: ObservationCreate) -> Observation:
    return create_observation_record(payload.raw_content, payload.observed_at, payload.source_url)


@router.get("", response_model=list[Observation])
def list_observations(
    promoted: bool | None = None, ids: str | None = None, dismissed: bool | None = None
) -> list[Observation]:
    """`ids` (virgülle ayrılmış) — Faz 12 sonrası gerçek kullanımda çıkan bulgu (F58).

    Zamanlanmış tarama Inbox'a "TechCrunch: 17 yeni içerik" diye bir bildirim düşürüyor ve
    hangi gözlemlerden bahsettiğini `detail.observation_ids` içinde biliyor — ama o gözlemlere
    gitmenin hiçbir yolu yoktu: 181 kayıtlık listede başlıkları tek tek aratmak gerekiyordu.
    Bildirim geliyor, üzerine iş yapılamıyor. Bu parametre bildirimle gözlem listesi arasındaki
    bağı kuruyor."""
    conn = get_connection()
    id_list = [i.strip() for i in ids.split(",") if i.strip()] if ids else None

    clauses = []
    params: dict = {}
    if promoted is not None:
        clauses.append("o.promoted = $promoted")
        params["promoted"] = promoted
    if id_list:
        clauses.append("o.id IN $ids")
        params["ids"] = id_list
    if dismissed is not None:
        # Faz 16: kolon ALTER ile eklendi, eski kayitlarda NULL. NULL = "elenmemis" —
        # `o.dismissed = false` tek basina o kayitlari disarida birakirdi.
        clauses.append(
            "o.dismissed = true" if dismissed else "(o.dismissed IS NULL OR o.dismissed = false)"
        )
    where = f"WHERE {' AND '.join(clauses)} " if clauses else ""

    result = conn.execute(
        f"MATCH (o:Observation) {where}{_PRODUCED}{_FROM_EVIDENCE}"
        f"RETURN {_FIELDS_FULL} ORDER BY o.created_at",
        params,
    )
    return [_observation_from_row(row) for row in fetch_all(result)]


@router.get("/queue", response_model=ObservationQueue)
def observation_queue(
    limit: int = 200,
    offset: int = 0,
    host: str | None = None,
    max_score: float | None = None,
    min_score: float | None = None,
) -> ObservationQueue:
    """Faz 16 — degerlendirmeyi bekleyen gozlemler, sinyale gore sirali.

    Yol sirasi onemli: bu ucun `/observations/{observation_id}`DAN ONCE tanimlanmasi gerekiyor,
    yoksa FastAPI "queue" kelimesini bir gozlem id'si sanar."""
    return triage.build_queue(
        get_connection(), limit=limit, offset=offset, host=host,
        max_score=max_score, min_score=min_score,
    )


@router.get("/queue/count", response_model=QueueCount)
def observation_queue_count() -> QueueCount:
    """Nav rozeti: bekleyen gözlem sayısı, skorlamadan. `/queue` ile aynı tanım
    (`/observations/{observation_id}`'den önce tanımlı, bkz. yukarıdaki not)."""
    return QueueCount(pending=triage.pending_count(get_connection()))


@router.post("/dismiss", response_model=ObservationDismissResult)
def dismiss_observations(payload: ObservationDismiss) -> ObservationDismissResult:
    """Faz 16 — toplu eleme: "degerlendirildi, bilgiye donusturulmedi".

    Kayit SILINMEZ (Q17). Claim uretmis bir gozlem elenmez; `skipped` icinde doner."""
    return triage.dismiss(get_connection(), payload)


@router.post("/undismiss", response_model=ObservationDismissResult)
def undismiss_observations(payload: ObservationDismiss) -> ObservationDismissResult:
    """Elemeyi geri alir. Geri donusu olmayan bir toplu islem kullanilmaz."""
    return triage.undismiss(get_connection(), payload.observation_ids)


def _create_claim_from_observation(
    conn, observation: Observation, payload: ObservationPromote
) -> Claim:
    """promote'un çekirdeği: gözlem metninden claim üretir ve PRODUCED kenarını kurar.

    `safe_render_vault` BİLEREK burada değil — toplu promote 36 kaydı işlerken vault'u 36 kez
    yeniden yazardı. Çağıran katman render'ı bir kez, sonda tetikliyor. (2026-10-18'e kadar bu
    söz tutulmuyordu: çağrılan `create_claim` route'u kendi içinde render ediyordu.)"""
    claim = create_claim_record(
        conn,
        ClaimCreate(
            text=observation.raw_content,
            source_id=payload.source_id,
            # F12: gözlemin yayın tarihi claim'in valid_from'u olur.
            valid_from=observation.observed_at,
            about_entity_id=payload.about_entity_id,
            about_event_id=payload.about_event_id,
            evidence_ids=payload.evidence_ids,
            contradicting_evidence_ids=payload.contradicting_evidence_ids,
            corroborates=payload.corroborates,
            # F26: promote bu ikisini geçirmiyordu, dolayısıyla toplanan veriden gelen bir
            # claim ne çelişkili işaretlenebiliyor ne de eski bir claim'in yerini alabiliyordu.
            contradicts=payload.contradicts,
            supersedes=payload.supersedes,
        )
    )

    # Faz 16: eleme işareti her iki dalda da temizleniyor. "Değerlendirildi, bilgiye
    # DÖNÜŞTÜRÜLMEDİ" artık doğru değil — gözlem bir claim üretti. Elenmiş bir gözlem
    # sonradan promote edilebiliyor (kuyrukta değil ama Gözlemler sayfasında duruyor);
    # işaret kalsaydı kayıt kendi geçmişini yanlış anlatırdı.
    clear = "o.dismissed = false, o.dismissed_at = NULL, o.dismiss_reason = NULL"
    if claim.confidence >= PROMOTION_THRESHOLD:
        conn.execute(
            "MATCH (o:Observation {id: $oid}), (c:Claim {id: $cid}) "
            f"SET o.promoted = true, {clear} CREATE (o)-[:PRODUCED]->(c)",
            {"oid": observation.id, "cid": claim.id},
        )
    else:
        # Eşiği geçmedi: Claim yine de oluşturuldu (REPORTED gibi düşük bir state'te,
        # denetim/gelecekteki corroboration için erişilebilir) ama Observation
        # promoted=false kalır — Q1 katmanlı hafıza modeli.
        conn.execute(
            "MATCH (o:Observation {id: $oid}), (c:Claim {id: $cid}) "
            f"SET {clear} CREATE (o)-[:PRODUCED]->(c)",
            {"oid": observation.id, "cid": claim.id},
        )

    # Faz 26: arşiv kopyası promote anında, OTOMATİK oluşuyor. Kullanıcı onayına
    # bağlanmadı çünkü arşiv bir DEĞERLENDİRME değil, bir KAYIT: "bu iddia şu metne
    # dayanıyordu". Onaya bağlansaydı, onaylanmayan claim'lerin dayanağı yine
    # `source_url`den ibaret kalır ve faz kendi sorununu çözmezdi. Ağ kullanmadığı
    # için toplu promote'u da yavaşlatmıyor. Skora girmesi ayrı bir karardır ve
    # doğrulamaya bağlıdır (bkz. app/archive.py).
    archive.create_archive(conn, claim.id)
    return claim


def _existing_claim_id(conn, observation_id: str) -> str | None:
    """observation.promoted sadece eşiği GEÇEN durumu işaretliyor — eşiği geçmeyen bir
    observation'ı tekrar promote etmeye çalışmak (promoted hâlâ false) bu kontrolü atlayıp
    ikinci bir Claim daha üretebilirdi (idempotent değildi). Asıl garanti bu observation'ın
    zaten bir PRODUCED ilişkisi olup olmadığı — eşiği geçse de geçmese de."""
    row = fetch_one(
        conn.execute(
            "MATCH (:Observation {id: $oid})-[:PRODUCED]->(c:Claim) RETURN c.id AS id",
            {"oid": observation_id},
        )
    )
    return row["id"] if row else None


@router.post("/promote-batch", response_model=ObservationPromoteBatchResult)
def promote_observations_batch(payload: ObservationPromoteBatch) -> ObservationPromoteBatchResult:
    """Faz 16 (ikinci tur) — seçilen gözlemleri tek kararla promote eder.

    Kuyruğun ilk turu toplu ELEMEYİ ucuzlattı, promote kayıt başına kaldı: gerçek kuyrukta
    21 kayıt aynı kaynağa ve aynı entity'ye bağlanacaktı, yani aynı iki alan 21 kez
    onaylanacaktı — kapatılmaya çalışılan darboğazın küçültülmüş hali.

    **Kısmi başarısızlık normal ve görünür.** Bir kaydın atlanması (zaten claim üretmiş,
    kaynağı çözülememiş, entity bağı yok) diğerlerini durdurmuyor; her kaydın ne olduğu
    `items` içinde tek tek dönüyor. Sessizce yutulsaydı kullanıcı kuyruğa dönüp aradaki
    farkı kendi bulmak zorunda kalırdı."""
    conn = get_connection()
    ids = [i for i in dict.fromkeys(payload.observation_ids) if i]
    if not ids:
        return ObservationPromoteBatchResult(promoted=0, below_threshold=0, skipped=0)

    rows = fetch_all(
        conn.execute(
            f"MATCH (o:Observation) WHERE o.id IN $ids {_PRODUCED}{_FROM_EVIDENCE}"
            f"RETURN {_FIELDS_FULL}",
            {"ids": ids},
        )
    )
    found = {row["id"]: _observation_from_row(row) for row in rows}
    # Öneriler bağlam bir kez yüklenerek hesaplanıyor; kayıt başına graf sorgusu N+1 olurdu.
    suggestions = triage.suggestions_for(conn, list(found.values()))

    items: list[ObservationPromoteBatchItem] = []
    produced_any = False
    for observation_id in ids:
        observation = found.get(observation_id)
        if observation is None:
            items.append(
                ObservationPromoteBatchItem(
                    observation_id=observation_id, status="SKIPPED", headline="(bulunamadı)",
                    message="Gözlem bulunamadı.",
                )
            )
            continue

        head = claim_headline(observation.raw_content)
        suggestion = suggestions.get(observation_id, {})
        source_id = payload.source_id or suggestion.get("suggested_source_id")
        entity_id = payload.about_entity_id or suggestion.get("suggested_entity_id")

        if not source_id:
            items.append(
                ObservationPromoteBatchItem(
                    observation_id=observation_id, status="SKIPPED", headline=head,
                    message=(
                        "Kaynak çözülemedi: bu adres için kayıtlı bir Source yok "
                        f"({observation.source_url or 'adressiz'}). Kümeye tek bir kaynak seç "
                        "ya da kaynağı oluştur."
                    ),
                )
            )
            continue
        if payload.require_entity and not entity_id:
            items.append(
                ObservationPromoteBatchItem(
                    observation_id=observation_id, status="SKIPPED", headline=head,
                    message=(
                        "Entity bağı yok — bağlanmazsa claim yalıtık kalır (Memory Recall "
                        "bulamaz, vault notunda görünmez). Kümeye tek bir entity seç ya da bu "
                        "kaydı tek tek promote et."
                    ),
                )
            )
            continue

        try:
            # "Zaten claim üretmiş mi?" kontrolü ile üretim arasına başka bir promote
            # girmemeli (çift tıklama, iki sekme): ikisi de "yok" görüp iki claim yazıyordu.
            with graph_lock:
                existing = _existing_claim_id(conn, observation_id)
                if existing is None:
                    claim = _create_claim_from_observation(
                        conn,
                        observation,
                        ObservationPromote(source_id=source_id, about_entity_id=entity_id),
                    )
            if existing:
                items.append(
                    ObservationPromoteBatchItem(
                        observation_id=observation_id, status="SKIPPED", headline=head,
                        claim_id=existing,
                        message=f"Bu gözlemden zaten bir claim üretilmiş ({existing[:8]}…).",
                    )
                )
                continue
        except HTTPException as exc:
            # Bir kaydın reddi (ör. geçersiz kaynak id'si) kümenin geri kalanını durdurmamalı.
            items.append(
                ObservationPromoteBatchItem(
                    observation_id=observation_id, status="SKIPPED", headline=head,
                    message=str(exc.detail),
                )
            )
            continue

        produced_any = True
        above = claim.confidence >= PROMOTION_THRESHOLD
        items.append(
            ObservationPromoteBatchItem(
                observation_id=observation_id,
                status="PROMOTED" if above else "BELOW_THRESHOLD",
                headline=head,
                claim_id=claim.id,
                confidence=claim.confidence,
                # Eşik altı bir HATA değil: tek kaynaklı, doğrulanmamış bir claim'in
                # confidence'ı `0.40 × kaynak_güvenilirliği` olduğu için eşik (0.45) TEK
                # KAYNAKLA yapısal olarak erişilemez (mükemmel bir kaynak bile 0.40 verir).
                # Faz 16 ölçümü: 43 claim'in 42'si böyle. Mesaj bunu bir kayıp gibi
                # anlatmıyor, olması gereken durumu söylüyor.
                message=None if above else (
                    f"REPORTED olarak girdi (confidence {claim.confidence:.2f}) — tek kaynaklı "
                    "bir iddianın beklenen sonucu; ikinci bağımsız bir kaynak doğrulayınca yükselir."
                ),
            )
        )

    # Vault BİR kez, sonda. Kayıt başına render 36 kayıtta 36 tam re-render demekti.
    if produced_any:
        safe_render_vault(conn)

    return ObservationPromoteBatchResult(
        promoted=sum(1 for i in items if i.status == "PROMOTED"),
        below_threshold=sum(1 for i in items if i.status == "BELOW_THRESHOLD"),
        skipped=sum(1 for i in items if i.status == "SKIPPED"),
        items=items,
    )


@router.get("/{observation_id}", response_model=Observation)
def get_observation(observation_id: str) -> Observation:
    conn = get_connection()
    result = conn.execute(
        f"MATCH (o:Observation {{id: $id}}) {_PRODUCED}{_FROM_EVIDENCE}RETURN {_FIELDS_FULL}",
        {"id": observation_id},
    )
    row = fetch_one(result)
    if row is None:
        raise HTTPException(status_code=404, detail="Observation not found")
    return _observation_from_row(row)


@router.post("/{observation_id}/promote")
def promote_observation(observation_id: str, payload: ObservationPromote) -> dict:
    """Q1/Q8: ham observation değerlendirilir; deterministik confidence formülü eşiği
    (PROMOTION_THRESHOLD) geçerse Knowledge Graph'a (Claim olarak) yükselir ve
    observation.promoted=true işaretlenir. Geçmezse Observation ham haliyle kalır — silinmez.

    Faz 4 — OSINT Brain Memory Recall: about_entity_id/about_event_id verildiyse, YENİ claim
    oluşturulmadan ÖNCEKİ bilgi durumu ('daha önce ne biliyorduk') otomatik olarak dönülür,
    böylece kullanıcı/agent ayrı bir çağrı yapmak zorunda kalmadan geçmiş investigation/claim
    bağlamını görür (Research Relevance Recall dahil — investigation status'u ne olursa olsun
    listelenir).

    Faz 16: claim üretimi `_create_claim_from_observation`'a taşındı — toplu promote ile
    ORTAK. İki ayrı kopya olsaydı biri (ör. F26'daki contradicts/supersedes eksiği gibi)
    sessizce geride kalırdı; bu dosyanın geçmişi tam olarak o hatanın kaydı."""
    conn = get_connection()
    observation = get_observation(observation_id)

    # Kontrol ile üretim aynı kilit altında: çift tıklamada iki istek birden "claim yok"
    # görüp aynı gözlemden iki claim yazabiliyordu.
    with graph_lock:
        already_produced = _existing_claim_id(conn, observation_id)
        if already_produced:
            # F32: eski mesaj ("already processed") kullanıcıya hiçbir şey söylemiyordu — özellikle
            # eşiği geçmemiş bir promote sonrası, arayüz gözlemi hâlâ "işlenmemiş" gösterdiği için
            # tekrar denemek doğal bir davranıştı ve bu hata onu şaşırtıyordu.
            raise HTTPException(
                status_code=409,
                detail=(
                    "Bu gözlemden zaten bir claim üretilmiş "
                    f"(claim {already_produced[:8]}…). Confidence eşiği geçilmemiş olsa bile "
                    "claim graf'ta duruyor — aynı gözlemden ikinci bir claim üretilmez."
                ),
            )

        recall_before: dict | None = None
        if payload.about_entity_id:
            recall_before = {"about": "entity", "id": payload.about_entity_id, **entity_recall(conn, payload.about_entity_id)}
        elif payload.about_event_id:
            recall_before = {"about": "event", "id": payload.about_event_id, **event_recall(conn, payload.about_event_id)}

        claim = _create_claim_from_observation(conn, observation, payload)

    # Faz 11 (dogfooding F18): promote bir Claim üretiyor ama observations.py hiçbir yerde
    # vault render'ı tetiklemiyordu — diğer tüm yazma uçları tetikliyor. Sonuç: Obsidian'da
    # entity notu "bu entity hakkında henüz claim yok" demeye devam ediyordu.
    safe_render_vault(conn)

    final_claim = get_claim(claim.id)
    confidence_result = _gather_confidence_inputs(conn, claim.id)
    about_entity_id, about_event_id = _claim_about(conn, claim.id)
    reasons = compute_why_matters(conn, claim.id, {}, confidence_result, about_entity_id, about_event_id)

    return {
        "claim": final_claim.model_dump(mode="json"),
        "recall": recall_before,
        "why_matters": reasons,
    }
