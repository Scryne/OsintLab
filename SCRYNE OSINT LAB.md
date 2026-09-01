# SCRYNE OSINT LAB

> **A Personal Intelligence & Investigation System**
>
> Açık kaynaklardan dünyayı sürekli gözlemleyen, bilgiyi kendi hafızasında biriktiren, entity'ler, olaylar, kaynaklar ve kanıtlar arasında bağlantılar kuran ve önemli gelişmeleri kullanıcıya aktif olarak sunan yaşayan bir kişisel OSINT intelligence ekosistemi.

---

## 1. Proje Özeti

**Scryne OSINT Lab**, tek bir OSINT aracı veya tek bir dashboard değildir.

Sistem; açık kaynaklardan bilgi toplayan, bu bilgileri yapılandıran, doğrulayan, ilişkilendiren, zaman içerisinde hafızasında tutan, yeni bilgiler ile geçmiş bilgileri karşılaştıran ve kullanıcıya anlamlı intelligence çıktıları sağlayan **modüler ve sürekli yaşayan bir kişisel OSINT laboratuvarıdır.**

Sistemin merkezinde **OSINT Brain** bulunur.

OSINT Brain, sistemin hafızası ve bağlamsal bilgi katmanıdır.

Sistem çalışmaya başladığında başlangıçta sınırlı bir bilgiye sahiptir. Zaman içerisinde izlediği kaynaklardan, gerçekleştirdiği araştırmalardan, tespit ettiği entity'lerden, olaylardan, kanıtlardan ve ilişkilerden kendi bilgi evrenini oluşturur.

Bu nedenle Scryne statik bir bilgi tabanı değildir.

> **Scryne, zaman içerisinde büyüyen bir intelligence system'dir.**

---

# 2. Temel Vizyon

Scryne'in nihai vizyonu:

> **Kullanıcının dünyayı araştırmak için açtığı, dünyanın ise kullanıcıya kendisini anlatmaya devam ettiği kişisel bir intelligence system oluşturmak.**

Kullanıcı sistemi açtığında yalnızca arama yapmaz.

Sistem kullanıcıya:

- dünyada ne değiştiğini,
- takip edilen konularda ne olduğunu,
- yeni hangi entity'lerin ortaya çıktığını,
- hangi ilişkilerin değiştiğini,
- hangi olayların önem kazandığını,
- hangi iddiaların doğrulandığını,
- hangi bilgilerin önceki bilgilerle çeliştiğini,
- hangi eski araştırmaların yeni gelişmelerle bağlantılı olduğunu

gösterebilir.

Sistem yalnızca **sorulduğunda cevap veren** bir yapı değil, gerektiğinde **kullanıcıyı bilgilendiren aktif bir intelligence companion** olmalıdır.

---

# 3. Projenin Felsefesi

Scryne aşağıdaki temel prensipler üzerine kurulmalıdır.

## 3.1 Everything Is Connected

Sistemdeki anlamlı hiçbir bilgi izole olmamalıdır.

Bir:

- kişi,
- şirket,
- organizasyon,
- olay,
- kaynak,
- belge,
- iddia,
- kanıt,
- konum,
- araştırma

başka bilgi nesneleriyle ilişkilendirilebilir olmalıdır.

Örnek:

```text
Person
  ↓
works_for
  ↓
Organization
  ↓
involved_in
  ↓
Event
  ↓
reported_by
  ↓
Source
  ↓
contains
  ↓
Evidence
```

Bu bağlantılar Scryne'in intelligence graph'ının temelini oluşturur.

---

## 3.2 Memory Over Search

Sistem her sorguda dünyayı sıfırdan araştırmamalıdır.

Önce mevcut hafızasını kullanmalı, ardından gerektiğinde dış kaynaklara başvurmalıdır.

```text
User Query
    ↓
OSINT Brain
    ↓
Existing Knowledge
    ↓
Known Relationships
    ↓
Historical Context
    ↓
External Research
    ↓
New Information
    ↓
Memory Update
```

Böylece sistem zaman içerisinde daha fazla bağlam kazanır.

---

## 3.3 Research Creates Memory

Bir araştırma yalnızca kullanıcıya sonuç üretmemelidir.

Araştırma sırasında elde edilen anlamlı bilgiler sistemin kalıcı bilgi evrenine dahil edilebilir.

Örneğin:

```text
Investigation #042
        ↓
Company X discovered
        ↓
Entity created
        ↓
Organization Y discovered
        ↓
Relationship created
        ↓
Source Z discovered
        ↓
Source history recorded
```

Daha sonra başka bir araştırmada bu bilgiler tekrar kullanılabilir.

---

## 3.4 Observation Is Continuous

Scryne yalnızca kullanıcı sisteme girdiğinde çalışmamalıdır.

Tanımlanmış izleme alanları için sistem sürekli gözlem yapabilmelidir.

```text
Monitor
   ↓
Observe
   ↓
Detect Change
   ↓
Compare With Memory
   ↓
Evaluate Significance
   ↓
Update Knowledge
   ↓
Notify User
```

---

## 3.5 Evidence Before Conclusions

Sistem bilgiyi kesin gerçek olarak kabul etmek yerine:

- kaynağını,
- güvenilirliğini,
- bağımsızlığını,
- zamanını,
- bağlamını,
- destekleyen kanıtları,
- çelişen kanıtları

dikkate almalıdır.

Sistem:

