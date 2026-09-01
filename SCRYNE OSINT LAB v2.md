# SCRYNE OSINT LAB

> **A Personal Intelligence Operating System**
>
> Dünyayı sürekli gözlemleyen, açık kaynaklardan intelligence toplayan, gördüklerini hatırlayan, yeni bilgileri geçmiş bilgileriyle karşılaştıran, entity'ler ve olaylar arasındaki ilişkileri keşfeden, belirsizlikleri ve çelişkileri koruyan ve kullanıcıyı önemli gelişmeler hakkında aktif olarak bilgilendiren yaşayan bir kişisel OSINT intelligence ekosistemi.

---

# 1. Proje Özeti

**Scryne OSINT Lab**, klasik anlamda bir OSINT arama motoru, haber takip uygulaması veya dashboard değildir.

Scryne; açık kaynaklardan veri toplayan, bu verileri yapılandıran, kaynaklarını ve provenance bilgisini koruyan, entity'leri ve olayları birbirine bağlayan, araştırmaları kalıcı hafızaya dönüştüren ve zaman içerisinde kendi intelligence knowledge base'ini oluşturan **yaşayan bir kişisel intelligence operating system'dir.**

Sistemin merkezinde:

> **OSINT Brain**

bulunur.

OSINT Brain, Scryne'in hafızası, bağlamı ve uzun dönemli knowledge katmanıdır.

Sistem doğduğu anda dünyayı bilmez.

Zaman içerisinde:

- gözlemler,
- kaynaklar,
- entity'ler,
- olaylar,
- iddialar,
- kanıtlar,
- ilişkiler,
- araştırmalar,
- timeline'lar,
- kullanıcı doğrulamaları

aracılığıyla kendi bilgi evrenini oluşturur.

Bu nedenle Scryne statik bir database değildir.

> **Scryne zaman içerisinde yaşayan, değişen ve kendi geçmişini taşıyan bir intelligence system'dir.**

---

# 2. Vizyon

Scryne'in nihai vizyonu:

> **Kullanıcının dünyayı araştırmak için açtığı, dünyanın ise kullanıcıya kendisini anlatmaya devam ettiği kişisel bir intelligence system oluşturmak.**

Kullanıcı yalnızca:

> "Company X hakkında bilgi ara."

dememelidir.

Sistem aynı zamanda:

> "Company X hakkında daha önce ne biliyoruz?"

> "Son araştırmadan beri ne değişti?"

> "Bu gelişmenin geçmişteki hangi olaylarla bağlantısı var?"

> "Bu bilgiyi destekleyen bağımsız kaynaklar hangileri?"

> "Bu olay daha önce yürüttüğümüz bir investigation ile ilişkili mi?"

> "Bu gelişme neden önemli?"

sorularını cevaplayabilmelidir.

---

# 3. Temel Felsefe

Scryne aşağıdaki prensipler üzerine kurulmalıdır.

---

## 3.1 Everything Is Connected

Sistemdeki anlamlı hiçbir intelligence nesnesi izole olmamalıdır.

Bir:

- Person
- Company
- Organization
- Event
- Source
- Claim
- Evidence
- Location
- Investigation

başka nesnelerle ilişkilendirilebilir olmalıdır.

Örnek:

```text
Person A
    ↓
works_for
    ↓
Organization B
    ↓
involved_in
    ↓
Event C
    ↓
reported_by
    ↓
Source D
    ↓
supports
    ↓
Claim E
```

Sistem bu bağlantıları zaman içerisinde keşfetmeli ve korumalıdır.

---

# 3.2 Memory Over Search

Sistem her sorguda dünyayı sıfırdan araştırmamalıdır.

Önce kendi hafızasına bakmalıdır.

```text
USER QUERY
    ↓
OSINT BRAIN
    ↓
EXISTING KNOWLEDGE
    ↓
KNOWN RELATIONSHIPS
    ↓
HISTORICAL CONTEXT
    ↓
NEW EXTERNAL RESEARCH
    ↓
NEW INFORMATION
    ↓
MEMORY UPDATE
```

Böylece her yeni araştırma sistemin gelecekteki araştırma kapasitesini artırır.

---

# 3.3 Research Creates Memory

Bir araştırma yalnızca kullanıcıya cevap üretmemelidir.

Araştırmadan elde edilen anlamlı ve yeterince güvenilir bilgiler kalıcı knowledge'a dönüşebilmelidir.

```text
Investigation
    ↓
Observations
    ↓
Entities
    ↓
Events
    ↓
Claims
    ↓
Evidence
    ↓
Relationships
    ↓
Evaluation
    ↓
Long-Term Knowledge
```

Ancak her araştırma çıktısı otomatik olarak gerçek kabul edilmemelidir.

**Discovery ile Knowledge aynı şey değildir.**

---

# 3.4 Observation Is Not Truth

Sistemin dış dünyadan gördüğü ilk bilgi yalnızca bir:

> **Observation**

olmalıdır.

Örneğin:

```text
Observation:

Source A reports:
"Event X occurred in Location Y."
```

Bu bilgi doğrudan:

```text
FACT
```

haline gelmemelidir.

Bunun yerine:

```text
Observation
    ↓
Evaluation
    ↓
Corroboration
    ↓
Evidence
    ↓
Confidence
    ↓
Knowledge State
```

sürecinden geçebilir.

---

# 3.5 Evidence Before Conclusions

Sistem sonuç üretirken mümkün olduğunca:

- source
- evidence
- provenance
- independence
- chronology
- contradictions
- confidence

gibi faktörleri dikkate almalıdır.

Sistem:

> "Bu kesinlikle doğru."

demek yerine gerektiğinde:

> "Bu iddia üç bağımsız kaynak tarafından destekleniyor ancak doğrudan kanıt bulunmuyor."

diyebilmelidir.

---

# 3.6 Uncertainty Is Information

OSINT dünyasında bilinmeyen şeyler de önemlidir.

Sistem zorla kesin cevap üretmemelidir.

Örneğin:

```text
Location:

Location A
Confidence: 61%

Location B
Confidence: 28%

Unknown:
11%
```

Sistem:

> **UNKNOWN**

durumunu geçerli bir knowledge state olarak kabul etmelidir.

---

# 3.7 The Brain Can Be Wrong

OSINT Brain hiçbir zaman mutlak doğru kabul edilmemelidir.

Yeni kanıtlar eski bilgileri değiştirebilir.

```text
OLD UNDERSTANDING
        ↓
NEW EVIDENCE
        ↓
RE-EVALUATION
        ↓
UPDATED UNDERSTANDING
```

Ancak eski bilgi silinmemelidir.

Örneğin:

```text
Previous understanding:
Person A was CEO.

Valid:
2024 → 2026-05-12

Updated understanding:
Person B is CEO.

Reason:
Official company announcement.
```

