# DURUM — OsintLab

> Envanter, sertifika değil: ölçülen gerçek durum. Yol haritası `docs/Roadmap.md`, kararlar `docs/Final-Dokuman.md`.

**Ölçüm tarihi:** 2026-11-13 (bitirme denetimi)

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
