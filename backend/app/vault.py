"""
Faz 9 — Living Brain: Obsidian Vault Sistemi.

`data/vault/`, KùzuDB Knowledge Graph'ın **deterministik bir render'ı**dır — ayrı bir hafıza
deposu DEĞİLDİR. AvenoxBeyin'in `flush.py`/`compile.py`'ı (LLM ile ham konuşmadan kavram
çıkarma) burada bilinçli olarak taşınmadı: OsintLab'de zaten KùzuDB'de confidence/provenance/
lineage'li bir ground truth var (Q4/Q6/Q12), vault sadece bunu Obsidian'da okunabilir hale
getiriyor. Hiçbir not içeriği LLM'den geçmez — hepsi graph sorgularından doğrudan üretilir
(bkz. docs/Roadmap.md Faz 9 karar notu).

Entity/Event/Investigation/Source klasörleri her render'da SIFIRDAN yeniden yazılır (silinip
yeniden oluşturulur) — bir isim değiştiğinde (ör. Entity PATCH ile yeniden adlandırılırsa)
eski slug'lı dosyanın vault'ta öksüz kalmaması için. `daily/` bunun dışında: append-only,
session-end hook'u tarafından güncellenir (bkz. .claude/hooks/vault-session-end.ps1).
"""
import re
import shutil
import sys
from pathlib import Path

from app.db import DATA_ROOT, fetch_all, fetch_one
from app.recall import same_as_group

# `OSINTLAB_DATA_DIR` ile taşınabilir (db.py'deki DATA_ROOT). Faz 16'da düzeltildi: sabit
# proje yolu, izole bir veri köküyle çalıştırılan bir test koşusunun GERÇEK vault'u baştan
# yazmasına yol açtı — ki DATA_ROOT tam olarak bunu önlemek için (Faz 13'ün canlı dersiyle)
# eklenmişti, ama vault ve daily/ kapsam dışında kalmıştı.
VAULT_DIR = DATA_ROOT / "vault"

_ACTIVE_INVESTIGATION_STATUSES = ("OPEN", "ACTIVE", "PAUSED")

# Confidence Spectrum — frontend'deki (docs/Design.md) etiketlerin markdown karşılığı. Emoji
# kullanılmıyor (proje ikonografi kuralı: SVG/metin, emoji yok) — düz metin etiket + yüzde.
CONFIDENCE_LABEL_TR = {
    "UNKNOWN": "BİLİNMİYOR",
    "OBSERVED": "GÖZLEMLENDİ",
    "REPORTED": "BİLDİRİLDİ",
    "SUPPORTED": "DESTEKLENİYOR",
    "CORROBORATED": "DOĞRULANDI",
    "HIGH_CONFIDENCE": "YÜKSEK GÜVEN",
    "CONTRADICTED": "ÇELİŞKİLİ",
}

_SLUG_STRIP_RE = re.compile(r"[^\w\s-]", re.UNICODE)
_SLUG_WS_RE = re.compile(r"[\s_]+")
_TR_MAP = str.maketrans("çÇğĞıİöÖşŞüÜ", "cCgGiIoOsSuU")


def _slugify(text: str) -> str:
    text = text.translate(_TR_MAP).strip().lower()
    text = _SLUG_STRIP_RE.sub("", text)
    text = _SLUG_WS_RE.sub("-", text).strip("-")
    return text[:60] or "untitled"


def note_stem(node_id: str, name: str) -> str:
    """Dosya adı (uzantısız) — slug + id'nin ilk 8 hanesi, aynı isimli iki node çakışmasın."""
    return f"{_slugify(name)}--{node_id[:8]}"


def wikilink(subdir: str, node_id: str, name: str) -> str:
    return f"[[{subdir}/{note_stem(node_id, name)}|{name}]]"


def confidence_tag(state: str | None, confidence: float | None = None) -> str:
    if not state:
        return ""
    label = CONFIDENCE_LABEL_TR.get(state, state)
    if confidence is not None:
        return f"**[{label} · %{round(confidence * 100)}]**"
    return f"**[{label}]**"


def _yaml_scalar(value) -> str:
    if value is None:
        return '""'
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    s = str(value)
    s = s.replace('"', '\\"')
    return f'"{s}"'


