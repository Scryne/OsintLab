# OsintLab

Bu proje Scryne'ın Proje Çalışma Akışı'nı takip eder (bkz. global `~/.claude/CLAUDE.md`, ve
detaylı gerekçeler için ScryneOS vault'unda `🧠 500-Knowledge/Proje-Calisma-Akisi.md`).

## Durum

Şu anki aşama `.claude/state.json` içinde tutulur, `session-start` hook'u her oturum başında
bunu okuyup bağlama enjekte eder — nerede kaldığımızı sormana gerek kalmaz. Bir aşama
bittiğinde `asama` alanını sırayla güncelle: `fikir` → `denetim` → `finalizasyon` → `roadmap`
→ `uygulama` → `tamamlandi`. Aynı anda ScryneOS vault'undaki
`🏰 300-Projects/OsintLab.md` index notunu da güncelle.

## Dosyalar

- `docs/Proje-Fikri.md` — ilk fikir (kullanıcının "SCRYNE OSINT LAB" v1/v2 taslaklarından
  derlendi, v2 esas alındı — tam vizyon dokümanı içeride korunuyor)
- `docs/Final-Dokuman.md` — nihai kararlar (teknoloji stack, mimari, riskler)
- `docs/Roadmap.md` — fazlı yol haritası; her faz "Durum" sütunuyla takip edilir, hook bunu
  otomatik okur
- `docs/Design.md` — bu projeye özel frontend kimliği (accent palet, tipografi, mood)

## Proje-özel not: OSINT Brain'in teknik temeli

"OSINT Brain" kavramı muhtemelen ScryneOS vault'unda (`C:\Users\scryn\Documents\ScryneOS`)
zaten kullanılan AvenoxBeyin mimarisi (dosya tabanlı hafıza, session-end özetleme, gece
derlemesi — bkz. https://avenox.lol/beyin.md) üzerine, bu proje özelinde izole ve OSINT'e
özelleştirilmiş bir kurulumla inşa edilecek. Bu, finalizasyon aşamasında netleşecek bir
mimari karar — bkz. `docs/Proje-Fikri.md` sonundaki mimari not.

## Frontend

Taban disiplin global `~/.claude/CLAUDE.md`'deki Dark Glassmorphism kuralları — bunlar sabit
ve her projede aynı. Projeye özel karakteri `docs/Design.md` belirler; o dosya boşsa veya yer
tutucu içeriyorsa frontend işine başlamadan önce `ui-ux-pro-max` skill'iyle doldur.

Araç sırası: `frontend-design` (yön) → `shadcn`/`21st` MCP (component) → `ui-ux-pro-max`
(palet/UX) → `frontend-ui-engineering` (production/erişilebilirlik) → `tailwind-ui-refactor`
(son cila).
