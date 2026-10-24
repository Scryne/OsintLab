---
proje: OsintLab
created: 2026-10-24
type: kullanim-rehberi
---
# v6 Kullanım Rehberi — Pivot Katmanı

v6'nın eklediği iş akışları, kısa ve uygulamalı. Sayfaların kendi (?) düğmesi ayrıntılı adımları
gösterir; burası hangi soruya hangi ekranla cevap verildiğinin haritası.

## Herhangi bir değer: "Bunu biliyor muyum?"

**Ctrl+K** (ya da **/**) her sayfadan açılır. Bir alan adı, IP, URL, hash, CVE, ATT&CK tekniği
(T1059), ASN (AS13335), BTC/ETH adresi ya da "enlem, boylam" yapıştır — defang'li yazım da olur
(`hxxps://evil[.]com`). İlk satır "Pivotla": seçicinin sayfasına götürür, grafta yoksa ekler.
Değer bir seçici değilse entity, olay, investigation, kaynak, seçici ve claim metinlerinde arar.

## Seçici sayfası (`Seçiciler` → bir satır)

1. **Zenginleştirme** → "Pasif modüllerin hepsini çalıştır". Hedefe dokunmadan DNS, RDAP
   (WHOIS), sertifika şeffaflığı, Wayback, Shodan InternetDB, RIPEstat, urlscan, KEV/EPSS/NVD,
   ATT&CK, haber araması. Yavaş kaynaklar (Wayback, crt.sh) arka planda biter, kart kendiliğinden
   güncellenir.
2. **Pivotlar** → bulunan yeni seçiciler (IP, alt alan adı, ad sunucusu, ASN...) ilişkisine göre
   gruplu ve iki adımlık grafta. Tıkla, devam et.
3. **Görüldüğü yerler** → bu değerin hangi kaynakta, hangi cümlede geçtiği; kaç farklı yayıncı.
4. **Dış araçlar** → 100'ü aşkın araçta (VirusTotal, Shodan, Censys, urlscan, OTX...) değerle hazır
   bağlantı + arama operatörü tarifleri. OsintLab bu servislere istek atmaz; tarayıcında açılır.
5. **Entity bağları** → "bu altyapı şu kuruma ait" iddiası. Sistem kendisi kurmaz.
6. **İzlemeye al** → günde bir yeniden sorgulanır; yeni alt alan adı, DNS/kayıt değişikliği, yeni
   port, KEV'e giriş, yaptırım listesine giriş Inbox'a düşer.

Bir zenginleştirme sonucunu iddiaya çevirmek: koşunun altında **Gözleme çevir** → Promote Kuyruğu.

## Gerçekte sömürülen açıklar

Ana Çalışma Alanı'nın altındaki **Korpusta sömürülen açıklar** paneli: topladığın metinlerde
geçen ve CISA KEV'e göre gerçekte sömürülen CVE'ler; fidye yazılımında kullanılanlar önce, sonra
EPSS. Seçiciler sayfasında "Yalnız sömürülenler (KEV)" filtresi aynı listeyi verir. Yeni gelen
CVE'ler için: Seçiciler → CVE türü → "Bu türün hepsine uygula → CISA KEV" (yerel, saniyeler).

## Bir iddiayı doğrulamak

Claim sayfası (`/claims/view`, aramadan ya da seçici sayfasından) → **Bu iddiayı başka kim
söylüyor?** → haber araması. Bağımsız bir yayıncının haberini **Gözlem** düğmesiyle ekle; Promote
Kuyruğu ve Doğrulama ekranı onu bu claim'in olası doğrulayıcısı olarak önerir. Claim sayfası
ayrıca NATO/Admiralty kodunu (ör. **B2**: genellikle güvenilir kaynak, muhtemelen doğru bilgi)
gösterir.

## Kurum araştırması (entity sayfası → "Altyapı ve zenginleştirme")

Wikidata (resmi site, ülke, ana kurum, LEI), GLEIF (tüzel kişi kaydı), OFAC yaptırım taraması
ve haber araması. **Ad eşleşmesi kimlik değildir** — yaptırım eşleşmesini doğrulamadan iddia
etme (ör. "Astra" AI modeli İran yaptırım listesindeki "ASTRA" ile ad olarak eşleşiyor).
Wikidata'nın önerdiği resmi siteyi tek tıkla seçici olarak ekleyip bağlayabilirsin.

## Görsel doğrulama (Kanıt Kasası → görsel → "Görsel analizi")

Kamera, çekim zamanı, GPS (→ otomatik koordinat seçicisi), düzenleme yazılımı izi, içerik kimlik
bilgisi (C2PA), dosyanın kendi beyan ettiği AI üretimi, algısal hash (aynı görselin yeniden
kodlanmış kopyalarını bulur), görseldeki yazının OCR'ı. Metadata yoksa bu bir şey kanıtlamaz —
sosyal medya yüklemede siler. Ters görsel arama için dosyayı indirip seçtiğin servise yükle.

**Kronolokasyon** (Araç Rehberi → Güneş konumu): konum + tarih ver, fotoğraftaki dik bir
nesnenin gölge yönünü ve/veya boy oranını gir → o gün bu gölgenin oluştuğu saatler (UTC).

## Telegram kanalı izlemek

Toplayıcılar → mod "Telegram kanalı" → `@kanal`. Allowlist'te `t.me` olmalı. Yalnızca herkese
açık önizlemesi olan kanallar (son ~20 mesaj); zamanlanmış taramaya da alınabilir.

## Analiz ve rapor (investigation sayfası)

- **ACH matrisi** (en az iki hipotez + kanıt varken): kanıt × hipotez; en olası hipotez en az
  tutarsız olandır. Boş hücre "tartılmadı" demek; hücreye tıklayarak duruşu belirle.
- **Rapor**: TLP etiketini seç → "Raporu aç (yazdırılabilir)" (tarayıcıdan PDF'e) ya da Markdown
  indir. Rapor deterministik: yorum yalnızca senin Analiz/Sonuç metnindir; her bulguda confidence
  dökümü, Admiralty kodu, kaynak, arşiv hash'i, seçiciler ve zenginleştirme özetleri.

## OPSEC

- **Pasif** modüller üçüncü taraf veritabanına sorar, hedefe dokunmaz — ama sorgu o servise
  ilgini gösterir. **Yerel** modüller (KEV, ATT&CK, OFAC) hiçbir yere sormaz. **Aktif** modül
  (HTTP parmak izi) hedefin sunucusuna istek atar: varsayılan kapalı, her seferinde onay ister.
- Aynı soru önbellek süresi içinde tekrar sorulmaz; "Yeniden sor" bilinçli bir karardır.
- Zenginleştirme sayfasından her modülü tek tek kapatabilirsin; her koşunun ham yanıtı SHA-256
  ile saklanır ve "Son koşular" listesi neyin nereye ne zaman sorulduğunun kaydıdır.
