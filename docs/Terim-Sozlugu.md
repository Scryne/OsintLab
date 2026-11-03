# Terim Sözlüğü

Arayüzde görünen her metin bu sözlüğe bağlıdır. Yeni ekran, düğme ya da hata mesajı yazarken
terimi buradan al; listede yoksa önce buraya ekle.

**Değişmeyenler.** Bu sözlük yalnızca *ekranda görünen* metni bağlar. Rota (`/entities`),
API alanı (`entity_type`, `knowledge_state`), veritabanı tablo/kenar adı (`Entity`,
`ABOUT_ENTITY`, `SAME_AS`) ve enum değerleri (`OPEN`, `CORROBORATED`, `NEW_OBSERVATION`…)
İngilizce kalır. Enum'ların ekrandaki adları `frontend/src/lib/labels.ts` içinde; varlık
türü (`entity_type`) serbest metin olduğu için kayıtlı değer korunur, ekranda Türkçe adı
gösterilir ("Organization" → "Kurum") ve formda Türkçe yazılan tür bilinen değere çevrilir.

**Olduğu gibi kalanlar.** Kısaltma ve özel adlar: OSINT, CVE, CISA KEV, RSS, IP, URL, ASN,
DNS, SPF, HTTP, PDF, OCR, EXIF, GPS, TLP, OPSEC, ACH, EPSS, MITRE ATT&CK, OFAC, GLEIF,
Wikidata, STIX, CSV, Markdown, SHA-256, NATO/Admiralty, Obsidian. "Hash" ve "web" yerleşik
teknik terim olarak kalır.

## Temel kavramlar

| İngilizce (kod/eski arayüz) | Arayüzde | Not |
|---|---|---|
| Entity | Varlık | Kişi, kurum, ürün, konum… |
| Event | Olay | |
| Claim | İddia | |
| Observation | Gözlem | Ham kayıt; yorum içermez |
| Evidence | Kanıt | Kanıt Kasası = elle yüklenen belgeler |
| Source | Kaynak | |
| Investigation | Soruşturma | |
| Hypothesis | Hipotez | |
| Finding | Bulgu | |
| Selector | Seçici | Alan adı, IP, hash, CVE… |
| Knowledge Graph | Bilgi Grafı | |
| Intelligence Inbox / Inbox | Gelen Kutusu | |
| Priority Intelligence | Öncelikli İstihbarat | |
| Promote | Terfi / terfi ettir | Gözlemi iddiaya çevirmek |
| Promote Kuyruğu | Terfi Kuyruğu | |
| Lineage | Köken | Kaynağın hangi kaynaktan türediği |
| Provenance | Menşe | Bir bilginin nereden geldiğinin kaydı |
| Confidence | Güven / güven skoru | |
| Corroboration | Doğrulama | İki bağımsız kaynağın aynı iddiayı desteklemesi |
| Alias | Diğer ad | |
| Same-as | Olası eşleşme / aynılık bağı | |
| Mention | Değme / bağ adayı | İddiada adı geçen varlık |
| Enrichment | Zenginleştirme | |
| Collector | Toplayıcı | |
| Pivot (eylem) | Çapraz sorgula | Bir değerle başka kaynaklarda arama |
| Pivot (bulunan bağ) | Bağlantı | Bir koşunun bulduğu yeni seçici |
| Supersede | Yerine geçme | |
| Timeline | Zaman çizelgesi | |
| Allowlist | İzin listesi | |
| Hostname | Sunucu adı | |
| Feed | Besleme | RSS beslemesi |
| Metadata | Üst veri | |
| Advisory | Güvenlik bülteni | |
| Defang | Zararsızlaştırılmış yazım | `hxxp`, `1.2.3[.]4` |
| Memory Recall | Hafıza sorgusu | |
| Vault | Kasa (Obsidian kasası) | |
| Workstation | Çalışma istasyonu | |

## Durum adları

| Değer | Arayüzde |
|---|---|
| UNKNOWN / OBSERVED / REPORTED / SUPPORTED | Bilinmiyor / Gözlemlendi / Bildirildi / Destekleniyor |
| CORROBORATED / HIGH_CONFIDENCE / CONTRADICTED | Doğrulandı / Yüksek güven / Çelişkili |
| CRITICAL / HIGH / MEDIUM / LOW / INFO | Kritik / Yüksek / Orta / Düşük / Bilgi |
| Investigation: OPEN / ACTIVE / PAUSED / RESOLVED / CLOSED / ARCHIVED | Açık / Sürüyor / Duraklatıldı / Sonuçlandı / Kapatıldı / Arşivlendi |
| Hypothesis: PROPOSED / SUPPORTED / WEAKENED / REFUTED / UNRESOLVED | Önerildi / Destekleniyor / Zayıfladı / Çürütüldü / Belirsiz |
| Inbox: NEW / IGNORED / CONFIRMED / REJECTED / INVESTIGATING / FOLLOWED | Yeni / Yoksayıldı / Onaylandı / Reddedildi / Araştırılıyor / Takipte |
| SOURCE FACT / SYSTEM INFERENCE / AI ANALYSIS / USER INTERPRETATION | KAYNAK OLGUSU / SİSTEM ÇIKARIMI / YZ ANALİZİ / KULLANICI YORUMU |

## Yan menü grupları

Hiçbir sayfa kaldırılmadı; 20 satır iş akışı sırasına göre gruplandı.

- *(üstte)* Ana Çalışma Alanı, Gelen Kutusu
- **Toplama:** Kaynaklar, Toplayıcılar, Gözlemler, Terfi Kuyruğu
- **Değerlendirme:** Doğrulama, Varlık Adayları, Bağ Adayları, İlişki Adayları, Olası Eşleşmeler
- **Bilgi Grafı:** Varlıklar, Olaylar, Soruşturmalar, Graf
- **Kanıt:** Kanıt Kasası, Kaynak Arşivi
- **Altyapı ve Araçlar:** Seçiciler, Zenginleştirme, Araç Rehberi

## Yazım

Tam imlalı Türkçe: "hâlâ", "hâle", "isteğe bağlı" (opsiyonel değil), "düğme" (buton değil),
"grafta" (graf'ta değil). Eylem düğmeleri eylemi söyler ("İlişkiyi kaldır", "Evet" değil).