> **"Bu kesinlikle doğru."**

demek yerine gerektiğinde:

> **"Bu iddia 4 bağımsız kaynak tarafından destekleniyor ancak konum doğrulaması eksik."**

gibi daha analitik çıktılar üretmelidir.

---

# 4. Scryne Nedir?

Scryne aynı anda birkaç farklı sistemin birleşimidir.

### 4.1 OSINT Collection System

Açık kaynaklardan veri toplar.

### 4.2 Intelligence Knowledge System

Toplanan bilgileri yapılandırır.

### 4.3 Personal Investigation Workspace

Kullanıcının araştırmalarını organize eder.

### 4.4 Knowledge Graph

Entity'ler ve olaylar arasındaki ilişkileri temsil eder.

### 4.5 Monitoring System

Dünyadaki değişimleri sürekli takip eder.

### 4.6 OSINT Brain

Sistemin kalıcı hafızasını ve bağlamını oluşturur.

### 4.7 Intelligence Interface

Bütün bu sistemleri kullanıcıya tek bir çalışma ortamında sunar.

---

# 5. OSINT Brain

OSINT Brain, Scryne'in merkezidir.

Ancak OSINT Brain, kullanıcının mevcut kişisel ikinci beyni değildir.

Kullanıcının kişisel ikinci beyni ile OSINT Brain birbirinden tamamen ayrı tutulmalıdır.

```text
PERSONAL BRAIN
│
├── User knowledge
├── Projects
├── Notes
├── Decisions
└── Personal context


OSINT BRAIN
│
├── Entities
├── Events
├── Sources
├── Evidence
├── Claims
├── Relationships
├── Investigations
└── Observations
```

---

# 6. Personal Brain ve OSINT Brain Ayrımı

Sistemin iki farklı bilgi evreni bulunur.

## Personal Brain

Kullanıcının kişisel ikinci beynidir.

Bu sistem:

- kişisel bilgileri,
- projeleri,
- notları,
- kararları,
- öğrenme sürecini,
- çalışma bağlamını

saklar.

---

## OSINT Brain

Sadece Scryne OSINT Lab içerisindeki intelligence yaşam döngüsünden doğan bilgileri saklar.

Başka bilgisayarlardaki kişisel dosyaları otomatik olarak taramaz.

Kullanıcının mevcut kişisel brain'inden otomatik veri import etmez.

Bu sistem kendi yaşam döngüsüne sahip bağımsız bir bilgi evrenidir.

---

# 7. OSINT Brain'in Doğum Konsepti

OSINT Brain'in belirli bir başlangıç noktası bulunmalıdır.

Örneğin:

```text
OSINT BRAIN
Born: 2026-08-28

Entities: 0
Events: 0
Sources: 0
Investigations: 0
Relationships: 0
```

Sistem çalışmaya başladıkça hafızası oluşur.

```text
Day 001
+ Observations
+ Sources
+ Entities
+ Events

Day 030
+ Thousands of observations
+ Hundreds of entities
+ Hundreds of relationships

Day 365
+ Historical intelligence
+ Established entity network
+ Source reliability history
+ Long-term event timelines
```

Bu yaklaşım sistemin zaman içerisinde gerçek bir **intelligence history** oluşturmasını sağlar.

---

# 8. Core Knowledge Model

Scryne'in temel bilgi modeli aşağıdaki nesnelerden oluşur.

## 8.1 Entity

Sistemin tanımlayabildiği varlık.

Örnek:

- Person
- Organization
- Company
- Government
- Military Unit
- Location
- Website
- Domain
- Institution
- Political Party
- Media Organization

---

## 8.2 Event

Gerçek dünyada gerçekleşen veya gerçekleştiği iddia edilen olay.

Örnek:

- saldırı
- seçim
- açıklama
- şirket satın alımı
- protesto
- askeri hareket
- ürün lansmanı
- istifa
- diplomatik görüşme

---

## 8.3 Source

Bilginin geldiği kaynak.

Örnek:

- haber sitesi
- resmi açıklama
- RSS
- web sayfası
- sosyal medya gönderisi
- kamuya açık veri seti
- belge
- arşiv

---

## 8.4 Claim

Bir kaynak veya entity tarafından ileri sürülen iddia.

Örnek:

```text
Claim:
"Event X occurred at Location Y."
```

---

## 8.5 Evidence

Bir iddiayı destekleyen veya çürüten kanıt.

Örnek:

- fotoğraf
- video
- belge
- uydu görüntüsü
- resmi kayıt
- metadata
- bağımsız haber
- arşiv kaydı

---

## 8.6 Relationship

Entity veya diğer nesneler arasındaki bağlantı.

Örnek:

```text
Person A
    └── works_for ──> Organization B

Organization B
    └── involved_in ──> Event C

Event C
    └── reported_by ──> Source D
```

---

## 8.7 Investigation

Belirli bir araştırma amacıyla oluşturulan çalışma alanı.

Bir investigation:

- research question
- hypotheses
- entities
- events
- sources
- claims
- evidence
- timeline
- findings
- conclusions

içerebilir.

---

## 8.8 Observation

Sistemin dış dünyada gözlemlediği yeni bilgi veya değişiklik.

Observation doğrudan gerçek kabul edilmez.

Önce değerlendirilir.

```text
Observation
    ↓
Processing
    ↓
Validation
    ↓
Knowledge Update
```

---

