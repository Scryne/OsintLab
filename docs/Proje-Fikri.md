---
proje: OsintLab
created: 2026-09-02
type: proje-fikri
status: taslak
---
# OsintLab — Proje Fikri

> Bu doküman kullanıcının iki taslağından ("SCRYNE OSINT LAB.md" = v1, "SCRYNE OSINT LAB
> v2.md" = v2) derlendi. v2, v1'in geliştirilmiş/güncel hali olarak esas alındı (kullanıcı
> onayıyla) — v1'de v2'de bulunmayan çelişen bir karar tespit edilmedi. Orijinal taslak
> dosyaları proje kökünde referans olarak duruyor.

## Problem

Klasik OSINT araçları (arama motorları, haber takip panelleri, dashboard'lar) her sorguda
dünyayı sıfırdan araştırır ve hiçbir şeyi hatırlamaz. Bireysel bir araştırmacı/analist için,
zaman içinde biriken bağlamı (hangi entity'ler daha önce araştırıldı, hangi ilişkiler
biliniyor, hangi kaynaklar güvenilir, hangi araştırmalar hangi olaylarla ilişkili) kaybetmeyen,
"memory over search" prensibiyle çalışan, kanıt ve provenance'ı koruyan yaşayan bir kişisel
intelligence sistemi eksik.

## Hedef Kullanıcı

Bireysel araştırmacı / analist (projenin sahibi Scryne) — tek kullanıcılı, kişisel kullanım
için tasarlanan bir intelligence workstation. Başka kullanıcılara açık bir platform hedeflenmiyor.

## Temel Özellikler (v1'de olması şart)

- **OSINT Brain** — kalıcı hafıza ve bağlam katmanı (bkz. aşağıdaki AvenoxBeyin mimari notu)
- **Core Knowledge Model** — Entity, Event, Source, Claim, Evidence, Relationship,
  Investigation, Observation
- **Investigation System** + Hypothesis System (H1/H2/H3 tarzı hipotez takibi)
- **Basic Knowledge Graph** — entity/event/source arası ilişkiler
- **Search / Ask arayüzü** — doğal dil sorguları, cevaplar yapılandırılmış veriye dayanır
- **Continuous Monitoring** + Change Detection (izlenen entity/topic/event'lerde değişim tespiti)
- **Intelligence Inbox** + önem seviyeli bildirimler (CRITICAL/HIGH/MEDIUM/LOW/INFO)
- **Timeline Engine** ve temel **Provenance** takibi (her bilginin nereden geldiği izlenebilir)

## Kapsam Dışı (bu sürümde bilerek yapılmayacaklar)

- Tüm interneti taramak, onlarca API entegrasyonu, yüzlerce OSINT aracı
- Tam otonom araştırma, kontrolsüz AI kararları (entity merge / claim verification / source
  trust / investigation conclusion gibi kritik kararlar kullanıcı onayı gerektirir)
- İleri OSINT domain'leri: GEOINT, SOCMINT, DOCINT, MEDIAINT, Corporate/Conflict/Political
  Intelligence (bunlar sonraki fazlara — bkz. v2 madde 73 Development Roadmap)
- Devasa frontend, gereksiz mikroservis mimarisi

## Açık Sorular (denetim aşamasında kapatılacak)

v2 taslağının 71. maddesinde (Q1–Q25) listelenen mimari sorular henüz kapatılmadı. Öne
çıkanlar:

- **Brain ne "hatırlamalı"?** Her observation mi, yoksa filtrelenmiş/değerlendirilmiş bilgi mi
  long-term memory'ye girecek? (Q1, Q8)
- **Confidence nasıl hesaplanacak?** Kural motoru mu, AI mi, hibrit mi? (Q4)
- **Source independence** teknik olarak nasıl tespit edilecek? (Q6)
- **Entity merge** otomatik mi yapılacak, yoksa her zaman kullanıcı onayı mı gerekecek? (Q7)
- **Local-first** ne kadar ileri götürülecek — %100 yerel mi, hibrit mi? (Q21)
- **Collector güvenliği**: prompt injection, SSRF, poisoned content gibi tehditlere karşı
  Collector → Intelligence Core sınırı nasıl korunacak? (Q22 — kritik güvenlik sorusu)
- **Otonomi sınırı**: observe/collect/classify/notify otomatik olabilir, ama
  investigate/conclude/verify/merge nerede insan onayı gerektirir? (Q23)
- **OSINT Brain'in teknik temeli**: AvenoxBeyin mimarisi bu proje özelinde nasıl izole ve
  özelleştirilecek? (aşağıdaki mimari nota bakınız — bu, projeye özgü ek bir açık soru)

## Kararlar (Denetim Aşaması)

Q1–Q25 sorularının kullanıcıyla grup grup gözden geçirilip kapatılan kararları. Her karar,
madde 71'deki (Q1–Q25) ilgili soruyu netleştirir.

### Grup 1 — Brain Hafıza Modeli Temelleri (2026-09-02)

- **Q1 — Brain ne hatırlar:** Katmanlı model. Her observation ham haliyle bir "daily log"a
  düşer (silinmez, ucuz — AvenoxBeyin'in `daily/` katmanına paralel). Sadece
  değerlendirilmiş/corroborate olmuş bilgi Knowledge Graph'a (`knowledge/` katmanına paralel)
  yükselir.
- **Q8 — Öğrenme eşiği:** Otomatik confidence eşiği. Belirli bir corroboration/confidence
  seviyesine ulaşınca sistem otomatik promote eder; düşük confidence'lı bilgi "REPORTED" gibi
  düşük bir knowledge state ile damgalanır, kesin kabul edilmez.
- **Q9 — Düzeltme mekanizması:** Contradiction + temporal versiyon. Çelişki önce
  "Contradiction" olarak UNRESOLVED işaretlenir; çözüldüğünde eski bilgi silinmez,
  "Valid: X→Y" ile temporal olarak supersede edilir (History Is Immutable ilkesi).
- **Q19 — Storage büyümesi:** v1'de ertelendi. Tek kullanıcılı kişisel ölçekte (Q20'deki
  ~1.000 entity civarı) storage büyümesi pratik bir sorun değil; Başlangıç Stratejisi
  ilkesiyle uyumlu, ileri faz notu olarak bırakıldı.

### Grup 2 — Truth & Confidence (2026-09-02)

- **Q3 — Truth modeli:** Hibrit. Kaba durum etiketi (UNKNOWN/OBSERVED/REPORTED/SUPPORTED/
  CORROBORATED/HIGH CONFIDENCE, yan dal CONTRADICTED/UNRESOLVED/DISPROVEN) ile Q4'teki
  formülden gelen %0-100 sayısal confidence birlikte tutulur.
- **Q4 — Confidence hesabı:** Deterministik kural motoru. Açıklanabilir ağırlıklı formül:
  source quality + independence + evidence sayısı + corroboration + historical reliability.
  Black-box değil, "neden bu confidence" sorusuna her zaman cevap verilebilir.
- **Q5 — Source reliability etkisi:** Bir girdi, tek başına belirleyici değil. Source
  reliability skoru Q4 formülündeki ağırlıklı faktörlerden biri; yeni claim yine kendi
  kanıtlarıyla değerlendirilir (bölüm 17 ilkesiyle uyumlu).
- **Q6 — Source independence:** v1'den itibaren **tam lineage graph** kurulacak (Original
  Source → Agency → Site A → Site B → Site C zinciri, bölüm 18). Önerilen hafif heuristic
  yaklaşımı yerine kullanıcı bunu v1'in bir parçası olarak istedi — ağır bir mühendislik
  yükü olarak bilinçli kabul edildi, finalizasyon aşamasında teknik yaklaşım (ne ile tespit
  edilecek: metin benzerliği, yayın zinciri metadata, syndication API'leri vb.) netleşecek.

### Grup 3 — Entity & Investigation Yaşam Döngüsü (2026-09-02)

- **Q2 — Brain/DB sınırı:** Brain, Intelligence Core'un (Entities/Events/Sources/Claims/
  Evidence/Relationships) üstüne oturan ayrı bir hatırlama/context katmanı — "hangi bağlam
  önemli, ne hatırlanmalı, ne zaman geri çağrılmalı" mantığını yürüten semantik indeks +
  recall katmanı. Aynı depoda yaşayabilir ama sorumlulukları Core'dan ayrı.
- **Q7 — Entity merge:** Asla otomatik değil, her zaman kullanıcı onayı. Yüksek confidence'ta
  bile sistem sadece "Possible Match" önerir, [Confirm]/[Reject] kullanıcıda kalır (Design
  Principle #7 Human Remains In Control).
- **Q16 — Investigation durumları:** Tam set — OPEN / ACTIVE / PAUSED / RESOLVED / CLOSED /
  ARCHIVED.
- **Q17 — Investigation → Brain aktarımı:** Sadece verified/validated findings. Bölüm 16'daki
  "Investigation → Evaluation → Validated Knowledge → Long-Term Memory" akışıyla birebir;
  geçici notlar/çürütülmüş hipotezler long-term memory'ye yatırılmaz (investigation kendi
  arşivinde kalır, sadece doğrulanmış bulgular Brain'e yükselir).

### Grup 4 — World State, Diff, Açıklama (2026-09-02)

- **Q10 — World State sıklığı:** On-demand hesaplanır, materialize edilmez. Q9'daki temporal
  versiyonlama kararı ("Valid: X→Y") sayesinde "T anındaki World State" zaten bir sorguyla
  anlık hesaplanabilir; v1'de ayrı snapshot depolamaya gerek yok.
- **Q11 — Diff kapsamı:** Hepsi birden — entity/graph/claims/confidence/source landscape
  değişikliklerinin tümü diff'e dahil, kullanıcı isterse filtreler.
- **Q12 — Why This Matters üretimi:** Kural + graph tabanlı, AI sadece yazım. Kural motoru
  graph-tabanlı sinyalleri (izlenen entity'ye yakınlık, investigation ilişkisi, bağımsız
  kaynak sayısı) değerlendirip yapılandırılmış bir gerekçe üretir; AI bunu akıcı cümleye
  çevirebilir ama karar mantığı kural tabanlı kalır, kaynağı her zaman gösterilebilir.

### Grup 5 — Active Intelligence & Kullanıcı Geri Beslemesi (2026-09-02)

- **Q13 — Bildirim eşiği:** Sabit eşik + kullanıcı manuel ayarlar. v1'de otomatik öğrenme yok;
  kullanıcı "sadece HIGH+ göster" gibi eşiği elle değiştirebilir.
- **Q14 — Davranış geri beslemesi:** Loglanır ama v1'de otomatik etkilemez. Ignore/Confirm/
  Reject/Investigate/Follow davranışları kaydedilir (ileride öğrenme için veri biriktirir) ama
  v1'de prioritization algoritmasını otomatik değiştirmez — Q13 kararıyla tutarlı.
- **Q15 — AI/Fact ayrımı:** 4 ayrı etiket — SOURCE FACT / AI ANALYSIS / SYSTEM INFERENCE /
  USER INTERPRETATION, farklı renk/badge ile görsel olarak ayrılır.

### Grup 6 — Evidence & Ölçek (2026-09-02)

- **Q18 — Evidence retention:** Yerel dosya + hash + tam metadata. Evidence dosyası yerelde
  saklanır, içerik hash'i (bütünlük doğrulama) ve tüm metadata (source, collected, first seen
  vb.) tutulur — Local-first ve Data Provenance ilkeleriyle uyumlu.
- **Q20 — Ölçek:** v1'den itibaren **ölçeklenebilir bir DB** seçilecek (örn. graph database) —
  önerilen "v1'de optimizasyon yapılmasın" seçeneğinin aksine, kullanıcı büyümeye baştan hazır
  bir mimari istedi. Bu, finalizasyon aşamasındaki Teknoloji Stack kararını doğrudan
  etkileyecek (graph DB seçimi — örn. Neo4j, KùzuDB, veya embedded bir graph çözümü —
  finalizasyonda karşılaştırılmalı).

### Grup 7 — Local-first, Güvenlik, Otonomi (2026-09-02)

- **Q21 — Local-first derinliği:** Hibrit — Local Core + dış API + opsiyonel Cloud AI. Brain'in
  temel verisi (entities/graph/evidence) yerelde kalır; harici zenginleştirme API'leri ve
  opsiyonel bulut AI servisleri kullanılabilir (AvenoxBeyin'in kendi deseniyle tutarlı).
- **Q22 — Collector güvenliği (kritik):** Sandbox + allowlist + içerik-veri ayrımı. Collector'lar
  izole çalışır (SSRF'e karşı private IP/localhost erişimi engellenir, çıkış istekleri
  doğrulanır). Toplanan içerik LLM'e asla "talimat" olarak verilmez — her zaman açıkça
  "güvenilmeyen veri" olarak işaretlenir, sistem prompt'undan izole tutulur. Finalizasyon
  aşamasında somut teknik tasarıma (sandbox mekanizması, allowlist yönetimi, içerik
  etiketleme şeması) dökülmesi gerekiyor.
- **Q23 — Otonomi sınırı:** Net split. Observe/collect/classify/connect/notify tam otomatik.
  Investigation açma sistem önerebilir ama başlatma kullanıcıda. Conclude/verify/merge her
  zaman kullanıcı onayı gerektirir (Q7 kararıyla tutarlı).

### Grup 8 — Otonomi Sınırı & Kapsam (2026-09-02)

- **Q24 — Kendiliğinden araştırma:** Hayır, sadece öneri. Brain anomali tespit ettiğinde
  "Investigation açmak ister misiniz?" önerir ama kendi başına research task başlatıp
  koşturmaz — Q23 kararıyla ve mevcut Kapsam Dışı ("tam otonom araştırma") ile tutarlı.
- **Q25 — Kapsam sınırı:** 3 katmanlı. **Desteklenen (v1):** Core Knowledge Model + temel
  WEBINT (haber/web toplama). **Deneysel (Phase 7+):** GEOINT/SOCMINT/DOCINT/MEDIAINT/
  Corporate/Conflict/Political Intelligence. **Kapsam dışı (kalıcı):** kitlesel toplama,
  hedef bazlı gözetim, kişisel araştırmacı amaçlı olmayan kullanımlar.

Q1–Q25 tamamı kapatıldı — **denetim aşaması tamamlandı.** Sıradaki adım: `docs/Final-Dokuman.md`
içinde teknoloji stack ve mimari kararlarının netleştirilmesi (finalizasyon aşaması). Önemli
finalizasyon girdileri: Q6 (v1'den tam source lineage graph), Q20 (v1'den ölçeklenebilir
graph DB), Q22 (collector sandbox/allowlist tasarımı), AvenoxBeyin mimarisinin OSINT'e somut
adaptasyonu.

---

## Mimari Not: AvenoxBeyin Temeli

Kullanıcının notu (proje-baslat kurulumu sırasında, 2026-09-02): bu projedeki amaç, ScryneOS
vault'unda (`C:\Users\scryn\Documents\ScryneOS`) zaten kullanılan "2. beyin" (AvenoxBeyin)
mimarisini — dosya tabanlı hafıza (Obsidian vault benzeri klasör yapısı), session-end
otomatik özetleme, gece derlemesi (bkz. https://avenox.lol/beyin.md) — bu proje özelinde,
**izole** ve **OSINT'e özelleştirilmiş** bir kurulumla yeniden kurup projeyi profesyonel bir
hale getirmek.

Bu, v2 taslağının "OSINT Brain" kavramının (bölüm 4–5, ilke 3.2 Memory Over Search) teknik
temeli olacak muhtemel aday mimari. ScryneOS vault'undaki mimari üç katmandan oluşuyor:

- **Dosya tabanlı hafıza**: `knowledge/` (derlenmiş semantik indeksler), `daily/` (oturum
  sonu günlük loglar)
- **Otomasyon**: SessionStart/SessionEnd hook'ları + oturum sonu özetleme, gece derlemesi
  script'leri
- **OSINT'e adaptasyon fikri**: İngileme katmanı (kaynaklar → yapılandırılmış notlar),
  Derleyici (zamansal grafikler, entity/ilişki haritaları, kanıt zincirleri), Sorgu (semantik
  arama + çapraz-referanslama)

Önemli: OSINT Brain, kullanıcının kişisel Brain'inden (ScryneOS/Personal Brain) tamamen
**ayrı** tutulmalı (bkz. v2 madde 4.1) — sadece mimari desen ödünç alınıyor, veri
paylaşılmıyor. Bu izolasyon kararı ve teknik detaylar finalizasyon aşamasında netleşecek.

---

## Tam Vizyon Dokümanı (v2 — kullanıcının orijinal taslağı)

> **A Personal Intelligence Operating System**
>
> Dünyayı sürekli gözlemleyen, açık kaynaklardan intelligence toplayan, gördüklerini
> hatırlayan, yeni bilgileri geçmiş bilgileriyle karşılaştıran, entity'ler ve olaylar
> arasındaki ilişkileri keşfeden, belirsizlikleri ve çelişkileri koruyan ve kullanıcıyı önemli
> gelişmeler hakkında aktif olarak bilgilendiren yaşayan bir kişisel OSINT intelligence
> ekosistemi.

### 1. Proje Özeti

**Scryne OSINT Lab**, klasik anlamda bir OSINT arama motoru, haber takip uygulaması veya
dashboard değildir.

Scryne; açık kaynaklardan veri toplayan, bu verileri yapılandıran, kaynaklarını ve provenance
bilgisini koruyan, entity'leri ve olayları birbirine bağlayan, araştırmaları kalıcı hafızaya
dönüştüren ve zaman içerisinde kendi intelligence knowledge base'ini oluşturan **yaşayan bir
kişisel intelligence operating system'dir.**

Sistemin merkezinde **OSINT Brain** bulunur — Scryne'in hafızası, bağlamı ve uzun dönemli
knowledge katmanı. Sistem doğduğu anda dünyayı bilmez; zaman içerisinde gözlemler, kaynaklar,
entity'ler, olaylar, iddialar, kanıtlar, ilişkiler, araştırmalar, timeline'lar ve kullanıcı
doğrulamaları aracılığıyla kendi bilgi evrenini oluşturur.

> **Scryne zaman içerisinde yaşayan, değişen ve kendi geçmişini taşıyan bir intelligence
> system'dir.**

### 2. Vizyon

> **Kullanıcının dünyayı araştırmak için açtığı, dünyanın ise kullanıcıya kendisini anlatmaya
> devam ettiği kişisel bir intelligence system oluşturmak.**

Kullanıcı yalnızca "Company X hakkında bilgi ara." dememelidir. Sistem aynı zamanda:

- "Company X hakkında daha önce ne biliyoruz?"
- "Son araştırmadan beri ne değişti?"
- "Bu gelişmenin geçmişteki hangi olaylarla bağlantısı var?"
- "Bu bilgiyi destekleyen bağımsız kaynaklar hangileri?"
- "Bu olay daha önce yürüttüğümüz bir investigation ile ilişkili mi?"
- "Bu gelişme neden önemli?"

sorularını cevaplayabilmelidir.

### 3. Temel Felsefe

**3.1 Everything Is Connected** — Sistemdeki anlamlı hiçbir intelligence nesnesi (Person,
Company, Organization, Event, Source, Claim, Evidence, Location, Investigation) izole
olmamalıdır; bunlar zaman içinde keşfedilip korunan bir knowledge graph'ı oluşturur.

**3.2 Memory Over Search** — Sistem her sorguda dünyayı sıfırdan araştırmamalı, önce kendi
hafızasına (Existing Knowledge → Known Relationships → Historical Context) bakmalı, sonra
gerekirse External Research'e gitmelidir. Her yeni araştırma sistemin gelecekteki araştırma
kapasitesini artırır.

**3.3 Research Creates Memory** — Bir araştırma yalnızca kullanıcıya cevap üretmemeli;
elde edilen anlamlı ve yeterince güvenilir bilgiler kalıcı knowledge'a dönüşebilmelidir. Ancak
her araştırma çıktısı otomatik olarak gerçek kabul edilmemelidir: **Discovery ile Knowledge
aynı şey değildir.**

**3.4 Observation Is Not Truth** — Dış dünyadan gelen ilk bilgi yalnızca bir Observation'dır,
doğrudan FACT haline gelmez. Observation → Evaluation → Corroboration → Evidence →
Confidence → Knowledge State sürecinden geçer.

**3.5 Evidence Before Conclusions** — Sistem "Bu kesinlikle doğru." demek yerine "Bu iddia üç
bağımsız kaynak tarafından destekleniyor ancak doğrudan kanıt bulunmuyor." diyebilmelidir;
source, evidence, provenance, independence, chronology, contradictions, confidence dikkate
alınır.

**3.6 Uncertainty Is Information** — OSINT dünyasında bilinmeyen şeyler de önemlidir. Sistem
zorla kesin cevap üretmemeli, UNKNOWN durumunu geçerli bir knowledge state olarak kabul
etmelidir.

**3.7 The Brain Can Be Wrong** — OSINT Brain hiçbir zaman mutlak doğru kabul edilmemelidir.
Yeni kanıtlar eski bilgileri değiştirebilir (Old Understanding → New Evidence →
Re-evaluation → Updated Understanding), ancak eski bilgi silinmez — Brain yalnızca ne
bildiğini değil, önceden ne düşündüğünü ve neden değiştirdiğini de hatırlar.

### 4. OSINT Brain

OSINT Brain, Scryne'in merkezi hafıza ve context sistemidir. Ancak bu Brain, kullanıcının
kişisel ikinci beyni değildir — Scryne içerisinde bağımsız bir bilgi evrenine sahiptir.

**4.1 Personal Brain vs OSINT Brain**

```text
PERSONAL BRAIN                    OSINT BRAIN
│                                  │
├── Personal knowledge             ├── Entities
├── Projects                       ├── Events
├── Notes                          ├── Sources
├── Decisions                      ├── Claims
├── Personal context                ├── Evidence
└── User memory                    ├── Relationships
                                   ├── Investigations
                                   ├── Observations
                                   └── World State
```

İki Brain varsayılan olarak birbirinden bağımsızdır. OSINT Brain: bilgisayardaki diğer
dosyaları otomatik taramaz, kişisel Brain'den otomatik bilgi almaz, kişisel notları
intelligence knowledge'a dönüştürmez. Sadece Scryne'in kendi yaşam döngüsünden doğan bilgileri
öğrenir.

### 5. OSINT Brain'in Doğumu

OSINT Brain'in belirli bir başlangıç noktası bulunmalıdır (`Born: 2026-XX-XX`, Entities: 0,
Events: 0, Sources: 0, Investigations: 0, Relationships: 0). Sistem çalıştıkça Day 001'den
(observations, sources, entities, events) Day 030'a (historical knowledge, relationships,
investigations) ve Day 365'e (long-term intelligence history, established entity network,
source history, event timelines) doğru büyür. Bu yaklaşım sistemin gerçek bir **intelligence
history** geliştirmesini sağlar.

