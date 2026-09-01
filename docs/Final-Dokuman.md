---
proje: OsintLab
created: 2026-09-02
type: final-dokuman
status: taslak
---
# OsintLab — Final Doküman

## Özet

Scryne OSINT Lab, açık kaynaklardan sürekli gözlem yapan, entity/olay/kaynak/kanıt arasında
bağlantılar kuran ve zaman içinde kendi hafızasını (OSINT Brain) biriktiren, tek kullanıcılı,
local-first bir kişisel intelligence operating system'dir. Mimari hibrit bir şekle sahiptir:
araştırma/analiz/hafıza işleri Claude Code ajanı (AvenoxBeyin desenine paralel) üzerinden
yürür, bunun yanında vizyon dokümanındaki (World Map, Entity Graph, Timeline, Intelligence
Inbox) profesyonel dashboard'u sunan bağımsız bir Next.js web arayüzü aynı veri katmanını
(KùzuDB graph + yerel dosyalar) okur/yazar. Evidence First, History Is Immutable, Human
Remains In Control ilkeleri mimarinin her katmanına (deterministik confidence formülü,
temporal versiyonlama, entity merge/conclude/verify'da zorunlu kullanıcı onayı) yansır.

## Teknoloji Stack

| Katman | Seçim | Gerekçe |
| --- | --- | --- |
| Ajan / Runtime | Claude Code (skills + hooks) | OSINT Brain'in araştırma, hafıza, önceliklendirme işlerini yürütür — AvenoxBeyin'deki dosya tabanlı hafıza + session-end özetleme desenine paralel (bkz. aşağıdaki Mimari). |
| Backend | Python 3.12 + FastAPI | OSINT'in veri işleme ekosistemiyle (scraping, NLP, graph algoritmaları) ve Anthropic'in olgun Python SDK'sıyla en uyumlu; Claude Code agent'ı ve Next.js frontend'i için tek giriş noktası API katmanı. **Python sürümü bilinçli olarak 3.12'ye pinlenir** — bkz. Riskler bölümündeki KùzuDB/Python 3.14 uyumsuzluğu bulgusu. |
| Graph Database | KùzuDB (embedded, dosya tabanlı) | Spike ile doğrulandı (bkz. Riskler ve Doğrulamalar). Local-first (Q21) kararıyla tam uyumlu, ayrı servis/kurulum gerektirmez, bu ölçekte Neo4j'den belirgin şekilde daha hızlı, Cypher benzeri sorgu dili sunar. |
| Frontend | Next.js + React + Tailwind | Global CLAUDE.md'deki dark glassmorphism disiplini ve shadcn/21st MCP araçları bu stack'le native çalışır; World Map/Entity Graph gibi zengin panelli dashboard için uygun. |
| Evidence Storage | Yerel dosya sistemi + SHA-256 hash + metadata | Q18 kararı — kanıt dosyaları yerelde saklanır, bütünlük hash'i ve tam provenance metadata'sı (source, collected, first seen) tutulur. |
| AI Sağlayıcı | Anthropic Claude (Claude Code agent + gerektiğinde API) | Q21 hibrit local-first kararıyla uyumlu — Brain'in temel verisi yerel kalır, AI opsiyonel/bulut bir katman olarak kullanılır. |
| Collector Sandbox | Belirlenecek (Faz 3) | Q22 kararı yön verdi (sandbox + allowlist + içerik-veri ayrımı) ama somut mekanizma (ayrı process/container/network policy) henüz doğrulanmadı — bkz. Riskler. |
| Source Independence Tespiti | Belirlenecek (ilk roadmap fazı) | Q6 kararı (v1'den tam lineage graph) yön verdi ama teknik yaklaşım henüz doğrulanmadı — bkz. Riskler. |

## Mimari

```text
┌─────────────────────────────────────────────────────────────────┐
│                      CLAUDE CODE AGENT KATMANI                   │
│  (skills + hooks — OSINT Brain: araştırma, hafıza, önceliklendirme) │
│  daily log (ham observation) ──► değerlendirme ──► knowledge      │
└───────────────────────────────┬─────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BACKEND API (Python + FastAPI)                 │
│   tek giriş noktası — collector sandbox sınırı burada uygulanır   │
└───────────┬─────────────────────────────────────┬─────────────────┘
            │                                     │
            ▼                                     ▼
┌───────────────────────────┐        ┌─────────────────────────────┐
│   KùzuDB (embedded graph)  │        │  Yerel Dosya Sistemi         │
│   Entities/Events/Sources/ │        │  Evidence (hash+metadata)    │
│   Claims/Relationships     │        │  Daily logs / raw observation│
└───────────┬─────────────────────────┴─────────────┬─────────────┘
            │                                        │
            └────────────────────┬───────────────────┘
                                  ▼
                    ┌───────────────────────────┐
                    │  Next.js + React + Tailwind │
                    │  (World Map, Entity Graph,  │
                    │   Timeline, Inbox — dark    │
                    │   glassmorphism)             │
                    └───────────────────────────┘
```

**Veri akışı:** Collector (sandbox, allowlist) → Raw Observation (daily log dosyası,
değiştirilemez) → Değerlendirme (Q4 deterministik confidence formülü) → Knowledge Graph
(KùzuDB, sadece eşiği geçen bilgi promote edilir — Q1/Q8) → Brain (recall/context katmanı,
Q2) → Backend API → Frontend / Claude Code Agent → Kullanıcı.

**Brain ile Intelligence Core ayrımı (Q2):** Intelligence Core (KùzuDB + dosyalar) ham
yapılandırılmış veriyi tutar; Brain bunun üzerine oturan "ne hatırlanmalı, ne zaman geri
çağrılmalı" mantığını yürüten bir context/recall katmanıdır — aynı depoda yaşar ama
sorumlulukları ayrıdır.

**AvenoxBeyin ile ilişki:** Claude Code Agent katmanı, ScryneOS vault'undaki AvenoxBeyin
mimarisinin (dosya tabanlı hafıza, session-end özetleme, gece derlemesi) OSINT'e özelleştirilmiş
ve tamamen izole bir uyarlamasıdır — kişisel Brain'den (ScryneOS) veri paylaşımı yoktur, sadece
mimari desen ödünç alınmıştır (bkz. `docs/Proje-Fikri.md` madde 4.1). Somut dosya şeması ve
derleme script'lerinin tasarımı roadmap/uygulama aşamasında netleşecek.

## Kapsam (v1)

`docs/Proje-Fikri.md`'deki "Temel Özellikler" listesi ve Q25'teki 3 katmanlı kapsam sınırı
geçerlidir: **Desteklenen** = Core Knowledge Model + temel WEBINT (haber/web toplama) +
Investigation/Hypothesis System + Basic Knowledge Graph + Search/Ask + Continuous
Monitoring + Intelligence Inbox. **Deneysel** (Phase 7+) = GEOINT/SOCMINT/DOCINT/MEDIAINT/
Corporate/Conflict/Political Intelligence. **Kapsam dışı (kalıcı)** = kitlesel toplama, hedef
bazlı gözetim.

## Riskler ve Doğrulamalar

### Graph DB seçimi (Q20) — Doğrulandı (spike, 2026-09-02)

Docker'da `python:3.12-slim` üzerinde, OSINT şemasına uygun sentetik bir veri seti (47 node:
15 Person, 10 Organization, 12 Event, 10 Source; 67 ilişki: WORKS_FOR, INVOLVED_IN,
REPORTED_BY, ACQUIRED) hem KùzuDB hem Neo4j 5'te kuruldu, aynı 3 sorgu (multi-hop traversal,
aggregation/sıralama, variable-length shortest path) her ikisinde de çalıştırıldı.

