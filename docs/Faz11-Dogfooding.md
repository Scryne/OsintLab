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
anahtarı üretir, yani o 80 gözlem için kopya oluşabilir. Faz 12'den önce feed'leri bir kez
sıfırlamak gerekebilir.

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

## Faz 13'e ertelenenler (kozmetik / nice-to-have)

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