def _frontmatter(fields: dict) -> str:
    lines = ["---"]
    for key, value in fields.items():
        if isinstance(value, (list, tuple)):
            if value:
                lines.append(f"{key}:")
                lines.extend(f"  - {_yaml_scalar(v)}" for v in value)
            else:
                lines.append(f"{key}: []")
        else:
            lines.append(f"{key}: {_yaml_scalar(value)}")
    lines.append("---")
    return "\n".join(lines)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _reset_dir(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------
# Veri toplama — her tip için graph'tan gerekli her şeyi tek yerde çeker.
# --------------------------------------------------------------------------

def first_line(text: str) -> str:
    """Claim metninin okunabilir ilk satırı (RSS başlığı). Boş satırlar atlanır — F19'un
    bulduğu şey buydu: metin çok satırlı ve ham hali Markdown listesini kırıyor."""
    for line in (text or "").splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return "(boş claim)"


def claim_bullet(text: str, tag: str, src: str | None = None) -> str:
    """Bir Claim'i okunabilir tek bir Markdown maddesine çevirir.

    Faz 11 (dogfooding F19): claim metni çok satırlıdır (RSS'ten gelen başlık + özet).
    Doğrudan `- {text}` olarak basılınca içindeki boş satır Markdown listesini KIRIYOR —
    Obsidian'da madde yapısı dağılıyor, ikinci paragraf listenin dışına düşüyordu.

    Artık: ilk satır kalın başlık + güven etiketi + kaynak, kalanı girintili devam satırı."""
    parts = [line.strip() for line in text.splitlines() if line.strip()]
    head = parts[0] if parts else "(boş claim)"
    rest = " ".join(parts[1:])
    line = f"- **{head}** · {tag}"
    if src:
        line += f" — Kaynak: {src}"
    if rest:
        line += f"\n  {rest}"
    return line


def _claim_contradictions(conn, claim_id: str) -> list[str]:
    """Faz 11 (dogfooding F27, vault ayağı): notta bir claim'in ÇELİŞKİLİ olduğunu görmek,
    neyle çeliştiğini bilmeden işe yaramıyor. why-matters ucunda kapatıldı ama vault ayrı bir
    renderer — Living Brain'in (Faz 9) okunabilir olması bunu orada da göstermeyi gerektiriyor.

    İlişki graf'ta tek yön saklanır, anlamı simetriktir: iki yön de taranır."""
    heads: list[str] = []
    seen: set[str] = set()
    for pattern in (
        "MATCH (c:Claim {id: $id})-[r:CLAIM_CONTRADICTS]->(o:Claim) ",
        "MATCH (o:Claim)-[r:CLAIM_CONTRADICTS]->(c:Claim {id: $id}) ",
    ):
        for row in fetch_all(
            conn.execute(
                pattern + "WHERE r.status = 'UNRESOLVED' RETURN o.id AS id, o.text AS text",
                {"id": claim_id},
            )
        ):
            if row["id"] in seen:
                continue
            seen.add(row["id"])
            parts = [ln.strip() for ln in (row["text"] or "").splitlines() if ln.strip()]
            heads.append(parts[0][:100] if parts else "(boş claim)")
    return heads


def _entity_claims(conn, entity_id: str) -> list[dict]:
    return fetch_all(
        conn.execute(
            # F34: yerini almış claim vault notunda da işaretlenmeli — Living Brain'de eskimiş
            # bilginin güncelinden ayırt edilememesi, notu okuyanı yanıltır.
            "MATCH (s:Source)-[:ASSERTS]->(c:Claim)-[:ABOUT_ENTITY]->(:Entity {id: $id}) "
            "OPTIONAL MATCH (yeni:Claim)-[:SUPERSEDES]->(c) "
            "RETURN c.id AS id, c.text AS text, c.knowledge_state AS knowledge_state, "
            "c.confidence AS confidence, s.id AS source_id, s.name AS source_name, "
            "yeni.id AS superseded_by_claim_id ORDER BY c.created_at",
            {"id": entity_id},
        )
    )


def _entity_events(conn, entity_id: str) -> list[dict]:
    return fetch_all(
        conn.execute(
            "MATCH (:Entity {id: $id})-[r:INVOLVED_IN]->(e:Event) "
            "RETURN e.id AS id, e.title AS title, r.role AS role ORDER BY e.created_at",
            {"id": entity_id},
        )
    )


def _entity_investigations(conn, entity_id: str) -> list[dict]:
    return fetch_all(
        conn.execute(
            "MATCH (i:Investigation)-[:INCLUDES]->(:Entity {id: $id}) "
            "RETURN i.id AS id, i.title AS title, i.status AS status ORDER BY i.created_at",
            {"id": entity_id},
        )
    )


def _entity_relations(conn, entity_id: str) -> list[dict]:
    # Faz 10: ENTITY_RELATION artık yazılıyor (bkz. routers/entities.py). SUPERSEDED
    # kenarlar (silinmiş/eskimiş ilişkiler) vault notunda görünmemeli.
    #
    # Faz 19: GELEN kenarlar da eklendi. Kenar tek yön saklanıyor ("OpenAI -geliştirdi->
    # Astra") ama not iki uçta da okunuyor — yalnızca giden yön render edilseydi Astra'nın
    # notu, OpenAI'ın notundan görülebilen bir ilişkiyi göstermezdi. Bağlantılı düşünmeyi
    # taşıyan şey wikilink'ler; tek yönlü bir wikilink Obsidian graph'ında kopuk bir uç
    # bırakırdı. Yön `direction` ile korunuyor: "geliştirdi" ile "geliştirildi" aynı şey değil.
    outgoing = fetch_all(
        conn.execute(
            "MATCH (:Entity {id: $id})-[r:ENTITY_RELATION]->(other:Entity) "
            "WHERE r.status <> 'SUPERSEDED' "
            "RETURN other.id AS id, other.name AS name, r.relation_type AS relation_type, "
            "r.valid_from AS valid_from, 'OUTGOING' AS direction",
            {"id": entity_id},
        )
    )
    incoming = fetch_all(
        conn.execute(
            "MATCH (other:Entity)-[r:ENTITY_RELATION]->(:Entity {id: $id}) "
            "WHERE r.status <> 'SUPERSEDED' "
            "RETURN other.id AS id, other.name AS name, r.relation_type AS relation_type, "
            "r.valid_from AS valid_from, 'INCOMING' AS direction",
            {"id": entity_id},
        )
    )
    return sorted(outgoing + incoming, key=lambda r: r["valid_from"])


def _entity_mentions(conn, entity_id: str) -> list[dict]:
    """Faz 21: `MENTIONS` — claim'in DEĞDİĞİ entity'ler, öznesi değil. Sadece CONFIRMED
    olanlar render edilir; reddedilmiş öneri graf'ta karar kaydı olarak durur ama Living
    Brain'de görünmemeli."""
    return fetch_all(
        conn.execute(
            "MATCH (c:Claim)-[m:MENTIONS]->(:Entity {id: $id}) WHERE m.status = 'CONFIRMED' "
            "OPTIONAL MATCH (c)-[:ABOUT_ENTITY]->(subject:Entity) "
            "OPTIONAL MATCH (c)-[:ABOUT_EVENT]->(event:Event) "
            "RETURN c.id AS id, c.text AS text, c.knowledge_state AS knowledge_state, "
            "c.confidence AS confidence, subject.id AS subject_entity_id, "
            "subject.name AS subject_entity_name, event.id AS about_event_id, "
            "event.title AS about_event_title ORDER BY c.created_at DESC",
            {"id": entity_id},
        )
    )


def _entity_monitor(conn, entity_id: str) -> dict | None:
    return fetch_one(
        conn.execute(
            "MATCH (m:Monitor {target_type: 'Entity', target_id: $id, active: true}) "
            "RETURN m.id AS id, m.label AS label",
            {"id": entity_id},
        )
    )


def render_entity_note(conn, entity: dict) -> str:
    # F31: onaylanmış SAME_AS vault'ta da görünmeli — aksi halde Living Brain'de iki ayrı not
    # durmaya devam eder ve birleştirme okuyucu için hiç olmamış gibidir.
    same_as = same_as_group(conn, entity["id"])
    claims = _entity_claims(conn, entity["id"])
    events = _entity_events(conn, entity["id"])
    investigations = _entity_investigations(conn, entity["id"])
    relations = _entity_relations(conn, entity["id"])
    monitor = _entity_monitor(conn, entity["id"])
    # Faz 21: adı geçen ama öznesi olmadığı claim'ler. Vault'ta ayrı bir başlık altında,
    # çünkü ikisini karıştırmak "bu entity hakkında 5 iddia var" yanılgısı üretirdi —
    # oysa değme, iddianın o entity HAKKINDA olduğu anlamına gelmez.
    mentions = _entity_mentions(conn, entity["id"])

    fm = _frontmatter({
        "id": entity["id"],
        "type": "Entity",
        "entity_type": entity["entity_type"],
        "aliases": entity["aliases"] or [],
        "created_at": str(entity["created_at"]),
        "monitored": monitor is not None,
    })

    lines = [fm, "", f"# {entity['name']}", ""]
    lines.append(f"**Tür:** {entity['entity_type']}")
    if entity["aliases"]:
        lines.append(f"**Alias'lar:** {', '.join(entity['aliases'])}")
    lines.append(f"**İzleniyor:** {'Evet' if monitor else 'Hayır'}")
    lines.append("")

    if same_as:
        lines.append("## Aynı kayıt (onaylanmış)")
        for other in same_as:
            lines.append(f"- {wikilink('entities', other['id'], other['name'])} ({other['entity_type']})")
        lines.append("")
        lines.append(
            "_Kayıtlar birleştirilmedi, silinmedi — aynı oldukları onaylandı "
            "(History Is Immutable). Aşağıdaki claim'ler yalnızca bu kaydın kendisine aittir; "
            "birleşik görünüm için arayüzdeki entity sayfasına bak._"
        )
        lines.append("")

    lines.append("## Known Relationships")
    if relations:
        for r in relations:
            if r["direction"] == "OUTGOING":
                lines.append(f"- {r['relation_type']} → {wikilink('entities', r['id'], r['name'])}")
            else:
                lines.append(f"- {wikilink('entities', r['id'], r['name'])} → {r['relation_type']} → bu kayıt")
    else:
        lines.append("_Henüz kaydedilmiş bir ilişki yok._")
    lines.append("")

    lines.append("## Event'ler")
    if events:
        for e in events:
            role = f" ({e['role']})" if e.get("role") else ""
            lines.append(f"- {wikilink('events', e['id'], e['title'])}{role}")
    else:
        lines.append("_Bu entity henüz bir event'e karışmadı._")
    lines.append("")

    lines.append("## Claim'ler")
    if claims:
        for c in claims:
            tag = confidence_tag(c["knowledge_state"], c["confidence"])
            src = wikilink("sources", c["source_id"], c["source_name"]) if c["source_id"] else "?"
            lines.append(claim_bullet(c["text"], tag, src))
            if c.get("superseded_by_claim_id"):
                lines.append("  - ⏳ Bu bilginin yerini daha yenisi aldı (silinmedi, arşivde).")
            # F27: "ÇELİŞKİLİ" etiketi tek başına eksik bilgi — karşı taraf da yazılır.
            for other in _claim_contradictions(conn, c["id"]):
                lines.append(f"  - ⚔ Çelişiyor: «{other}»")
    else:
        lines.append("_Bu entity hakkında henüz claim yok._")
    lines.append("")

    lines.append("## Adı Geçen Claim'ler")
    if mentions:
        lines.append(
            "_Bu claim'ler bu kayıt HAKKINDA değil, ona DEĞİYOR — adı metinde geçiyor. "
            "Öznesi olduğu iddialar yukarıdaki bölümde._"
        )
        for m in mentions:
            tag = confidence_tag(m["knowledge_state"], m["confidence"])
            about = ""
            if m.get("subject_entity_id"):
                about = f" — öznesi: {wikilink('entities', m['subject_entity_id'], m['subject_entity_name'])}"
            elif m.get("about_event_id"):
                about = f" — olay: {wikilink('events', m['about_event_id'], m['about_event_title'])}"
            lines.append(f"- **{first_line(m['text'])}** · {tag}{about}")
    else:
        lines.append("_Bu kaydın adı başka bir claim'de geçmiyor._")
    lines.append("")

    lines.append("## Investigation'lar")
    if investigations:
        for i in investigations:
            lines.append(f"- {wikilink('investigations', i['id'], i['title'])} ({i['status']})")
    else:
        lines.append("_Bu entity bir investigation'a dahil değil._")
    lines.append("")

    return "\n".join(lines)


def _event_claims(conn, event_id: str) -> list[dict]:
    return fetch_all(
        conn.execute(
            "MATCH (s:Source)-[:ASSERTS]->(c:Claim)-[:ABOUT_EVENT]->(:Event {id: $id}) "
            "RETURN c.id AS id, c.text AS text, c.knowledge_state AS knowledge_state, "
            "c.confidence AS confidence, s.id AS source_id, s.name AS source_name "
            "ORDER BY c.created_at",
            {"id": event_id},
        )
    )


def _event_entities(conn, event_id: str) -> list[dict]:
    return fetch_all(
        conn.execute(
            "MATCH (e:Entity)-[r:INVOLVED_IN]->(:Event {id: $id}) "
            "RETURN e.id AS id, e.name AS name, r.role AS role ORDER BY e.name",
            {"id": event_id},
        )
    )


def _event_investigations(conn, event_id: str) -> list[dict]:
    return fetch_all(
        conn.execute(
            "MATCH (i:Investigation)-[:INVESTIGATES]->(:Event {id: $id}) "
            "RETURN i.id AS id, i.title AS title, i.status AS status ORDER BY i.created_at",
            {"id": event_id},
        )
    )


def render_event_note(conn, event: dict) -> str:
    claims = _event_claims(conn, event["id"])
    entities = _event_entities(conn, event["id"])
    investigations = _event_investigations(conn, event["id"])

    fm = _frontmatter({
        "id": event["id"],
        "type": "Event",
        "event_type": event["event_type"],
        "location": event["location"],
        "occurred_at": str(event["occurred_at"]) if event["occurred_at"] else None,
        "knowledge_state": event["knowledge_state"],
        "confidence": event["confidence"],
        "created_at": str(event["created_at"]),
    })

    lines = [fm, "", f"# {event['title']}", ""]
    lines.append(f"**Tür:** {event['event_type']} {confidence_tag(event['knowledge_state'], event['confidence'])}")
    if event["location"]:
        lines.append(f"**Konum:** {event['location']}")
    if event["occurred_at"]:
        lines.append(f"**Zaman:** {event['occurred_at']}")
    lines.append("")

    lines.append("## Entity'ler")
    if entities:
        for e in entities:
            role = f" ({e['role']})" if e.get("role") else ""
            lines.append(f"- {wikilink('entities', e['id'], e['name'])}{role}")
    else:
        lines.append("_Henüz bir entity bağlanmadı._")
    lines.append("")

    lines.append("## Claim'ler")
    if claims:
        for c in claims:
            tag = confidence_tag(c["knowledge_state"], c["confidence"])
            src = wikilink("sources", c["source_id"], c["source_name"]) if c["source_id"] else "?"
            lines.append(claim_bullet(c["text"], tag, src))
    else:
        lines.append("_Bu event hakkında henüz claim yok._")
    lines.append("")

    lines.append("## Investigation'lar")
    if investigations:
        for i in investigations:
            lines.append(f"- {wikilink('investigations', i['id'], i['title'])} ({i['status']})")
    else:
        lines.append("_Bu event bir investigation'a dahil değil._")
    lines.append("")

    return "\n".join(lines)


def _investigation_findings(conn, inv_id: str) -> list[dict]:
    rows = fetch_all(
        conn.execute(
            "MATCH (i:Investigation {id: $id})-[:HAS_FINDING]->(c:Claim) "
            "RETURN c.id AS id, c.text AS text, c.knowledge_state AS knowledge_state, "
            "c.confidence AS confidence",
            {"id": inv_id},
        )
    )
    validated_ids = {
        r["id"]
        for r in fetch_all(
            conn.execute(
                "MATCH (:Investigation {id: $id})-[:VALIDATED_FINDING]->(c:Claim) RETURN c.id AS id",
                {"id": inv_id},
            )
        )
    }
    for r in rows:
        r["validated"] = r["id"] in validated_ids
    return rows


def _investigation_hypotheses(conn, inv_id: str) -> list[dict]:
    return fetch_all(
        conn.execute(
            "MATCH (:Investigation {id: $id})-[:HAS_HYPOTHESIS]->(h:Hypothesis) "
            "RETURN h.id AS id, h.text AS text, h.status AS status ORDER BY h.created_at",
            {"id": inv_id},
        )
    )


def _investigation_entities(conn, inv_id: str) -> list[dict]:
    return fetch_all(
        conn.execute(
            "MATCH (:Investigation {id: $id})-[:INCLUDES]->(e:Entity) "
            "RETURN e.id AS id, e.name AS name ORDER BY e.name",
            {"id": inv_id},
        )
    )


def _investigation_events(conn, inv_id: str) -> list[dict]:
    return fetch_all(
        conn.execute(
            "MATCH (:Investigation {id: $id})-[:INVESTIGATES]->(e:Event) "
            "RETURN e.id AS id, e.title AS title ORDER BY e.title",
            {"id": inv_id},
        )
    )


def render_investigation_note(conn, inv: dict) -> str:
    findings = _investigation_findings(conn, inv["id"])
    hypotheses = _investigation_hypotheses(conn, inv["id"])
    entities = _investigation_entities(conn, inv["id"])
    events = _investigation_events(conn, inv["id"])

    fm = _frontmatter({
        "id": inv["id"],
        "type": "Investigation",
        "status": inv["status"],
        "created_at": str(inv["created_at"]),
        "updated_at": str(inv["updated_at"]),
    })

    lines = [fm, "", f"# {inv['title']}", ""]
    lines.append(f"**Durum:** {inv['status']}")
    lines.append(f"**Research Question:** {inv['research_question']}")
    lines.append("")

    lines.append("## Entity'ler")
    if entities:
        lines.append(", ".join(wikilink("entities", e["id"], e["name"]) for e in entities))
    else:
        lines.append("_Henüz entity dahil edilmedi._")
    lines.append("")

    lines.append("## Event'ler")
    if events:
        lines.append(", ".join(wikilink("events", e["id"], e["title"]) for e in events))
    else:
        lines.append("_Henüz event dahil edilmedi._")
    lines.append("")

    # Faz 13 (madde 30): Analiz ve Sonuç. Bunları vault'a yazmamak, tam da bu projenin
    # tekrar eden hatası olurdu — araştırmanın CEVABI yalnızca web arayüzünde kalırdı,
    # Obsidian'daki "beyin" ise soruyu bilip cevabı bilmezdi.
    lines.append("## Analiz")
    lines.append(inv.get("analysis") or "_Henüz analiz yazılmadı._")
    lines.append("")

    lines.append("## Findings")
    if findings:
        for f in findings:
            tag = confidence_tag(f["knowledge_state"], f["confidence"])
            validated = " **[validated]**" if f["validated"] else ""
            # Faz 11 (F43): burada ham `f['text']` basılıyordu — claim metni çok satırlı
            # (RSS başlığı + özet) olduğu için içindeki boş satır Markdown listesini KIRIYOR
            # ve güven etiketi gövdenin sonuna düşüyordu. F19 tam olarak bu hatayı entity
            # notlarında `claim_bullet()` ile düzeltmişti; bu kod yolu güncellenmemişti.
            lines.append(claim_bullet(f["text"], f"{tag}{validated}"))
    else:
        lines.append("_Henüz finding eklenmedi._")
    lines.append("")

    lines.append("## Sonuç")
    if inv.get("conclusion"):
        lines.append(inv["conclusion"])
    elif inv["status"] == "ARCHIVED":
        lines.append("_Sonuç yazılmadan arşivlendi._")
    else:
        lines.append("_Henüz sonuç yazılmadı._")
    lines.append("")

    lines.append("## Hipotezler")
    if hypotheses:
        for h in hypotheses:
            # F43: hipotez metni de çok satırlı yazılabilir — aynı kırılma riski.
            lines.append(claim_bullet(h["text"], f"**{h['status']}**"))
    else:
        lines.append("_Henüz hipotez yok._")
    lines.append("")

    return "\n".join(lines)


def _source_lineage(conn, source_id: str):
    from app.lineage import resolve_independent_root

    ancestors = fetch_all(
        conn.execute(
            "MATCH (:Source {id: $id})-[:DERIVED_FROM*1..10]->(a:Source) "
            "RETURN DISTINCT a.id AS id, a.name AS name",
            {"id": source_id},
        )
    )
    descendants = fetch_all(
        conn.execute(
            "MATCH (d:Source)-[:DERIVED_FROM*1..10]->(:Source {id: $id}) "
            "RETURN DISTINCT d.id AS id, d.name AS name",
            {"id": source_id},
        )
    )
    root_id = resolve_independent_root(conn, source_id)
    return ancestors, descendants, root_id


def _source_claims(conn, source_id: str) -> list[dict]:
    return fetch_all(
        conn.execute(
            "MATCH (:Source {id: $id})-[:ASSERTS]->(c:Claim) "
            "RETURN c.id AS id, c.text AS text, c.knowledge_state AS knowledge_state, "
            "c.confidence AS confidence ORDER BY c.created_at",
            {"id": source_id},
        )
    )


def render_source_note(conn, source: dict) -> str:
    ancestors, descendants, root_id = _source_lineage(conn, source["id"])
    claims = _source_claims(conn, source["id"])

    fm = _frontmatter({
        "id": source["id"],
        "type": "Source",
        "source_type": source["source_type"],
        "url": source["url"],
        "reliability": source["reliability"],
        "created_at": str(source["created_at"]),
        "independent_root_id": root_id,
    })

    lines = [fm, "", f"# {source['name']}", ""]
    lines.append(f"**Tür:** {source['source_type']} · **Güvenilirlik:** {source['reliability']}")
    if source["url"]:
        lines.append(f"**URL:** {source['url']}")
    lines.append("")

    lines.append("## Otomatik Tarama")
    schedules = fetch_all(
        conn.execute(
            "MATCH (sc:ScanSchedule)-[:SCANS_SOURCE]->(src:Source {id: $id}) "
            "RETURN sc.url AS url, sc.mode AS mode, sc.interval_minutes AS interval_minutes, "
            "sc.active AS active, sc.last_run_at AS last_run_at, sc.last_status AS last_status, "
            "sc.last_error AS last_error, sc.last_new_count AS last_new_count "
            "ORDER BY sc.created_at",
            {"id": source["id"]},
        )
    )
    if schedules:
        for sc in schedules:
            state = "aktif" if sc["active"] else "kapalı"
            hours = sc["interval_minutes"] / 60
            freq = f"{hours:g} saatte bir" if hours >= 1 else f"{sc['interval_minutes']} dakikada bir"
            line = f"- `{sc['url']}` ({sc['mode']}) — {freq}, {state}"
            if sc["last_run_at"]:
                line += f" · son koşu {sc['last_run_at']}"
                if sc["last_status"] == "OK":
                    line += f", {sc['last_new_count']} yeni gözlem"
                else:
                    # Hata mesajını notta göstermek şart: sessizce ölen bir tarama, hiç
                    # kurulmamış olmaktan kötü (kullanıcı izlendiğini sanır).
                    line += f", **HATA**: {sc['last_error']}"
            else:
                line += " · henüz çalışmadı"
            lines.append(line)
    else:
        lines.append("_Bu kaynak için zamanlanmış tarama yok._")
    lines.append("")

    lines.append("## Lineage (Source Independence)")
    if ancestors:
        lines.append("**Türediği kaynaklar (upstream):** " + ", ".join(wikilink("sources", a["id"], a["name"]) for a in ancestors))
    if descendants:
        lines.append("**Bundan türeyenler (downstream):** " + ", ".join(wikilink("sources", d["id"], d["name"]) for d in descendants))
    if not ancestors and not descendants:
        lines.append("_Bilinen bir lineage ilişkisi yok — bağımsız kaynak._")
    lines.append("")

    lines.append("## Bu kaynağın attığı Claim'ler")
    if claims:
        for c in claims:
            tag = confidence_tag(c["knowledge_state"], c["confidence"])
            lines.append(claim_bullet(c["text"], tag))
    else:
        lines.append("_Bu kaynak henüz bir claim atfetmedi._")
    lines.append("")

    return "\n".join(lines)


def _inbox_new_items(conn) -> list[dict]:
    return fetch_all(
        conn.execute(
            "MATCH (n:InboxItem {status: 'NEW'}) "
            "RETURN n.id AS id, n.item_type AS item_type, n.priority AS priority, "
            "n.title AS title, n.detail AS detail, n.target_type AS target_type, "
            "n.target_id AS target_id, n.created_at AS created_at ORDER BY n.created_at DESC",
            {},
        )
    )


def _one_line(value: str) -> str:
    """Saklanan bir metni tek satıra indirger.

    Faz 12 sonrası bulgu (F57): `InboxItem.title` SAKLANAN bir alan ve eski kayıtlarda çok
    satırlı olabiliyor (F46'nın düzeltilmesinden önce yazılmış "Yeni claim: <ham metin>"
    başlıkları). İçindeki boş satır Obsidian'da Markdown listesini ortadan KIRIYORDU. Bugünkü
    kod artık `claim_headline` kullanıyor, ama geçmiş kayıtlar düzelmiyor — ve düzelmemeli
    (History Is Immutable). Doğru yer render tarafı: burası saklanan metnin tek satır
    olduğunu VARSAYMAMALI."""
    return " ".join((value or "").split())


# Faz 12: Source da izlenebilir bir hedef oldu (zamanlanmış tarama bildirimleri).
_TARGET_SUBDIR = {"Entity": "entities", "Event": "events", "Investigation": "investigations", "Source": "sources"}
_PRIORITY_ORDER = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")


def _target_link(conn, target_type: str, target_id: str) -> str:
    subdir = _TARGET_SUBDIR.get(target_type)
    if not subdir:
        return target_id
    label_field = "name" if target_type in ("Entity", "Source") else "title"
    row = fetch_one(
        conn.execute(
            f"MATCH (t:{target_type} {{id: $id}}) RETURN t.{label_field} AS label", {"id": target_id}
        )
    )
    if row is None:
        return target_id
    return wikilink(subdir, target_id, row["label"])


def _inbox_headlines(item: dict, limit: int = 5) -> list[str]:
    """Tarama bildiriminin taşıdığı başlıklar (varsa). Bunlar zaten `detail`de duruyordu ama
    vault hiç okumuyordu — "yazılıyor ama okunmuyor" kalıbının bir örneği daha."""
    import json as _json

    try:
        detail = _json.loads(item.get("detail") or "{}")
    except ValueError:
        return []
    headlines = detail.get("headlines")
    if not isinstance(headlines, list):
        return []
    return [h for h in headlines[:limit] if isinstance(h, str)]


def render_inbox_note(conn) -> str:
    items = _inbox_new_items(conn)
    by_priority: dict[str, list[dict]] = {p: [] for p in _PRIORITY_ORDER}
    for item in items:
        by_priority.setdefault(item["priority"], []).append(item)

    lines = ["# Intelligence Inbox", "", "_Sadece status=NEW öğeler — bkz. web UI'da tam geçmiş için `/inbox`._", ""]
    for priority in _PRIORITY_ORDER:
        bucket = by_priority.get(priority, [])
        if not bucket:
            continue
        lines.append(f"## {priority}")
        for item in bucket:
            link = _target_link(conn, item["target_type"], item["target_id"])
            # Faz 12 sonrası bulgu (F56): aynı kaynaktan gelen iki tarama bildirimi burada
            # birebir aynı satır olarak görünüyordu ("Security Affairs: 2 yeni içerik" iki
            # kez) — farklı koşular, farklı gözlemler, ama Obsidian'da ayırt edilemiyordu.
            # Web arayüzü başlıkları satırın altında gösterdiği için orada ayrışıyordu; vault
            # ise yalnızca başlığı basıyordu. Saat + gelen içeriğin başlıkları eklendi.
            # Yerel saat, UTC değil: vault'u okuyan insan Obsidian'da otururken web
            # arayüzü de yerel saat gösteriyor. Aynı olayın iki yerde farklı saatle
            # görünmesi, F47'nin düzelttiği belirsizliğin aynısı olurdu. (Tek kullanıcılı,
            # local-first bir araç — makinenin yerel saati kullanıcının saati.)
            stamp = item["created_at"].astimezone().strftime("%H:%M")
            lines.append(f"- `{stamp}` **{item['item_type']}** — {_one_line(item['title'])} — {link}")
            for headline in _inbox_headlines(item):
                lines.append(f"    - {_one_line(headline)}")
        lines.append("")
    if not items:
        lines.append("_Inbox boş._")

    return "\n".join(lines)


def render_dashboard_note(conn) -> str:
    from datetime import datetime, timezone

    counts = {
        "Entity": fetch_one(conn.execute("MATCH (n:Entity) RETURN count(n) AS c"))["c"],
        "Event": fetch_one(conn.execute("MATCH (n:Event) RETURN count(n) AS c"))["c"],
        "Source": fetch_one(conn.execute("MATCH (n:Source) RETURN count(n) AS c"))["c"],
        "Claim": fetch_one(conn.execute("MATCH (n:Claim) RETURN count(n) AS c"))["c"],
        "Investigation": fetch_one(conn.execute("MATCH (n:Investigation) RETURN count(n) AS c"))["c"],
    }
    active_investigations = fetch_all(
        conn.execute(
            "MATCH (i:Investigation) WHERE i.status IN $statuses "
            "RETURN i.id AS id, i.title AS title, i.status AS status ORDER BY i.updated_at DESC",
            {"statuses": list(_ACTIVE_INVESTIGATION_STATUSES)},
        )
    )
    high_priority_inbox = fetch_all(
        conn.execute(
            "MATCH (n:InboxItem {status: 'NEW'}) WHERE n.priority IN ['CRITICAL', 'HIGH'] "
            "RETURN n.title AS title, n.priority AS priority ORDER BY n.created_at DESC LIMIT 10"
        )
    )

    queue_stats = _queue_stats(conn)

    lines = ["# OsintLab — Dashboard", ""]
    lines.append(f"_Son render: {datetime.now(timezone.utc).isoformat()}_")
    lines.append("")
    lines.append("## Genel Durum")
    lines.append(
        f"- {counts['Entity']} Entity · {counts['Event']} Event · {counts['Source']} Source · "
        f"{counts['Claim']} Claim · {counts['Investigation']} Investigation "
        f"({len(active_investigations)} aktif)"
    )
    lines.append("")
    # Faz 16 — kuyruk derinliği Obsidian'da da görünsün. Vault, grafın deterministik
    # render'ı; "sistem bir şey biriktiriyor ama kimse değerlendirmiyor" hâlini burada da
    # görebilmek, kuyruğun tekrar sessizce şişmesini önleyen ikinci gözdür.
    lines.append("## Değerlendirme Kuyruğu")
    if queue_stats["pending"]:
        # "0 gündür bekliyor" bir bilgi değil gürültü; ibare ancak gerçekten günler geçmişse anlamlı.
        days = queue_stats["oldest_days"]
        oldest = f", en eskisi {days} gündür bekliyor" if days else ""
        lines.append(
            f"- **{queue_stats['pending']}** gözlem promote kararı bekliyor{oldest}."
        )
        lines.append(f"- {queue_stats['dismissed']} gözlem değerlendirilip elendi (silinmedi).")
    else:
        lines.append("_Bekleyen gözlem yok — biriken her kayıt değerlendirilmiş._")
    lines.append("")
    lines.append("## Açık Investigation'lar")
    if active_investigations:
        for i in active_investigations:
            lines.append(f"- {wikilink('investigations', i['id'], i['title'])} ({i['status']})")
    else:
        lines.append("_Açık investigation yok._")
    lines.append("")
    lines.append("## Yüksek Öncelikli Bekleyen Inbox Öğeleri")
    if high_priority_inbox:
        for item in high_priority_inbox:
            lines.append(f"- [{item['priority']}] {item['title']}")
    else:
        lines.append("_CRITICAL/HIGH öncelikli bekleyen bir şey yok._")
    lines.append("")
    lines.append("## Son Oturumda Ne Değişti")
    lines.append("_Bkz. [[daily/" + datetime.now(timezone.utc).date().isoformat() + "]] — session-end hook'u tarafından güncellenir._")
    lines.append("")

    return "\n".join(lines)


def _queue_stats(conn) -> dict:
    """Dashboard notu için kuyruk derinliği. `triage.build_queue`'nun tamamını çağırmıyoruz:
    orası her gözlemi entity tablosuna karşı eşleştiriyor ve vault her yazma ucundan sonra
    yeniden render ediliyor — sayaç için o maliyet gereksiz."""
    from datetime import datetime, timezone

    pending = fetch_all(
        conn.execute(
            "MATCH (o:Observation) WHERE o.promoted = false "
            "AND (o.dismissed IS NULL OR o.dismissed = false) "
            "OPTIONAL MATCH (o)-[:PRODUCED]->(c:Claim) "
            "RETURN o.created_at AS created_at, c.id AS claim_id"
        )
    )
    waiting = [row["created_at"] for row in pending if not row["claim_id"]]
    dismissed = fetch_one(
        conn.execute("MATCH (o:Observation) WHERE o.dismissed = true RETURN count(o) AS n")
    )["n"]
    oldest = min(waiting, default=None)
    return {
        "pending": len(waiting),
        "dismissed": dismissed,
        "oldest_days": (datetime.now(timezone.utc) - oldest).days if oldest else None,
    }


def render_all(conn) -> dict:
    """Tam, idempotent re-render — tüm graph'ı tarar, entities/events/investigations/
    sources klasörlerini sıfırdan yazar (isim değişikliklerinde öksüz dosya kalmasın diye),
    Inbox ve Dashboard notlarını günceller. daily/'ye dokunmaz (append-only, ayrı akış)."""
    VAULT_DIR.mkdir(parents=True, exist_ok=True)

    entities = fetch_all(conn.execute(
        "MATCH (n:Entity) RETURN n.id AS id, n.entity_type AS entity_type, n.name AS name, "
        "n.aliases AS aliases, n.created_at AS created_at"
    ))
    events = fetch_all(conn.execute(
        "MATCH (n:Event) RETURN n.id AS id, n.title AS title, n.event_type AS event_type, "
        "n.occurred_at AS occurred_at, n.location AS location, n.knowledge_state AS knowledge_state, "
        "n.confidence AS confidence, n.created_at AS created_at"
    ))
    investigations = fetch_all(conn.execute(
        "MATCH (n:Investigation) RETURN n.id AS id, n.title AS title, "
        "n.research_question AS research_question, n.status AS status, "
        "n.analysis AS analysis, n.conclusion AS conclusion, "
        "n.created_at AS created_at, n.updated_at AS updated_at"
    ))
    sources = fetch_all(conn.execute(
        "MATCH (n:Source) RETURN n.id AS id, n.name AS name, n.source_type AS source_type, "
        "n.url AS url, n.reliability AS reliability, n.created_at AS created_at"
    ))

    _reset_dir(VAULT_DIR / "entities")
    for e in entities:
        _write(VAULT_DIR / "entities" / f"{note_stem(e['id'], e['name'])}.md", render_entity_note(conn, e))

    _reset_dir(VAULT_DIR / "events")
    for e in events:
        _write(VAULT_DIR / "events" / f"{note_stem(e['id'], e['title'])}.md", render_event_note(conn, e))

    _reset_dir(VAULT_DIR / "investigations")
    for i in investigations:
        _write(VAULT_DIR / "investigations" / f"{note_stem(i['id'], i['title'])}.md", render_investigation_note(conn, i))

    _reset_dir(VAULT_DIR / "sources")
    for s in sources:
        _write(VAULT_DIR / "sources" / f"{note_stem(s['id'], s['name'])}.md", render_source_note(conn, s))

    (VAULT_DIR / "inbox").mkdir(parents=True, exist_ok=True)
    _write(VAULT_DIR / "inbox" / "Intelligence-Inbox.md", render_inbox_note(conn))
    _write(VAULT_DIR / "Dashboard.md", render_dashboard_note(conn))
    (VAULT_DIR / "daily").mkdir(parents=True, exist_ok=True)

    return {
        "entities": len(entities),
        "events": len(events),
        "investigations": len(investigations),
        "sources": len(sources),
    }


def safe_render_inbox_only(conn) -> None:
    """Inbox durum değişiklikleri (Q14 Confirm/Reject/...) sık olabilir ve sadece
    inbox/Intelligence-Inbox.md'yi etkiler — tam graph taramasına gerek yok."""
    try:
        VAULT_DIR.mkdir(parents=True, exist_ok=True)
        (VAULT_DIR / "inbox").mkdir(parents=True, exist_ok=True)
        _write(VAULT_DIR / "inbox" / "Intelligence-Inbox.md", render_inbox_note(conn))
    except Exception as exc:  # noqa: BLE001
        print(f"[vault] inbox render başarısız oldu, isteğe devam ediliyor: {exc}", file=sys.stderr)


def safe_render_vault(conn) -> None:
    """render_all()'ı çağıran mutasyon uçlarının kullandığı sarmalayıcı — vault sadece
    graph'ın türetilmiş bir görünümü, bir render hatası asıl API isteğini ASLA
    başarısız kılmamalı (bkz. Faz 9 karar notu)."""
    try:
        render_all(conn)
    except Exception as exc:  # noqa: BLE001 - kasıtlı: render hatası API'yi kırmasın
        print(f"[vault] render_all başarısız oldu, isteğe devam ediliyor: {exc}", file=sys.stderr)
