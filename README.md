# OsintLab

Tek kullanıcılı, yerelde çalışan kişisel açık kaynak istihbarat (OSINT) çalışma ortamı. Kaynakları sürekli tarar,
gözlemleri kanıtla birlikte saklar, entity / olay / iddia / kaynak arasında bağlantı kurar ve zamanla kendi hafızasını
biriktirir. İlkeler: önce kanıt, geçmiş değişmez, karar insanda (merge, sonuçlandırma ve doğrulama kullanıcı onayı ister).

## Katmanlar

| Katman | Ne yapar |
|---|---|
| Toplama | RSS/web toplayıcıları, zamanlanmış tarama, Telegram kanal toplayıcısı, Kanıt Kasası'na belge/görsel yükleme (PDF metin + OCR, EXIF/GPS) |
| Değerlendirme | Gözlem kuyruğu (sinyale göre sıralı, toplu eleme), deterministik confidence formülü, bağımsız kaynak soy ağacı |
| Bilgi grafı | Entity, olay, iddia, investigation; KùzuDB (gömülü graf), zamansal sürümleme, Obsidian vault çıktısı |
| Pivot | Seçici katmanı (alan adı, IP, ASN, hash … deterministik çıkarım), anahtarsız zenginleştirme modülleri, pivot grafı, altyapı izleme |
| Araç Rehberi | 713 dış araç, 21 kategori, her birinin kaynağı; arama operatörü kurucu, Ctrl+K hızlı pivot |
| Rapor | Investigation'ı iddiaları, confidence'ı ve kanıtıyla dışa aktarır |

Ayrıntı: `docs/Final-Dokuman.md` (kararlar ve mimari), `docs/Roadmap.md` (36 faz), `DESIGN.md` (arayüz kimliği).

## Çalıştırma

```powershell
.\start.ps1                     # backend (8420) + frontend (3000)
.\start.ps1 -Stop               # ikisini de kapat
.\start.ps1 -Reload             # backend --reload (yalnız hata ayıklarken: gömülü KùzuDB bağlantısını yeniler)
.\start.ps1 -InstallAutostart   # backend'i oturum açılışında pencere açmadan başlat ("OsintLab Backend" görevi)
```

- Arayüz http://localhost:3000, API dokümanı http://127.0.0.1:8420/docs, vault `data/vault/`.
- Portlar sabit: frontend `NEXT_PUBLIC_API_BASE`, CORS ve oturum sonu vault senkronu 8420'ye bağlı.
- İlk kurulum: `cd backend; py -3.12 -m venv .venv; .venv\Scripts\pip install -r requirements-dev.txt`,
  `cd frontend; npm install`.

## Test

```powershell
cd backend; .venv\Scripts\python -m pytest       # testler kendi geçici veri kökünde, gerçek data/'ya dokunmaz
cd frontend; npx tsc --noEmit; npm run lint; npm run build
```

CI (`.github/workflows/ci.yml`) her push'ta backend testlerini ve frontend tip/lint/derlemesini koşar.

Veri (`data/`) ve gizli ayarlar git'e girmez.