Böylece Brain yalnızca ne bildiğini değil, **önceden ne düşündüğünü ve neden değiştirdiğini** de hatırlar.

---

# 4. OSINT Brain

OSINT Brain, Scryne'in merkezi hafıza ve context sistemidir.

Ancak bu Brain, kullanıcının kişisel ikinci beyni değildir.

Scryne içerisinde bağımsız bir bilgi evrenine sahiptir.

---

## 4.1 Personal Brain vs OSINT Brain

```text
PERSONAL BRAIN
│
├── Personal knowledge
├── Projects
├── Notes
├── Decisions
├── Personal context
└── User memory


OSINT BRAIN
│
├── Entities
├── Events
├── Sources
├── Claims
├── Evidence
├── Relationships
├── Investigations
├── Observations
└── World State
```

İki Brain varsayılan olarak birbirinden bağımsızdır.

OSINT Brain:

- bilgisayardaki diğer dosyaları otomatik taramaz,
- kişisel Brain'den otomatik bilgi almaz,
- kişisel notları intelligence knowledge'a dönüştürmez.

OSINT Brain yalnızca Scryne'in kendi yaşam döngüsünden doğan bilgileri öğrenir.

---

# 5. OSINT Brain'in Doğumu

OSINT Brain'in belirli bir başlangıç noktası bulunmalıdır.

```text
OSINT BRAIN

Born:
2026-XX-XX

Entities:
0

Events:
0

Sources:
0

Investigations:
0

Relationships:
0
```

Sistem çalıştıkça:

```text
Day 001
+ Observations
+ Sources
+ Entities
+ Events

Day 030
+ Historical knowledge
+ Relationships
+ Investigations

Day 365
+ Long-term intelligence history
+ Established entity network
+ Source history
+ Event timelines
```

oluşur.

Bu yaklaşım sistemin gerçek bir **intelligence history** geliştirmesini sağlar.

---

# 6. Core Knowledge Model

Scryne'in temel bilgi modeli aşağıdaki nesnelerden oluşur.

---

## 6.1 Entity

Sistemin tanımlayabildiği varlık.

Örnek:

- Person
- Organization
- Company
- Government
- Military Unit
- Location
- Institution
- Political Party
- Media Organization
- Website
- Domain

---

## 6.2 Event

Gerçek dünyada gerçekleşen veya gerçekleştiği iddia edilen olay.

Örnek:

- saldırı
- protesto
- seçim
- açıklama
- istifa
- satın alma
- askeri hareket
- diplomatik görüşme
- doğal afet
- ürün lansmanı

---

## 6.3 Source

Bilginin geldiği kaynak.

Örnek:

- haber sitesi
- resmi açıklama
- web sayfası
- RSS
- sosyal medya
- kamuya açık database
- belge
- arşiv

---

## 6.4 Claim

Bir source veya entity tarafından ileri sürülen iddia.

```text
Claim:

"Event X occurred at Location Y."
```

---

## 6.5 Evidence

Bir claim'i destekleyen veya çürüten kanıt.

Örnek:

- belge
- fotoğraf
- video
- resmi kayıt
- metadata
- uydu görüntüsü
- arşiv kaydı

---

## 6.6 Relationship

İki veya daha fazla entity/knowledge object arasındaki bağlantı.

```text
Person A
    └── works_for ──> Company X

Company X
    └── acquired ──> Company Y

Company Y
    └── involved_in ──> Event Z
```

---

## 6.7 Investigation

Belirli bir araştırma amacıyla oluşturulan çalışma alanıdır.

Bir investigation:

```text
Research Question
Hypotheses
Entities
Events
Sources
Claims
Evidence
Timeline
Relationships
Findings
Conclusion
```

içerebilir.

---

## 6.8 Observation

Sistemin dış dünyada gözlemlediği ham intelligence sinyalidir.

Observation:

> bilgi olabilir, ancak henüz doğrulanmış gerçek değildir.

---

# 7. Knowledge States

Knowledge nesneleri farklı durumlara sahip olabilir.

Örnek:

```text
UNKNOWN
    ↓
OBSERVED
    ↓
REPORTED
    ↓
SUPPORTED
    ↓
CORROBORATED
    ↓
HIGH CONFIDENCE
```

Alternatif olarak:

```text
REPORTED
    ↓
CONTRADICTED
    ↓
UNRESOLVED
```

veya:

```text
REPORTED
    ↓
DISPROVEN
```

Sistem bilgi durumlarını tarihçesiyle saklamalıdır.

---

# 8. Intelligence Graph

Scryne'in knowledge graph'ı bütün intelligence nesnelerini birbirine bağlar.

Örnek:

```text
                 Person A
                    │
                 founded
                    │
                    ▼
               Company X
                /       \
             owns       acquired
              /            \
             ▼              ▼
        Company Y        Company Z
             │
         involved_in
             │
             ▼
          Event #42
             │
         reported_by
             │
             ▼
          Source #91
```

Graph zaman içerisinde büyür.

---

# 9. Temporal Intelligence

Bilginin yalnızca ne olduğu değil, **ne zaman geçerli olduğu** önemlidir.

Her önemli bilgi mümkün olduğunca temporal context taşımalıdır.

```text
CEO:
Person A

Valid:
2024-01-01 → 2026-05-12


CEO:
Person B

Valid:
2026-05-12 → Present
```

Böylece Brain geçmişi kaybetmez.

---

# 10. World State

Scryne'in önemli kavramlarından biri **World State** olacaktır.

World State, sistemin belirli bir zamandaki dünya anlayışının snapshot'ıdır.

Örneğin:

```text
WORLD STATE
2026-08-29 00:00

Entities:
...

Active Events:
...

Relationships:
...

Known Conflicts:
...

Active Investigations:
...

Significant Changes:
...
```

Başka bir tarihte yeni World State oluşturulabilir.

---

# 11. Intelligence Diff

İki World State arasındaki değişiklikler hesaplanabilir.

```text
WORLD STATE A
        ↓
        DIFF
        ↓
WORLD STATE B
```

Sonuç:

```text
NEW ENTITY
REMOVED ENTITY
NEW EVENT
UPDATED EVENT
NEW RELATIONSHIP
REMOVED RELATIONSHIP
CLAIM CHANGED
CONFIDENCE CHANGED
STATUS CHANGED
```

Bu özellik:

> **"Son 72 saatte ne değişti?"**

sorusunun temelini oluşturabilir.

---

# 12. Change Detection

Scryne'in en önemli capability'lerinden biri değişim tespiti olmalıdır.

Örneğin:

```text
Yesterday:

Company X
CEO → Person A
```

Bugün:

```text
Company X
CEO → Person B
```

Sistem:

```text
CHANGE DETECTED

Company X

CEO:
Person A → Person B
```

olarak değerlendirebilir.

---

# 13. Why This Matters?

Scryne yalnızca alert üretmemelidir.

Her önemli intelligence çıktısı mümkün olduğunda:

> **Why does this matter?**

sorusunu cevaplamalıdır.

Örneğin:

```text
HIGH PRIORITY

New relationship detected.

Company X
        ↓
possible supplier
        ↓
Organization Y


Why this matters:

• Organization Y is part of Investigation #12.
• This relationship was previously unknown.
• 3 independent sources support the connection.
• Similar activity was detected 18 days ago.
```

Böylece sistem yalnızca bilgi değil, **context** sağlar.

---

# 14. Memory Recall

OSINT Brain geçmiş bilgileri aktif olarak geri çağırmalıdır.

Yeni bilgi:

```text
New Event
```

Brain:

```text
Related historical events:
Event #12
Event #31

Related investigation:
Investigation #08

Previous hypothesis:
H2

Relevant source:
Source #17
```

diyebilmelidir.

Bu davranış Scryne'in "Brain" olmasının temel göstergelerinden biridir.

---

# 15. Research Relevance Recall

Yeni bir gelişme eski araştırmaları yeniden önemli hale getirebilir.

Örneğin:

```text
NEW EVENT
    ↓
Historical Search
    ↓
Investigation #23
    ↓
Last updated:
4 months ago
```

Sistem:

> **"Bu gelişme Investigation #23 ile ilişkili olabilir."**

diyebilir.

---

# 16. Investigation → Long-Term Memory

Bir investigation tamamlandığında bütün içeriği doğrudan Brain'e aktarılmamalıdır.

Bunun yerine:

```text
Investigation
    ↓
Evaluation
    ↓
Validated Knowledge
    ↓
Long-Term Memory
```

süreci uygulanmalıdır.

Bu sayede:

- geçici araştırma notları,
- hipotezler,
- doğrulanmamış iddialar

ile:

- doğrulanmış knowledge

birbirinden ayrılır.

---

# 17. Source Intelligence

Scryne kaynakları yalnızca URL olarak görmemelidir.

Kaynakların zaman içerisinde davranış geçmişi oluşabilir.

```text
SOURCE X

Observations:
142

Confirmed:
91

Partially confirmed:
27

Contradicted:
14

Unresolved:
10
```

Bu veriler source evaluation sistemine yardımcı olabilir.

Ancak hiçbir source yalnızca geçmiş performansı nedeniyle otomatik olarak "truth source" kabul edilmemelidir.

---

# 18. Source Independence

Scryne aynı haberin farklı kaynaklarda kopyalanmasını bağımsız doğrulama olarak değerlendirmemelidir.

Örneğin:

```text
Original Source
      ↓
News Agency
      ↓
News Site A
      ↓
News Site B
      ↓
News Site C
```

Görünen dört kaynak aslında tek bir information lineage olabilir.

Bu nedenle source independence graph oluşturulması uzun vadeli hedeflerden biridir.

---

# 19. Contradiction Engine

Kaynaklar veya claims birbirleriyle çelişebilir.

Örneğin:

```text
Source A:
Event occurred at 14:00

Source B:
Event occurred at 17:00
```

Sistem:

```text
CONTRADICTION DETECTED

Event time

14:00
vs
17:00
```

olarak işaretleyebilir.

Çelişki çözülmeden bilgi zorla tek bir değere indirgenmemelidir.

---

# 20. Entity Resolution

Aynı entity farklı kaynaklarda farklı isimlerle geçebilir.

```text
John Smith
J. Smith
John A. Smith
@johnsmith
```

Sistem bunların aynı entity olma ihtimalini değerlendirebilir.

Ancak otomatik merge işlemleri:

- confidence
- evidence
- context

ile desteklenmelidir.

---

# 21. Duplicate Detection

Sistem aynı event'in farklı kaynaklarda tekrar yayınlanmasını tespit etmelidir.

Amaç:

> **Signal-to-noise ratio'yu yükseltmek.**

---

# 22. Continuous Monitoring

Scryne yalnızca kullanıcı açtığında çalışmamalıdır.

Kullanıcı:

```text
Entity
Topic
Event
Location
Organization
Person
Domain
Investigation
```

izlemeye alabilir.

Sistem:

```text
Observe
    ↓
Detect
    ↓
Evaluate
    ↓
Compare With Memory
    ↓
Update
    ↓
Notify
```

döngüsünü gerçekleştirebilir.

---

# 23. Active Intelligence

Scryne'in temel farklarından biri aktif olmasıdır.

Kullanıcı hiçbir şey sormadan sistem:

```text
NEW EVENT
NEW RELATIONSHIP
SIGNIFICANT CHANGE
INVESTIGATION UPDATE
CONTRADICTION
ANOMALY
```

tespit edip uygun öncelik seviyesinde kullanıcıya sunabilir.

---

# 24. Intelligence Prioritization

Her observation kullanıcıya gösterilmemelidir.

Önem değerlendirmesinde:

- novelty
- relevance
- confidence
- source quality
- source independence
- impact
- entity importance
- geographic significance
- temporal significance
- investigation relevance

gibi faktörler kullanılabilir.

Örnek:

```text
CRITICAL
HIGH
MEDIUM
LOW
INFO
```

---

# 25. Notification Philosophy

Amaç:

> **More signal, less noise.**

Sistem kullanıcıyı sürekli bildirimlerle rahatsız etmemelidir.

Bildirimler:

- importance
- confidence
- relevance

kombinasyonuna göre filtrelenebilmelidir.

---

# 26. Morning Intelligence Brief

Sistem günlük intelligence brief oluşturabilir.

```text
SCRYNE MORNING BRIEF

Since your last session:

17 significant changes

4 new events

8 new entities

12 new relationships

2 contradictions

3 investigations updated
```

Ardından:

### Priority Intelligence

```text
Conflict escalation detected
```

### Historical Connection

```text
Related to Investigation #17
```

### Important Change

```text
Leadership change detected
```

---

# 27. Intelligence Inbox

Kullanıcı yeni gelişmeleri tek bir intelligence inbox içerisinde görebilir.

```text
INTELLIGENCE INBOX

[HIGH]
New conflict event

[HIGH]
Entity relationship changed

[MEDIUM]
Previous claim contradicted

[MEDIUM]
Investigation updated

[LOW]
New mention detected
```

Her item'ın:

- neden önemli olduğu,
- hangi entity'lerle ilişkili olduğu,
- hangi source'lara dayandığı

görülebilmelidir.

---

# 28. Entity Intelligence

Her entity için kapsamlı bir intelligence page bulunabilir.

```text
COMPANY X

Overview

Identity
Aliases
Status
Known Relationships

────────────────

LATEST EVENTS

────────────────

TIMELINE

────────────────

SOURCES

────────────────

CLAIMS

────────────────

EVIDENCE

────────────────

INVESTIGATIONS

────────────────

RECENT CHANGES

────────────────

MONITORING
```

---

# 29. Event Intelligence

Her event için:

```text
EVENT #042

Title
Time
Location
Status
Confidence

Timeline

Entities

Sources

Claims

Evidence

Related Events

Contradictions

Historical Context
```

bulunabilir.

---

# 30. Investigation Workspace

Araştırma ortamı:

```text
Research Question
        ↓
Scope
        ↓
Entities
        ↓
Sources
        ↓
Observations
        ↓
Claims
        ↓
Evidence
        ↓
Hypotheses
        ↓
Analysis
        ↓
Findings
        ↓
Conclusion
```

şeklinde ilerleyebilir.

---

# 31. Hypothesis System

Araştırmalarda birden fazla hipotez bulunabilir.

```text
H1:
Company X is directly controlled by Organization Y.

H2:
The relationship is indirect.

H3:
The apparent relationship is coincidental.
```

Kanıtlar hipotezleri:

- destekleyebilir,
- zayıflatabilir,
- çürütebilir,
- unresolved bırakabilir.

---

# 32. Evidence Vault

Kanıtlar ayrı bir evidence system içerisinde tutulmalıdır.

Örneğin:

```text
Evidence #001

Type:
Video

Source:
...

Collected:
...

First Seen:
...

Hash:
...

Related Claims:
...

Related Events:
...
```

Mümkün olduğunca provenance korunmalıdır.

---

# 33. Provenance

Her önemli bilginin:

> **"Bu nereden geldi?"**

sorusuna cevap verebilmesi gerekir.

Örneğin:

```text
Entity X
    ↓
discovered_from
    ↓
Article #123
    ↓
published_by
    ↓
Source Y
    ↓
published_at
    ↓
2026-08-28 09:31
```

---

# 34. Research Reproducibility

Araştırmanın nasıl gerçekleştirildiği mümkün olduğunca kaydedilmelidir.

```text
Investigation #42

Started:
2026-08-28

Queries:
...

Sources:
...

Evidence:
...

Entities:
...

Analyst actions:
...

Conclusion:
...
```

Bu sayede araştırma daha sonra yeniden incelenebilir.

---

# 35. AI Role

AI sistemin kendisi değildir.

AI aşağıdaki görevlerde yardımcı olabilir:

- entity extraction
- classification
- summarization
- entity resolution
- relationship suggestion
- anomaly detection
- hypothesis generation
- semantic search
- research assistance
- contradiction discovery

Ancak:

```text
SOURCE FACT
    ≠
AI INTERPRETATION
```

ayrımı korunmalıdır.

---

# 36. Human-in-the-Loop

Kullanıcı gerektiğinde sistemin önerilerini değerlendirebilmelidir.

Örneğin:

```text
POSSIBLE ENTITY MATCH

Person A
may be
Person B

Confidence:
71%

[CONFIRM]
[REJECT]
[INVESTIGATE]
```

Kullanıcı kararları sistemin gelecekteki değerlendirmelerinde kullanılabilir.

---

# 37. Learning From Feedback

Scryne'in öğrenmesi kontrolsüz olmamalıdır.

Önerilen model:

```text
Observation
    ↓
AI / Rule Suggestion
    ↓
Human Feedback
    ↓
Evaluation
    ↓
Knowledge Update
```

Daha ileri aşamada:

```text
Feedback
    ↓
Pattern Detection
    ↓
Rule / Model Improvement
    ↓
Validation
    ↓
Deployment
```

---

# 38. Knowledge Evolution

Scryne'in knowledge base'i statik değildir.

Bir bilgi:

```text
UNKNOWN
    ↓
OBSERVED
    ↓
REPORTED
    ↓
SUPPORTED
    ↓
CORROBORATED
```

şeklinde gelişebilir.

Yeni evidence geldiğinde:

```text
CORROBORATED
    ↓
CONTRADICTED
    ↓
RE-EVALUATED
```

olabilir.

Bütün değişimler tarihçesiyle korunmalıdır.

---

# 39. Intelligence History

Scryne zaman içerisinde kendi geçmişini oluşturmalıdır.

Örneğin:

```text
2026-08-28
Entity X discovered.

2026-09-02
New relationship detected.

2026-09-17
Relationship corroborated.

2026-10-04
Contradicting source discovered.

2026-10-05
Knowledge re-evaluated.
```

Bu history gelecekteki intelligence üretiminde kullanılabilir.

---

# 40. World Memory

Scryne yalnızca entity'leri hatırlamamalıdır.

Dünyanın zaman içerisindeki durumlarını da hatırlamalıdır.

Örneğin:

```text
Region X

January:
Low activity

March:
New organization appears

June:
Conflict begins

August:
Escalation detected
```

Bu uzun dönemli context, yalnızca güncel haberleri görmekten çok daha değerlidir.

---

# 41. Intelligence Diff

Sistem:

> "Dün ile bugün arasında ne değişti?"

veya:

> "Son 30 günde bu entity hakkında ne değişti?"

sorusuna doğrudan cevap verebilmelidir.

Örneğin:

```text
COMPANY X

Changes in last 30 days:

+ 2 new executives
+ 1 acquisition
+ 4 new relationships
+ 7 significant mentions
- 1 previous claim
```

---

# 42. Global Intelligence Map

Sistem dünya olaylarını harita üzerinde gösterebilir.

Örneğin:

```text
WORLD MAP

● Conflict
● Political Event
● Protest
● Corporate Event
● Disaster
```

Filtreler:

```text
Time
Region
Event Type
Severity
Confidence
Entity
Source
```

---

# 43. Timeline Engine

Her entity ve event için tarihsel timeline oluşturulabilir.

```text
2023
│
├── Event A
│
2024
│
├── Event B
│
2025
│
├── Event C
│
2026
│
└── Event D
```

---

# 44. Relationship Explorer

İki entity arasındaki bilinen bağlantılar gösterilebilir.

```text
Person A
    ↓
Organization B
    ↓
Company C
    ↓
Event D
    ↓
Source E
```

Sistem:

> "A ile E arasında 4 bilinen bağlantı bulundu."

diyebilir.

---

# 45. Search / Ask Interface

Kullanıcı doğal dille sistemi sorgulayabilmelidir.

Örneğin:

```text
"What do we know about Company X?"

"What changed about Company X this week?"

"Why is Company X relevant to Investigation #12?"

"What evidence supports this claim?"

"Which entities are connected to Person A?"

"What changed in Region X over the last 30 days?"
```

Cevaplar mümkün olduğunca Brain + Intelligence Core verilerine dayanmalıdır.

---

# 46. Research Assistant

Kullanıcı:

> "Company X'i araştır."

dediğinde sistem:

```text
Existing Memory
        ↓
Entity Resolution
        ↓
Recent Information
        ↓
Sources
        ↓
Events
        ↓
Relationships
        ↓
Claims
        ↓
Evidence
        ↓
Historical Context
```

oluşturabilmelidir.

---

# 47. Multi-Domain OSINT

