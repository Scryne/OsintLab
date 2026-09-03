---
proje: OsintLab
created: 2026-09-03
type: faz-log
status: aktif
---
# Faz 11 — Dogfooding Sürtünme Günlüğü

Gerçek kullanımda bulunan sürtünme noktaları ve bug'lar. Kritik olanlar bu fazda kapatılır,
kozmetik/nice-to-have olanlar Faz 13'e not edilir.

**Araştırma konusu:** AI/LLM ekosistemi (kullanıcı seçimi, 2026-09-03). Birincil kaynaklar
(openai.com, deepmind.google) + ikincil kaynaklar (techcrunch.com, theverge.com) bilinçli
olarak birlikte seçildi — Faz 6 DERIVED_FROM lineage'ını gerçek veriyle sınamak için.

## Oturum 1 — 2026-09-03: İlk collector taraması

Tarama: `https://openai.com/news/rss.xml`, mode=rss, UI'dan (Toplayıcılar sayfası).
Sonuç: **1164 observation** tek taramada.

### F1 — RSS yayın tarihi sessizce atılıyor  🔴 KRİTİK → ✅ kapatıldı

`collector.py::parse_rss` her item için `published` alanını çıkarıyor (satır 161), ama
`routers/collectors.py::fetch` bunu `create_observation_record`'a geçirmiyor — oysa fonksiyon
`observed_at` parametresini zaten kabul ediyor. `published` üretilip hiçbir yerde
tüketilmiyor (grep: tek eşleşme, üretim satırının kendisi).

Sonuç: 1164 kaydın **3 farklı `observed_at`'i var** (hepsi 15:44:52 ±ms). 2023'ten bir
duyuru da, dünkü duyuru da "bugün gözlendi" görünüyor.

Neden kritik: temporal analiz OSINT'in çekirdeği. Faz 2'nin `Valid: X→Y` supersede mantığı ve
Faz 7'nin "son 30 günde ne değişti" sorgusu gerçek veride anlamsızlaşıyor — tüm arşiv "yeni"
sayılıyor. Laboratuvarda görünmedi çünkü test observation'ları elle, tek tek, o an
oluşturulmuştu.

### F2 — Collector'da limit/zaman penceresi yok  🔴 KRİTİK → ✅ kapatıldı

Feed'in **tüm arşivi** tek seferde sisteme giriyor. OpenAI feed'i 707KB / 1164 item taşıyor
(tipik RSS 10-50 item; bu feed arşivin tamamını yayınlıyor — parser suçsuz, doğru sayıyor).

Neden kritik: Faz 12 (zamanlanmış otomatik tarama) bunun üzerine kurulacak. Şimdi
kapatılmazsa her zamanlanmış çalıştırma arşivin tamamını yeniden dökecek.

### F3 — Observation dedup'ı yok  🔴 KRİTİK → ✅ kapatıldı

`create_observation_record` koşulsuz `CREATE` yapıyor; aynı `source_url` daha önce görülmüş mü
diye bakmıyor. `dedup.py` sadece Entity SAME_AS adayları için — observation'ı kapsamıyor.

Sonuç: aynı feed ikinci kez taranırsa 1164 kopya daha. F2 ile birleşince Faz 12'de her
çalıştırmada tam arşiv tekrarı.

### Düzeltmeler (2026-09-03, aynı oturum)

- **F1:** `collector.py::_entry_published()` eklendi — feedparser'ın `published_parsed`/
  `updated_parsed` struct_time'ı UTC datetime'a çevriliyor, `collectors.py::fetch` bunu
  `create_observation_record(observed_at=...)`'a geçiriyor. Tarihsiz item'lar eskisi gibi
  "şimdi"ye düşer (tarih uydurmak yerine bilinmezliği koruyoruz).
- **F2:** `CollectorFetchRequest`'e `limit` (varsayılan 50, 1-500) ve opsiyonel `since_days`
  eklendi; `_select_items()` en yeniden başlayarak seçiyor. UI'da (Toplayıcılar sayfası) iki
  alan olarak açıldı — RSS modunda görünür. Sonuç kutusu artık "kaynakta N öğe · M
  değerlendirildi · K kopya atlandı" diyor, yani limitin devrede olduğu gizlenmiyor.
- **F3:** `_existing_pairs()` — dedup anahtarı bilerek `(source_url, raw_content)` çifti,
  sadece URL değil. Sadece URL olsaydı Faz 7'nin change detection'ı kırılırdı: aynı sayfa
  DEĞİŞMİŞ içerikle yeniden tarandığında yeni observation oluşması gerekiyor, değişmemişse
  oluşmaması. Aynı fetch içinde tekrar eden item'lar da yakalanıyor.
- **Temizlik:** kullanıcı onayıyla 1164 observation silindi (`DETACH DELETE`, promote edilmiş
  kayıt yoktu, diğer tablolar boştu), `data/daily/2026-09-03.jsonl` de silindi — DB'de
  olmayan kayıt ham log'da kalmasın diye.

### F4 — Allowlist `www.` varyantını görmüyor  🔴 KRİTİK → ✅ kapatıldı

Kullanıcı `theverge.com`'u allowlist'e ekledi, feed ise `www.theverge.com`'da. `collector.py`
düz set üyeliği (`hostname not in allowlist`) yaptığı için tarama reddedildi — **doğru siteyi
eklemiş olmasına rağmen**. Hata mesajı da yol göstermiyordu ("allowlist'te değil", ama
"`theverge.com` var, www varyantını da ekle" demiyordu).

Düzeltme: `_host_allowed()` — yalnızca tam `www.` prefix'i, iki yönlü. Kapsam bilerek dar:
genel subdomain wildcard'ı (`*.example.com`) DEĞİL, çünkü o allowlist'in amacını zayıflatır
ve alt alan devralma riskini içeri alır; `www` ise alan sahibinin kanonik host'unun kendisi.
Doğrulandı: `www.theverge.com`→izin, `theverge.com`→izin, `evil.theverge.com`→red,
`theverge.com.evil.net`→red.

### F5 — API hataları ekrana ham JSON olarak basılıyor  🟠 → ✅ kapatıldı

Kullanıcı allowlist reddinde ekranda şunu gördü: `{"detail":"Reddedildi: 'www.theverge.com'
allowlist'te değil"}`. `api.ts::request()` `res.text()`'i doğrudan hata mesajı yapıyordu.
**Collectors'a özel değil — tüm uygulamada her hata böyle görünüyordu.**

Düzeltme: `errorMessage()` FastAPI'nin `detail` alanını çıkarıyor; doğrulama hatalarında
(`detail` bir liste) alan adı + mesaj olarak birleştiriyor; JSON değilse ham metne düşüyor.

### F6 — Allowlist'e tam URL yapıştırma  🟡 önlem (kullanıcı yaşamadı)

F4'ü düzeltirken görüldü: allowlist alanına `https://www.theverge.com/rss/...` yapıştırılırsa
o dizi hostname olarak kaydedilir ve hiçbir zaman eşleşmez — sebebi de ekranda görünmez.
`normalize_hostname()` eklendi (URL→hostname, küçük harf, port/kullanıcı/sondaki nokta
temizliği), `POST /collectors/allowlist` bundan geçiyor. Spekülatif değil ama kullanıcı
tökezlemeden önce kapatıldı; bulgu değil, önlem olarak işaretli.

### F8 — Tür alanları UI'da kilitli, backend'de serbest  🔴 KRİTİK → ✅ kapatıldı

Kullanıcı "Astra" entity'sine `AI Model` türünü **giremedi** — form sabit bir `<Select>`
açıyordu. Backend'de `entity_type` serbest string; `models.py`'deki `examples=[...]` bir
ÖNERİ listesiydi, frontend onu KURAL sanmıştı.

Sistemik: aynı hata **üç formda** vardı — `entities/page.tsx` (Person/Organization/Company/
Location), `sources/page.tsx` (3 tür), `evidence-link-dialog.tsx` (4 tür). Bir OSINT
sisteminde entity türü dört değere kilitlenemez (Vessel, Domain, Malware, Wallet...).

Kritik olma sebebi sadece engel değil, **sessizce yanlış veri**: kullanıcı devam etmek için
Astra'yı `Organization` ya da `Company` seçmek zorunda kalırdı ve graf kalıcı olarak
yanlışlanırdı — üstelik hiçbir hata görünmeden.

Düzeltme: ortak `components/forms/type-combo.tsx` — serbest metin + öneri (native
`<datalist>`). Öneriler sabit çekirdek listeye ek olarak **sistemde zaten kullanılan
türlerden** besleniyor, böylece esneklik tutarlılığı bozmuyor. Üç form da buna geçirildi.