### 6. Core Knowledge Model

- **6.1 Entity** — Person, Organization, Company, Government, Military Unit, Location,
  Institution, Political Party, Media Organization, Website, Domain
- **6.2 Event** — saldırı, protesto, seçim, açıklama, istifa, satın alma, askeri hareket,
  diplomatik görüşme, doğal afet, ürün lansmanı
- **6.3 Source** — haber sitesi, resmi açıklama, web sayfası, RSS, sosyal medya, kamuya açık
  database, belge, arşiv
- **6.4 Claim** — bir source veya entity tarafından ileri sürülen iddia (örn. "Event X
  occurred at Location Y.")
- **6.5 Evidence** — bir claim'i destekleyen veya çürüten kanıt (belge, fotoğraf, video,
  resmi kayıt, metadata, uydu görüntüsü, arşiv kaydı)
- **6.6 Relationship** — iki veya daha fazla entity/knowledge object arasındaki bağlantı
  (`Person A --works_for--> Company X --acquired--> Company Y --involved_in--> Event Z`)
- **6.7 Investigation** — belirli bir araştırma amacıyla oluşturulan çalışma alanı (Research
  Question, Hypotheses, Entities, Events, Sources, Claims, Evidence, Timeline, Relationships,
  Findings, Conclusion içerebilir)