Sistem zaman içerisinde farklı intelligence domain'lerini destekleyebilir.

## GEOINT

- harita
- konum
- uydu görüntüsü
- coğrafi analiz

## SOCMINT

- sosyal medya
- açık profiller
- bilgi yayılımı

## WEBINT

- web araştırması
- domain
- website
- arşiv

## DOCINT

- PDF
- belge
- OCR
- metadata

## MEDIAINT

- fotoğraf
- video
- metadata
- görsel doğrulama

## CONFLICT INTELLIGENCE

- savaş
- çatışma
- askeri olaylar

## POLITICAL INTELLIGENCE

- siyasi aktörler
- seçimler
- açıklamalar
- siyasi olaylar

## CORPORATE INTELLIGENCE

- şirketler
- yöneticiler
- iştirakler
- satın almalar
- hukuki gelişmeler

---

# 48. Collection Layer

Collector sistemleri Brain'in kendisi değildir.

Collector'ın görevi:

> **Dünyayı gözlemlemek.**

```text
External World
    ↓
Collectors
    ↓
Raw Data
    ↓
Normalization
    ↓
Observation
```

Brain ise:

> **Gözlemlenen dünyayı hatırlamak ve anlamlandırmakla ilgilenir.**

---

# 49. Separation of Concerns

Sistem aşağıdaki ayrımı korumalıdır:

```text
COLLECTOR
"Bir şey buldum."

INTELLIGENCE CORE
"Bu ne?"

BRAIN
"Bununla ilgili daha önce ne biliyoruz?"

ANALYSIS
"Bu ne anlama geliyor?"

MONITORING
"Bu değişti mi?"

ALERTING
"Bu kullanıcı için önemli mi?"

USER
"Ne yapmalıyım / neyi araştırmalıyım?"
```

Bu ayrım sistemin büyümesi açısından kritiktir.

---

# 50. Brain-Centric Architecture

Nihai mimari:

```text
                       SCRYNE OSINT LAB
                              │
                              ▼
                       ┌──────────────┐
                       │  OSINT BRAIN │
                       │              │
                       │ Memory       │
                       │ Context      │
                       │ Recall       │
                       │ History      │
                       └──────┬───────┘
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
         ▼                    ▼                    ▼
    COLLECTION            ANALYSIS             MONITORING
         │                    │                    │
         └────────────────────┼────────────────────┘
                              │
                       ┌──────▼───────┐
                       │ INTELLIGENCE │
                       │     CORE     │
                       └──────┬───────┘
                              │
       ┌──────────────────────┼──────────────────────┐
       │                      │                      │
       ▼                      ▼                      ▼
   ENTITIES                EVENTS                 SOURCES
       │                      │                      │
       └──────────────────────┼──────────────────────┘
                              │
                       ┌──────▼───────┐
                       │ KNOWLEDGE    │
                       │    GRAPH     │
                       └──────┬───────┘
                              │
            ┌─────────────────┼─────────────────┐
            │                 │                 │
            ▼                 ▼                 ▼
      INVESTIGATIONS       EVIDENCE          TIMELINES
            │                 │                 │
            └─────────────────┼─────────────────┘
                              │
                       ┌──────▼───────┐
                       │ INTELLIGENCE │
                       │  INTERFACE   │
                       └──────┬───────┘
                              │
                              ▼
                             USER
```

---

# 51. Active Intelligence Loop

Scryne'in temel yaşam döngüsü:

```text
                 ┌──────────────┐
                 │   OBSERVE    │
                 └──────┬───────┘
                        ↓
                 ┌──────────────┐
                 │   COLLECT    │
                 └──────┬───────┘
                        ↓
                 ┌──────────────┐
                 │   PROCESS    │
                 └──────┬───────┘
                        ↓
                 ┌──────────────┐
                 │   REMEMBER   │
                 └──────┬───────┘
                        ↓
                 ┌──────────────┐
                 │   CONNECT    │
                 └──────┬───────┘
                        ↓
                 ┌──────────────┐
                 │   ANALYZE    │
                 └──────┬───────┘
                        ↓
                 ┌──────────────┐
                 │ DETECT CHANGE│
                 └──────┬───────┘
                        ↓
                 ┌──────────────┐
                 │ RE-EVALUATE  │
                 └──────┬───────┘
                        ↓
                 ┌──────────────┐
                 │    ALERT     │
                 └──────┬───────┘
                        ↓
                       USER
                        │
                        ↓
                 NEW INVESTIGATION
                        │
                        ↓
                 NEW KNOWLEDGE
                        │
                        └────────→ BRAIN
```

Bu döngü Scryne'in temel yaşam mekanizmasıdır.

---

# 52. Interface Philosophy

Arayüz klasik bir admin paneli olmamalıdır.

Hedef:

- professional
- modern
- information-dense
- fast
- analytical
- dark-first
- low-noise

bir intelligence workstation hissidir.

Ancak information density ile visual chaos birbirinden ayrılmalıdır.

> **Amaç çok fazla bilgi göstermek değil, çok fazla bilgi içerisinden anlam çıkarmayı kolaylaştırmaktır.**

---

# 53. Main Intelligence Workspace

Ana ekran:

```text
┌──────────────────────────────────────────────┐
│ SCRYNE                          ● LIVE        │
├──────────────────────────────────────────────┤
│                                              │
│ Search / Ask / Investigate                   │
│                                              │
├──────────────────────────────────────────────┤
│ PRIORITY INTELLIGENCE                        │
│                                              │
│ ⚠ Significant change                         │
│ ● New relationship                           │
│ ● Investigation update                       │
│                                              │
├──────────────────────────────────────────────┤
│                                              │
│ WORLD MAP      ENTITY GRAPH     TIMELINE     │
│                                              │
└──────────────────────────────────────────────┘
```

---

# 54. Intelligence Navigation

Kullanıcı her knowledge object üzerinden diğerlerine geçebilmelidir.

```text
Company X
    ↓
Event #72
    ↓
Source #142
    ↓
Person Y
    ↓
Organization Z
    ↓
Investigation #18
    ↓
Evidence #92
```

Sistem bir "web of intelligence" hissi vermelidir.

---

# 55. Security & Privacy

Scryne kişisel bir intelligence laboratuvarıdır.

Öncelikler:

- local-first
- least privilege
- secure secrets
- encrypted credentials
- audit logging
- safe integrations
- backup
- restore
- access control
- network safety

Özellikle dış kaynaklardan veri toplayan sistemlerde:

- SSRF
- malicious content
- poisoned documents
- prompt injection
- malicious web content

gibi tehditler mimarinin bir parçası olarak ele alınmalıdır.

---

# 56. Data Provenance

Önemli veriler mümkün olduğunca:

```text
source
timestamp
collection method
original location
content hash
processing history
```

bilgilerine sahip olmalıdır.

---

# 57. Resilience