# 9. Intelligence Graph

Scryne'in temel mimari bileşenlerinden biri knowledge graph olmalıdır.

Örnek:

```text
                Person A
                   │
                founded
                   │
                   ▼
             Company X
              /       \
        owns          acquired
         /               \
        ▼                 ▼
Company Y             Company Z
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

Bu graph kullanıcı tarafından görsel olarak keşfedilebilir olmalıdır.

---

# 10. Investigation System

Kullanıcı belirli bir konu hakkında araştırma başlatabilmelidir.

Örneğin:

```text
INVESTIGATION #0042

Title:
Company X Investigation

Question:
What is the relationship between
Company X and Organization Y?

Status:
ACTIVE
```

Araştırma içerisinde:

```text
Question
Hypotheses
Entities
Sources
Claims
Evidence
Timeline
Relationships
Findings
```

bulunabilir.

---

# 11. Hypothesis System

Araştırmalar yalnızca bilgi toplama şeklinde ilerlememelidir.

Kullanıcı hipotezler oluşturabilmelidir.

```text
H1:
Company X is directly controlled by Organization Y.

H2:
The relationship is indirect.

H3:
The apparent relationship is coincidental.
```

Kanıtlar hipotezleri destekleyebilir veya zayıflatabilir.

Bu sayede sistem araştırma mantığına daha uygun hale gelir.

---

# 12. Source Intelligence

Scryne kaynakları yalnızca veri sağlayıcı olarak görmemelidir.

Her kaynak zaman içerisinde kendi geçmişini oluşturmalıdır.

Örneğin:

```text
SOURCE: Example News

Reliability:
Medium

Historical behavior:
- 142 observations
- 91 confirmed
- 27 partially confirmed
- 14 contradicted
- 10 unresolved
```

Bu tür metrikler otomatik olarak oluşturulabilir ancak kullanıcı tarafından nihai gerçek olarak kabul edilmemelidir.

---

# 13. Source Independence

Sistem aynı haberin onlarca farklı kaynakta yayınlanmasını:

> "30 farklı doğrulama"

olarak değerlendirmemelidir.

Kaynakların birbirinden türemiş olma ihtimali araştırılmalıdır.

Örneğin:

```text
Original Source
      ↓
Agency
      ↓
News Site A
      ↓
News Site B
      ↓
News Site C
```

Bu durumda görünürde dört kaynak olsa da gerçek bilgi zinciri çok daha dar olabilir.

---

# 14. Claim Verification

Her önemli iddia için:

```text
Claim
│
├── Supporting Sources
├── Contradicting Sources
├── Evidence
├── First Seen
├── Last Updated
├── Confidence
└── Status
```

tutulabilir.

Örneğin:

```text
CLAIM

"Event X occurred at Location Y."

Status:
PARTIALLY VERIFIED

Supporting:
4 sources

Independent:
2 sources

Evidence:
1 video
1 satellite image

Contradictions:
1 source

Confidence:
78%
```

---

# 15. Continuous Monitoring

Scryne'in yaşayan tarafıdır.

Kullanıcı aşağıdakileri izlemeye alabilir:

```text
Entity
Topic
Event
Location
Organization
Person
Domain
Keyword
Investigation
```

Sistem belirli aralıklarla yeni verileri kontrol eder.

---

# 16. Change Detection

Sistem yalnızca yeni veri bulmamalıdır.

**Değişimi** tespit etmelidir.

Örneğin:

```text
Yesterday:

Company X
CEO: Person A

Today:

Company X
CEO: Person B
```

Sistem:

```text
CHANGE DETECTED

Company X

CEO changed:
Person A → Person B
```

şeklinde anlamlı bir event oluşturabilir.

---

# 17. Active Intelligence

Scryne'in temel farklılıklarından biri aktif olmasıdır.

Kullanıcı sistemi açmadan önce bile belirlenen monitoring görevleri çalışabilir.

Örneğin:

```text
06:00

New event detected.

07:30

Entity relationship changed.

08:12

Three independent sources report
a significant development.

09:40

Previous investigation has become
relevant again.
```

Sistem bunları önem derecesine göre kullanıcıya sunabilir.

---

# 18. Intelligence Prioritization

Her yeni bilgi kullanıcıya gösterilmemelidir.

Sistem önem değerlendirmesi yapmalıdır.

Örnek faktörler:

- novelty
- source quality
- source independence
- relevance
- entity importance
- geographic significance
- temporal significance
- confidence
- potential impact
- relation to active investigations

Bunlardan bir **intelligence priority score** üretilebilir.

---

# 19. Notification Philosophy

Sistem kullanıcıyı spam'e boğmamalıdır.

Amaç:

> **More signal, less noise.**

Bildirimler örneğin:

```text
CRITICAL
HIGH
MEDIUM
LOW
INFO
```

seviyelerine ayrılabilir.

---

# 20. Morning Intelligence Brief

Sistem kullanıcı sisteme ilk girdiğinde günlük intelligence özeti oluşturabilir.

Örneğin:

```text
SCRYNE MORNING BRIEF

Since your last session:

17 significant changes

4 new events

8 new entities

12 new relationships

2 contradictions