- **6.8 Observation** — sistemin dış dünyada gözlemlediği ham intelligence sinyali; bilgi
  olabilir ama henüz doğrulanmış gerçek değildir

### 7. Knowledge States

```text
UNKNOWN → OBSERVED → REPORTED → SUPPORTED → CORROBORATED → HIGH CONFIDENCE
```

Alternatif dallar: `REPORTED → CONTRADICTED → UNRESOLVED` veya `REPORTED → DISPROVEN`. Sistem
bilgi durumlarını tarihçesiyle saklamalıdır.

### 8. Intelligence Graph

Scryne'in knowledge graph'ı bütün intelligence nesnelerini birbirine bağlar (Person →
founded → Company → owns/acquired → Company Y/Z → involved_in → Event → reported_by →
Source). Graph zaman içerisinde büyür.

### 9. Temporal Intelligence

Bilginin yalnızca ne olduğu değil, **ne zaman geçerli olduğu** önemlidir. Örnek: `CEO: Person
A, Valid: 2024-01-01 → 2026-05-12` ardından `CEO: Person B, Valid: 2026-05-12 → Present`.
Böylece Brain geçmişi kaybetmez.

### 10. World State

**World State**, sistemin belirli bir zamandaki dünya anlayışının snapshot'ıdır (Entities,
Active Events, Relationships, Known Conflicts, Active Investigations, Significant Changes).
Başka bir tarihte yeni World State oluşturulabilir.

