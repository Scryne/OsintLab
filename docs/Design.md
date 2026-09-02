---
proje: OsintLab
created: 2026-09-02
type: design-sistemi
---
# OsintLab — Design Sistemi

Taban disiplin (sabit, tüm projelerde aynı): `~/.claude/CLAUDE.md` içindeki Dark
Glassmorphism kuralları — blur/border/kontrast/performans değerleri buradan gelir, burada
tekrar edilmez.

## Proje Kimliği
(Bu projeyi diğerlerinden ayıran katman)

- **Mood:** Gece masası / dosya odası — flaşlı bir "SaaS dashboard" değil, tek bir analistin
  geç saatte önündeki dava dosyasını çalıştığı bir masa. Sakin, yoğun, dekorasyonsuz;
  "teşhir" değil "çalışma yüzeyi".

- **Accent Palet:** İki AYRI, birbirine karışmaması gereken renk sistemi var — bu projenin
  en önemli tasarım kararı. Genel "koyu tema + tek parlak accent" klişesinin bilinçli
  reddi: burada renk zaten bir bilgi taşıyor (confidence + priority), dekorasyon değil.

  1. **Confidence Spectrum** (soğuk→sıcak, `knowledge_state`'in birebir karşılığı —
     imza öğe, aşağıda detay):
     `UNKNOWN #4B5768 → OBSERVED #3E6E93 → REPORTED #2F8FA6 → SUPPORTED #34A183 →
     CORROBORATED #C99A3E → HIGH_CONFIDENCE #E8B84B` — `CONTRADICTED #C4466E` bu rampanın
     DIŞINDA, bilinçli bir "kırılma" rengi (mor-gül tonu, ramp'a ait değilmiş gibi durmalı).
  2. **Priority/Alarm Scale** (Inbox'a özel, mor-kırmızı ailesi — confidence'ın mavi-yeşil-
     altın ailesiyle KARIŞTIRILMAMALI):
     `INFO #6B7690 → LOW #7C74C4 → MEDIUM #C4703E → HIGH #DD5A46 → CRITICAL #E23A6B`
  3. **UI Accent** (buton/link/aktif nav/focus ring — chrome rengi, epistemik anlamı yok):
     `#9B8AFB` (sinyal moru) — confidence/priority rampalarının hiçbirine yakın değil,
     kullanıcı "bu bir buton" ile "bu bir güven seviyesi" göstergesini asla karıştırmasın.
  4. **Zemin:** düz siyah değil — `#05070A` taban üstünde sol-üstte çok düşük alpha çivit
     mavisi (`#1B2340`), sağ-altta çok düşük alpha pas/kahve (`#2A1B12`) mesh gradient
     (global kural: ışık kaynağı sol-üst). Opak paneller (tablo, timeline satırı, graph
     canvas — okunabilirlik/performans için CAM DEĞİL): `#0E121A` (`--surface`), hover
     `#141924`. Cam sadece: üst nav, Inbox paneli, modal'lar, birincil CTA butonları.

- **Tipografi Eşleşmesi:** 3 rollü, "dava dosyası" mantığıyla:
  - **Display** (kısıtlı kullanım — Entity/Investigation başlıkları, "OSINT LAB" wordmark'ı):
    **IBM Plex Serif**, 600, dar letter-spacing — dosya gömleği/antet hissi.
  - **Body/UI** (nav, buton, tablo başlığı, paragraf): **IBM Plex Sans**, 400/500/600 —
    teknik ama insani, kurumsal soğukluğa kaçmıyor.
  - **Data/mono** (timestamp, id, hash, confidence sayısı, source URL, kod-benzeri değer):
    **JetBrains Mono**, 400/500 — teleks/terminal hissi, verinin "ham" olduğunu işaretler.
  - Google Fonts: `IBM+Plex+Serif:wght@500;600`, `IBM+Plex+Sans:wght@400;500;600`,
    `JetBrains+Mono:wght@400;500`.

- **Farklılaştırıcı Detay (imza öğe):** **Confidence Spectrum'un kendisi arayüzün omurgası
  olması** — süsleme değil, mekanizmanın görselleşmesi. Her Claim/Entity/Event kartının sol
  kenar rengi doğrudan `knowledge_state`'ten geliyor; Entity/Investigation sayfalarında bu
  6 durumu gösteren ince bir dikey "spectrum rail" gerçek bir lejant olarak duruyor (dekoratif
  gradient değil, tıklanabilir filtre). Kullanıcı renk okumasını öğrendikçe, grafiği/timeline'ı
  taramadan "bu bilgi ne kadar sağlam" sorusunu göz ucuyla cevaplayabiliyor.

## Uygulama Notları
(Component bazlı özel kararlar — bu projede nav nasıl duruyor, kart stili vb.)

- **Q15 (SOURCE FACT / AI ANALYSIS / SYSTEM INFERENCE / USER INTERPRETATION) ayrımı RENKLE
  DEĞİL, kenarlık stili + ikonla yapılır** — üçüncü bir renk sistemi eklemek confidence/
  priority'yi sulandırır. Sol kenarlık (2px):
  - SOURCE FACT: düz çizgi, `quote` glyph, normal ağırlık.
  - SYSTEM INFERENCE: kesikli (dashed) çizgi, `git-branch`/kural-motoru glyph'i.
  - AI ANALYSIS: noktalı (dotted) çizgi, `sparkle` glyph, metin *italik*.
  - USER INTERPRETATION: düz çizgi ama **UI Accent moru** (`#9B8AFB`) — bilinçli tek istisna,
    çünkü bu tek kategori kullanıcının kendi sesi. `pencil` glyph'i, zemin %4 opaklıkta mor
    tint.
- **Yoğunluk:** dashboard-dense (8–32px spacing skalası) — Search/Ask + Priority Intelligence
  + Entity Graph + Timeline aynı ekranda, "maksimum veri görünürlüğü, minimal padding".
- **"World Map" paneli v1 kapsamı dışı bırakıldı** — GEOINT (coğrafi harita) Proje-Fikri.md'de
  açıkça sonraki fazlara bırakılmış bir domain; Main Workspace'te onun yerine **Entity Graph +
  Timeline** iki ana panel olarak duruyor.
- **Hareket:** kısıtlı — sadece 150–250ms hover/transition, `backdrop-filter` ASLA anime
  edilmiyor (performans, global kural). `prefers-reduced-motion` her yerde saygı görüyor.
- **İkonografi:** SVG (Lucide) — emoji yok.
- **Nav:** sol tarafta ince, cam, sabit bir dikey şerit (Search/Ask, Inbox badge'i ile,
  Entities, Investigations, Sources) — geniş bir üst mega-menu değil, tek kullanıcılı bir
  araç için gereksiz.
