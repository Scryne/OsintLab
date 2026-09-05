---
version: alpha
name: OsintLab
description: Tek kullanıcılı, local-first bir intelligence workstation; renk burada dekorasyon değil, bilginin ne kadar sağlam olduğunu taşıyan veri.
colors:
  # shadcn semantik eşleştirmesinde `--primary: var(--text-primary)` — birincil buton
  # zemini neredeyse beyaz, üstündeki metin koyu. Marka moru (`brand-accent`) ayrı bir
  # roldür: link/focus/aktif nav, yani "bu etkileşimli" işareti.
  primary: "#f4f4f5"
  primary-foreground: "#090a0c"
  bg-base: "#090a0c"
  text-primary: "#f4f4f5"
  text-secondary: "#a1a1aa"
  text-tertiary: "#86868f"
  brand-accent: "#8b5cf6"
  brand-accent-foreground: "#14101f"
  brand-accent-text: "#956af7"
  confidence-unknown: "#5b697d"
  confidence-observed: "#3e6e93"
  confidence-reported: "#2f8fa6"
  confidence-supported: "#34a183"
  confidence-corroborated: "#c99a3e"
  confidence-high-confidence: "#e8b84b"
  confidence-contradicted: "#c4466e"
  confidence-unknown-text: "#76869d"
  confidence-observed-text: "#528ab6"
  confidence-reported-text: "#2f8fa6"
  confidence-supported-text: "#34a183"
  confidence-corroborated-text: "#c99a3e"
  confidence-high-confidence-text: "#e8b84b"
  confidence-contradicted-text: "#cd6284"
  priority-info: "#6b7690"
  priority-low: "#7c74c4"
  priority-medium: "#c4703e"
  priority-high: "#dd5a46"
  priority-critical: "#e23a6b"
  priority-info-text: "#9099ad"
  priority-low-text: "#9993d1"
  priority-medium-text: "#cf8b63"
  priority-high-text: "#e47d6e"
  priority-critical-text: "#ea6e92"
typography:
  sans:
    fontFamily: Inter
  mono:
    fontFamily: JetBrains Mono
rounded:
  base: 0.75rem
---

# OsintLab

## Overview

OsintLab tek kullanıcılı, local-first bir intelligence workstation. Arayüzün işi maksimum
veri görünürlüğü: Search/Ask, Priority Intelligence, graf ve timeline aynı ekranda, dar
padding'le. Görsel dil koyu, cam yüzeyli ve indigo/violet ağırlıklı bir SaaS-workstation
hissi taşıyor.

Bu ürünün tasarımını diğerlerinden ayıran karar şu: **renk bilgi taşıyor.** "Koyu tema + tek
parlak accent" klişesi bilinçli olarak reddedildi, çünkü burada renk bir claim'in ne kadar
sağlam olduğunu ve bir bildirimin ne kadar acil olduğunu söylüyor. Bu yüzden birbirine
karışmaması gereken **iki ayrı renk sistemi** var ve bunlar sistemin en önemli tasarım
kısıtı.

## Colors

**Confidence Spectrum** (`confidence-*`) `knowledge_state`'in birebir karşılığıdır: soğuktan
sıcağa bir "epistemik sıcaklık" rampası. Sıra anlamlıdır ve luminans olarak da artar —
`unknown → observed → reported → supported → corroborated → high-confidence`.
`confidence-contradicted` bu rampanın **dışındadır**: mor-gül tonu, rampaya ait değilmiş gibi
durmalıdır, çünkü çelişki bir güven seviyesi değil bir kırılmadır.

**Priority Scale** (`priority-*`) yalnızca Intelligence Inbox'a aittir ve mor-kırmızı
ailesindedir. Confidence'ın mavi-yeşil-altın ailesiyle **karıştırılmamalıdır**: ikisi farklı
soruları cevaplıyor — "ne kadar eminiz" ile "ne kadar acil".

**UI Accent** (`brand-accent`) her iki sistemin de dışındadır ve epistemik anlamı yoktur;
yalnızca "bu etkileşimli" demektir. Buton, link, aktif nav ve focus ring bu rengi kullanır.