### 11. Intelligence Diff

İki World State arasındaki değişiklikler hesaplanabilir (`WORLD STATE A → DIFF → WORLD STATE
B`), sonuç: NEW ENTITY, REMOVED ENTITY, NEW EVENT, UPDATED EVENT, NEW/REMOVED RELATIONSHIP,
CLAIM CHANGED, CONFIDENCE CHANGED, STATUS CHANGED. Bu özellik "Son 72 saatte ne değişti?"
sorusunun temelini oluşturur.

### 12. Change Detection

Sistem yalnızca yeni veri bulmamalı, **değişimi** tespit etmelidir. Örnek: `Company X CEO:
Person A → Person B` değişimi `CHANGE DETECTED` olarak işaretlenir.

### 13. Why This Matters?

Her önemli intelligence çıktısı mümkün olduğunda "Why does this matter?" sorusunu
cevaplamalıdır — örn. yeni bir ilişki bulunduğunda: ilgili entity zaten izleniyor mu, hangi
investigation'a dahil, kaç bağımsız kaynak destekliyor, benzer aktivite daha önce görüldü mü.
Böylece sistem yalnızca bilgi değil, **context** sağlar.

### 14. Memory Recall

OSINT Brain geçmiş bilgileri aktif olarak geri çağırmalıdır: yeni bir event geldiğinde ilgili
geçmiş event'leri, ilgili investigation'ı, önceki hipotezi, ilgili kaynağı hatırlayıp
sunabilmelidir. Bu davranış Scryne'in "Brain" olmasının temel göstergelerinden biridir.

### 15. Research Relevance Recall

Yeni bir gelişme eski araştırmaları yeniden önemli hale getirebilir — sistem "Bu gelişme
Investigation #23 ile ilişkili olabilir." diyebilir.

### 16. Investigation → Long-Term Memory

