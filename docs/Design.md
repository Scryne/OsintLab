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

> **2026-09-02 güncellemesi:** Scryne kendi hazırladığı "Frontend-taslak" reposunu (generic
> dark-glass SaaS şablonu) canlıda görünce OsintLab'ın "chrome"unun (zemin/glass/tipografi/
> buton/nav stili) o repoya çevrilmesini istedi. Confidence Spectrum + Priority Scale renk
> sistemi ve bunların taşıdığı epistemik anlam KORUNDU — reskin sadece dekoratif katmanı
> etkiledi. Aşağıdaki Mood/Zemin/Tipografi/UI Accent alt-maddeleri bu kararla güncellendi,
> Confidence Spectrum/Priority Scale maddeleri değişmedi.

- **Mood:** Taslağın modern, indigo/violet ağırlıklı SaaS-workstation hissi — önceki "gece
  masası/dosya odası" bespoke kimliğinin yerini aldı. Yine de her elemente cam sürülmüyor
  (performans/okunabilirlik prensibi korunuyor, aşağıya bkz.).

- **Accent Palet:** İki AYRI, birbirine karışmaması gereken renk sistemi var — bu projenin
  en önemli tasarım kararı, taslağa geçişte de dokunulmadı. Genel "koyu tema + tek parlak
  accent" klişesinin bilinçli reddi: burada renk zaten bir bilgi taşıyor (confidence +
  priority), dekorasyon değil.

  1. **Confidence Spectrum** (soğuk→sıcak, `knowledge_state`'in birebir karşılığı —
     imza öğe, aşağıda detay):
     `UNKNOWN #5B697D → OBSERVED #3E6E93 → REPORTED #2F8FA6 → SUPPORTED #34A183 →
     CORROBORATED #C99A3E → HIGH_CONFIDENCE #E8B84B` — `CONTRADICTED #C4466E` bu rampanın
     DIŞINDA, bilinçli bir "kırılma" rengi (mor-gül tonu, ramp'a ait değilmiş gibi durmalı).
     (`UNKNOWN` 2026-09-06'da `#4B5768`'den yükseltildi — bkz. Kontrast Sözleşmesi. Bunlar
     nokta/kenarlık değerleridir; **metin** için `-text` tokenları kullanılır.)
  2. **Priority/Alarm Scale** (Inbox'a özel, mor-kırmızı ailesi — confidence'ın mavi-yeşil-
     altın ailesiyle KARIŞTIRILMAMALI):
     `INFO #6B7690 → LOW #7C74C4 → MEDIUM #C4703E → HIGH #DD5A46 → CRITICAL #E23A6B`
  3. **UI Accent** (buton/link/aktif nav/focus ring — chrome rengi, epistemik anlamı yok):
     `#8B5CF6` (taslağın violet/ring rengi) — confidence/priority rampalarının hiçbirine
     yakın değil, kullanıcı "bu bir buton" ile "bu bir güven seviyesi" göstergesini asla
     karıştırmasın. Birincil CTA butonları taslağın imza gradyanını kullanır:
     `linear-gradient(135deg, #4F46E5, #6366F1)`.
  4. **Zemin:** taslağın mesh'i — `#090A0C` taban üstünde sol-üstte düşük alpha violet
     (`rgba(139,92,246,.14)`), sağ-altta düşük alpha mavi (`rgba(59,130,246,.10)`) radial
     gradient + 48px'lik çok düşük alpha grid çizgileri (global kural: ışık kaynağı
     sol-üst). Opak paneller (tablo, timeline satırı, graph canvas — okunabilirlik/
     performans için hâlâ blur'lu CAM DEĞİL, ama artık taslağın translucent beyaz-üstü-
     koyu tonuyla): `rgba(255,255,255,.045)` (`--surface`), hover `rgba(255,255,255,.065)`.
     Cam (gerçek `backdrop-filter`) hâlâ sadece: üst nav, Inbox paneli, modal'lar —
     taslağın `.glass-strong` tarifine göre (16px blur + inset highlight + shadow).

- **Tipografi Eşleşmesi:** Taslağa göre tek aileye indirildi (önceki 3-rollü IBM Plex/
  JetBrains Serif ayrımı terk edildi):
  - **Display + Body/UI** (başlıklar, nav, buton, paragraf — hepsi): **Inter**, 400–700.
  - **Data/mono** (timestamp, id, hash, confidence sayısı, source URL): **JetBrains Mono**
    korunuyor — taslakta bir mono kullanım örneği yok ama bu proje için hâlâ işlevsel
    (verinin "ham/makine-okunur" olduğunu işaretliyor), o yüzden bilerek elenmedi.
  - Google Fonts: `Inter:wght@400;500;600;700`, `JetBrains+Mono:wght@400;500`.