Harici kaynakların çalışmaması sistemin tamamen kullanılamaz hale gelmesine yol açmamalıdır.

```text
External Source Down
        ↓
Cached / Historical Knowledge
        ↓
System remains usable
```

Ancak eski bilgi ile güncel bilgi açıkça ayrılmalıdır.

---

# 58. Local-First Intelligence

Uzun vadede:

- memory
- investigation
- graph
- evidence
- historical data

olabildiğince yerel tutulabilir.

External API'ler capability sağlayabilir ancak Brain'in tamamı tek bir üçüncü taraf servise bağımlı olmamalıdır.

---

# 59. Extensibility

Sistem zaman içerisinde yeni capability'lerle büyüyebilmelidir.

```text
Scryne v1
→ Research

Scryne v2
→ Entity Intelligence

Scryne v3
→ Event Intelligence

Scryne v4
→ Monitoring

Scryne v5
→ Intelligence Graph

Scryne v6
→ GEOINT

Scryne v7
→ Media / Document Intelligence
```

Core knowledge model mümkün olduğunca stabil tutulmalıdır.

---

# 60. Capability Model

Yeni yetenekler bağımsız capability olarak eklenebilir.

```text
capabilities/
│
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

---

# 61. Örnek Senaryo — Şirket

Kullanıcı:

> "Company X hakkında ne biliyoruz?"

Sistem:

```text
Existing Memory
    ↓
Entity Resolution
    ↓
Known Relationships
    ↓
Historical Events
    ↓
Recent Changes
    ↓
Current Sources
    ↓
Investigations
    ↓
Claims
    ↓
Evidence
```

Sonuç:

```text
COMPANY X

Known since:
2026-01-14

Related entities:
23

Known events:
41

Investigations:
3

Sources:
87

Recent changes:
4

New relationships:
2

Contradictions:
1
```

---

# 62. Örnek Senaryo — Çatışma

Sistem bir bölgeyi sürekli izlemektedir.

Yeni observation:

```text
Region X

Potential conflict escalation detected.
```

Sistem:

```text
Source discovery
        ↓
Independent corroboration
        ↓
Event creation
        ↓
Historical comparison
        ↓
Related entities
        ↓
Confidence evaluation
```

sonucunda:

```text
EVENT #142

Status:
Developing

Confidence:
81%

Sources:
7

Independent:
3

Evidence:
2

Historical context:
Related to Event #119
```

kullanıcıya sunabilir.

---

# 63. Örnek Senaryo — Eski Araştırmanın Yeniden Canlanması

Yeni event tespit edilir.

Brain:

```text
Related Investigation:
#023

Last activity:
4 months ago
```

Sistem:

> **"Bu gelişme daha önce yürütülen Investigation #023 ile ilişkili olabilir."**

der.

Araştırmanın eski hipotezleri yeniden değerlendirilir.

```text
OLD HYPOTHESIS
        ↓
NEW EVIDENCE
        ↓
RE-EVALUATION
```

Bu, Brain'in gerçekten geçmişi hatırladığını gösterir.

---

# 64. Örnek Senaryo — Intelligence Diff

Kullanıcı:

> "Company X hakkında son 30 günde ne değişti?"

Sistem:

```text
WORLD STATE -30 DAYS
        ↓
DIFF
        ↓
CURRENT WORLD STATE
```

çıktısı:

```text
+ 2 new executives
+ 1 acquisition
+ 4 new relationships
+ 11 significant sources
+ 1 new investigation

- 1 previous claim

Confidence changes:
3
```

---

# 65. Örnek Senaryo — Why This Matters

Sistem yeni bir relationship bulur:

```text
Person A
    ↓
possible relationship
    ↓
Organization X
```

Sistem bunu yalnızca göstermez.

```text
WHY THIS MATTERS

• Person A is already monitored.
• Organization X appears in Investigation #12.
• Relationship was previously unknown.
• 3 independent sources support the connection.
• Similar activity was observed previously.
```

Bu intelligence prioritization sisteminin temel davranışlarından biridir.

---

# 66. Örnek Senaryo — Contradiction

Sistem:

```text
Claim:
Person A attended Event X.
```

bulur.

Ancak:

```text
Source A:
Person A attended.

Source B:
Person A was in another country.
```

Sistem:

```text
CONTRADICTION

Status:
UNRESOLVED

Supporting:
1

Contradicting:
1
```

olarak işaretler.

Sonuç zorla kesinleştirilmez.

---

# 67. Başlangıç Stratejisi

Scryne ilk günden bütün OSINT dünyasını çözmeye çalışmamalıdır.

İlk hedef:

> **Sağlam bir OSINT Brain + Core Knowledge Model + Investigation System + temel Collection + Monitoring döngüsü oluşturmak.**

Öncelik:

```text
Brain
    ↓
Knowledge Model
    ↓
Investigation
    ↓
Collection
    ↓
Monitoring
    ↓
Graph
    ↓
Advanced Analysis
```

---

# 68. İlk Temel Capability'ler

İlk gerçek sürüm için:

```text
✓ OSINT Brain
✓ Persistent Memory
✓ Entities
✓ Events
✓ Sources
✓ Claims
✓ Evidence
✓ Relationships
✓ Investigations
✓ Timeline
✓ Basic Graph
✓ Search
✓ Monitoring
✓ Change Detection
✓ Intelligence Inbox
✓ Notifications
```

---

# 69. İlk Sürümde Yapılmaması Gerekenler

İlk sürümde:

- bütün interneti taramak,
- yüzlerce API bağlamak,
- bütün OSINT alanlarını desteklemek,
- tamamen otonom investigation,
- kontrolsüz AI kararları,
- gereksiz microservice karmaşası,
- devasa frontend

hedeflenmemelidir.

Önce Brain'in ve knowledge modelinin doğru çalışması sağlanmalıdır.

---

# 70. Mimari Karar İlkesi

Her yeni özellik şu sorudan geçmelidir:

> **"Bu özellik Scryne'in intelligence yaşam döngüsüne gerçekten katkı sağlıyor mu?"**

Eğer sağlamıyorsa yalnızca teknoloji eklemek için sisteme eklenmemelidir.

---

# 71. Açık Mimari Sorular

Aşağıdaki sorular proje ilerlemeden önce cevaplanması gereken tasarım sorularıdır.

---

## Q1 — Brain tam olarak neyi "hatırlamalı"?

Her observation Brain'e girmeli mi?

Yoksa:

```text
Observation
→ Temporary Memory
→ Evaluation
→ Long-Term Memory
```

şeklinde filtrelenmeli mi?

**Karar gerektiriyor.**

---

## Q2 — Brain ile Intelligence Database arasındaki sınır nerede?

Brain:

- memory mi?
- semantic context mi?
- knowledge store mu?
- bunların hepsi mi?

Intelligence Core ile hangi verinin nerede tutulacağı netleştirilmelidir.

**Karar gerektiriyor.**

---

## Q3 — "Truth" nasıl tanımlanacak?

Sistem:

```text
verified
high confidence
supported
reported
unresolved
false
```

gibi hangi knowledge states'i kullanacak?

**Karar gerektiriyor.**

---

## Q4 — Confidence nasıl hesaplanacak?

Confidence:

- source quality,
- source independence,
- evidence,
- corroboration,
- historical reliability

gibi faktörlerden nasıl üretilecek?

AI tarafından mı, deterministic rule engine tarafından mı, hibrit modelle mi?

**Karar gerektiriyor.**

---

## Q5 — Source Reliability nasıl belirlenecek?

Bir kaynağın geçmiş performansı:

```text
confirmed
contradicted
unresolved
```

olarak tutulacak.

Peki bu geçmiş future confidence'ı ne kadar etkileyecek?

**Karar gerektiriyor.**

---

## Q6 — Source Independence nasıl tespit edilecek?

İki haber:

```text
A
B
```

gerçekten bağımsız mı?

Yoksa:

```text
Original Source
    ↓