Bir investigation tamamlandığında bütün içeriği doğrudan Brain'e aktarılmamalı; Investigation
→ Evaluation → Validated Knowledge → Long-Term Memory sürecinden geçmelidir. Böylece geçici
araştırma notları/hipotezler/doğrulanmamış iddialar ile doğrulanmış knowledge birbirinden
ayrılır.

### 17. Source Intelligence

Kaynakların zaman içinde davranış geçmişi oluşur (Observations, Confirmed, Partially
confirmed, Contradicted, Unresolved sayıları). Bu veriler source evaluation sistemine yardımcı
olabilir, ancak hiçbir source yalnızca geçmiş performansı nedeniyle otomatik "truth source"
kabul edilmemelidir.

### 18. Source Independence

Aynı haberin farklı kaynaklarda kopyalanması bağımsız doğrulama olarak değerlendirilmemelidir
— görünen dört kaynak aslında tek bir information lineage olabilir (`Original Source → News
Agency → Site A → Site B → Site C`). Source independence graph oluşturulması uzun vadeli
hedeflerden biridir.

### 19. Contradiction Engine

Kaynaklar veya claims birbirleriyle çelişebilir (örn. event saati 14:00 vs 17:00). Sistem
bunu `CONTRADICTION DETECTED` olarak işaretler; çelişki çözülmeden bilgi zorla tek bir değere
indirgenmez.

### 20. Entity Resolution

Aynı entity farklı kaynaklarda farklı isimlerle geçebilir (John Smith / J. Smith / John A.
Smith / @johnsmith). Sistem bunların aynı entity olma ihtimalini değerlendirebilir, ancak
otomatik merge işlemleri confidence, evidence, context ile desteklenmelidir.

### 21. Duplicate Detection

Sistem aynı event'in farklı kaynaklarda tekrar yayınlanmasını tespit etmelidir — amaç
signal-to-noise ratio'yu yükseltmek.

### 22. Continuous Monitoring

Kullanıcı Entity/Topic/Event/Location/Organization/Person/Domain/Investigation izlemeye
alabilir. Sistem Observe → Detect → Evaluate → Compare With Memory → Update → Notify
döngüsünü gerçekleştirebilir.

### 23. Active Intelligence

Kullanıcı hiçbir şey sormadan sistem NEW EVENT / NEW RELATIONSHIP / SIGNIFICANT CHANGE /
INVESTIGATION UPDATE / CONTRADICTION / ANOMALY tespit edip uygun öncelik seviyesinde
sunabilir.

### 24. Intelligence Prioritization

Her observation kullanıcıya gösterilmemeli; önem değerlendirmesi novelty, relevance,
confidence, source quality, source independence, impact, entity importance, geographic/
temporal significance, investigation relevance gibi faktörlerle yapılır (CRITICAL / HIGH /
MEDIUM / LOW / INFO).

### 25. Notification Philosophy

> **More signal, less noise.**

Sistem kullanıcıyı sürekli bildirimlerle rahatsız etmemeli; bildirimler importance,
confidence, relevance kombinasyonuna göre filtrelenmelidir.

### 26. Morning Intelligence Brief

Sistem günlük intelligence brief oluşturabilir (Since your last session: N significant
changes, N new events/entities/relationships, N contradictions, N investigations updated),
ardından Priority Intelligence / Historical Connection / Important Change bölümleri.

### 27. Intelligence Inbox

`[HIGH] New conflict event`, `[MEDIUM] Previous claim contradicted` gibi öğeler; her item'ın
neden önemli olduğu, hangi entity'lerle ilişkili olduğu, hangi source'lara dayandığı
görülebilmelidir.

### 28. Entity Intelligence

Her entity için kapsamlı bir intelligence page: Overview (Identity, Aliases, Status, Known
Relationships), Latest Events, Timeline, Sources, Claims, Evidence, Investigations, Recent
Changes, Monitoring.

### 29. Event Intelligence

Her event için: Title, Time, Location, Status, Confidence, Timeline, Entities, Sources,
Claims, Evidence, Related Events, Contradictions, Historical Context.

### 30. Investigation Workspace

`Research Question → Scope → Entities → Sources → Observations → Claims → Evidence →
Hypotheses → Analysis → Findings → Conclusion`.

### 31. Hypothesis System

Araştırmalarda birden fazla hipotez bulunabilir (H1/H2/H3). Kanıtlar hipotezleri
destekleyebilir, zayıflatabilir, çürütebilir veya unresolved bırakabilir.

### 32. Evidence Vault

Kanıtlar ayrı bir evidence system içinde tutulur (Type, Source, Collected, First Seen, Hash,
Related Claims, Related Events) — mümkün olduğunca provenance korunmalıdır.

### 33. Provenance

Her önemli bilginin "Bu nereden geldi?" sorusuna cevap verebilmesi gerekir (`Entity X →
discovered_from → Article #123 → published_by → Source Y → published_at → timestamp`).

### 34. Research Reproducibility

Araştırmanın nasıl gerçekleştirildiği (Started, Queries, Sources, Evidence, Entities, Analyst
actions, Conclusion) mümkün olduğunca kaydedilmelidir, böylece araştırma daha sonra yeniden
incelenebilir.

### 35. AI Role

AI sistemin kendisi değildir; entity extraction, classification, summarization, entity
resolution, relationship suggestion, anomaly detection, hypothesis generation, semantic
search, research assistance, contradiction discovery gibi görevlerde yardımcı olur. Ancak
`SOURCE FACT ≠ AI INTERPRETATION` ayrımı korunmalıdır.

### 36. Human-in-the-Loop

Kullanıcı gerektiğinde sistemin önerilerini değerlendirebilmelidir (`POSSIBLE ENTITY MATCH,
Confidence: 71%, [CONFIRM] [REJECT] [INVESTIGATE]`). Kullanıcı kararları sistemin gelecekteki
değerlendirmelerinde kullanılabilir.

### 37. Learning From Feedback

