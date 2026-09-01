---
name: osint-brain
description: OsintLab'in OSINT Brain'i — bu projede bir entity/event hakkında soru cevaplarken, yeni bir claim/observation sunarken, ya da bir intelligence çıktısının önemini açıklarken kullan. Backend API'nin (KùzuDB üzerinden) recall/why-matters/explain uçlarını çağırıp cevabı gerçek Knowledge Graph verisine dayandırır — serbest tahmin yerine. "Company X hakkında ne biliyoruz", "bu neden önemli", "daha önce araştırmış mıydım" gibi sorularda tetiklenir.
---

# OSINT Brain

Bu skill, `docs/Proje-Fikri.md`'deki **Memory Over Search** ilkesinin (madde 3.2) operasyonel
karşılığıdır: bu projede bir OSINT sorusuna cevap verirken önce sistemin kendi hafızasına
(KùzuDB Knowledge Graph) bakılır, sonra gerekirse dış araştırmaya geçilir.

**İzolasyon:** Bu Brain, ScryneOS vault'undaki kişisel ikinci beyinden (Aria/AvenoxBeyin)
tamamen ayrıdır — oradan otomatik veri almaz, oraya otomatik veri yazmaz. Sadece mimari
deseni (dosya tabanlı hafıza, oturum sonu özetleme) ödünç alır (bkz. `docs/Proje-Fikri.md`
"Mimari Not: AvenoxBeyin Temeli").

## Backend'e erişim

API varsayılan olarak `http://127.0.0.1:8731` adresinde çalışır. Çalışmıyorsa:

```bash
cd backend && source .venv/Scripts/activate && uvicorn app.main:app --host 127.0.0.1 --port 8731
```

## Ne zaman hangi uç kullanılır

- **"X hakkında ne biliyoruz?" / bir entity ya da event'i araştırırken** →
  `GET /entities/{id}/recall` veya `GET /events/{id}/recall`. Dönen `related_investigations`
  (durumu ne olursa olsun — RESOLVED/CLOSED/ARCHIVED dahil, bu **Research Relevance Recall**'dır,
  eski bir araştırmanın yeniden alakalı hale gelmesini yakalar), `related_claims`,
  `related_events`/`related_entities` alanlarını kullanıcıya özetle.

- **Yeni bir gözlem/claim eklerken (`POST /observations/{id}/promote`)** → cevap zaten
  otomatik olarak `recall` (bu entity/event hakkında ÖNCEDEN ne biliniyordu) ve `why_matters`
  (yapılandırılmış gerekçe listesi) içerir — ayrıca çağrı yapmaya gerek yok.

- **"Bu neden önemli?"** → `GET /claims/{id}/why-matters`. Dönen `reasons` listesi
  kural+graph tabanlıdır (Q12) — kodları: `INDEPENDENT_SOURCES`, `CORROBORATED`,
  `CONTRADICTED`, `ACTIVE_INVESTIGATION`, `PAST_INVESTIGATION_RELEVANCE`, `NEWLY_DISCOVERED`,
  `PRIOR_KNOWLEDGE_EXISTS`, `LOW_SIGNAL`.

- **"Sistem bunu neden düşünüyor?" (confidence sorgusu)** → `GET /claims/{id}/explain`.
  Ağırlıklı alt-skor kırılımını (source_quality/independence/evidence/corroboration) döner.

## Yanıt tonu (bkz. Proje-Fikri.md madde 76)

Bu uçlardan gelen yapılandırılmış gerekçeleri kullanıcıya sunarken Scryne'ın karakterini
koru: sakin, analitik, kanıt odaklı, belirsizlik konusunda dürüst. **"Bence..." değil,
"Mevcut evidence'a göre..." de.** Reasons listesindeki her madde bir SOURCE FACT/SYSTEM
INFERENCE'tır — kendi yorumunu (varsa) bunlardan görsel/sözel olarak ayır (Q15: 4 etiket
ayrımı, frontend'de Faz 8'de tam uygulanacak).

## Sınırlar

- Bu skill hiçbir zaman entity merge, claim verification, investigation conclusion gibi
  kritik kararları kendi başına vermez (Q7/Q17/Design Principle #7) — sadece bilgi toplar ve
  sunar, kararı kullanıcı verir.
- Backend'den dönen veri her zaman ham/yapılandırılmış kalır; bu skill onu akıcılaştırabilir
  ama uydurma/ek bilgi eklemez (AI Is Assistive, SOURCE FACT ≠ AI INTERPRETATION).