| Metrik | KùzuDB (embedded) | Neo4j 5 (Docker, bolt) |
| --- | --- | --- |
| Şema oluşturma | 23.7 ms | 181.4 ms |
| Veri yükleme (47 node + 67 ilişki) | 297.2 ms | 1.392,5 ms |
| 3 sorgu | 21.2 ms | 530.0 ms |
| Toplam (sunucu başlatma hariç) | **353.4 ms** | 3.033,2 ms |
| Operasyonel yük | Yok — `pip install kuzu` yeterli | Ayrı container/servis, auth, network config, ~980MB image |

Sonuç kümeleri iki motorda da (sıralama farkları dışında) tutarlıydı.

**Karar: KùzuDB.** Bu ölçekte belirgin şekilde daha hızlı, sıfır operasyonel yük — local-first
(Q21) kararıyla tam uyumlu. Cypher benzeri sorgu dili (variable-length shortest path dahil)
Neo4j'e yeterince yakın; ölçek gerçekten 1M+ entity'ye ulaşırsa (Q20'nin uzun vadeli senaryosu)
Neo4j'e geçiş mimari olarak mümkün kalır.

**Tespit edilen risk — Python 3.14 uyumsuzluğu:** KùzuDB (0.11.3), bu makinenin varsayılan
Python'ı olan 3.14.7 için henüz derlenmiş bir paket (wheel) sunmuyor; `pip install kuzu`
kaynaktan derlemeye düşüyor ve eksik build-tool'lar (cmake/C++ derleyici) nedeniyle
başarısız oluyor. **Karar:** backend için proje-özel bir Python 3.12 virtualenv kullanılacak
(kuzu + FastAPI ekosisteminin tamamı 3.12'de sorunsuz çalıştığı doğrulandı) — sistem genelindeki
Python 3.14 kurulumuna dokunulmadı.

### Source independence lineage graph (Q6) — Doğrulanmadı

Karar (v1'den tam lineage graph kurulması) verildi ama teknik tespit yaklaşımı (metin
benzerliği/near-duplicate detection mi, yayın metadata'sı mı, syndication API'leri mi, yoksa
hibrit mi) henüz bir spike ile doğrulanmadı. Roadmap'in ilgili fazında (Intelligence Core /
Collection) küçük bir prototiple (gerçek haber makaleleriyle) test edilmesi gerekiyor.

### Collector sandbox mekanizması (Q22, kritik güvenlik) — Doğrulanmadı

Yön (sandbox + allowlist + içerik-veri ayrımı) belirlendi ama somut mekanizma (ayrı process mı,
container izolasyonu mu, network policy mi, hangi prompt-injection işaretleme şeması) henüz
seçilmedi. Roadmap'in Collection fazında, ilk collector inşa edilmeden önce netleştirilmesi
gereken kritik bir ön koşul.

## Kapsam Dışı

`docs/Proje-Fikri.md`'deki "Kapsam Dışı" bölümü ve Q25'teki kalıcı kapsam-dışı tanımı
(kitlesel toplama, hedef bazlı gözetim, kişisel araştırmacı amaçlı olmayan kullanımlar)
geçerlidir. Ayrıca: Neo4j (ya da başka bir server-tabanlı graph DB) — spike sonucunda bu
ölçek için gerekli görülmedi, ölçek gerçekten zorlarsa yeniden değerlendirilir.