3 active investigations updated
```

Ardından:

### Priority Event

```text
Conflict escalation detected
```

### New Relationship

```text
Organization A ↔ Organization B
```

### Investigation Update

```text
Investigation #023
New supporting evidence detected
```

---

# 21. Search / Ask Interface

Sistem kullanıcıya doğal dil üzerinden araştırma imkanı sunmalıdır.

Örneğin:

```text
"What do I know about Company X?"
```

veya:

```text
"What changed about Company X this week?"
```

veya:

```text
"Show all known relationships between
Organization A and Person B."
```

veya:

```text
"What evidence supports this claim?"
```

Sistem yalnızca LLM cevabı vermemeli.

Cevap mümkün olduğunca sistemin yapılandırılmış intelligence verisine dayanmalıdır.

---

# 22. Entity Intelligence Page

Her entity için kapsamlı bir intelligence workspace bulunabilir.

Örneğin:

```text
COMPANY X

Overview

Type:
Company

Status:
Active

────────────────────

KEY ENTITIES

Person A
Person B
Organization C

────────────────────

RELATIONSHIPS

...

────────────────────

LATEST EVENTS

...

────────────────────

TIMELINE

...

────────────────────

SOURCES

...

────────────────────

EVIDENCE

...

────────────────────

INVESTIGATIONS

...

────────────────────

MONITORING

ACTIVE
```

---

# 23. Event Intelligence Page

Bir event için:

```text
EVENT #042

Title:
Conflict escalation in Region X

Time:
2026-08-28

Location:
Region X

Status:
Developing

Confidence:
82%

────────────────

TIMELINE

08:12
First observation

08:31
Local source

09:04
Official statement

10:12
Independent confirmation

────────────────

ENTITIES

...

────────────────

SOURCES

...

────────────────

EVIDENCE

...

────────────────

RELATED EVENTS

...
```

---

# 24. Global Intelligence Map

Sistem dünya üzerindeki olayları ve entity'leri harita üzerinde gösterebilir.

Örneğin:

```text
WORLD MAP

● Conflict
● Protest
● Political Event
● Corporate Event
● Natural Event
```

Filtreler:

```text
Time
Region
Event Type
Confidence
Severity
Entity
Source
```

---

# 25. Timeline Engine

Sistemin bütün olayları zamansal olarak ilişkilendirebilmesi gerekir.

Bir entity için:

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

Kullanıcı:

> "Bu entity'nin son 5 yıldaki önemli gelişmelerini göster."

diyebilir.

---

# 26. Relationship Explorer

Kullanıcı iki entity arasındaki bağlantıları araştırabilmelidir.

Örneğin:

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

> "A ile E arasında 4 bağlantı bulundu."

gibi sonuçlar sunabilir.

---

# 27. World Monitoring

Sistem yalnızca kullanıcı tarafından tanımlanan entity'leri değil, genel dünya gelişmelerini de takip edebilir.

Örneğin:

```text
GLOBAL MONITORING

Conflicts
Politics
Economy
Technology
Companies
Security
Science
Disasters
Geopolitics
```

Kullanıcı ilgisini istediği alanlara göre şekillendirebilir.

---

# 28. Custom Monitoring

Kullanıcı kendi izleme görevlerini oluşturabilir.

Örneğin:

```text
MONITOR

Entity:
Company X

Watch:
- Leadership
- Acquisitions
- Legal events
- Major news

Frequency:
Every 30 minutes

Alert:
HIGH+ only
```

---

# 29. Research Workspace

Kullanıcı manuel araştırma yaparken sistem onun çalışma alanı olabilir.

Örneğin:

```text
RESEARCH

Question
    ↓
Sources
    ↓
Notes
    ↓
Claims
    ↓
Evidence
    ↓
Hypotheses
    ↓
Findings
```

Araştırma sonunda sonuçlar sistemin knowledge graph'ına uygun biçimde işlenebilir.

---

# 30. Evidence Vault

Sistem araştırmalarda kullanılan kanıtları saklamalıdır.

Örneğin:

```text
Evidence #001

Type:
Video

Source:
...

Collected:
...

Hash:
...

First observed:
...

Related claims:
...

Related events:
...
```

Kanıtların provenance bilgisi mümkün olduğunca korunmalıdır.

---

# 31. Provenance

Sistemde önemli bir bilgi için:

> "Bu bilgi nereden geldi?"

sorusunun cevabı bulunabilmelidir.

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

Bu yapı sistemin auditability özelliğini güçlendirir.

---

# 32. Temporal Intelligence

Bilginin yalnızca ne olduğu değil, **ne zaman doğru olduğu** da önemlidir.

Örneğin:

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

Sistem geçmişteki bilgiyi silmek yerine tarihsel olarak saklamalıdır.

---

# 33. Knowledge Evolution

Scryne'in bilgisi değişebilir.

Bir entity hakkındaki bilgi:

```text
UNKNOWN
   ↓
REPORTED
   ↓
SUPPORTED
   ↓
VERIFIED
```

veya:

```text
REPORTED
   ↓
CONTRADICTED
   ↓
REJECTED
```

gibi yaşam döngülerine sahip olabilir.

---

# 34. Uncertainty

Sistem belirsizliği saklamalıdır.

OSINT dünyasında:

> Bilinmiyor

da bir bilgidir.

Örneğin:

```text
Location:
Possible: Location A
Confidence: 61%

Alternative:
Location B
Confidence: 31%

Unknown:
8%
```

Sistem zorla tek bir cevap üretmemelidir.

---

# 35. Contradiction Engine

Farklı kaynakların birbirleriyle çelişmesi tespit edilmelidir.

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

Claim:
Event time

14:00
vs
17:00
```