Önemli ayrım korundu: gerçek kısıtı olan alanlar `<Select>` olarak BIRAKILDI — Evidence
`stance` (SUPPORTS/CONTRADICTS) ve `Monitor.target_type` (backend'de `MONITOR_TARGET_TYPES`
tuple'ıyla zorlanır). Kural olan kilitli, öneri olan serbest.

## Oturum 1 (devam) — Promote akışı ve kapatma

### F10 — Gözlemler sayfasında metin araması yok  🔴 → ✅ kapatıldı

Tek tarama 80 gözlem üretti; içinden 4 tanesini bulmak elle kaydırmaya kalıyordu. Sekmeler
(Tümü/Bekliyor/Promote edildi) sayıyı azaltmıyor. `useMemo` ile metin+URL araması eklendi,
sağda `eşleşen / toplam` sayacı var.

### F12 — Yayın tarihi Claim'e taşınmıyor (F1'in kardeşi)  🔴 KRİTİK → ✅ kapatıldı

F1'i Observation katmanında düzelttik ama zincir bir adım sonra kopuyordu: `claims.py`
`valid_from: $now` yazıyordu, promote ise observation'ın `observed_at`'ini geçirmiyordu. Dört
claim'in de `valid_from`'u "bugün" çıktı, oysa gözlemler 09-01/09-02 tarihliydi.

Asıl zarar burada: Faz 2'nin temporal supersede mantığı `valid_from`/`valid_to` üzerinde
çalışıyor. Arşivden gelen 08-10 tarihli bir duyuru, 09-02 tarihli bir güncellemeden SONRA
girilmiş görünür ve yanlış claim'i supersede ederdi.

Düzeltme: `ClaimCreate.valid_from` (opsiyonel) eklendi; `create_claim` artık `created_at`
(kayıt anı, değişmez) ile `valid_from`'u (iddianın geçerlilik başlangıcı) ayırıyor; promote
gözlemin `observed_at`'ini geçiriyor. Mevcut 4 claim backfill ile onarıldı — doğrulandı:
`valid_from` 09-01/09-02, `created_at` 09-03.

**Ders:** bir alanı bir katmanda düzeltmek yetmiyor; veri zincirinin tamamı izlenmeli.

### F13 — RSS metnindeki HTML entity/etiketleri temizlenmiyor  🟠 → ✅ kapatıldı

Verge'in özeti sisteme `OpenAI&#8217;s Astra release ... [&#8230;]` olarak girdi ve bu metin
`Claim.text`'e aynen kopyalandığı için kirlilik graf'ın kalıcı katmanına sızıyordu.
`_clean_feed_text()` eklendi (BeautifulSoup `get_text` — etiketi ayıklar, entity'yi çözer).

Backfill'de yalnızca `Claim.text` temizlendi (türetilmiş alan); `Observation.raw_content`
HAM kayıt olduğu için kaynaktan geldiği gibi bırakıldı.

**Yan etki (bilinçli kabul):** aynı feed yeniden taranırsa temizlenmiş metin farklı bir dedup
anahtarı üretir, yani o 80 gözlem için kopya oluşabilir. F21 (web modu çıkarımı) aynı etkiyi
büyüttü — mevcut 81 gözlemin tamamı artık "eski çıkarım" ile kayıtlı. **Faz 12'ye (zamanlanmış
tarama) geçmeden önce gözlem tabanını bir kez sıfırlamak gerekiyor**; aksi halde ilk otomatik
tarama her kaydın kopyasını üretir.

### F14 — `start.ps1 -Stop` öksüz process bırakıyor, KùzuDB kilidi düşmüyor  🔴 KRİTİK → ✅ kapatıldı

`-Reload` ile başlatılan uvicorn iki process açıyor (izleyici + işçi). `-Stop` yalnızca portu
DİNLEYENİ öldürdüğü için işçi hayatta kalıyor ve KùzuDB lock'unu tutmaya devam ediyordu:
`Could not set lock on file`. Port boş göründüğü için bir sonraki başlatma "temiz" sanılıyor,
sonra backend veritabanına bağlanamıyor. Aynı sorun `node` tarafında da varmış.

İncelik: ebeveyn önce öldürülürse çocuk process ağacında **görünmez olur**. Bu yüzden
`Get-DescendantIds` çocukları ÖNCE topluyor, sonra öldürme yapılıyor. Ayrıca son bir güvenlik
ağı olarak komut satırında proje kökü geçen artakalan python/node process'leri taranıyor
(ebeveyni ölmüş bir öksüz ağaç yürüyüşüyle bulunamaz).

Doğrulandı: `-Stop` → "alt process ... durduruldu" ×2, artakalan yok, DB kilidi serbest.

### F15 — Promote'ta "İlgili" alanı sessizce atlanabiliyor  🔴 KRİTİK → ✅ kapatıldı

Promote dialog'unda `aboutType` varsayılanı `"none"` ve etiket "İlgili (opsiyonel)"di. Dört
claim de bu yüzden hiçbir entity'ye bağlanmadan oluştu. Atlanınca **hiçbir uyarı yok**, ama:

- `entity_recall()` claim'i bulamıyor → Faz 4 Memory Recall fiilen çalışmıyor
- `why_matters` bağlam üretemiyor → LOW_SIGNAL'e düşüyor (PRIOR_KNOWLEDGE_EXISTS tetiklenmiyor)
- entity sayfasında ve Obsidian vault notunda claim görünmüyor

Yani sistemin en değerli katmanı, tek bir varsayılan yüzünden sessizce kapanıyordu.

Düzeltme: varsayılan `"entity"`, etiket "İlgili entity/event", ve bağ kurulmamışken görünür
bir uyarı ("Bağlanmazsa bu claim yalıtık kalır…").

### F16 — Claim oluştuktan sonra entity/event bağı kurulamıyor  🔴 KRİTİK → ✅ kapatıldı

F15'in yarattığı hasarı onarmanın **hiçbir yolu yoktu**: `claims.py`'de PATCH/PUT/DELETE ucu
yok, promote ise idempotent olduğu için ikinci denemede 409 veriyor. Bir kez atlanan bağ
kalıcıydı.

Düzeltme: `PATCH /claims/{claim_id}/about` + `ClaimLinkDialog` (entity sayfasında "Mevcut
claim'i bağla"). Bağlantısız claim'ler listenin başında gösteriliyor.

History Is Immutable ile çelişmiyor: claim'in METNİ (kaynağın iddiası) değişmiyor, yalnızca
sınıflandırması düzeltiliyor. Bir claim aynı anda hem entity hem event hakkında olamaz (422).

### F17 — `about_entity_id` yazılabiliyor ama okunamıyor  🟠 → ✅ kapatıldı

`ClaimCreate` bu alanları kabul ediyor, `_claim_about()` helper'ı zaten okuyor, ama `Claim`
yanıt modelinde bu alanlar **yoktu** — ne listede ne tekil çağrıda. Arayüz "bu claim bir
entity'ye bağlı mı" sorusunu cevaplayamıyordu (F16'nın UI'ı bu ayrıma muhtaç).

Teşhis açısından da tehlikeliydi: `claim.get("about_entity_id")` çağrısı `None` döndürüyordu
ve bu "bağ yok" gibi okunuyordu, oysa gerçek anlamı "alan hiç döndürülmüyor"du. İki farklı
durum aynı görünüyordu.

Düzeltme: `Claim` modeline `about_entity_id`/`about_event_id` eklendi, `_row_to_claim()`
dolduruyor. (Bağın gerçekten kurulmadığı `entity_recall`'un boş dönmesiyle ayrıca doğrulandı.)

### F18 — Promote vault render'ı tetiklemiyor  🔴 KRİTİK → ✅ kapatıldı

`safe_render_vault(conn)` her yazma ucunda çağrılıyor (entities 8×, investigations 7×,
events 4×, sources 3×, claims 1×) ama **observations.py'de hiç yoktu**. Promote bir Claim
üretiyor, vault ise güncellenmiyordu: Obsidian'da Astra notu 4 claim bağlıyken bile "Bu entity
hakkında henüz claim yok" diyordu.

Gerçek kullanımda bulunmasının sebebi bu: Obsidian'ı açıp bakmadan görünmez bir hata.
Kullanıcı vault'a bakıp "sistem çalışmıyor" sonucuna varabilirdi, oysa graf doğruydu — sadece
render bayattı. **Bayat veri, eksik veriden daha tehlikeli: ikisi de aynı görünüyor.**

Düzeltme: `promote_observation` ve yeni eklenen `update_claim_about` artık render tetikliyor.

### F19 — Vault'ta claim render'ı Markdown listesini kırıyor  🟠 → ✅ kapatıldı

Claim metni çok satırlıdır (RSS başlığı + özet). `vault.py` bunu doğrudan `- {text}` olarak
basıyordu; metnin içindeki boş satır Markdown listesini kırıyor, Obsidian'da ikinci paragraf
listenin dışına düşüyordu — üç ayrı render noktasında (entity, event, investigation notları).

Düzeltme: ortak `claim_bullet()` — ilk satır kalın başlık · güven etiketi · kaynak wikilink'i,
kalanı girintili devam satırı. Üç çağrı yeri de buna geçirildi.

## Oturum 1 eki — `web` modunun ilk testi (2026-09-03)

Kullanıcının bir arkadaşı `kayisu.github.io` adresini denemeyi önerdi. Araştırma konusuyla
(AI/LLM ekosistemi) ilgisi yok — kişisel bir portfolyo sayfası — ama **collector'un `web`
modu Faz 11 boyunca hiç çalıştırılmamıştı**: sekiz tarama yapıldı, hepsi RSS. Kodun test
edilmemiş yarısı buydu. Observation olarak alındı, bilinçli olarak promote EDİLMEDİ (Astra
grafını kirletmemek için).

Güvenlik ön kontrolü (Q22): injection deneme yok, gizli/görünmez element yok, form/iframe
yok. Temiz.

### F21 — `web` modu sayfa iskeletini içerik sanıyor  🟠 → ✅ kapatıldı

`extract_text_from_html` tüm gövdeyi düz metne çeviriyordu; sonuç 137 satırın **74'ü tekrar**:
`→` 13 kez, "Opens in a new tab" 7 kez, menü öğeleri 3-5 kez, "Skip to main content", tema
seçici ("System/Light/Dark")...

Sadece okunabilirlik sorunu değil: Faz 7 change detection içeriği karşılaştırdığı için, site
**menüsünü** değiştirdiğinde tüm sayfa "değişmiş" sayılıp yanlış alarm üretirdi. Dedup
anahtarı da (`source_url`, `raw_content`) aynı sebeple kırılırdı.

Düzeltme: semantic HTML'e güven — `<main>`/`<article>` varsa onu al, yoksa gövdeden
nav/header/footer/aside çıkar. Daraltma içeriğin neredeyse tamamını yerse (JS ile dolan bir
kabuk olabilir) ham gövdeye dönen bir güvenlik ağı var.

Doğrulandı: 2723→2329 karakter, ilk satır "Skip to main content" yerine "Personal portfolio",
"Theme" ve "Skip to main content" 0 kez.

### F22 — JS ile render edilen içerik sessizce eksik geliyor  🟡 Faz 13

Aynı sayfada çıktının içinde `Loading the solar system…` kaldı: sayfanın asıl gövdesi
JavaScript ile geliyor, collector ise statik HTML alıyor (requests + BeautifulSoup, tarayıcı
yok). Bu beklenen bir mimari sınırlama, **ama hiçbir yerde yazmıyor ve kullanıcıya
bildirilmiyor** — "sayfayı taradım" denilirken içeriğin bir kısmı hiç gelmemiş oluyor.

Faz 13 önerisi: fetch yanıtında bir uyarı bayrağı (ör. `<noscript>` içeriği, "loading"/"enable
javascript" kalıpları, ya da script-ağırlıklı + metin-fakir sayfa oranı) ve UI'da görünür not.
Tam çözüm (headless tarayıcı) v1 kapsamı dışında.

## Oturum 1 kapanışı — lineage denemesi (Faz 13'ten öne çekilen dilim)

Astra vakasının en öğretici yarısı eksik kalmıştı: sistem "dört kaynak var" diyebiliyor ama
"üçü aynı kaynaktan besleniyor" diyemiyordu. F11 (lineage UI'a bağlı değil) Faz 13 kapsamında
olsa da, kalan dört oturumun her birinde aynı duvara toslanacağı için en küçük dilim öne
çekildi (start.ps1'in Faz 14'ten öne çekilmesiyle aynı gerekçe).

Sonuç beklenenden farklı çıktı: vaka kapatılamadı, ama projenin **iki çekirdek varsayımının
sınırı** bulundu. Bunlar bug değil — doğrulanmamış varsayımlar.

### F23 — Otomatik lineage tespiti gerçek veride çalışmıyor  🔴 → 📋 Faz 13 (kısmen kapatıldı)

Astra vakasının dört claim çiftinde de `detect_derivation` **similarity = 0.0000** verdi.

Sebep tek değil, iki sorun üst üste binmiş:
1. **Yayıncılık kültürü farkı.** `lineage.py` dokstring'i Faz 6 spike'ının Türk haber
   siteleriyle doğrulandığını yazıyor (`aa.com.tr → ensondakika.com.tr` 0.44,
   `karsmanset → yildirimgazetesi → marmarisyenisayfa` 0.56-0.60). O ekosistemde ajans metni
   BİREBİR kopyalanır. TechCrunch/The Verge ise aynı olayı kendi cümleleriyle yazıyor —
   ortak 5-kelimelik dizi yok.
2. **RSS özetleri çok kısa.** Claim metni ~30-40 kelime; `SHINGLE_SIZE=5` ile bu ~30 shingle
   demek. Yöntem tam makale gövdesi varsayıyor, collector RSS modunda başlık+özet topluyor.

Faz 6 "en az 3 türetilmiş kaynak örneğinde çalışıyor" kriteriyle kapatılmıştı ve o kriter
gerçekten sağlanmıştı — ama test kümesinin tamamı tek bir yayıncılık kültüründen geliyordu.

**Bu fazda kapatılan kısım:** kararı insana veren yol açıldı (aşağıda). **Faz 13'e kalan:**
tespit yönteminin iyileştirilmesi (entity/olay örtüşmesi + zaman yakınlığı + "OpenAI said" /
"according to" atıf kalıpları). Salt n-gram benzerliği yeterli değil.

### F23b — Manuel lineage kurma yolu yoktu  🔴 → ✅ kapatıldı

Otomatik tespit başarısız olduğunda insanın kararını graf'a yazmasının hiçbir yolu yoktu:
`sources.py`'de yalnızca `POST /lineage/detect` (otomatik) vardı. Oysa Design Principle #7
(Human Remains In Control) gereği son karar zaten insanda olmalı.

Eklendi: `POST /sources/{id}/derived-from` + `DELETE /sources/{id}/derived-from/{upstream}`
(F16'nın dersi: düzeltilemeyen veri kötü veridir) + `LineageDialog` (Kaynaklar sayfası).
Elle kurulan bağ `method='MANUAL'` olarak işaretleniyor — kararı sistemin mi insanın mı
verdiği graf'ta ayırt edilebilir kalmalı (Auditability). Döngü koruması ve kendine-bağlama
koruması var; bağ kurulunca etkilenen claim'lerin confidence'ı yeniden hesaplanıyor.

### F24 — Lineage yanlış seviyede modellenmiş  🔴 KRİTİK → 📋 Faz 13 (şema kararı)

**Astra vakasının lineage'ı bilinçli olarak KURULMADI** — kurmak, çözmeye çalıştığımız
sorundan daha büyük bir sorun yaratırdı.

`DERIVED_FROM` ilişkisi Source→Source. Ama türetme gerçekte **haber (claim) seviyesinde**
oluyor. `confidence.py`'de `independence`, corroborating kaynakları
`resolve_independent_root()` ile indirgiyor — yani kaynak seviyesinde ve KALICI olarak.

Somut sonuç: "TechCrunch → OpenAI" bağı kurulsaydı, sistem TechCrunch'ın OpenAI hakkındaki
*her* claim'ini OpenAI kökenli sayardı. Astra haberi için doğru, TechCrunch'ın
Nvidia–Hugging Face haberi için tamamen yanlış — ve sessizce yanlış.

Faz 6'nın test kümesinde bu görünemezdi: `ensondakika.com.tr` gibi siteler *sürekli* ajanstan
kopyalar, orada kaynak seviyesi doğru soyutlama. TechCrunch bağımsız bir yayın organı, yalnızca
bu haberde aktarıcı. Yani sorun "kaynak seviyesi yanlış" değil — **tek bir seviye yetmiyor.**

Faz 13 önerisi: `Claim -[:DERIVED_FROM]-> Claim` ekle, kaynak seviyesini (sürekli aktaran
siteler için) koru. `independence` hesabı önce claim seviyesine, yoksa kaynak seviyesine
baksın. Şema değişikliği gerektirdiği için Faz 11'de yapılmadı.

## Oturum 2 — 2026-09-03: Siber güvenlik / tehdit aktörü ekosistemi

Konu seçimi (kullanıcı "sen karar ver" dedi): bu alan Faz 11'de henüz hiç zorlanmamış üç
şeyi aynı anda zorluyor — atıf tartışmaları doğal olarak **çelişen claim** üretir (Faz 2
contradiction motoru gerçek veriyle hiç tetiklenmedi), tehdit aktörlerinin çok isimli olması
**SAME_AS** merge'ini (Faz 10'da eklendi, hiç kullanılmadı) zorunlu kılar, ve güvenlik haber
siteleri CISA advisory'lerini bloklar halinde kopyaladığı için **F23'ün lineage sorunu ikinci
kez, bu sefer gerçekten kopyalayan veriyle** sınanabilir.

Kaynak seti bilinçli olarak 1 otorite + 3 aktaran: cisa.gov (birincil), bleepingcomputer.com,
securityaffairs.com, krebsonsecurity.com.

### F25 — HTTP hata yanıtı sessizce "içerik" sanılıyor  🔴 KRİTİK → ✅ kapatıldı

**Semptom (gerçek kullanım):** kullanıcı UI'dan `https://www.cisa.gov/cybersecurity-
advisories/all.xml` taradı, ekranda **"0 gözlem oluşturuldu · Kaynakta 0 öğe"** çıktı.

**Gerçek sebep:** cisa.gov (Akamai arkasında) isteği **403 Access Denied** ile reddediyordu.
`safe_fetch` (`collector.py`) `raise_for_status()` çağırmadığı için 403'ün 410 byte'lık HTML
gövdesi "içerik" olarak dönüyor, `parse_rss` onda haklı olarak 0 item buluyor, arayüz de
bunu boş bir feed gibi gösteriyordu. **"Site seni engelledi" ile "kaynakta yeni haber yok"
tamamen ayırt edilemez hale gelmişti.**

`web` modunda sonuç daha ağır olurdu: hata sayfası kalıcı bir Observation olarak graf'a
girer, üstelik Faz 7 change detection engelleme kalktığında "içerik değişti" diye yanlış
alarm üretirdi.

**Neden 403 alıyorduk (ve neden UA suçlu değil):** ilk ölçüm yanıltıcıydı — başarısız denemeler
önce, başarılılar sonra geldiği için "geçici blok" ihtimali vardı. Sıra ters çevrilip 3 kez
tekrarlandı, sonuç deterministik çıktı:

| İstek | Sonuç |
| --- | --- |
| Sadece `User-Agent: OsintLab-Collector/0.1` | **403** (3/3) |
| Aynı UA + `Accept-Language` | **200** (391 KB, 30 item) |
| `requests` varsayılan header'ları (UA: `python-requests/2.32.3`) | **200** |

Yani engelleyen bizim kimliğimiz değil — `python-requests` UA'sı bile geçiyor. Engelleyen,
isteğin **yarım** görünmesi. Düzeltme UA'yı gizlemiyor (hâlâ kendimizi söylüyoruz), sadece
sıradan `Accept` / `Accept-Language` header'larını ekliyor.

**Düzeltme (iki katman):**
1. `collector.py`: `DEFAULT_HEADERS` (UA + Accept + Accept-Language) ve yeni bir
   `CollectorFetchError`. 4xx/5xx artık içerik olarak dönmüyor, durum koduna göre **ayrı
   teşhis** veriyor — "engellendin" (401/403/429), "böyle bir adres yok" (404), "sunucu
   arızalı" (5xx) kullanıcı için farklı eylemler gerektirdiği için tek cümleye toplanmadı.
2. `routers/collectors.py`: `CollectorSecurityError` → **403** (BİZ reddettik: allowlist/SSRF,
   kullanıcının düzeltebileceği yapılandırma), `CollectorFetchError` → **502** (KARŞI TARAF
   reddetti). Ayrıca ikinci savunma: rss modunda 200 dönüp içerik XML değilse ve 0 item
   ayrıştırılmışsa, bu "boş feed" değil "yanlış içerik"tir — ayrı bir 502 mesajıyla söyleniyor
   ("bu bir sayfaysa `web` modunu dene").

**Doğrulama:**

| Vaka | Önce | Sonra |
| --- | --- | --- |
| cisa.gov feed | 0 item (sessiz) | **30 item** |
| bleepingcomputer.com | 15 item | 15 item (regresyon yok) |
| securityaffairs.com | 10 item | 10 item |
| krebsonsecurity.com | 10 item | 10 item |
| cisa.gov 404 adres | 0 item (sessiz) | **502** "böyle bir adres yok — feed adresini kontrol et" |
| allowlist dışı host | 403 | 403 (değişmedi) |

**Neden birim testiyle yakalanamazdı:** test sunucusu 200 döndürür. Bu hata yalnızca gerçek
bir kaynak seni gerçekten engellediğinde ortaya çıkıyor — ve tam da o an sessiz kalıyordu.
Oturum 1'in ortak desenini birebir tekrarlıyor: kod "yanlış çalışmıyor", sistem kendini
anlatamıyor.

### F26 — Çelişki motoru toplanan veri boru hattından erişilemiyor  🔴 KRİTİK → ✅ kapatıldı

**Nasıl bulundu:** Oturum 2'nin verisinde Oturum 1'in Astra vakası devam ediyordu
(securityaffairs 2026-09-02: "OpenAI Astra Brings Autonomous Zero-Day Exploitation to AI").
Graf'taki 4 Astra claim'i zıt çerçevelemeler taşıyor ama **hiçbiri çelişkili işaretli değil**,
hepsi `REPORTED`. Faz 2'nin bitti kriteri "çelişen ikinci claim eklendiğinde Contradiction
objesi oluşuyor" diyordu — neden hiç oluşmamıştı?

**Tespit — üç katmanlı bir boşluk:**

1. Çelişki **otomatik tespit edilmiyor**; kullanıcının `POST /claims` gövdesinde
   `contradicts` alanıyla beyan etmesi gerekiyor. (Design Principle #7 açısından doğru bir
   tercih — kritik kararı insan verir — ama Roadmap'te Faz 2 kriteri "otomatik" diyordu.
   Kriter metni gerçeği yansıtmıyordu; aşağıda düzeltildi.)
2. `ObservationPromote` modelinde `contradicts`/`supersedes` alanları **yoktu**. `create_claim`
   ikisini de destekliyordu, promote geçirmiyordu. Promote ise toplanan veriden Claim'e giden
   **tek** yol.
3. Sonradan kurmanın **hiçbir yolu yoktu**: `CLAIM_CONTRADICTS` yalnızca claim oluşturulma
   anında yazılıyor, claims router'ında başka bir uç yok.

Üçü birleşince: collector'dan gelen bir claim asla çelişkili işaretlenemez. Yani
`confidence.py`'deki `has_unresolved_contradiction` dalı ve `CONTRADICTED` knowledge_state,
gerçek boru hattı için **ölü kod**. Frontend'de de asimetri vardı — `claim-form.tsx`
(Entity sayfasından "Yeni Claim") üç alanı da sunuyordu, promote diyaloğu yalnızca
`corroborates`'i.

**Neden bu F15/F16'nın kardeşi:** aynı desen üçüncü kez çıktı — *bir yetenek şemada ve
formülde var, ama gerçek kullanımın geçtiği yoldan erişilemiyor.* (v1 denetiminde
`Evidence -[:CONTRADICTS]-> Claim` aynı şekilde hiç yaratılamıyordu; Faz 10 onu açtı, bu
onun Claim↔Claim karşılığı.) Ayrıca gerçek araştırma sırası bunu zorunlu kılıyor: **çelişen
ikinci haber, ilk claim kaydedildikten günler sonra çıkıyor** — oluşturma anında beyan
etmeyi şart koşan bir tasarım, gerçek zaman akışıyla uyumsuz.

**Düzeltme:**
- `models.py`: `ObservationPromote`'a `contradicts` + `supersedes`; yeni `ClaimContradictionAdd`.
- `routers/observations.py`: promote ikisini `create_claim`'e geçiriyor.
- `routers/claims.py`: yeni `POST /claims/{id}/contradicts`. Çelişki simetrik ama graf'ta
  **tek yön** yazılıyor — okuma tarafı (`_gather_confidence_inputs`) zaten hem gelen hem
  giden kenara bakıyor, iki yön yazmak çift sayıma yol açardı. İki claim de yeniden
  hesaplanıp ikisi için de bildirim üretiliyor; tek taraflı bırakmak grafı tutarsız yapardı.
- Frontend: promote diyaloğuna "Çeliştiği claim'ler" + "Yerini aldığı claim" alanları
  (sonucu açıklayan yardım metinleriyle), ve Entity sayfasına `ClaimContradictDialog`
  ("Çelişki kur"). Backend'de bırakmak F23b'nin dersini tekrarlamak olurdu: yol var ama
  UI'a bağlı değil.

**Doğrulama:** `ObservationPromote` şeması artık 8 alan döndürüyor (`contradicts`,
`supersedes` dahil); `POST /claims/{id}/contradicts` → kendisiyle çelişki **422**, olmayan
claim **404**, var olan çelişkiyi tekrar kurma **409**. `tsc --noEmit` temiz.

**Sınır (kasıtlı):** *sonradan supersede* eklenmedi — supersede eski claim'in `valid_to`
alanını yazdığı için zaman çizgisini geriye dönük değiştirir ve doğru "hangi an" kararı
(haberin yayın tarihi mi, düzeltmenin tarihi mi) tek başına bir modelleme sorusu. Promote
sırasında artık yapılabiliyor; sonradan yapmak Faz 13'e.

### F27 — "Bir çelişki var" deniyor, "neyle" hiçbir yerden öğrenilemiyor  🟠 → ✅ kapatıldı

**Nasıl bulundu:** F26 kapatıldıktan sonra ilk gerçek çelişki UI'dan kuruldu (Astra: OpenAI'ın
kendi duyurusu ↔ "Researchers fear safety disaster"). Graf doğru davrandı — ikisi de
`CONTRADICTED`, üçüncü Astra claim'i dokunulmadan `REPORTED` kaldı. Ama çıktıyı denetlerken
iki şey göze çarptı; **biri bug değildi, biri bug'dı.**

**Bug olmayan (kayda geçiyor ki tekrar sorgulanmasın):** çelişki kurulunca sayısal confidence
hiç değişmedi (0.3 ve 0.28 aynı kaldı). Bu kasıtlı: `confidence.py` başında yazıyor —
claim↔claim çelişkisi sayıyı düşürmez, yalnızca `knowledge_state`'i `CONTRADICTED`'a zorlar
(Q3 hibrit model: sayı ile durum etiketi ayrı tutulur). Sayıyı cezalandıran şey *kanıt*
tabanlı çelişki (`contradicting_evidence_count`), claim tabanlı değil.

**Asıl bulgu:** `why-matters`'ın `CONTRADICTED` gerekçesinde `detail` **boştu** (`{}`), oysa
kardeş gerekçe `PRIOR_KNOWLEDGE_EXISTS` `prior_claim_ids`'i dolduruyordu. `GET /claims/{id}`
çelişki alanı döndürmüyor, entity recall'ın `related_claims`'i de döndürmüyor. Yani sistem
"bu bilgi başka bir claim ile çelişiyor" diyor ve **hangi claim olduğunu hiçbir uçtan
söyleyemiyor** — halbuki araştırmadaki asıl soru tam olarak o: *"OpenAI böyle diyor, peki
aksini kim söylüyor?"*

F26'nın açtığı yeteneği yarım bırakıyordu: çelişki kurulabiliyor ama okunamıyor.

**Düzeltme:** `recall.py`, `CLAIM_CONTRADICTS`'i iki yönde de tarayıp (ilişki tek yön saklanır,
anlamı simetrik) `detail`'e `contradicting_claim_ids` + `contradicting_claims` (id + alıntı)
yazıyor. **Gerekçe metninin kendisi de karşı tarafı adlandırıyor** — çünkü arayüz `detail`'i
hiçbir yerde göstermiyordu, yalnızca `reason.text`'i basıyordu; sadece detail'i doldurmak
gerekçeyi görünür yapmazdı. Frontend'de `WhyMattersDisclosure` çelişen claim'leri madde
madde listeliyor.

**Link vermedim, bilerek:** tek bir claim'in detay sayfası (`/claims/[id]`) yok — link kırık
olurdu, yani F20'nin (Dashboard'un henüz oluşmamış nota link vermesi) aynısını yapardım.
Bkz. F28.

**Vault ayağı (aynı bulgunun ikinci yeri):** `vault.py` ayrı bir renderer ve aynı eksiği
taşıyordu — entity notunda iki claim `[ÇELİŞKİLİ]` etiketliydi ama neyle çeliştikleri
yazmıyordu. Living Brain'in (Faz 9) tek işi okunabilir olmak; "çelişkili" tek başına
okunabilir değil. `_claim_contradictions()` eklendi, çelişen claim alt madde olarak
yazılıyor (`⚔ Çelişiyor: «...»`), iki yönde de doğrulandı.

**Doğrulama (API):** her iki yönden de sorulduğunda karşı tarafı adlandırıyor —
`498d07bc` → «Researchers fear safety disaster ahead of OpenAI's Astra release»,
`ee1dbe53` → «Path to Astra: critical capabilities and frontier safeguards».

**Süreç notu (kendi hatam):** düzeltmeyi yazarken `split("
")` kaçışı dosyaya gerçek satır
sonu olarak düştü, backend açılmadı (`SyntaxError: unterminated string literal`). `start.ps1`
bunu doğru raporladı ("Backend 45 sn icinde yanit vermedi"), sessiz kalmadı — F14'ün
düzeltmesinin yan faydası. `splitlines()` ile onarıldı.

### F29 — Entity birleştirmenin elle yolu yok, otomatik tespit bu alanda yapısal olarak çalışmıyor  🔴 KRİTİK → ✅ kapatıldı

**Nasıl bulundu:** SAME_AS (Faz 10'da eklendi, hiç kullanılmamıştı) gerçek bir vakayla
sınandı. SecurityAffairs aynı aktörü iki haberde dört isimle veriyor: *"Chaotic Eclipse, also
known as INFINITE NIGHTMARE, MSNightmare and Nightmare-Eclipse"*. İki entity oluşturuldu ve
kullanıcıdan birleştirme yolunu bulması istendi — **bulamadı.**

**Tespit:** yol aslında vardı (entity sayfasında "Olası Eşleşmeler" sekmesi + sol menüde aynı
adlı sayfa) ama **boş görünüyordu**: `GET /entities/{id}/same-as/candidates` boş liste
döndürüyordu. UI'da SAME_AS önermenin **tek yolu** otomatik tespit edilmiş bir adaya "Öner"
demekti; aday yoksa hiçbir çıkış yolu yoktu. Boş durum mesajı bile ("isim/alias benzerliğine
göre otomatik hesaplanır") çıkışsızlığı doğruluyordu.

**Neden aday çıkmadı — ve neden bu düzeltilebilir bir eşik meselesi değil:** `dedup.py`
skoru `name + aliases` token kümeleri üzerinden `containment_similarity` ile hesaplıyor.
"Chaotic Eclipse" ile "INFINITE NIGHTMARE" arasında **ortak token yok**, skor 0. Bu, tehdit
aktörü alanında yapısal bir sınır: farklı firmalar aynı gruba bilinçli olarak birbiriyle
alakasız isimler verir (APT28 = Fancy Bear = Sofacy = Sednit = STRONTIUM). Bilgi isimlerde
değil, **metinde** ("also known as...") yaşıyor. Eşiği düşürmek çözmez, yanlış eşleşme üretir.

F23'ün lineage'da öğrettiği dersin aynısı, entity tarafında: *otomatik tespit gerçek veride
tutmayabilir; sistemin bunu kabul edip kararı insana verebilen bir yolu olmalı.* Çözüm de
F23b'nin aynısı.

**Düzeltme:** `SameAsManualDialog` — herhangi iki entity için elle SAME_AS önerme yolu.
Q7 korunuyor: uç yalnızca **PENDING** öneri yaratır (`suggest_same_as` skor ne olursa olsun
asla CONFIRMED yazmaz), birleştirmeyi yine insan onaylar. Boş durum metni de artık çıkışsız
bırakmıyor, bu yolu gösteriyor.

### F30 — `aliases` API'de var, arayüzde hiç yok — tespitin alias yarısı ölü koddu  🔴 KRİTİK → ✅ kapatıldı

F29'u incelerken çıktı. `aliases` şemada (`STRING[]`), `EntityCreate`'te ve `PATCH
/entities/{id}`'de baştan beri vardı. Ama frontend hiçbir yerde **yazmıyordu**: oluşturma
formunda alan yok (`api.entities.create` çağrısı `aliases`'ı hiç göndermiyordu), düzenleme
yolu ise hiç yok — `api.entities` içinde `update` metodu bile tanımlı değildi. Entity sayfası
alias'ları yalnızca *gösteriyordu*.

Sonuç: alias'lar gerçek kullanımda **her zaman boş**. Ve `dedup.py` skoru `name + aliases`
üzerinden hesapladığı için, eşleşme tespitinin alias yarısı hiç çalışmamıştı — oysa OSINT'te
asıl sinyal tam olarak orada.

**Düzeltme:** `api.entities.update` eklendi; oluşturma formuna "Alias'lar" alanı, entity
sayfasına `EntityAliasesDialog` (alias düzenleme) geldi. Alias kaydedilince eşleşme adayları
da yeniden yükleniyor.

**Doğrulama — düzeltmenin etkisi ölçüldü:** "Chaotic Eclipse"e üç alias yazıldı; aynı
`candidates` ucu **boş listeden** `INFINITE NIGHTMARE / benzerlik 1.0`'a geçti. Yani F30
yalnızca eksik bir form alanı değildi: otomatik tespiti bu vakada **çalışır hale getiren**
şeydi. F29'un elle yolu ise isimlerin hiç örtüşmediği ve alias'ın da bilinmediği durumlar
için gerekli olmayı sürdürüyor.

**Süreç notu (kendi hatam, iki kez):** bu bulguyu incelerken önce "PATCH alias'ları sessizce
düşürüyor" diye yanlış bir sonuca vardım. Gerçekte PATCH çalışıyordu; benim curl gövdemdeki
Türkçe karakterler (`Tehdit Aktörü`) cp1252 olarak gidip JSON'u bozmuş, 422 dönmüş, ben de
hata gövdesinde `aliases` anahtarı olmadığı için `None` okumuştum. İzole bir KùzuDB testi ve
ASCII-kaçışlı bir tekrar denemesi ayırt etti. Aynı gün ikinci kez: konsol çıktısındaki bozuk
Türkçe de (F27 doğrulamasında) API değil terminal kaynaklıydı. **Ders:** bu ortamda
Türkçe/UTF-8 içeren doğrulamalarda ham byte'lara bakmadan "veri kaybı var" denmemeli.

### F31 — Onaylanan birleştirme hiçbir şey yapmıyordu (CONFIRMED yazılıyor, hiç okunmuyor)  🔴 KRİTİK → ✅ kapatıldı

**Nasıl bulundu:** F29/F30 kapatıldıktan sonra kullanıcı UI'dan gerçek birleştirmeyi yaptı
(Chaotic Eclipse = INFINITE NIGHTMARE). Graf doğru davrandı: iki entity de duruyor, hiçbiri
silinmedi (Q7 / History Is Immutable — `confirm_same_as` bilinçli olarak node birleştirmiyor,
yalnızca kenarı CONFIRMED'e çekiyor), pending kuyruğu boşaldı. Sonra şu soruldu: **peki bu
onay bir işe yarıyor mu?**

**Tespit:** `SAME_AS`'in `CONFIRMED` durumu **hiçbir yerde okunmuyordu.**

| Yer | CONFIRMED okunuyor mu |
| --- | --- |
| `recall.py` (Memory Recall) | hayır — `SAME_AS` hiç geçmiyor |
| `vault.py` (Living Brain) | hayır — hiç geçmiyor |
| Router'lar | yalnızca `PENDING` sorgulanıyor (aday listesi + çözümleme) |
| Frontend | hayır |

Yani kullanıcı birleştirmeyi onaylıyor, "Eşleşme onaylandı" bildirimini alıyor ve sistemde
fiilen hiçbir şey değişmiyordu: Chaotic Eclipse sayfasında INFINITE NIGHTMARE'in claim'leri
görünmüyor, vault'ta iki ayrı not durmaya devam ediyor. Q7 gereği node'lar fiziksel olarak
birleştirilmediğine göre, "aynılık" **okuma zamanında** çözülmek zorundaydı — ve hiç
çözülmüyordu. Birleştirmenin tek anlamı iki kaydın bilgisinin birlikte hatırlanmasıdır;
o olmayınca özellik bir durum alanı yazmaktan ibaret kalıyordu.

Bu, oturumun desenindeki en uç örnek: F26'da yol kapalıydı, F27'de sonuç okunamıyordu,
burada **işlem hiç gerçekleşmiyordu.**

**Düzeltme:**
- `recall.py`: `same_as_group()` — CONFIRMED kenarlar üzerinde genişlik-öncelikli gezinti.
  Kenar tek yön saklanır ama anlamı simetrik, **ve aynılık geçişlidir** (A=B, B=C ⇒ A=C);
  bu yüzden düz komşu sorgusu değil, gerçek bir gezinti. `entity_recall` artık grubun
  tamamının claim/event/investigation'larını topluyor.
- Her satırda `via_entity_name`: satır başka bir kayıttan geldiyse hangisinden. Bu olmadan
  kullanıcı ekranda gördüğü claim'in neden orada olduğunu anlayamazdı — F27'de öğrenilen
  ders (sonuç görünüyorsa gerekçesi de görünmeli) baştan uygulandı.
- `vault.py`: entity notunda "Aynı kayıt (onaylanmış)" bölümü, wikilink'le ve kayıtların
  silinmediğini açıkça söyleyen bir notla.
- Frontend: başlıkta "Aynı kayıt: ..." (diğer kayda link) ve claim kartlarında "Aynı olduğu
  onaylanan X kaydından geliyor" etiketi.

**Doğrulama:** `recall` her iki yönden de grubu döndürüyor (Chaotic Eclipse → INFINITE
NIGHTMARE ve tersi), vault notu bölümü render ediyor. **Eksik kalan:** iki entity'nin de
henüz claim'i yok, dolayısıyla claim'lerin gerçekten karşı kayıttan aktığı gerçek veriyle
henüz kanıtlanmadı — bir sonraki adımda (INFINITE NIGHTMARE'e bir claim promote edilip
Chaotic Eclipse sayfasında aranarak) kapatılacak.

### F32 — Eşiği geçmeyen promote "hiç olmamış" gibi görünüyor  🔴 KRİTİK → ✅ kapatıldı

**Nasıl bulundu:** F31'in düzeltmesini gerçek veriyle kanıtlamak için kullanıcıdan bir gözlemi
INFINITE NIGHTMARE'e promote etmesi istendi. Cevap: **"promote etmiyor."** Ama etmişti —
API'den aynı çağrı tekrarlandığında `409 already processed` geldi, oysa gözlem listede hâlâ
`promoted=false` görünüyordu.

**Tespit:** `promoted` bayrağı yalnızca confidence **eşiğini geçen** durumu işaretler
(`PROMOTION_THRESHOLD = 0.45`). Eşiği geçmeyen bir promote da bir Claim üretir — claim graf'a
girer, entity sayfasında ve vault'ta görünür, `PRODUCED` kenarı kurulur — ama observation
`promoted=false` kalır. Bu ayrım Q1'in katmanlı hafıza modeli gereği **doğru**; sorun,
arayüzün üç durumu iki rozetle göstermesiydi:

| Gerçek durum | Kullanıcının gördüğü |
| --- | --- |
| Hiç işlenmemiş | "bekliyor" |
| İşlendi, claim üretildi, eşiği geçmedi | **"bekliyor"** + Promote butonu duruyor |
| İşlendi, eşiği geçti | "promoted" |

Üstüne üç mesaj birbiriyle çelişiyordu: toast "Eşik geçilmedi, **ham gözlem olarak kaldı**"
diyordu (claim'den hiç söz etmeden), liste "bekliyor" gösteriyordu, ve tekrar denendiğinde
409 "already processed" geliyordu. Kullanıcının "promote etmiyor" sonucuna varması bu üçünün
doğal okuması.

**Ölçek:** düzeltme sonrası tarandığında bu görünmez halde **5 observation** çıktı — dördü
Oturum 1'den. Yani Astra vakasının claim'lerinin tamamı, listede "bekliyor" görünmeye devam
eden gözlemlerden üretilmişti; hangi ham verinin işlendiği hiçbir yerden okunamıyordu.

**Düzeltme:**
- `Observation` modeline `produced_claim_id` (`OPTIONAL MATCH (o)-[:PRODUCED]->(c)`, liste
  uçlarında N+1 sorgu olmasın diye aynı sorguya eklendi).
- Liste rozeti üçe ayrıldı: `bekliyor` / `claim üretildi · eşik altı` / `promoted`.
- Promote butonu artık claim üretilmiş HER gözlemde gizleniyor (yalnızca `promoted`
  olanlarda değil) — tekrar denemenin 409'a çarpması bu yüzden oluyordu.
- Toast: "Eşik geçilmedi, ham gözlem olarak kaldı" → "Claim oluşturuldu (eşik altı) — gözlem
  ham haliyle de duruyor". Ne olduğunu söylüyor, ne olmadığını değil.
- 409 mesajı claim id'sini ve nedenini veriyor.

**Doğrulama:** `bekliyor 140 / claim üretildi·eşik altı 5 / promoted 1`; 409 mesajı claim
id'siyle dönüyor.

**Yan sonuç — F31 gerçek veriyle kanıtlandı:** kullanıcının promote'u aslında başarılı
olduğu için, INFINITE NIGHTMARE'e bağlanan claim (`0d43b171`) **Chaotic Eclipse'in
recall'ında `via_entity_name = "INFINITE NIGHTMARE"` ile göründü.** F31'in eksik kalan
doğrulaması böylece kapandı: onaylanmış SAME_AS artık gerçekten okunuyor ve bilgi iki kayıt
arasında akıyor.

### F33 — Aynı claim bir sekmede açıklanıyor, diğerinde açıklanmıyor + başlık taşması  🟠 → ✅ kapatıldı

**Nasıl bulundu:** kullanıcı F31'i teyit etmek için Chaotic Eclipse sayfasının ekran
görüntüsünü gönderdi. Doğrulama başarılıydı (Alias satırı, "Aynı kayıt: INFINITE NIGHTMARE",
Claim'ler (1) — karşı kayıttan gelen claim orada). Ama ekranda iki sorun vardı.

**1. Etiket yalnızca bir sekmede.** F31'in "Aynı olduğu onaylanan X kaydından geliyor"
etiketini **Claim'ler** sekmesine eklemiştim; kullanıcı **Timeline** sekmesindeydi ve orada
claim hiçbir açıklama olmadan duruyordu. Timeline claim'lerini `fullClaims`'ten
(`GET /claims/{id}`) kuruyor, `via_entity_name` ise recall'da — yani veri elde vardı,
bağlanmamıştı. Sonuç: aynı claim bir sekmede gerekçeli, diğerinde gerekçesiz görünüyordu;
F27'de kapattığım "sonuç görünüyorsa gerekçesi de görünmeli" ilkesinin aynı sayfada delinmiş
hali. Düzeltme: recall'dan `claim_id → via_entity_name` eşlemesi kurulup Timeline kartına da
basılıyor.

**2. Başlık taşması — bu oturumun kendi yan hasarı.** Entity başlığındaki aksiyon satırı
`shrink-0` ile tek satıra sabitlenmişti ve 4 buton için tasarlanmıştı. Bu oturumda ikisini
ben ekledim (F26 "Çelişki kur", F30 "Alias'lar") → 6 buton. Sonuç: "Chaotic Eclipse" başlığı
iki satıra kırıldı ve "Tehdit Aktörü" rozeti araya sıkıştı. Düzeltme: başlık `lg`'nin altında
dikey yığılıyor, aksiyonlar kendi satırına sarabiliyor, rozet satırı da `flex-wrap`.

**Ders:** dogfooding'de eklenen her aksiyon başlık satırına bir buton daha koyuyor. Faz 13'ün
UI cilasında bu satırın bir taşma menüsüne ("…") dönmesi gerekecek — 6 buton sınırda, 7.'si
taşıracak.

## Sistematik tarama — 2026-09-03 (oturum arası)

Oturum 2 bitince şu gözlemle bir karar verildi: **28 bulgunun tamamı tek bir sınıf** —
*"yetenek şemada/formülde var, gerçek yolda erişilemiyor ya da görünmüyor."* Bu sınıf artık
taranabilir; tek tek oturumla keşfetmek pahalı. Kalan oturumların **yeni** sürtünme türleri
bulması için ucuz olanlar tek geçişte kapatıldı.

**Yöntem — desenin üç sorusu, üç ayrı tarama:**

| Soru | Nasıl tarandı | Sonuç |
| --- | --- | --- |
| Okunuyor mu? | 20 rel tablosunun her biri için CREATE/MATCH sayımı | 1 şüpheli: `SUPERSEDES` |
| Görünüyor mu? | node tablolarının alanları ↔ frontend kaynağı | temiz |
| Yazılabiliyor mu? | 70 OpenAPI ucu ↔ `frontend/src/lib/api.ts` | 6 uç hiç çağrılmıyor |

İlk tarayıcı hatalıydı ve bunu kaydetmek gerekiyor: regex `[:REL]` arıyordu, oysa kod
`[r:SAME_AS]` gibi değişken adlı kenarlar da kullanıyor — SAME_AS ve CLAIM_CONTRADICTS yanlışlıkla
"hiç okunmuyor" işaretlendi. Düzeltilmiş tarama tek gerçek şüpheliyi verdi. **Otomatik tarama
sonucu, doğrulanmadan bulgu sayılmaz** (F23'ün dersinin tarama araçlarına uygulanmış hali).

### F34 — `SUPERSEDES` yazılıyor, hiçbir yerde okunmuyor  🔴 KRİTİK → ✅ kapatıldı

Bir claim supersede edildiğinde `(yeni)-[:SUPERSEDES]->(eski)` kenarı kuruluyor ve
`eski.valid_to` yazılıyor. Ama kenar kaynak kodda **yalnızca 1 kez** geçiyor (o CREATE), ve
`Claim.valid_to`'yu **hiçbir sorgu filtrelemiyor** (yalnızca `ENTITY_RELATION.valid_to`
kullanılıyor, o da `status` alanı üzerinden).

Sonuç: yerini almış bir claim entity sayfasında, timeline'da ve vault'ta güncel olanla
**birebir aynı** görünüyor. Faz 2'nin bitti kriteri "eski bilgi silinmeden temporal
supersede ediliyor" diyor — depolama katmanında ediliyor, kullanıcının gördüğü hiçbir şeyde
etmiyor. F31'in ("onaylanan birleştirme hiçbir şey yapmıyordu") birebir kardeşi, bu kez
oturum yapmadan, taramayla bulundu.

**Düzeltme:** `Claim`e `superseded_by_claim_id` + `supersedes_claim_id` (iki soru da
sorulabilmeli: "bu bilgi hâlâ geçerli mi" ve "neyin yerini aldı"); recall ve vault sorguları
`OPTIONAL MATCH (yeni)-[:SUPERSEDES]->(c)` ile işaretliyor; arayüz Claim'ler sekmesinde ve
timeline'da "yerini daha yenisi aldı — arşiv kaydı" uyarısı gösteriyor. **Gizlemiyoruz,
işaretliyoruz** — History Is Immutable.

**Doğrulama:** sorgu mantığı izole bir KùzuDB'de iki yönde de doğrulandı
(`eski → superseded_by=yeni`, `yeni → supersedes=eski`); API alanları dönüyor. **Eksik:**
graf'ta henüz gerçek bir supersede yok, bu yüzden işaretin gerçek veride görünmesi
sınanmadı — uydurma veri üretmek yerine Oturum 3'e bırakıldı.

### F35 — Investigation'ın kapsamı arayüzden kurulamıyor, hiçbir yerden okunamıyor  🔴 KRİTİK → ✅ kapatıldı

`PUT /investigations/{id}/entities/{id}` ve `.../events/{id}` backend'de vardı, **arayüz
ikisini de hiç çağırmıyordu**. Dahası: karşılığında **hiçbir GET yoktu** — kapsam kurulsa
bile geri okunamıyordu, yani `INCLUDES`/`INVESTIGATES` fiilen yaz-bir-daha-okuma.

Faz 3'ün akışı (Proje-Fikri madde 30) "Research Question → **Scope → Entities** → Sources →
... → Conclusion" diye ilerliyor; Scope adımı erişilemezdi. Faz 3 roadmap'te ✅ ama gerçek
kullanımda hiç çalıştırılmamış (graf'ta 0 investigation var) — bu yüzden görülmemişti.

Ek olarak iki bug: PUT'lar **idempotent değildi** (aynı entity iki kez eklenince iki
`INCLUDES` kenarı), ve kapsamdan **çıkarma yolu yoktu** — yanlış ekleneni geri almanın hiçbir
yolu olmaması, Faz 11'de üç kez tekrarlanan hatanın (F16, F23b, F29) dördüncüsü olurdu.

**Düzeltme:** `GET /investigations/{id}/scope`, `DELETE` uçları, PUT'lara idempotency guard;
frontend'de "Kapsam" bölümü (ekle/çıkar), Findings'ten **önce** — akış sırası bu.

### F36 — Hipoteze kanıt bağlama arayüzden çağrılmıyor  🟠 → ✅ kapatıldı

`PUT /hypotheses/{id}/evidence` hipotezin durumunu bağlı kanıtlara göre yeniden hesaplıyor
(SUPPORTED/WEAKENED/REFUTED), ama arayüzden hiç çağrılmıyordu. Sonuç: `HYPOTHESIS_EVIDENCE`
hiç yazılmaz, hipotez durumu gerçek kullanımda **hep UNRESOLVED** kalırdı. Hipotez sistemi
(Faz 3) kanıt bağlanamayınca yalnızca bir metin listesi. Düzeltme: hipotez kartına "Kanıt
bağla" (kanıt + duruş seçimi).

### F37 — Otomatik türetme tespiti arayüzden tetiklenemiyor  🟠 → ✅ kapatıldı

`POST /sources/lineage/detect` (Faz 6'nın otomatik tespiti) arayüzden hiç çağrılmıyordu.
F23b'de **elle** lineage kurma yolu açılmıştı; otomatik olan hâlâ erişilemezdi — kullanıcı
"bu iki haber birbirinden mi türemiş" sorusunu sisteme soramıyordu. Düzeltme: Kaynaklar
sayfasına "Türetme sına". Sonuç **ham haliyle** gösteriliyor (benzerlik skoru + yöntem),
çünkü F23'te öğrenildi: tespit gerçek veride 0.0000 verebiliyor ve kararı insanın
verebilmesi için skoru görmesi gerekiyor.

**Tarama sonrası:** çağrılmayan uç 6'dan 2'ye düştü. Kalan ikisi bilinçli kabul —
`POST /vault/render` her yazmada zaten otomatik tetikleniyor, `GET /hypotheses/{id}` ise
hipotezler investigation üzerinden listelendiği için gereksiz. İkisi de bir yeteneği
gizlemiyor.

### F38 — Investigation açılamıyor, finding eklenemiyordu (taramanın kendi kör noktası)  🔴 KRİTİK → ✅ kapatıldı

**Nasıl bulundu:** Oturum 3'ün ilk adımını yazarken investigations sayfasına bakıldı —
**"Yeni investigation" butonu yoktu.** `api.investigations` içinde `create` metodu da yoktu.

**Taramanın kör noktası:** ilk uç taraması kapsamayı **YOL** düzeyinde kontrol ediyordu.
`GET /investigations` çağrıldığı için `/investigations` yolu "kapsanmış" göründü ve
`POST /investigations`'ın hiç çağrılmadığı görülmedi. Metot düzeyinde tarayınca çıktı.
İkinci tarayıcı da kusurluydu (jenerik tipler çok satıra yayıldığı için `/inbox`,
`/monitors`, `findings` GET'i gibi çağrılan uçları "çağrılmıyor" sandı) — sonuçlar tek tek
elle doğrulanarak ayıklandı. **Aynı ders üçüncü kez: otomatik tarama sonucu, doğrulanmadan
bulgu sayılmaz** (F23 → tarayıcı regex'i → tarayıcı kapsama düzeyi).

**Gerçek boşluklar:**
- `POST /investigations` — investigation UI'dan **hiç açılamıyordu**. Faz 3'ün roadmap'te ✅
  olmasına rağmen graf'ta 0 investigation olmasının sebebi buydu; F35'te "hiç
  çalıştırılmamış" derken sebebini henüz bilmiyorduk.
- `PUT /investigations/{id}/findings/{claim_id}` — bulgu eklenemiyordu. Findings bölümü
  yalnızca okunuyordu ve hiçbir zaman dolamazdı; kapanışta `VALIDATED_FINDING`'e yükselecek
  bir şey de olmazdı. Yani Faz 3'ün "kapanan investigation'ın doğrulanmış bulguları kalıcı
  bilgiye yükselir" kriteri gerçek kullanımda hiç tetiklenemezdi.

**Düzeltme:** `NewInvestigationDialog` (başlık + araştırma sorusu), `AddFindingDialog`
(claim seçimi, kapanışta ne olacağını açıklayan notla), `DELETE .../findings/{claim_id}`
(yanlış eklenen geri alınabilmeli — claim silinmez, yalnızca bulgu listesinden çıkar) ve
`add_finding`'e idempotency guard (kapsam PUT'larıyla aynı çift-kenar sorunu).

**Doğrulama:** `/investigations` artık `GET,POST`; `.../findings/{claim_id}` artık
`PUT,DELETE`; olmayan investigation'a finding eklemek 404 dönüyor.

### F39 — Event'ler oluşturulamıyor, listelenemiyor  🟠 → 📋 Faz 13

`POST /events` arayüzden hiç çağrılmıyor ve `frontend/src/app/events/` altında **yalnızca
`[id]` var — liste sayfası yok**, sol menüde de Event girişi yok. Yani Event, Core Knowledge
Model'in ana node tiplerinden biri olmasına rağmen: oluşturulamıyor, gezilemiyor. Yalnızca
bir claim'in `about_event` bağıyla dolaylı olarak var olabiliyor (ki o da promote ekranındaki
"Event" seçeneği boş liste gösterdiği için pratikte imkânsız).

**Bilerek bu fazda yapılmadı:** yeni bir liste sayfası + menü girişi + oluşturma formu, Faz
11'in "ucuz olanları tek geçişte kapat" kapsamının dışında; ve Oturum 3'ün (Astra
investigation) event'e ihtiyacı yok. Faz 13'ün UI maddelerine eklendi. **Sonuç:** Faz 11
boyunca event tarafı sınanmamış olarak kalacak — bunu bilerek kabul ediyoruz.

**Ayrıca bilinçli kabul (bulgu değil):** `DELETE /entities/{id}`, `DELETE /events/{id}`,
`DELETE /sources/{id}` arayüzden çağrılmıyor. Silme yıkıcı bir işlem ve `sources` zaten
provenance kaybını 409 ile engelliyor; v1'de arayüzden silme sunmamak savunulabilir bir
tercih. `GET /observations/{id}` ve `GET /hypotheses/{id}` liste uçları üzerinden
karşılanıyor, `POST /vault/render` her yazmada otomatik tetikleniyor.

## Faz 13'e ertelenenler (kozmetik / nice-to-have)

### F28 — Tek bir claim'in detay sayfası yok  🟡 Faz 13

Frontend'de `/claims/[id]` rotası yok (`app/` altında claims klasörü hiç yok). Claim'ler
yalnızca bağlı oldukları Entity/Event/Observation sayfalarında, liste içinde görünüyor.

F27'de somut bir engel oldu: çelişen claim'i adlandırabildik ama ona **gidilemedi**, çünkü
gidecek bir sayfa yok. Aynı sınır ileride her yerde çıkacak — çelişki, corroboration,
supersede zinciri, evidence bağları: hepsi "şu claim" diye işaret ediyor ve işaret edilen
şeyin adresi yok. Ayrıca claim id'leri arayüzde hiçbir yerde görünmüyor, bu yüzden dışarıdan
(ör. API çıktısından) gelen bir id'yi kullanıcı ekranda eşleştiremiyor.

Faz 13 önerisi: `/claims/[id]` — metin, kaynak, confidence dökümü (`explain`), why-matters,
çelişki/corroboration/supersede ilişkileri ve üretildiği Observation.

### F20 — Dashboard henüz oluşmamış daily notuna link veriyor  🟡 Faz 13

`Dashboard.md` içindeki `[[daily/2026-09-03]]` linki, o günün notu session-end hook'u
tarafından yazılana kadar kırık görünüyor (Obsidian'da soluk). Kendiliğinden çözülüyor ama
gün içinde vault'a bakan kullanıcıya kırık link olarak görünüyor.

### F9 — `TypeCombo` native `<datalist>` kullanıyor  🟡 Faz 13

Açılan öneri listesi tarayıcı tarafından render edildiği için dark-glass diline tam uymuyor
(stil verilemez). İşlevsel ve erişilebilir olduğu için Faz 11'de kabul edildi; custom
combobox'a çevirmek Faz 13'ün UI cilası kapsamına daha uygun.

### F7 — `Source.reliability` tek boyutlu, iki ayrı şeyi taşıyamıyor  🟡 Faz 13

Gerçek kaynaklara değer verirken çıktı: bir kurumun kendi ürünü hakkındaki resmi duyurusu
**olgusal doğruluğu yüksek** (ne yaptığını bilir) ama **seçiciliği de yüksek** (aleyhine olanı
yazmaz). Bir haber sitesinde bu ikisi ters yönde: daha az iç bilgi, daha az çıkar çatışması.
Tek bir 0-1 skaları bunu taşıyamıyor ve confidence formülü `source_quality`'yi doğrudan bu
sayıdan besliyor (ağırlık 0.40 — en büyük terim).

Somut örnek: OpenAI'ın Astra duyurusu "stronger safeguards" diyor; Verge'in taşıdığı "ajanlar
test sırasında gerçek hedeflere saldırdı" detayı OpenAI metninde **yok**. Bu bir yanlışlık
değil, seçicilik — ama tek skalar bunu ifade edemiyor.

Öneri (Faz 13): `reliability`'yi ikiye ayır — `factual_accuracy` ve `independence`/`bias`.
Şimdi yapılmadı çünkü şema değişikliği dogfooding turunu keser; gerçek modelleme boşluğu
olduğu için kozmetik değil, Faz 13'ün ilk maddesi.

## Değerlendirilecek

- Vault (Faz 9) gerçek kullanımda okunabilirliği — henüz entity/investigation üretmedik.