Scryne'in öğrenmesi kontrolsüz olmamalı: `Observation → AI/Rule Suggestion → Human Feedback →
Evaluation → Knowledge Update`, ileri aşamada `Feedback → Pattern Detection → Rule/Model
Improvement → Validation → Deployment`.

### 38. Knowledge Evolution

Bilgi `UNKNOWN → OBSERVED → REPORTED → SUPPORTED → CORROBORATED` şeklinde gelişebilir; yeni
evidence geldiğinde `CORROBORATED → CONTRADICTED → RE-EVALUATED` olabilir. Bütün değişimler
tarihçesiyle korunur.

### 39. Intelligence History

Scryne zaman içerisinde kendi geçmişini oluşturur (örn. "Entity X discovered" →
"Relationship detected" → "Relationship corroborated" → "Contradicting source discovered" →
"Knowledge re-evaluated"). Bu history gelecekteki intelligence üretiminde kullanılabilir.

### 40. World Memory

Scryne yalnızca entity'leri değil, dünyanın zaman içindeki durumlarını da hatırlamalıdır
(örn. bir bölgenin Ocak/Mart/Haziran/Ağustos boyunca değişen aktivite seviyesi). Bu uzun
dönemli context, yalnızca güncel haberleri görmekten çok daha değerlidir.

### 41. Intelligence Diff (kullanım örneği)

"Dün ile bugün arasında ne değişti?" veya "Son 30 günde bu entity hakkında ne değişti?"
sorularına doğrudan cevap verebilmelidir (örn. `+2 new executives, +1 acquisition, +4 new
relationships, +7 significant mentions, -1 previous claim`).

### 42. Global Intelligence Map

Sistem dünya olaylarını harita üzerinde gösterebilir (Conflict, Political Event, Protest,
Corporate Event, Disaster), filtreler: Time, Region, Event Type, Severity, Confidence,
Entity, Source.

### 43. Timeline Engine

Her entity ve event için tarihsel timeline oluşturulabilir.

### 44. Relationship Explorer

İki entity arasındaki bilinen bağlantılar gösterilebilir (`Person A → Organization B →
Company C → Event D → Source E`) — sistem "A ile E arasında 4 bilinen bağlantı bulundu."
diyebilir.

### 45. Search / Ask Interface

Kullanıcı doğal dille sistemi sorgulayabilmelidir ("What do we know about Company X?", "What
changed about Company X this week?", "Why is Company X relevant to Investigation #12?", "What
evidence supports this claim?", "Which entities are connected to Person A?"). Cevaplar mümkün
olduğunca Brain + Intelligence Core verilerine dayanmalıdır.

### 46. Research Assistant

"Company X'i araştır." dendiğinde sistem: Existing Memory → Entity Resolution → Recent
Information → Sources → Events → Relationships → Claims → Evidence → Historical Context
oluşturabilmelidir.

### 47. Multi-Domain OSINT

GEOINT (harita, konum, uydu görüntüsü, coğrafi analiz), SOCMINT (sosyal medya, açık
profiller, bilgi yayılımı), WEBINT (web araştırması, domain, website, arşiv), DOCINT (PDF,
belge, OCR, metadata), MEDIAINT (fotoğraf, video, metadata, görsel doğrulama), Conflict
Intelligence, Political Intelligence, Corporate Intelligence — zaman içinde eklenebilecek
domain'ler.

### 48. Collection Layer

Collector sistemleri Brain'in kendisi değildir; görevi dünyayı gözlemlemek
(`External World → Collectors → Raw Data → Normalization → Observation`). Brain ise
gözlemlenen dünyayı hatırlamak ve anlamlandırmakla ilgilenir.

### 49. Separation of Concerns

```text
COLLECTOR         "Bir şey buldum."
INTELLIGENCE CORE "Bu ne?"
BRAIN             "Bununla ilgili daha önce ne biliyoruz?"
ANALYSIS          "Bu ne anlama geliyor?"
MONITORING        "Bu değişti mi?"
ALERTING          "Bu kullanıcı için önemli mi?"
USER              "Ne yapmalıyım / neyi araştırmalıyım?"
```

Bu ayrım sistemin büyümesi açısından kritiktir.

### 50. Brain-Centric Architecture

```text
                       SCRYNE OSINT LAB
                              │
                       ┌──────────────┐
                       │  OSINT BRAIN │  Memory / Context / Recall / History
                       └──────┬───────┘
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
    COLLECTION            ANALYSIS             MONITORING
         └────────────────────┼────────────────────┘
                       ┌──────▼───────┐
                       │ INTELLIGENCE │
                       │     CORE     │
                       └──────┬───────┘
       ┌──────────────────────┼──────────────────────┐
       ▼                      ▼                      ▼
   ENTITIES                EVENTS                 SOURCES
       └──────────────────────┼──────────────────────┘
                       ┌──────▼───────┐
                       │  KNOWLEDGE   │
                       │    GRAPH     │
                       └──────┬───────┘
            ┌─────────────────┼─────────────────┐
            ▼                 ▼                 ▼
      INVESTIGATIONS       EVIDENCE          TIMELINES
            └─────────────────┼─────────────────┘
                       ┌──────▼───────┐
                       │ INTELLIGENCE │
                       │  INTERFACE   │
                       └──────┬───────┘
                              ▼
                             USER
```

### 51. Active Intelligence Loop

```text
OBSERVE → COLLECT → PROCESS → REMEMBER → CONNECT → ANALYZE → DETECT CHANGE →
RE-EVALUATE → ALERT → USER → NEW INVESTIGATION → NEW KNOWLEDGE → BRAIN
```

Bu döngü Scryne'in temel yaşam mekanizmasıdır.

### 52. Interface Philosophy

Arayüz klasik bir admin paneli olmamalı; hedef professional, modern, information-dense,
fast, analytical, dark-first, low-noise bir intelligence workstation hissi. Ancak information
density ile visual chaos birbirinden ayrılmalıdır.

> **Amaç çok fazla bilgi göstermek değil, çok fazla bilgi içerisinden anlam çıkarmayı
> kolaylaştırmaktır.**

### 53. Main Intelligence Workspace

```text
┌──────────────────────────────────────────────┐
│ SCRYNE                          ● LIVE        │
├──────────────────────────────────────────────┤
│ Search / Ask / Investigate                    │
├──────────────────────────────────────────────┤
│ PRIORITY INTELLIGENCE                         │
│ ⚠ Significant change                          │
│ ● New relationship                            │
│ ● Investigation update                        │
├──────────────────────────────────────────────┤
│ WORLD MAP      ENTITY GRAPH     TIMELINE      │
└──────────────────────────────────────────────┘
```

### 54. Intelligence Navigation

Kullanıcı her knowledge object üzerinden diğerlerine geçebilmelidir (`Company X → Event #72
→ Source #142 → Person Y → Organization Z → Investigation #18 → Evidence #92`) — sistem bir
"web of intelligence" hissi vermelidir.

### 55. Security & Privacy

Öncelikler: local-first, least privilege, secure secrets, encrypted credentials, audit
logging, safe integrations, backup, restore, access control, network safety. Özellikle dış
kaynaklardan veri toplayan sistemlerde SSRF, malicious content, poisoned documents, prompt
injection, malicious web content gibi tehditler mimarinin bir parçası olarak ele alınmalıdır.

### 56. Data Provenance

Önemli veriler mümkün olduğunca source, timestamp, collection method, original location,
content hash, processing history bilgilerine sahip olmalıdır.

### 57. Resilience

Harici kaynakların çalışmaması sistemin tamamen kullanılamaz hale gelmesine yol açmamalıdır
(`External Source Down → Cached/Historical Knowledge → System remains usable`). Eski bilgi ile
güncel bilgi açıkça ayrılmalıdır.

### 58. Local-First Intelligence

Uzun vadede memory, investigation, graph, evidence, historical data olabildiğince yerel
tutulabilir. External API'ler capability sağlayabilir ancak Brain'in tamamı tek bir üçüncü
taraf servise bağımlı olmamalıdır.

### 59. Extensibility

