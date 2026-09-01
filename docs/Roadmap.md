---
proje: OsintLab
created: 2026-09-02
type: roadmap
status: aktif
---
# OsintLab — Roadmap

Durum sütunu session-start hook'u tarafından otomatik okunur — format bozulmasın:
⏳ Bekliyor / 🔄 Devam Ediyor / ✅ Tamamlandı.

Bu roadmap, `docs/Proje-Fikri.md`'deki v2 taslağının 73. maddesindeki (Phase 0–8) fikrin,
finalizasyon aşamasındaki somut teknoloji kararlarıyla (Python 3.12 + FastAPI, KùzuDB,
Next.js) yeniden işlenmiş, v1 kapsamına (Q25: Desteklenen katman) odaklanmış halidir. GEOINT/
SOCMINT/DOCINT/MEDIAINT gibi deneysel domain'ler ve tam otonom araştırma bilinçli olarak bu
roadmap'in dışında bırakıldı.

| Faz | Adı | Durum | Bitti Kriteri |
| --- | --- | --- | --- |
| 1 | Temel Altyapı | ✅ Tamamlandı | FastAPI health-check endpoint ve KùzuDB şeması (Entity/Event/Source/Claim/Evidence/Relationship/Investigation/Observation) çalışıyor; API üzerinden temel entity CRUD test edilebiliyor. |
| 2 | Core Knowledge Model + Confidence Motoru | ✅ Tamamlandı | Bir claim eklenip deterministik formülle confidence hesaplanabiliyor; çelişen ikinci claim eklendiğinde Contradiction objesi otomatik oluşuyor; eski bilgi silinmeden temporal (Valid: X→Y) supersede ediliyor. |
| 3 | Investigation & Hypothesis System | ⏳ Bekliyor | Investigation açılıp durumları (OPEN→...→CLOSED/ARCHIVED) arasında geçebiliyor; kapanan investigation'ın sadece verified findings'i Knowledge Graph'a yükseliyor, geçici notlar yükselmiyor. |
| 4 | OSINT Brain (Claude Code Agent Katmanı) | ⏳ Bekliyor | Yeni bir observation eklendiğinde ilgili geçmiş investigation/entity otomatik hatırlatılıyor (Memory Recall); bir intelligence çıktısı için kural+graph tabanlı "Why This Matters" gerekçesi üretilebiliyor. |
| 5 | Collection (temel WEBINT) + Collector Güvenliği | ⏳ Bekliyor | Collector sandbox mekanizması seçilip doğrulandı (Q22 spike); bir RSS/web kaynağından güvenli şekilde içerik toplanıp Observation olarak sisteme giriyor; temel prompt-injection/SSRF testleri geçiyor. |
| 6 | Source Independence Lineage Graph | ⏳ Bekliyor | Teknik tespit yaklaşımı doğrulandı (Q6 spike); en az 3 türetilmiş kaynak örneğinde (agency → site A → site B) sistem bunları bağımsız değil türetilmiş olarak işaretleyebiliyor. |
| 7 | Monitoring, Change Detection, Intelligence Inbox | ⏳ Bekliyor | İzlenen bir entity'de değişiklik olduğunda doğru öncelik seviyesiyle (CRITICAL/HIGH/.../INFO) Inbox'a düşüyor; "son 30 günde ne değişti" (Intelligence Diff, on-demand) sorgusu çalışıyor. |
| 8 | Frontend (Next.js Dashboard) | ⏳ Bekliyor | `docs/Design.md` dolduruldu; kullanıcı tarayıcıdan bir entity arayıp ilişkilerini/timeline'ını görebiliyor; Inbox'ı görüntüleyip Confirm/Reject/Investigate aksiyonu alabiliyor (davranış loglanıyor); SOURCE FACT/AI ANALYSIS/SYSTEM INFERENCE/USER INTERPRETATION 4 etiketi UI'da ayrışıyor. |

## Faz Detayları

