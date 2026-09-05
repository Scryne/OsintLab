---
proje: OsintLab
tarih: 2026-09-06
type: sertlestirme-turu
---
# Frontend Sertleştirme Turu — 2026-09-06

v3'e (Faz 18-20) başlamadan önce yapılan, numaralı bir faz olmayan bir tur. Faz 11'in
dogfooding turuyla aynı türden iş: **yeni özellik yok**, mevcut olanın ölçülüp onarılması.

Roadmap özeti: `docs/Roadmap.md` → "Ara iş: Frontend Sertleştirme Turu".
Tasarım kimliği: kökteki `DESIGN.md`. Kontrast sözleşmesi: `docs/Design.md`.

## Yöntem notu

**Her bulgu ölçüldü, hiçbiri "şöyle görünüyor" diye kaydedilmedi.** Kontrast zemin
kompozitleri hesaplanarak, istek sayıları tarayıcıda sayılarak, lint baseline'ı `git stash`
ile ayrı ayrı ölçülerek. Bunun bir bedeli oldu ve iki kez kendi ilk sonucumu düzeltmek
zorunda kaldım — aşağıda ikisi de yazılı.

## Bulgular

### F1 — Badge metinleri okunamıyordu (7 token)

`text-xs` (12px) metin için WCAG eşiği 4.5:1. Ölçüldüğünde yedi token kalıyordu. **En kötüsü
şuydu: en çok görülmesi gereken iki durum en zor okunanlar arasındaydı** —
`CONTRADICTED` 3.61, `CRITICAL` 4.10. `UNKNOWN` nokta olarak 2.32 ile UI-bileşeni eşiği
3:1'i bile geçmiyordu, yani rampanın en sönük ucu fiilen görünmezdi.

Düzeltme rampanın **anlamını bozmuyor**: ton ve doygunluk sabit, sadece açıklık 4.6'yı
geçecek en az miktarda yükseltildi. Soğuk→sıcak luminans sırası ve `CONTRADICTED`'ın rampa
dışında durması korundu. Zemin/nokta hâli ile metin hâli ayrı tokenlar oldu.

**Kendi ilk ölçümümü düzelttim:** `PriorityBadge`'i düz cam üzerinde ölçmüştüm. Oysa kendi
rengiyle %22 tint'lenmiş bir pill ve metin o tint'in üzerinde duruyor. Yeniden ölçünce beş
durumun **hepsi** kalıyordu (2.91–3.51) ve ilk hesapladığım tonlar yetmiyordu. Tint'i
düşürmek de çözmüyor: %10'a inilse bile ham renkle tavan 4.15.

### F2 — 38 etiket hiçbir kontrole bağlı değildi

74 `<Label>` vardı, 36 `htmlFor`. Ekran okuyucu alanı isimsiz duyuruyor, etikete tıklamak
alana odaklanmıyordu.

**Kök neden `SearchablePicker`'dı:** `id` prop'u almadığı için yanındaki `<Label>`
bağlanamıyordu. Önce o düzeltildi, sonra 38 etiketin tamamı bağlandı → **75/75**.

`lineage-dialog`'daki iki `<Label>` düz başlığa çevrildi: bir listeyi başlıklıyorlardı,
hiçbir zaman bir alana bağlanamazlardı — `<Label>` orada ekran okuyucuya yanlış vaatte
bulunuyordu.

### F3 — Seçim listesi 40 isimsiz buton yığınıydı

`SearchablePicker`'ın seçenekleri düz `<button>`'lardı: `role="listbox"`/`option`/
`aria-selected` yok. Ekran okuyucu 40 kez "button" diyor, hangisinin seçili olduğunu
söylemiyordu — seçim durumu yalnızca arkaplan tonundan belliydi.

### F4 — `ConfirmButton` odağı düşürüyordu ve zaman sınırı vardı

Armed olunca tetikleyici buton DOM'dan kalkıyor, odak `body`'ye düşüyordu; klavye kullanıcısı
sayfanın başına dönüyordu. Değişim de duyurulmuyordu. Ayrıca 3 saniyelik otomatik geri alma
WCAG 2.2.1'i (Timing Adjustable) çiğniyordu — yıkıcı bir onayı 3 saniyeye sığdırmak yavaş
okuyan ya da motor güçlüğü olan bir kullanıcı için kararı fiilen imkânsız kılıyor.

Zaman sınırı kaldırıldı (Escape + dışarı tıklama), odak onay butonuna taşınıyor, vazgeçilince
tetikleyiciye dönüyor, değişim `role="alert"` ile duyuruluyor.

### F5 — 24 dialog'un hiçbirinde açıklama yoktu

`aria-describedby` hiç kurulmuyordu. Her birine ne olacağını söyleyen bir açıklama eklendi
("eski kayıt silinmez, geçerlilik aralığı kapanır" gibi).

### F6 — Tek sayfa açılışında 2336 istek ⚠️ en ciddi

`/observations`'ta bildirilen küçük bir konsol hatasını incelerken çıktı.

`PromoteDialog` **her gözlem satırında** render ediliyor ve içinde 5 `useApi` var; hepsi
mount'ta koşulsuz çekiyordu. 233 gözlem × 5, üstüne dev modunun çift mount'u = **2336
istek**. Tarayıcı `ERR_INSUFFICIENT_RESOURCES` ile bir kısmını düşürüyordu. **Hiçbiri
gerekli değildi — dialogların hepsi kapalı.**