A
    ↓
B
```

mi?

Bu ayrımın teknik olarak nasıl yapılacağı belirlenmelidir.

**Karar gerektiriyor.**

---

## Q7 — Entity Merge ne zaman yapılacak?

Sistem:

```text
Person A
Person B
```

aynı kişi olabilir dediğinde otomatik merge yapacak mı?

Yoksa:

```text
Possible Match
```

olarak mı bırakacak?

**Karar gerektiriyor.**

---

## Q8 — Brain ne zaman "öğrenmiş" sayılacak?

Bir bilgi Brain'e:

- keşfedildiğinde mi,
- doğrulandığında mı,
- kullanıcı onayladığında mı,
- belirli confidence seviyesine ulaştığında mı

girmeli?

**Karar gerektiriyor.**

---

## Q9 — Brain'in yanlış bilgiyi düzeltme mekanizması nasıl olacak?

Yeni bilgi eski bilgiyi:

- overwrite mı edecek?
- version mı oluşturacak?
- contradiction mı oluşturacak?

**Karar gerektiriyor.**

---

## Q10 — World State ne sıklıkla oluşturulacak?

World State:

- sürekli mi,
- saatlik mi,
- günlük mü,
- event-driven mı

oluşturulmalı?

**Karar gerektiriyor.**

---

## Q11 — Intelligence Diff neyi karşılaştıracak?

Diff:

- sadece entity değişikliklerini mi,
- graph değişikliklerini mi,
- claims'i mi,
- confidence'ı mı,
- source landscape'i mi

karşılaştırmalı?

**Karar gerektiriyor.**

---

## Q12 — "Why This Matters" nasıl üretilecek?

Bu açıklama:

- rule-based,
- AI-generated,
- graph-based,
- hibrit

olmalı mı?

Ve AI ürettiği açıklamanın kaynağını nasıl gösterecek?

**Karar gerektiriyor.**

---

## Q13 — Active Intelligence ne kadar aktif olmalı?

Sistem:

```text
sadece önemli gelişmeleri
```

mi bildirmeli?

Yoksa zaman içerisinde kullanıcı davranışından öğrenerek kendi notification threshold'larını değiştirebilmeli mi?

**Karar gerektiriyor.**

---

## Q14 — Kullanıcı davranışı Brain'in bilgisini etkiler mi?

Kullanıcının:

```text
Ignore
Confirm
Reject
Investigate
Follow
```

davranışları sistemin future prioritization'ını değiştirmeli mi?

**Karar gerektiriyor.**

---

## Q15 — AI ile Source Fact nasıl kesin olarak ayrılacak?

Sistem UI'da:

```text
SOURCE FACT
AI ANALYSIS
SYSTEM INFERENCE
USER INTERPRETATION
```

ayrımını nasıl gösterecek?

**Karar gerektiriyor.**

---

## Q16 — Investigation ne zaman kapanır?

Bir investigation:

```text
OPEN
ACTIVE
PAUSED
RESOLVED
CLOSED
ARCHIVED
```

gibi hangi durumlara sahip olacak?

**Karar gerektiriyor.**

---

## Q17 — Investigation sonuçları nasıl Brain'e aktarılacak?

Tamamlanan investigation'ın:

- bütün notları,
- yalnızca verified findings'leri,
- hypotheses'leri,
- source graph'ını

hangileri long-term memory'ye aktarılacak?

**Karar gerektiriyor.**

---

## Q18 — Evidence retention nasıl olacak?

Evidence:

- sonsuza kadar mı saklanacak?
- hash tutulacak mı?
- yalnızca metadata mı saklanacak?
- orijinal dosya lokal olarak tutulacak mı?

**Karar gerektiriyor.**

---

## Q19 — Historical Knowledge nasıl korunacak?

Bilgi değiştiğinde eski bilgi:

```text
deleted
```

olmamalıdır.

Ancak storage büyümesi nasıl kontrol edilecek?

**Karar gerektiriyor.**

---

## Q20 — OSINT Brain'in ölçek sınırı ne olacak?

Başlangıçta:

```text
1,000 entities
```

olabilir.

İleride:

```text
1M entities
100M observations
```

gibi ölçeklere ulaşırsa mevcut Brain modeli yeterli olacak mı?

**Uzun vadeli mimari sorusu.**

---

## Q21 — Local-first ne kadar ileri götürülecek?

Sistem:

```text
100% local
```

mi olacak?

Yoksa:

```text
Local Core
+
External Intelligence APIs
+
Optional Cloud AI
```

hibrit modeli mi kullanacak?

**Karar gerektiriyor.**

---

## Q22 — Collector güvenliği nasıl sağlanacak?

Web'den gelen içerikler:

- prompt injection,
- malicious HTML,
- malicious documents,
- SSRF,
- poisoned data

içerebilir.

Collector → Intelligence Core sınırı nasıl güvenli hale getirilecek?

**Kritik güvenlik sorusu.**

---

## Q23 — Scryne ne kadar otonom olacak?

Sistem:

```text
observe
collect
classify
connect
notify
```

işlerini otomatik yapabilir.

Peki:

```text
investigate
conclude
verify
merge
```

işlerinde insan onayı nerede gerekecek?

**Temel ürün felsefesi kararı.**

---

## Q24 — Brain kendi başına araştırma başlatabilecek mi?

İleri aşamada:

```text
Brain notices anomaly
        ↓
Creates research task
        ↓
Collects sources
        ↓
Analyzes
        ↓
