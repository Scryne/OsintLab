# DURUM — OsintLab

> Envanter, sertifika değil: ölçülen gerçek durum. Yol haritası `docs/Roadmap.md`, kararlar `docs/Final-Dokuman.md`.

**Ölçüm tarihi:** 2026-11-25 (yayına hazır turu; önceki: 2026-11-13)

**Yayına hazır karnesi (2026-11-25):** Kod ✅ · Ürün ✅ · Ön yüz ✅ (vitrin: siniyor) · Belge ✅ · Kapı: ağaç temiz, geçmişte
`1737109` (11-03 `gh pr merge`) gerçek e-posta kimliği taşıyor, geçmişi yeniden yazma kararı Scryne'da · Dış adım yok
(yerel, tek kullanıcılı araç). Bitiş çizgisi ScryneOS `🎯 100-Command-Center/Yayina-Hazir-Karnesi.md`'de; bundan sonra
bulunan şey aşağıdaki "v2 fikirleri"ne girer.

## 2026-11-25 ölçümü

- **Canlı servis:** `\OsintLab Backend` görevi bir aydır kesintisiz; günlükte 10-24'ten sonra hata yok, son uyarılar
  11-13'teki geçici DNS kesintisi. Toplama sürüyor (11-24'te 100, 11-25 öğlene kadar 55 kayıt; CISA ICS duyuruları dahil).
- **Kod:** pytest 143/143, `tsc --noEmit` 0, eslint 0, `next build` temiz. `npm audit`: next 16.4.3'te 1 orta açık →
  16.4.6 (kesin sürüm, `eslint-config-next` aynı), 0.
- **Gezi (canlı veri, `next start` + canlı API):** 19 rota (ana sayfa, gelen kutusu, olaylar, graf, varlıklar,
  soruşturmalar, kaynaklar, iddialar, kanıt, gözlemler, toplayıcılar, doğrulama, zenginleştirme, seçiciler, araçlar,
  arşiv) × 390/1440 × 2 tema + ana sayfa 4 genişlik: taşma 0, konsol 0.
- **Bulunan → düzeltilen:** CISA 10-24..10-31 arası düşmüş, 11-01'de düzelmişti; "3 kez üst üste başarısız" uyarısı bir
  ay sonra hâlâ Ana Çalışma Alanı'nın öncelikli listesindeydi. Başarılı taramada karar bekleyen `SCAN_FAILED` öğesi
  INFO'ya iniyor, başlığı "yeniden çalışıyor" oluyor (durumu NEW kalır; IGNORED kullanıcı kararı sayıldığı için
  yazılmaz). Test düzeltmeden önce düştü. Servis yeni kodla yeniden başlatıldı, CISA taraması elle koşturuldu, uyarı
  listeden indi (`d8e999f`).

## v2 fikirleri

- Düzelen kaynak için ayrı bir "kaynak yeniden çalışıyor" bildirimi yerine kaynak sağlığı paneli.
- Terfi kuyruğu 948 öğe: kuyruk tazeliği kuralı çalışıyor ama kuyruk büyüyor; eşik/otomatik eleme incelemesi.

---

**Önceki ölçüm (2026-11-13, bitirme denetimi)**

## Ölçüldü

- **Backend:** pytest 142 test geçti (testler kendi geçici veri kökünde, `OSINTLAB_DATA_DIR`).
- **Ön yüz:** `tsc --noEmit` 0, eslint 0, `next build` temiz.
- **CI:** `master`'daki son üç koşu yeşil; açık PR yok.
- **Port / CORS:** `OSINTLAB_FRONTEND_PORT=4146` verilince API `Access-Control-Allow-Origin: http://localhost:4146`
  döndürüyor ve arayüz veri alıyor. `start.ps1 -WebPort` betiğin kendisiyle denenmedi: betik API'yi sabit 8420'de
  açtığı için o sırada çalışan servisle çakışırdı.
- **Gezi:** ayrı veri kökü + ayrı portlar (API 4145, arayüz 4146), canlı servise dokunulmadan.
  - Boş veriyle (`next dev`): 21 rota (20 menü maddesi + 404) × 390/768/1280/1440 koyu + 1440 açık = 105 ekran,
    0 taşma, 0 konsol hatası (404 sayfasının kendi 404'ü beklenen).
  - Kurgusal demo veriyle (`next build` + `next start`): aynı 105 ekran, 0 taşma, 0 konsol hatası; ana çalışma
    alanı, graf, varlık, soruşturma, doğrulama ve kaynaklar ekranlarına gözle bakıldı.

## Bu denetimde bulunan → düzeltilen

- Sekme başlığı her rotada "OsintLab"tı. Rotaya göre başlık eklendi (`e38cdbc`); Next hidrasyondan sonra kök
  metadata başlığını yeniden yazdığı için `<head>` izlenip başlık geri konuyor (`475bd96`). Tarayıcıda doğrulandı.
- Varlık sayfasında 7 aksiyon düğmesi 1440'ta başlığı daraltıyordu ("MV Vela Nord" iki satıra kırılıyordu): başlık
  her genişlikte tam satır, aksiyonlar altında (`f7c26bd`).
- Grafta sağ kenara yakın düğümün etiketi tuvalin dışında kesiliyordu: etiket sola yazılır (`4e4eaf3`).
- Soruşturma durum düğmeleri "→ ACTIVE / → ARCHIVED", doğrulama adayı "· SUPPORTED" ham değerlerini gösteriyordu:
  Türkçe etiketler (`79522e1`, `952f852`).

## Bilinen / açık

- ~~Grafta sağ üst köşeye yerleşen düğüm yakınlaştırma denetiminin altında kalabiliyor.~~ Kapandı (11-16):
  yerleşim denetimin bölgesini (220×64 viewBox birimi) boş bırakıyor.
- Kareler: `_portfolyo/ekranlar/OsintLab/2026-11/` (kapak: varlık sayfası + güven yelpazesi ve çelişki rozetleri,
  960×600 @3; ana-calisma-alani, bilgi-grafi, varlik-vela, dogrulama, 1440×900 @2). Hepsi kurgusal demo verisi.