`[open]` bağımlılığı zaten "açılınca tazele" niyetini taşıyordu; eksik olan `useApi`'nin
mount'ta koşulsuz çekmesiydi. Fetcher da aynı koşula bağlandı. Aynı kalıp **15 yerde daha**
vardı. Bu kalıp kod tabanının kendi idiyomu: `evidence-claim-link-dialog` önceden böyle
yapılmıştı.

| Rota | Önce | Sonra |
| --- | --- | --- |
| `/observations` | 2336 | 6 |
| `/observations/queue` | 46 | 6 |
| `/investigations/{id}` | 24 | 18 |
| `/entities/{id}` | 61 | 51 |

Fırtına bu turdan değil — yapı Faz 11'den (`9b3b290`) beri aynıydı, git ile doğrulandı.

### F7 — Base UI konsol hatası

`Button`, `render={<Link/>}` ile `<a>` olarak render ediliyordu ama `nativeButton` varsayılanı
`true`. Aynı kalıp `evidence` sayfasındaki indirme bağlantılarında zaten doğru uygulanmıştı,
`observations` onu kaçırmış.

### F8 — Grep'e görünmeyen dosya

`bulk-promote.tsx` composite key ayracı olarak kaynağa **ham bir NUL byte** koymuş. Ayracın
kendisi doğru (veride geçemez, çakışmasız anahtar verir), ama ham byte git ve ripgrep'e
dosyayı ikili gösteriyor: **bu denetimde iki taramadan sessizce düştü** ve içindeki bir
responsive hata ancak dosya elle okununca çıktı. Ayraç kaçış dizisine çevrildi — çalışma
zamanında birebir aynı karakter, dosya artık düz metin.

*Bu, projenin kendi "sessiz veri kaybı" deseninin bir denetim aracına yansımış hâli:
görünmeyen şey eksik değil, **yok** gibi görünüyor.*

### F9 — İki farklı yükleme dili, çıkmaz boş durumlar, jenerik metinler

Liste sayfaları iskelet, detay sayfaları spinner gösteriyordu. 15 boş durumun hiçbiri
sonraki adımı söylemiyordu. Onay düğmeleri "Evet" diyordu. Hata mesajı "Bir şeyler ters
gitti" + ham `error.message`'dı.

Hepsi düzeltildi: tek yükleme dili, boş durumlar değer→aksiyon, onaylar eylemi tekrar ediyor
("İlişkiyi kaldır"), hatalar ne→neden→nasıl (fetch hatasında artık "Sunucuya ulaşılamadı —
`start.ps1` ile başlat").

### F10 — 5 React derleyici hatası

`use-api.ts` render'da ref yazıyordu; `evidence` türetilebilir bir değeri effect'te state
olarak tutuyordu (etkisi ölçülebilir: iş bitince bir tur daha boşa 1.5 sn yoklama);
`inbox` render'da `Date.now()` çağırıyordu; `investigation-narrative` gereksiz bir senkron
effect'i taşıyordu. Hepsi düzeltildi, **lint 5 → 0**.

## Reddedilen karar

`docs/Design.md` "her Claim/Entity/Event kartının sol kenar rengi doğrudan
`knowledge_state`'ten gelir" diye söz veriyordu ve **hiç uygulanmamıştı**. Uygulandı, canlı
veriyle bakıldı, **geri alındı**.

**Neden:** gerçek dağılım tek renkli. 44 claim'in 29'u REPORTED, 11'i SUPPORTED — bir entity
sayfasındaki kartların neredeyse hepsi aynı kenar rengini alıyor, yani kenar **hiçbir ayrım
üretmiyor**. Badge durumu zaten yazıyla, noktayla ve yüzdeyle söylüyordu; kenar rengin üçüncü
tekrarıydı. Bilgi taşımayan renk dekorasyondur, ve doygun renk şeritleri koyu monokrom bir
arayüzde şablon hissi veriyor.

**Çıkarılan kural** (kökteki `DESIGN.md` "Do's and Don'ts"ta): durum başına renk ancak
**karışık** bir kümede ayırt edicidir. Bu projede confidence rengi nokta/badge/rail
ölçeğinde kalır, yüzey ölçeğine çıkmaz.

**Faz 18-20 grafı çeşitlendirdikten sonra yeniden değerlendirilebilir** — ama o zaman da
önce canlı veriyle bakılarak.

## Kapsam dışı bırakılanlar

- **`/events` liste sayfası ve nav girişi** — Faz 18'in bitti kriteri, v3 işi. Ana sayfadaki
  "Event" kartı bilerek `href`'siz.
- **`/entities/{id}`'deki N+1** — claim başına `/claims/{id}`, 33 istek. Bilinçli bir
  birleştirme: `recall` kısmi şekil veriyor, `/claims/{id}` tamını (F31/F33). Büyük bir
  entity'de sorun olursa bakılacak yer burası.
- **`w-4 h-4` → `size-4`** — 99 kullanım, sıfır görünür fayda, yüksek diff gürültüsü.
- **`fixing-metadata`** — tek kullanıcılı, `localhost`'ta çalışan bir araçta OG etiketi ve
  canonical URL üretmek boş iş.

## Doğrulama

- Derleme temiz, **lint 0** (baseline 5'ti, `git stash` ile ölçüldü).
- Kontrast `globals.css`'ten okunarak yeniden hesaplandı: 12 metin + 7 nokta + accent, hepsi
  eşiği geçiyor.
- Playwright ile 12 rota tarandı: **konsol hatası sıfır**, 375px'te **yatay taşma sıfır**.
- Dialogların hâlâ veri yüklediği ayrıca doğrulandı (promote dialogu açılınca tam 5 istek,
  149 seçenek) — performansı düzeltip işlevi kırmamak için.