şeklinde işaretleyebilir.

---

# 36. Entity Resolution

Aynı entity farklı kaynaklarda farklı biçimlerde geçebilir.

Örneğin:

```text
John Smith
J. Smith
John A. Smith
@johnsmith
```

Sistem bunların aynı entity olma ihtimalini değerlendirebilir.

Ancak otomatik birleştirme her zaman kesin kabul edilmemeli; confidence ve evidence mekanizması kullanılmalıdır.

---

# 37. Duplicate Detection

Sistem aynı olayın:

- farklı haberlerde,
- farklı URL'lerde,
- farklı dillerde

tekrar yayınlanmasını tespit edebilmelidir.

Bu, intelligence signal-to-noise oranını yükseltir.

---

# 38. Language Intelligence

Sistem zamanla çok dilli kaynakları işleyebilir.

Örneğin:

```text
Turkish
English
Arabic
Russian
French
German
...
```

Aynı event farklı dillerdeki kaynaklarla ilişkilendirilebilir.

---

# 39. OSINT Domains

Scryne tek bir OSINT alanıyla sınırlı olmamalıdır.

Zaman içerisinde aşağıdaki alanlar eklenebilir.

### GEOINT

- harita
- uydu görüntüsü
- konum analizi
- coğrafi ilişkiler

### SOCMINT

- sosyal medya
- açık profiller
- bilgi yayılımı
- trend analizi

### WEBINT

- web araştırması
- domain
- website
- arşiv

### DOCINT

- belgeler
- PDF
- OCR
- metadata
- belge ilişkileri

### MEDIAINT

- fotoğraf
- video
- görsel metadata
- medya doğrulama

### CONFLICT INTELLIGENCE

- savaş
- çatışma
- askeri olaylar
- bölgesel gelişmeler

### POLITICAL INTELLIGENCE

- politik aktörler
- açıklamalar
- seçimler
- siyasi olaylar

### CORPORATE INTELLIGENCE

- şirketler
- yöneticiler
- satın almalar
- iştirakler
- hukuki gelişmeler

---

# 40. Modüler Mimari

Sistem tek bir monolith olmak yerine capability tabanlı büyümelidir.

```text
SCRYNE
│
├── Brain
│
├── Intelligence Core
│
├── Collection
│
├── Monitoring
│
├── Analysis
│
├── Investigation
│
├── Graph
│
├── Geo
│
├── Evidence
│
├── Verification
│
└── Interface
```

Yeni yetenekler mevcut sistemi bozmak yerine Core'a bağlanmalıdır.

---

# 41. Brain-Centric Architecture

Temel mimari:

```text
                     SCRYNE OSINT LAB
                            │
                            ▼
                     ┌─────────────┐
                     │ OSINT BRAIN │
                     └──────┬──────┘
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
          ▼                 ▼                 ▼
      COLLECTION         ANALYSIS         MONITORING
          │                 │                 │
          └─────────────────┼─────────────────┘
                            │
                            ▼
                    INTELLIGENCE CORE
                            │
             ┌──────────────┼──────────────┐
             │              │              │
             ▼              ▼              ▼
          Entities        Events        Evidence
             │              │              │
             └──────────────┼──────────────┘
                            ▼
                      KNOWLEDGE GRAPH
                            │
                            ▼
                       INTERFACE
                            │
                            ▼
                           USER
```

---

# 42. Data Flow

Temel veri yaşam döngüsü:

```text
EXTERNAL WORLD
      ↓
COLLECT
      ↓
RAW DATA
      ↓
NORMALIZE
      ↓
EXTRACT
      ↓
OBSERVATION
      ↓
CLASSIFY
      ↓
ENTITY / EVENT / CLAIM
      ↓
VERIFY
      ↓
RELATE
      ↓
INTELLIGENCE GRAPH
      ↓
OSINT BRAIN
      ↓
MONITORING / ALERTING
      ↓
USER
```

---

# 43. Information Lifecycle

Her anlamlı bilgi aşağıdaki yaşam döngüsünden geçebilir:

```text
DISCOVERED
    ↓
INGESTED
    ↓
NORMALIZED
    ↓
CLASSIFIED
    ↓
LINKED
    ↓
EVALUATED
    ↓
STORED
    ↓
MONITORED
    ↓
UPDATED
    ↓
ARCHIVED
```

---

# 44. Memory Lifecycle

OSINT Brain'in hafıza yaşam döngüsü:

```text
OBSERVATION
    ↓
SHORT-TERM CONTEXT
    ↓
STRUCTURED KNOWLEDGE
    ↓
RELATIONSHIP
    ↓
LONG-TERM MEMORY
    ↓
RECALLED
    ↓
RE-EVALUATED
    ↓
UPDATED
```

---

# 45. Active Intelligence Loop

Sistem sürekli çalışan bir döngüye sahip olmalıdır.

```text
        ┌─────────────┐
        │   OBSERVE   │
        └──────┬──────┘
               ↓
        ┌─────────────┐
        │   PROCESS   │
        └──────┬──────┘
               ↓
        ┌─────────────┐
        │   REMEMBER  │
        └──────┬──────┘
               ↓
        ┌─────────────┐
        │   CONNECT   │
        └──────┬──────┘
               ↓
        ┌─────────────┐
        │   ANALYZE   │
        └──────┬──────┘
               ↓
        ┌─────────────┐
        │   DETECT    │
        └──────┬──────┘
               ↓
        ┌─────────────┐
        │   NOTIFY    │
        └──────┬──────┘
               │
               └──────────→ OBSERVE
```