`Scryne v1 → Research`, `v2 → Entity Intelligence`, `v3 → Event Intelligence`, `v4 →
Monitoring`, `v5 → Intelligence Graph`, `v6 → GEOINT`, `v7 → Media/Document Intelligence`.
Core knowledge model mümkün olduğunca stabil tutulmalıdır.

### 60. Capability Model

```text
capabilities/
├── geoint/
├── webint/
├── socmint/
├── docint/
├── mediaint/
├── corporate/
├── political/
└── conflict/
```

Her capability Core ve Brain ile standart bir interface üzerinden konuşmalıdır.

### 61–66. Örnek Senaryolar

- **Şirket**: "Company X hakkında ne biliyoruz?" → Existing Memory → Entity Resolution →
  Known Relationships → Historical Events → Recent Changes → Current Sources →
  Investigations → Claims → Evidence.
- **Çatışma**: Bir bölge sürekli izlenir; yeni observation → source discovery → independent
  corroboration → event creation → historical comparison → related entities → confidence
  evaluation.
- **Eski Araştırmanın Yeniden Canlanması**: Yeni event tespit edilir, Brain ilgili eski
  Investigation'ı hatırlatır, eski hipotezler yeni kanıtla yeniden değerlendirilir.
- **Intelligence Diff**: "Company X hakkında son 30 günde ne değişti?" → World State diff.
- **Why This Matters**: Yeni bir relationship bulunduğunda sadece gösterilmez, neden önemli
  olduğu (izlenen entity, ilgili investigation, kaç bağımsız kaynak, geçmiş benzer aktivite)
  açıklanır.
- **Contradiction**: Bir claim için çelişen kaynaklar bulunduğunda `UNRESOLVED` olarak
  işaretlenir, sonuç zorla kesinleştirilmez.

### 67. Başlangıç Stratejisi

İlk hedef: **Sağlam bir OSINT Brain + Core Knowledge Model + Investigation System + temel
Collection + Monitoring döngüsü oluşturmak.** Öncelik sırası: Brain → Knowledge Model →
Investigation → Collection → Monitoring → Graph → Advanced Analysis.

### 68. İlk Temel Capability'ler

```text
✓ OSINT Brain            ✓ Persistent Memory      ✓ Entities
✓ Events                 ✓ Sources                ✓ Claims
✓ Evidence               ✓ Relationships          ✓ Investigations
✓ Timeline               ✓ Basic Graph            ✓ Search
✓ Monitoring             ✓ Change Detection       ✓ Intelligence Inbox
✓ Notifications
```

### 69. İlk Sürümde Yapılmaması Gerekenler

Bütün interneti taramak, yüzlerce API bağlamak, bütün OSINT alanlarını desteklemek, tamamen
otonom investigation, kontrolsüz AI kararları, gereksiz microservice karmaşası, devasa
frontend — önce Brain'in ve knowledge modelinin doğru çalışması sağlanmalıdır.

### 70. Mimari Karar İlkesi

> **"Bu özellik Scryne'in intelligence yaşam döngüsüne gerçekten katkı sağlıyor mu?"**

Eğer sağlamıyorsa yalnızca teknoloji eklemek için sisteme eklenmemelidir.

### 71. Açık Mimari Sorular (Q1–Q25)

Proje ilerlemeden önce cevaplanması gereken tasarım soruları — bkz. yukarıdaki "Açık
Sorular" bölümü için öne çıkanlar. Tam liste:

1. **Q1** — Brain tam olarak neyi "hatırlamalı"? Her observation mi, yoksa filtrelenmiş bir
   `Observation → Temporary Memory → Evaluation → Long-Term Memory` akışı mı?
2. **Q2** — Brain ile Intelligence Database arasındaki sınır nerede? (memory / semantic
   context / knowledge store — hangisi nerede tutulacak?)
3. **Q3** — "Truth" nasıl tanımlanacak? (verified / high confidence / supported / reported /
   unresolved / false gibi hangi knowledge states kullanılacak?)
4. **Q4** — Confidence nasıl hesaplanacak? (source quality, independence, evidence,
   corroboration, historical reliability — AI mi, deterministic rule engine mi, hibrit mi?)
5. **Q5** — Source reliability geçmişi future confidence'ı ne kadar etkileyecek?
6. **Q6** — Source independence teknik olarak nasıl tespit edilecek?
7. **Q7** — Entity merge otomatik mi yapılacak, yoksa her zaman "Possible Match" olarak mı
   bırakılacak?
8. **Q8** — Brain ne zaman "öğrenmiş" sayılacak? (keşfedildiğinde / doğrulandığında /
   kullanıcı onayladığında / belirli confidence seviyesine ulaştığında?)
9. **Q9** — Brain'in yanlış bilgiyi düzeltme mekanizması: overwrite mi, version mı,
   contradiction mı oluşturacak?
10. **Q10** — World State ne sıklıkla oluşturulacak? (sürekli / saatlik / günlük /
    event-driven?)
11. **Q11** — Intelligence Diff neyi karşılaştıracak? (entity / graph / claims / confidence /
    source landscape değişiklikleri?)
12. **Q12** — "Why This Matters" nasıl üretilecek? (rule-based / AI-generated / graph-based /
    hibrit — ve AI'ın kaynağı nasıl gösterilecek?)
13. **Q13** — Active Intelligence ne kadar aktif olmalı — sabit eşik mi, kullanıcı
    davranışından öğrenen dinamik threshold mı?
14. **Q14** — Kullanıcının Ignore/Confirm/Reject/Investigate/Follow davranışları sistemin
    future prioritization'ını etkilemeli mi?
15. **Q15** — AI ile Source Fact UI'da nasıl kesin olarak ayrılacak? (SOURCE FACT / AI
    ANALYSIS / SYSTEM INFERENCE / USER INTERPRETATION)
16. **Q16** — Investigation hangi durumlara sahip olacak? (OPEN / ACTIVE / PAUSED / RESOLVED /
    CLOSED / ARCHIVED?)
17. **Q17** — Tamamlanan investigation'ın hangi kısımları (tüm notlar / yalnızca verified
    findings / hypotheses / source graph) long-term memory'ye aktarılacak?
18. **Q18** — Evidence retention nasıl olacak? (sonsuza kadar mı, hash mi, sadece metadata mı,
    orijinal dosya lokal mi tutulacak?)
19. **Q19** — Eski bilgi silinmeyecekse storage büyümesi nasıl kontrol edilecek?
20. **Q20** — OSINT Brain'in ölçek sınırı ne olacak? (1,000 entity'den 1M entity / 100M
    observation'a giderse mevcut model yeterli mi?)
21. **Q21** — Local-first ne kadar ileri götürülecek? (%100 local mi, Local Core + External
    APIs + Optional Cloud AI hibrit mi?)
22. **Q22** — Collector güvenliği nasıl sağlanacak? (prompt injection, malicious HTML/
    documents, SSRF, poisoned data — Collector → Intelligence Core sınırı nasıl güvenli hale
    getirilecek? **Kritik güvenlik sorusu.**)