- **Farklılaştırıcı Detay (imza öğe):** **Confidence Spectrum'un kendisi arayüzün omurgası
  olması** — süsleme değil, mekanizmanın görselleşmesi. Entity ve Investigation sayfalarında
  6 durumu gösteren dikey "spectrum rail" gerçek bir lejant olarak duruyor (dekoratif gradient
  değil, tıklanabilir filtre). Durum her claim'de `ConfidenceBadge` ile de okunuyor: renkli
  nokta + Türkçe etiket + yüzde.

  > **2026-09-06 — kart kenarı denendi ve REDDEDİLDİ.** Bu madde daha önce "her kartın sol
  > kenar rengi doğrudan `knowledge_state`'ten gelir" diyordu. Uygulandı, canlı veriyle
  > bakıldı, geri alındı. **Neden:** gerçek dağılım tek renkli — 44 claim'in 29'u REPORTED,
  > 11'i SUPPORTED. Bir entity sayfasındaki claim'lerin neredeyse hepsi aynı durumda
  > olduğu için kenar aynı rengi tekrarlıyor ve **hiçbir ayrım üretmiyor**; badge zaten
  > durumu yazıyla, noktayla ve yüzdeyle söylüyor, kenar rengin üçüncü tekrarı oluyor.
  > Bilgi taşımayan renk dekorasyondur, ve koyu monokrom bir arayüzde doygun renk şeritleri
  > "şablon" hissi veriyor. Scryne'ın değerlendirmesi: "çok kötü duruyor, AI slop olduğu
  > belli oluyor."
  >
  > **Çıkarılan kural:** durum başına renk ancak **karışık** bir kümede ayırt edici olur.
  > Bu projede claim listeleri neredeyse hep tek durumda; o yüzden confidence rengi
  > *nokta/badge/rail* ölçeğinde kalır, yüzey ölçeğine (kenar, zemin, şerit) çıkmaz.
  > Faz 18-20 grafı çeşitlendirdikten sonra dağılım gerçekten karışırsa bu yeniden
  > değerlendirilebilir — ama o zaman da önce canlı veriyle bakılarak.

## Kontrast Sözleşmesi (2026-09-06)

Renk bu projede bilgi taşıyor, dolayısıyla okunabilirliği bir tercih değil bir kısıt.
Rampaların **anlamı** (soğuk→sıcak sıra, CONTRADICTED'ın rampa dışında durması, priority'nin
ayrı aile olması) dokunulmaz; kontrast bunun **üzerine** ton değil açıklık oynayarak sağlanır.

**Kural: bir rengin zemin/nokta/kenarlık hâli ile metin hâli ayrı tokenlardır.**

| Kullanım | Token | Eşik | Ölçüm zemini |
| --- | --- | --- | --- |
| Nokta, kenarlık, rail bloğu, kart kenarı | `--confidence-*`, `--priority-*` | 3:1 (WCAG 1.4.11, UI bileşeni) | `.glass-panel` (#1b1c1e) |
| Badge/etiket metni (`text-xs` = 12px) | `--confidence-*-text`, `--priority-*-text` | 4.5:1 | aşağıya bkz. |
| Link/vurgu metni | `--brand-accent-text` | 4.5:1 | cam + surface |
| Buton zemini | `--brand-accent` | — | metin `--brand-accent-foreground`'dan |

**Ölçüm zemini iki badge'de farklıdır — karıştırılmamalı:**
- `ConfidenceBadge` saydamdır; metin doğrudan cam/surface üzerindedir.
- `PriorityBadge` kendi rengiyle **%22 tint'lenmiş** bir pill'dir; metin o tint üzerindedir
  ve zemin renge yaklaştığı için kontrast belirgin şekilde düşer. Bu yüzden priority metin
  tokenları confidence'dakilerden daha açıktır. Tint'i düşürmek çözüm değildir: %10'a
  indirilse bile ham renkle tavan 4.15'tir.

**2026-09-06 denetiminde düzeltilenler.** Ölçülmeden önce yedi token kalıyordu; en kötüsü,
en çok görülmesi gereken iki durumun (CONTRADICTED 3.61, CRITICAL 4.10) en zor okunanlar
arasında olmasıydı. `UNKNOWN` ise nokta olarak 2.32 ile 3:1'i bile geçmiyordu — rampanın en
sönük ucu fiilen görünmezdi; ham değeri `#4B5768 → #5B697D` yükseltildi (luminans sırası
korunarak, tek ham değer değişikliği).

**Yeni renk eklerken:** `frontend/src/app/globals.css` içindeki tokenları okuyup her eşiği
yeniden ölçen doğrulama, Paket 1 çalışmasında kullanıldı; token eklendiğinde aynı ölçüm
tekrarlanmalı. Değerler elle tahmin edilmez.

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