---

# 46. Interface Philosophy

Arayüz klasik admin dashboard mantığında olmamalıdır.

Sistem:

- yoğun,
- profesyonel,
- information-dense,
- hızlı,
- analitik,
- modern,
- dark-first

bir intelligence workstation hissi vermelidir.

Ancak görsel karmaşa oluşturulmamalıdır.

Amaç:

> **Çok fazla bilgiyi göstermek değil, çok fazla bilgiden anlam çıkarmayı kolaylaştırmak.**

---

# 47. Main Workspace

Ana ekran kullanıcının intelligence command center'ı olabilir.

```text
┌──────────────────────────────────────────────┐
│ SCRYNE                           ● LIVE       │
├──────────────────────────────────────────────┤
│                                              │
│ Search / Ask / Investigate                   │
│                                              │
├──────────────────────────────────────────────┤
│                                              │
│ PRIORITY INTELLIGENCE                        │
│                                              │
│ ⚠ Event escalation                           │
│ ● New entity relationship                    │
│ ● Investigation update                      │
│                                              │
├──────────────────────────────────────────────┤
│                                              │
│ WORLD        ENTITIES       EVENTS           │
│ MAP          GRAPH          TIMELINE         │
│                                              │
└──────────────────────────────────────────────┘
```

---

# 48. Investigation-First UX

Kullanıcı sistemde:

```text
Search
→ Entity
→ Investigation
→ Evidence
→ Relationship
→ Event
→ Source
```

şeklinde dolaşabilmelidir.

Her nesneden diğer nesnelere geçiş mümkün olmalıdır.

Örneğin:

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
```

---

# 49. Intelligence Inbox

Kullanıcının yeni intelligence gelişmelerini göreceği merkez.

Örneğin:

```text
INTELLIGENCE INBOX

[HIGH]
New conflict event detected

[HIGH]
Entity relationship changed

[MEDIUM]
New source confirms previous claim

[MEDIUM]
Investigation #14 updated

[LOW]
New mention detected
```

Kullanıcı bunları:

- açabilir,
- inceleyebilir,
- ignore edebilir,
- investigation'a ekleyebilir,
- takip edebilir.

---

# 50. User Control

Scryne aktif bir sistem olsa da kontrol kullanıcıda kalmalıdır.

Sistem:

- önerir,
- toplar,
- analiz eder,
- ilişkilendirir,
- uyarır.

Ancak kritik kararları kullanıcı adına otomatik olarak vermemelidir.

Özellikle:

- entity merge
- claim verification
- source trust
- investigation conclusion

gibi konularda kullanıcı onayı veya açık confidence modeli kullanılmalıdır.

---

# 51. AI Role

AI sistemin kendisi değildir.

AI:

- extraction
- classification
- summarization
- entity resolution
- relationship suggestion
- anomaly detection
- hypothesis generation
- semantic search
- research assistance

gibi görevlerde kullanılabilir.

Ancak AI çıktısı ile gerçek kaynak verisi birbirinden ayrılmalıdır.

```text
SOURCE FACT
    ≠
AI INTERPRETATION
```

---

# 52. Human-in-the-Loop

Sistem gerektiğinde kullanıcıdan değerlendirme isteyebilmelidir.

Örneğin:

```text
Possible Entity Match

Person A
may be
Person B

Confidence:
71%

[Confirm]
[Reject]
[Investigate]
```

Kullanıcı kararı sistemin gelecekteki değerlendirmelerine yardımcı olabilir.

---

# 53. Self-Improving System

Scryne'in zaman içerisinde daha iyi hale gelmesi hedeflenmelidir.

Ancak:

> "AI kendi kendini eğitiyor"

gibi kontrolsüz bir sistem yerine:

```text
Observation
↓
Feedback
↓
Evaluation
↓
Rule / Model Improvement
↓
Validation
↓
Deployment
```

gibi kontrollü bir süreç tercih edilmelidir.

---

# 54. Research Reproducibility

Her araştırmanın nasıl gerçekleştirildiği mümkün olduğunca kayıt altına alınmalıdır.

Örneğin:

```text
Investigation #42

Started:
2026-08-28

Queries:
...

Sources visited:
...

Evidence collected:
...

Entities identified:
...

Analyst actions:
...

Conclusion:
...
```

Bu sayede araştırmalar tekrar incelenebilir.

---

# 55. Auditability

Sistem önemli bilgilerin nereden geldiğini ve nasıl değiştiğini açıklayabilmelidir.

Örneğin:

```text
Why does Scryne believe this?

Because:

3 independent sources
+
1 official statement
+
1 supporting document
```

---

# 56. Security & Privacy

Scryne kişisel bir intelligence laboratuvarı olduğundan güvenlik temel prensip olmalıdır.

Öncelikler:

- local-first yaklaşım
- secret management
- encrypted credentials
- least privilege
- network isolation where appropriate
- audit logging
- safe external integrations
- secure storage
- backup
- restore testing

Kullanıcının kişisel Brain'i ile OSINT Brain'i birbirinden izole tutulmalıdır.

---

# 57. Data Provenance

Her verinin mümkün olduğunca:

```text
source
timestamp
collection method
original location
content hash
processing history
```

bilgileri tutulmalıdır.

---

# 58. Resilience

Sistem dış kaynakların erişilemez olması durumunda tamamen çalışamaz hale gelmemelidir.

Örneğin:

```text
External Source Down
        ↓