23. **Q23** — Observe/collect/classify/connect/notify otomatik olabilir; investigate/
    conclude/verify/merge işlerinde insan onayı nerede gerekecek? **Temel ürün felsefesi
    kararı.**
24. **Q24** — Brain kendi başına araştırma başlatabilecek mi? (anomaly → research task →
    collect → analyze → report — istenen otonomi seviyesi bu.)
25. **Q25** — Scryne'in kapsam sınırı nerede? Hangi domainler supported / experimental /
    unsupported olarak açıkça tanımlanacak?

### 72. Tasarım İlkeleri

1. Evidence First — kanıt yoksa kesinlik yok.
2. Memory Is Persistent — anlamlı knowledge geçmişini kaybetmez.
3. History Is Immutable — geçmişin nasıl değiştiği izlenebilir olmalıdır.
4. Uncertainty Is Valid — bilinmeyen bilgi olarak kabul edilir.
5. Everything Is Connected — knowledge graph sistemin temelidir.
6. AI Is Assistive — AI karar mekanizmasının yerine geçmez.
7. Human Remains In Control — kritik intelligence decisions kullanıcı tarafından
   denetlenebilir.
8. Signal Over Noise — her observation alert değildir.
9. Context Over Headlines — sistem yalnızca yeni bilgiyi değil, neden önemli olduğunu
   göstermelidir.
10. Memory Over Statelessness — her araştırma gelecekteki araştırmaları güçlendirmelidir.

### 73. Development Roadmap (v2 taslağındaki ilk faz fikri)

```text
Phase 0 — Brain Foundation        AvenoxBeyin Core → OSINT-specific adaptation →
                                   Memory Model → Knowledge Model
Phase 1 — Intelligence Core       Entities, Events, Sources, Claims, Evidence, Relationships
Phase 2 — Investigation           Investigations, Hypotheses, Findings, Evidence, Timeline
Phase 3 — Collection              RSS, Web, Public APIs, News, Documents
Phase 4 — Monitoring              Entity/Topic/Event Monitoring, Change Detection
Phase 5 — Brain Intelligence      Memory Recall, Historical Context, Knowledge Evolution,
                                   Contradiction, World State, Intelligence Diff
Phase 6 — Active Intelligence     Prioritization, Alerts, Morning Brief, Why This Matters,
                                   Investigation Relevance
Phase 7 — Advanced OSINT          GEOINT, SOCMINT, DOCINT, MEDIAINT, Corporate/Conflict
                                   Intelligence
Phase 8 — Advanced Assistant      Anomaly Detection, Research Suggestions, Autonomous
                                   Research Tasks, Advanced Graph Analysis, Cross-domain
                                   Intelligence
```

> Not: Phase 0'da geçen "AvenoxBeyin Core" ifadesi, kullanıcının ScryneOS vault'unda zaten
> kullandığı ikinci-beyin mimarisine referans — bkz. yukarıdaki "Mimari Not" bölümü. Bu
> roadmap taslağı, `docs/Roadmap.md`'nin faz faz somut "bitti kriteri" ile netleştirileceği
> roadmap aşamasında yeniden işlenecek; burada olduğu gibi doğrudan kopyalanmayacak.

### 74. Başarı Kriterleri

Scryne başarılı olduğunda kullanıcı "Dünyada ne oluyor?" sorusuna cevap alabilmeli; daha
önemlisi "Bu gelişme daha önce bildiğimiz şeylerle nasıl bağlantılı?" sorusuna da cevap
verebilmelidir. "Bunu daha önce araştırmış mıydım?" sorusuna "Evet. Investigation #17'de
bununla ilişkili bir hipotez oluşturmuştun." diyebilmelidir. Ayrıca "Bu neden önemli?"
sorusuna context, "Sistem bunu neden düşünüyor?" sorusuna evidence ve provenance
gösterebilmelidir.

### 75. Nihai Intelligence Loop

```text
WORLD → OBSERVE → COLLECT → UNDERSTAND → REMEMBER → CONNECT → COMPARE → DETECT CHANGE →
RE-EVALUATE → PRIORITIZE → INFORM → USER → INVESTIGATE → NEW KNOWLEDGE → BRAIN → WORLD
```

Bu döngü sürekli devam eder.

### 76. Scryne'in Karakteri

Scryne'in kişiliği bir chatbot olmamalıdır. Sakin, analitik, kanıt odaklı, belirsizlik
konusunda dürüst, bağlam sağlayan, gerektiğinde uyarıcı, gereksiz konuşmayan bir intelligence
companion olmalıdır. Sistem "Bence..." yerine "Mevcut evidence'a göre..." demelidir.

### 77. Nihai Tanım

> **Scryne, açık kaynaklardan dünyayı sürekli gözlemleyen, gördüğü bilgileri zaman
> içerisinde kendi hafızasında biriktiren, entity'ler, olaylar, kaynaklar, kanıtlar ve
> araştırmalar arasında bağlantılar kuran, geçmiş bilgileri yeni gelişmelerle yeniden
> değerlendiren ve önemli intelligence'ı kullanıcıya aktif olarak sunan kişisel bir
> Intelligence Operating System'dir.**

### 78. Nihai Vizyon

Scryne'in amacı başka insanların kullandığı bir OSINT platformu oluşturmak değildir. Amaç:
kullanıcının kendisine ait, zaman içerisinde gelişen, kendi hafızasını oluşturan, dünyayı
sürekli gözlemleyen, araştırmaları birbirine bağlayan, geçmişi unutmayan ve gerektiğinde
kullanıcıyı kendiliğinden bilgilendiren kişisel bir intelligence ecosystem oluşturmaktır.

Sistem doğduğunda her şeyi bilmez. Öğrendikçe büyür. Gözlemledikçe hafızası gelişir.
Araştırdıkça bağlantıları artar. Yeni kanıt geldiğinde eski anlayışını değiştirebilir. Zaman
geçtikçe kendi intelligence history'sini oluşturur.

> **Scryne yalnızca bilgi depolayan bir uygulama değil, dünyaya ilişkin kendi tarihine sahip
> yaşayan bir OSINT Brain haline gelir.**

### 79. Project Identity

- **Name:** Scryne OSINT Lab
- **Category:** Personal Intelligence / OSINT / Investigation / Knowledge Graph
- **Core Concept:** Living OSINT Brain
- **Architecture Philosophy:** Brain-centric, modular, local-first, evidence-driven
- **Primary User:** Individual researcher / analyst
- **Primary Goal:** Continuous open-source intelligence collection, memory, analysis and
  investigation
- **Long-Term Goal:** A personal intelligence operating system that continuously observes the
  external world, remembers its history, understands relationships, detects changes and
  develops an interconnected knowledge model over time.

### 80. Guiding Principle

```text
Observe. Remember. Connect. Verify. Compare. Understand. Monitor. Re-evaluate. Inform.
```

> **Scryne does not simply search the world. Scryne builds a memory of it. It does not
> simply remember what happened. It understands what changed, what is connected, what
> remains uncertain, and why it matters.**