Reports result
```

gibi bir sistem isteniyor mu?

Bu, projenin otonomi seviyesini belirleyecek.

**Uzun vadeli karar.**

---

## Q25 — Scryne'in sınırı nerede?

Sistem:

> "Her şeyi bilen OSINT sistemi"

olmaya çalışmamalıdır.

Hangi domainlerin:

- supported,
- experimental,
- unsupported

olduğu açıkça tanımlanmalıdır.

**Stratejik kapsam sorusu.**

---

# 72. Tasarım İlkeleri

Scryne geliştirilirken:

### 1. Evidence First

Kanıt yoksa kesinlik yok.

### 2. Memory Is Persistent

Anlamlı knowledge geçmişini kaybetmez.

### 3. History Is Immutable

Geçmişin nasıl değiştiği izlenebilir olmalıdır.

### 4. Uncertainty Is Valid

Bilinmeyen bilgi olarak kabul edilir.

### 5. Everything Is Connected

Knowledge graph sistemin temelidir.

### 6. AI Is Assistive

AI karar mekanizmasının yerine geçmez.

### 7. Human Remains In Control

Kritik intelligence decisions kullanıcı tarafından denetlenebilir.

### 8. Signal Over Noise

Her observation alert değildir.

### 9. Context Over Headlines

Sistem yalnızca yeni bilgiyi değil, neden önemli olduğunu göstermelidir.

### 10. Memory Over Statelessness

Her araştırma gelecekteki araştırmaları güçlendirmelidir.

---

# 73. Development Roadmap

## Phase 0 — Brain Foundation

```text
AvenoxBeyin Core
        ↓
OSINT-specific adaptation
        ↓
Memory Model
        ↓
Knowledge Model
```

---

## Phase 1 — Intelligence Core

```text
Entities
Events
Sources
Claims
Evidence
Relationships
```

---

## Phase 2 — Investigation

```text
Investigations
Hypotheses
Findings
Evidence
Timeline
```

---

## Phase 3 — Collection

```text
RSS
Web
Public APIs
News
Documents
```

---

## Phase 4 — Monitoring

```text
Entity Monitoring
Topic Monitoring
Event Monitoring
Change Detection
```

---

## Phase 5 — Brain Intelligence

```text
Memory Recall
Historical Context
Knowledge Evolution
Contradiction
World State
Intelligence Diff
```

---

## Phase 6 — Active Intelligence

```text
Prioritization
Alerts
Morning Brief
Why This Matters
Investigation Relevance
```

---

## Phase 7 — Advanced OSINT

```text
GEOINT
SOCMINT
DOCINT
MEDIAINT
Corporate Intelligence
Conflict Intelligence
```

---

## Phase 8 — Advanced Intelligence Assistant

```text
Anomaly Detection
Research Suggestions
Autonomous Research Tasks
Advanced Graph Analysis
Cross-domain Intelligence
```

---

# 74. Başarı Kriterleri

Scryne başarılı olduğunda kullanıcı:

> **"Dünyada ne oluyor?"**

sorusuna cevap alabilmelidir.

Ama daha önemlisi:

> **"Bu gelişme daha önce bildiğimiz şeylerle nasıl bağlantılı?"**

sorusuna da cevap verebilmelidir.

Ve:

> **"Bunu daha önce araştırmış mıydım?"**

sorusuna:

> **"Evet. Investigation #17'de bununla ilişkili bir hipotez oluşturmuştun."**

diyebilmelidir.

Ayrıca:

> **"Bu neden önemli?"**

sorusuna context sunabilmelidir.

Ve:

> **"Sistem bunu neden düşünüyor?"**

sorusuna evidence ve provenance gösterebilmelidir.

---

# 75. Nihai Intelligence Loop

Scryne'in özü:

```text
WORLD
  ↓
OBSERVE
  ↓
COLLECT
  ↓
UNDERSTAND
  ↓
REMEMBER
  ↓
CONNECT
  ↓
COMPARE
  ↓
DETECT CHANGE
  ↓
RE-EVALUATE
  ↓
PRIORITIZE
  ↓
INFORM
  ↓
USER
  ↓
INVESTIGATE
  ↓
NEW KNOWLEDGE
  ↓
BRAIN
  ↓
WORLD
```

Bu döngü sürekli devam eder.

---

# 76. Scryne'in Karakteri

Scryne'in kişiliği bir chatbot olmamalıdır.

Scryne:

- sakin,
- analitik,
- kanıt odaklı,
- belirsizlik konusunda dürüst,
- bağlam sağlayan,
- gerektiğinde uyarıcı,
- gereksiz konuşmayan

bir intelligence companion olmalıdır.

Sistem:

> "Bence..."

yerine:

> "Mevcut evidence'a göre..."

demelidir.

---

# 77. Nihai Tanım

Scryne'i tek cümlede tanımlamak gerekirse:

> **Scryne, açık kaynaklardan dünyayı sürekli gözlemleyen, gördüğü bilgileri zaman içerisinde kendi hafızasında biriktiren, entity'ler, olaylar, kaynaklar, kanıtlar ve araştırmalar arasında bağlantılar kuran, geçmiş bilgileri yeni gelişmelerle yeniden değerlendiren ve önemli intelligence'ı kullanıcıya aktif olarak sunan kişisel bir Intelligence Operating System'dir.**

---

# 78. Nihai Vizyon

Scryne'in amacı başka insanların kullandığı bir OSINT platformu oluşturmak değildir.

Amaç:

> **Kullanıcının kendisine ait, zaman içerisinde gelişen, kendi hafızasını oluşturan, dünyayı sürekli gözlemleyen, araştırmaları birbirine bağlayan, geçmişi unutmayan ve gerektiğinde kullanıcıyı kendiliğinden bilgilendiren kişisel bir intelligence ecosystem oluşturmasıdır.**

Sistem doğduğunda her şeyi bilmez.

Öğrendikçe büyür.

Gözlemledikçe hafızası gelişir.

Araştırdıkça bağlantıları artar.

Yeni kanıt geldiğinde eski anlayışını değiştirebilir.

Zaman geçtikçe kendi intelligence history'sini oluşturur.

Ve sonunda:

> **Scryne yalnızca bilgi depolayan bir uygulama değil, dünyaya ilişkin kendi tarihine sahip yaşayan bir OSINT Brain haline gelir.**

---

# 79. Project Identity

**Name:** Scryne OSINT Lab

**Category:** Personal Intelligence / OSINT / Investigation / Knowledge Graph

**Core Concept:** Living OSINT Brain

**Architecture Philosophy:** Brain-centric, modular, local-first, evidence-driven

**Primary User:** Individual researcher / analyst

**Primary Goal:** Continuous open-source intelligence collection, memory, analysis and investigation

**Long-Term Goal:** A personal intelligence operating system that continuously observes the external world, remembers its history, understands relationships, detects changes and develops an interconnected knowledge model over time.

---

# 80. Guiding Principle

```text
Observe.
Remember.
Connect.
Verify.
Compare.
Understand.
Monitor.
Re-evaluate.
Inform.
```

> **Scryne does not simply search the world.**
>
> **Scryne builds a memory of it.**
>
> **It does not simply remember what happened.**
>
> **It understands what changed, what is connected, what remains uncertain, and why it matters.**