### Faz 1: Temel Altyapı
- **İşler:**
  - Python 3.12 virtualenv + FastAPI proje iskeleti (backend Python 3.14 sistem kurulumuna
    dokunmadan, proje-özel pinlenmiş sürüm — bkz. Final-Dokuman.md Riskler).
  - KùzuDB şeması: node tabloları (Person, Organization, Event, Source, Claim, Evidence,
    Investigation, Observation dahil Core Knowledge Model'in tamamı) + rel tabloları.
  - Yerel dosya sistemi iskeleti: `daily/` (ham observation log), `evidence/` (hash+metadata).
  - Health-check + temel entity CRUD endpoint'leri.
- **Bitti Kriteri:** FastAPI health-check endpoint ve KùzuDB şeması çalışıyor; API üzerinden
  temel entity CRUD test edilebiliyor.
- **Notlar:** 2026-09-02 tamamlandı. `backend/` altında Python 3.12 venv (sistem Python 3.14'e
  dokunulmadan, `py -3.12 -m venv .venv`) + FastAPI + KùzuDB kuruldu. Şema `backend/app/
  schema.py`'de merkezi ve idempotent (`IF NOT EXISTS`, gerçek KùzuDB'ye karşı doğrulandı).
  `/entities` üzerinde CREATE/LIST/LIST-filtered/GET/PATCH/DELETE uçtan uca curl ile test
  edildi, hepsi çalışıyor. Bulunan bir hata (KùzuDB'de `RETURN e.*` düz alan adı değil
  `e.id` gibi prefiksli kolon döndürüyor) düzeltildi — sorgularda artık açık `AS` alias'ı
  kullanılıyor. `data/` klasörü (OSINT Brain'in canlı verisi) `.gitignore`'a eklendi, koddan
  ayrı tutuluyor. Sonraki fazlar için: Event/Source/Claim/Evidence/Investigation/Observation
  için de aynı router deseni tekrarlanacak (Faz 2-3).

### Faz 2: Core Knowledge Model + Confidence Motoru
- **İşler:**
  - Entity/Event/Source/Claim/Evidence/Relationship modellerinin tam CRUD'u.
  - Q3 hibrit knowledge state modeli (UNKNOWN/OBSERVED/REPORTED/SUPPORTED/CORROBORATED/HIGH
    CONFIDENCE + CONTRADICTED/UNRESOLVED/DISPROVEN) + %0-100 sayısal confidence alanı.
  - Q4 deterministik confidence formülü (source quality + independence + evidence sayısı +
    corroboration + historical reliability, ağırlıklar dokümante edilmiş).
  - Q9 temporal versiyonlama (Valid: X→Y) + Contradiction objesi.
  - Q1/Q8 katmanlı hafıza: ham observation → daily log, sadece eşiği geçen bilgi Knowledge
    Graph'a promote ediliyor.
- **Bitti Kriteri:** Bir claim eklenip formülle confidence hesaplanabiliyor; çelişen ikinci
  claim eklendiğinde Contradiction objesi otomatik oluşuyor; eski bilgi silinmeden temporal
  supersede ediliyor.
- **Notlar:** 2026-09-02 tamamlandı. `app/confidence.py`'de açıklanabilir (black-box olmayan)
  ağırlıklı formül: source_quality 0.40 + independence 0.25 + evidence 0.20 + corroboration
  0.15. `GET /claims/{id}/explain` ile kırılım her zaman görülebiliyor (Auditability). Uçtan
  uca test senaryosu: tek kaynaklı claim confidence=0.32/REPORTED → farklı kaynaktan simetrik
  corroboration + evidence eklenince her iki claim de confidence=0.495/SUPPORTED'a yükseldi
  (formül elle doğrulandı: 0.4×0.8+0.25×0.5+0.15×0.333=0.495) → çelişen üçüncü claim
  eklenince her iki taraf da otomatik CONTRADICTED'a döndü → yeni bir claim supersedes ile
  eskisinin yerini alınca eski claim silinmedi, sadece valid_to dolduruldu (tüm liste
  sorgusunda hâlâ görünüyor). Observation→promote akışı da test edildi: tek kaynaklı/kanıtsız
  observation eşiği (0.45) geçemediği için promoted=false kaldı, kanıt+corroboration eklenen
  ikinci observation promoted=true oldu — Q1/Q8 katmanlı hafıza modeli çalışıyor. CORROBORATES
  ilişkisi simetrik kurulacak şekilde tasarlandı (iki claim birbirini karşılıklı destekler).
  Test verisi ve KùzuDB temizlendi, Brain temiz başlıyor. Sonraki fazlar için: Event/
  Investigation'a da confidence/knowledge_state güncellemesi gerektiren akışlar eklenebilir
  (şu an sadece Claim üzerinde tam confidence motoru var, Event.confidence alanı Faz 3-4'te
  claim'lerden türetilecek).

### Faz 3: Investigation & Hypothesis System
- **İşler:**
  - Investigation modeli + Q16 durum makinesi (OPEN/ACTIVE/PAUSED/RESOLVED/CLOSED/ARCHIVED).
  - Hypothesis (H1/H2/H3) sistemi, kanıt-hipotez ilişkilendirme (destekler/zayıflatır/çürütür).
  - Q17 Investigation → Long-Term Memory akışı: Investigation → Evaluation → Validated
    Knowledge → Long-Term Memory (sadece verified findings promote edilir).
- **Bitti Kriteri:** Investigation açılıp durumları arasında geçebiliyor; kapanan
  investigation'ın sadece verified findings'i Knowledge Graph'a yükseliyor, geçici notlar/
  çürütülmüş hipotezler yükselmiyor.
- **Notlar:**

### Faz 4: OSINT Brain (Claude Code Agent Katmanı)
- **İşler:**
  - AvenoxBeyin desenine paralel proje-özel dosya yapısı ve Claude Code skill/hook kurulumu
    (bkz. Final-Dokuman.md Mimari — izole, kişisel Brain'den ayrı).
  - Memory Recall: yeni observation'a göre ilgili geçmiş entity/investigation/source'u
    otomatik hatırlatma.
  - Research Relevance Recall: yeni gelişmenin eski (ör. 4 ay önceki) bir investigation ile
    ilişkisini tespit etme.
  - Q12 Why This Matters: kural+graph tabanlı gerekçe üretimi, AI sadece yazım/akıcılaştırma.
- **Bitti Kriteri:** Yeni bir observation eklendiğinde ilgili geçmiş investigation/entity
  otomatik hatırlatılıyor; bir intelligence çıktısı için kural+graph tabanlı "Why This
  Matters" gerekçesi üretilip kaynağı gösterilebiliyor.
- **Notlar:**

### Faz 5: Collection (temel WEBINT) + Collector Güvenliği
- **İşler:**
  - Q22 spike: sandbox mekanizması karşılaştırması (ayrı process/container/network policy),
    somut karar ve gerekçesi Final-Dokuman.md'ye işlenir.
  - Allowlist yönetimi, çıkış isteği doğrulama (SSRF'e karşı private IP/localhost engeli).
  - İçerik-veri ayrımı: toplanan içerik LLM'e her zaman "güvenilmeyen veri" olarak
    işaretlenir, sistem prompt'undan izole tutulur.
  - Temel RSS/web collector → Observation dönüşümü.
- **Bitti Kriteri:** Collector sandbox mekanizması seçilip doğrulandı; bir RSS/web
  kaynağından güvenli şekilde içerik toplanıp Observation olarak sisteme giriyor; temel
  prompt-injection/SSRF testleri geçiyor.
- **Notlar:**

### Faz 6: Source Independence Lineage Graph
- **İşler:**
  - Q6 spike: teknik tespit yaklaşımının doğrulanması (metin benzerliği/near-duplicate,
    yayın metadata'sı, syndication API'leri veya hibrit) gerçek haber makaleleriyle test
    edilir.
  - Seçilen yaklaşımın Source modeline entegrasyonu (Original Source → Agency → Site A →
    Site B zinciri).
- **Bitti Kriteri:** Teknik tespit yaklaşımı doğrulandı; en az 3 türetilmiş kaynak örneğinde
  sistem bunları bağımsız değil türetilmiş olarak işaretleyebiliyor.
- **Notlar:**

### Faz 7: Monitoring, Change Detection, Intelligence Inbox
- **İşler:**
  - Continuous Monitoring: Entity/Topic/Event izleme kaydı.
  - Change Detection: Observe → Detect → Evaluate → Compare With Memory → Update → Notify
    döngüsü.
  - Q10/Q11 Intelligence Diff: on-demand hesaplanan World State karşılaştırması (entity/
    graph/claims/confidence/source landscape hepsi dahil).
  - Intelligence Inbox + Q13 sabit eşik + kullanıcı ayarlanabilir bildirim seviyesi.
- **Bitti Kriteri:** İzlenen bir entity'de değişiklik olduğunda doğru öncelik seviyesiyle
  Inbox'a düşüyor; "son 30 günde ne değişti" sorgusu çalışıyor.
- **Notlar:**

### Faz 8: Frontend (Next.js Dashboard)
- **İşler:**
  - `docs/Design.md` doldurulması (`ui-ux-pro-max` skill ile proje-özel kimlik — mood,
    accent palet, tipografi).
  - Main Workspace (Search/Ask + Priority Intelligence + World Map/Entity Graph/Timeline
    panelleri), Entity/Event Intelligence sayfaları.
  - Search/Ask arayüzü — yapılandırılmış Brain/Core verisine dayalı doğal dil sorguları.
  - Intelligence Inbox UI + Q14 davranış loglama (Ignore/Confirm/Reject/Investigate/Follow).
  - Q15 UI ayrımı: SOURCE FACT / AI ANALYSIS / SYSTEM INFERENCE / USER INTERPRETATION 4
    etiketi.
- **Bitti Kriteri:** Kullanıcı tarayıcıdan bir entity arayıp ilişkilerini/timeline'ını
  görebiliyor; Inbox'ı görüntüleyip aksiyon alabiliyor; 4 etiket ayrımı UI'da görünüyor.
- **Notlar:**