**Her rengin bir zemin hâli, bir de metin hâli vardır.** `*-text` ile biten tokenlar yalnızca
metin içindir; nokta, kenarlık ve rail bloğu ham rampa değerini kullanır. Ayrımın nedeni
ölçülebilir: metin eşiği 4.5:1, dekoratif UI bileşeni eşiği 3:1, ve bu iki eşiği tek bir
değerle geçmek rampanın tonunu bozmadan mümkün değildi. Ayrıntı ve ölçüm zeminleri:
`docs/Design.md` Kontrast Sözleşmesi.

Bir aksan rengi ekleme; bu üç sistem dışında dördüncü bir renk ailesi açmak üçünü birden
sulandırır.

## Typography

Tek aile: **Inter** başlık, nav, buton ve gövde için. **JetBrains Mono** yalnızca verinin ham
ve makine-okunur olduğunu işaretlemek için — timestamp, id, hash, confidence yüzdesi, kaynak
URL. Mono'yu dekoratif olarak kullanma; kullanıldığı yerde "bu bir insan cümlesi değil, bir
kayıt" demektir.

Sayısal veri her zaman `tabular-nums` ile hizalanır.

## Layout

Sol tarafta ince, cam, sabit bir dikey nav şeridi; kenara yapışık değil, kenarlardan boşluklu
ve yuvarlak köşeli bir "yüzen" panel. Tek kullanıcılı bir araç için geniş üst mega-menü
gereksiz.

Yoğunluk dashboard-dense: 8–32px aralığında bir spacing skalası, geniş nefes payı yerine
maksimum veri görünürlüğü.

## Elevation & Depth

Gerçek `backdrop-filter` camı **yalnızca anahtar yüzeylerde** kullanılır: nav, Inbox paneli,
modal'lar ve birincil CTA. Tablo satırı, kart ve graph canvas cam değildir — okunabilirlik ve
performans için yarı saydam opak yüzey kullanır. Her elemente cam sürmek hem camı
sıradanlaştırır hem GPU'yu yorar.

Panellerin kenarında düz tek renk border yerine üstten parlayıp alta sönümlenen bir gradient
"light-catcher" halka vardır; ışık kaynağı tutarlı biçimde sol-üsttedir.

`backdrop-filter` **asla anime edilmez.**

## Components

Q15 provenance ayrımı (SOURCE FACT / SYSTEM INFERENCE / AI ANALYSIS / USER INTERPRETATION)
**renkle değil**, sol kenarlık stili ve ikonla yapılır: düz / kesikli / noktalı çizgi.
Üçüncü bir renk sistemi eklemek confidence ve priority'yi sulandırırdı. Tek istisna
USER INTERPRETATION'dır ve `brand-accent` kullanır, çünkü o kategori kullanıcının kendi sesi.

Yıkıcı ya da geri dönüşü olmayan aksiyonlar iki adımlıdır ve onay düğmesi eylemi tekrar eder
("İlişkiyi kaldır", "Evet" değil). Zaman sınırı yoktur; Escape ve dışarı tıklama ile geri
alınır.

Boş durumlar bir sonraki adımı söyler. İlk-kullanım boşluğu yönlendirir, temizlenmiş boşluk
rahatlatır.

Hata mesajları ne→neden→nasıl sırasını izler; ham hata metni atılmaz ama ikincil kalır.

## Do's and Don'ts

- Confidence ve priority renklerini birbirinin yerine kullanma; farklı soruları cevaplıyorlar.
- Durum rengini yüzey ölçeğine (kart kenarı, zemin şeridi) çıkarma. 2026-09-06'da denendi ve
  geri alındı: gerçek dağılım tek renkli olduğu için kenar hiçbir ayrım üretmiyor, badge
  zaten durumu yazıyla söylüyor, ve doygun renk şeritleri koyu monokrom bir arayüzde şablon
  hissi veriyor. Durum başına renk ancak **karışık** bir kümede ayırt edicidir.
- `backdrop-filter` animasyonu kullanma.
- Emoji kullanma; ikonografi SVG'dir (Lucide).
- Metin için ham rampa rengini kullanma; `*-text` varyantı vardır.