Cached Knowledge
        ↓
Historical Memory
        ↓
System remains usable
```

Yeni veri alınamadığında bunun açıkça belirtilmesi gerekir.

---

# 59. Offline / Local Intelligence

Sistemin mümkün olduğunca yerel çalışabilmesi uzun vadeli hedeflerden biri olabilir.

Özellikle:

- memory
- investigations
- graph
- evidence
- historical data

yerel tutulabilir.

Dış servisler capability sağlayabilir ancak sistemin temel hafızası tek bir üçüncü taraf servise bağımlı olmamalıdır.

---

# 60. Extensibility

Sistem zaman içerisinde yeni OSINT yetenekleri eklenmesine uygun olmalıdır.

Örneğin:

```text
Scryne v1
→ Web Intelligence

Scryne v2
→ Entity Intelligence

Scryne v3
→ Event Intelligence

Scryne v4
→ GEOINT

Scryne v5
→ SOCMINT

Scryne v6
→ Document Intelligence
```

Ancak Core modelin stabil kalması hedeflenmelidir.

---

# 61. Plugin / Capability Model

Yeni yetenekler bağımsız capability olarak eklenebilir.

Örneğin:

```text
capabilities/
│
├── geoint/
├── social-intelligence/
├── document-intelligence/
├── media-verification/
├── corporate-intelligence/
└── conflict-intelligence/
```

Her capability Core'a bağlanır.

---

# 62. Örnek Kullanım Senaryosu — Şirket

Kullanıcı:

> "Company X hakkında ne biliyoruz?"

Sistem:

```text
1. Entity Resolution
2. Existing Memory Search
3. Related Entity Discovery
4. Recent Event Search
5. Source Discovery
6. Relationship Analysis
7. Investigation History
8. Confidence Evaluation
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
```

---

# 63. Örnek Kullanım Senaryosu — Kişi

Kullanıcı:

> "Person X hakkında bildiğin her şeyi çıkar."

Sistem:

```text
Identity
Aliases
Organizations
Positions
Events
Statements
Sources
Relationships
Timeline
Investigations
Evidence
Recent developments
```

Bunları kaynaklarıyla birlikte sunar.

---

# 64. Örnek Kullanım Senaryosu — Savaş / Çatışma

Sistem sürekli belirli bölgeleri izler.

Yeni gelişme:

```text
NEW EVENT

Region X

Detected:
08:12

Sources:
7

Independent:
3

Evidence:
2

Confidence:
81%
```

Sistem event'i mevcut knowledge graph'a bağlar:

```text
Region X
    ↓
Conflict
    ↓
Military Unit A
    ↓
Event #142
    ↓
Source #88
```

Kullanıcıya aktif bildirim gönderilir.

---

# 65. Örnek Kullanım Senaryosu — Yeni Bağlantı

Sistem iki entity'nin daha önce bilinmeyen bir bağlantısını tespit eder.

```text
NEW RELATIONSHIP

Organization A
        ↓
possible supplier
        ↓
Company B

Confidence:
73%

Evidence:
3 sources
```

Kullanıcı bunu araştırmaya dönüştürebilir.

---

# 66. Örnek Kullanım Senaryosu — Eski Bilginin Yeniden Ortaya Çıkması

Sistem yeni bir olay tespit eder.

Memory search:

```text
Related Investigation:
#023

Last activity:
4 months ago
```

Sistem kullanıcıya:

> **"Bu gelişme daha önce yürüttüğün Investigation #023 ile ilişkili olabilir."**

şeklinde bildirim verir.

Bu özellik OSINT Brain'in "hatırlama" kabiliyetinin temel örneklerinden biridir.

---

# 67. Long-Term Evolution

Scryne zaman içerisinde şu aşamalardan geçebilir:

```text
STAGE 1
Research Assistant

↓

STAGE 2
Knowledge System

↓

STAGE 3
Monitoring System

↓

STAGE 4
Intelligence Graph

↓

STAGE 5
Active Intelligence System

↓

STAGE 6
Personal OSINT Brain

↓

STAGE 7
Autonomous Research Assistant
```

Buradaki hedef tamamen otonom karar veren bir sistem değil, **yüksek derecede yetenekli ve kullanıcı kontrollü bir intelligence companion** oluşturmaktır.

---

# 68. Başlangıç Prensibi

Proje ilk günden bütün OSINT dünyasını çözmeye çalışmamalıdır.

İlk hedef:

> **Sağlam bir OSINT Brain + Core Knowledge Model + Investigation System oluşturmak.**

Bunlar stabil hale geldikten sonra collection ve monitoring yetenekleri eklenmelidir.

---

# 69. İlk Temel Capability'ler

İlk sürüm için temel yetenekler:

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
✓ Notifications
```

Daha ileri capability'ler sonraki aşamalara bırakılabilir.

---

# 70. Başlangıçta Yapılmaması Gerekenler

İlk sürümde:

- bütün interneti taramak,
- onlarca API entegrasyonu,
- yüzlerce OSINT aracı,
- tamamen otonom araştırma,
- kontrolsüz AI kararları,
- devasa frontend,
- gereksiz mikroservis mimarisi

hedeflenmemelidir.

Önce bilgi modelinin ve Brain'in doğru çalışması sağlanmalıdır.

---

# 71. Başarı Kriteri

Scryne başarılı olduğunda kullanıcı:

> "Dünyada ne oluyor?"

diye baktığında sistemden anlamlı bir cevap alabilmelidir.

Ama daha önemlisi:

> "Bu gelişmenin geçmişte bildiğimiz şeylerle bağlantısı ne?"

diye sorduğunda sistem bunu gösterebilmelidir.

Ve:

> "Ben bunu daha önce araştırmış mıydım?"

sorusuna da cevap verebilmelidir.

---

# 72. Nihai Hedef

Uzun vadede Scryne:

```text
OBSERVE
    ↓
UNDERSTAND
    ↓
REMEMBER
    ↓
CONNECT
    ↓
MONITOR
    ↓
DISCOVER
    ↓
INFORM
```

döngüsünü sürekli gerçekleştiren bir sistem haline gelmelidir.

Kullanıcı:

```text
SEARCH
INVESTIGATE
ANALYZE
DECIDE
```

yapar.

Sistem:

```text
OBSERVE
COLLECT
REMEMBER
CONNECT
VERIFY
MONITOR
ALERT
```

yapar.

---

# 73. Scryne'in Konsept Tanımı

Scryne'i tek cümlede tanımlamak gerekirse:

> **Scryne, açık kaynaklardan dünyayı sürekli gözlemleyen, gördüğü bilgileri kendi hafızasında zaman içerisinde biriktiren, entity'ler, olaylar, kaynaklar, kanıtlar ve araştırmalar arasında bağlantılar kuran ve önemli gelişmeleri kullanıcıya aktif olarak sunan kişisel bir intelligence operating system'dir.**

---

# 74. Scryne'in Temel İlkesi

> **The system should not merely know what is happening.**
>
> **It should remember what happened, understand what is connected, detect what changed, and help the analyst understand why it matters.**

---

# 75. Nihai Mimari Vizyon

```text
                           ┌─────────────────────┐
                           │       SCRYNE        │
                           │    OSINT LAB        │
                           └──────────┬──────────┘
                                      │
                              ┌───────▼───────┐
                              │   OSINT BRAIN │
                              │               │
                              │ Memory        │
                              │ Context       │
                              │ Recall        │
                              │ Knowledge     │
                              └───────┬───────┘
                                      │
                 ┌────────────────────┼────────────────────┐
                 │                    │                    │
                 ▼                    ▼                    ▼
            COLLECTION            ANALYSIS             MONITORING
                 │                    │                    │
                 │                    │                    │
                 └────────────────────┼────────────────────┘
                                      │
                              ┌───────▼───────┐
                              │ INTELLIGENCE  │
                              │     CORE      │
                              └───────┬───────┘
                                      │
             ┌────────────────────────┼────────────────────────┐
             │                        │                        │
             ▼                        ▼                        ▼
          ENTITIES                 EVENTS                  SOURCES
             │                        │                        │
             └────────────────────────┼────────────────────────┘
                                      │
                         ┌────────────▼────────────┐
                         │     KNOWLEDGE GRAPH     │
                         └────────────┬────────────┘
                                      │
                 ┌────────────────────┼────────────────────┐
                 │                    │                    │
                 ▼                    ▼                    ▼
           INVESTIGATIONS          EVIDENCE            TIMELINES
                 │                    │                    │
                 └────────────────────┼────────────────────┘
                                      │
                              ┌───────▼───────┐
                              │ INTELLIGENCE  │
                              │   INTERFACE   │
                              └───────┬───────┘
                                      │
                                      ▼
                                     YOU
```

---

# 76. Final Vision

Scryne'in amacı başka insanların kullandığı bir OSINT platformu oluşturmak değildir.

Amaç:

> **Kullanıcının kendisine ait, zaman içerisinde gelişen, kendi hafızasını oluşturan, dünyayı sürekli gözlemleyen, araştırmaları birbirine bağlayan ve gerektiğinde kullanıcıyı kendiliğinden bilgilendiren kişisel bir intelligence ecosystem oluşturmasıdır.**

Sistem doğduğu anda her şeyi bilmez.

Öğrendikçe büyür.

Gözlemledikçe hafızası gelişir.

Araştırdıkça bağlantıları artar.

Zaman geçtikçe geçmişi değer kazanır.

Yeni bilgi geldiğinde eski bilgiyi yeniden değerlendirir.

Ve sonunda:

> **Scryne yalnızca bilgi depolayan bir uygulama değil, dünyaya ilişkin kendi tarihine sahip yaşayan bir OSINT Brain haline gelir.**

---

## Project Identity

**Name:** Scryne OSINT Lab

**Category:** Personal Intelligence / OSINT / Investigation / Knowledge Graph

**Core Concept:** Living OSINT Brain

**Architecture Philosophy:** Brain-centric, modular, local-first, evidence-driven

**Primary User:** Individual researcher / analyst

**Primary Goal:** Continuous open-source intelligence collection, memory, analysis and investigation

**Long-Term Goal:** A personal intelligence operating system that continuously observes the external world and develops its own connected knowledge over time.

---

## Guiding Principle

```text
Observe.
Remember.
Connect.
Verify.
Understand.
Monitor.
Inform.
```

**Scryne does not simply search the world.

Scryne builds a memory of it.**