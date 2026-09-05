---
proje: OsintLab
created: 2026-09-02
updated: 2026-09-06
type: design-sistemi-ek
---
# OsintLab — Design Sistemi (ek notlar)

> **Tasarım kimliğinin doğruluk kaynağı artık proje kökündeki `DESIGN.md`'dir.**
> 2026-09-06'da Google DESIGN.md spec'ine (alpha) geçildi: normatif token değerleri orada,
> YAML frontmatter'da yaşıyor ve makine doğrulanabilir:
>
> ```bash
> npx @google/design.md lint DESIGN.md
> npx @google/design.md export --format css-tailwind DESIGN.md
> ```
>
> Bu dosya silinmedi çünkü bir şey taşıyor: aşağıdaki **Kontrast Sözleşmesi**, spec'in
> frontmatter şemasına sığmayan bir ölçüm ve gerekçe kaydı. Token DEĞERLERİ burada
> tekrarlanmaz — bir değeri değiştireceksen `DESIGN.md`'yi düzenle, sonra buradaki
> ölçümü yenile.

## Kontrast Sözleşmesi (2026-09-06)

Renk bu projede bilgi taşıyor, dolayısıyla okunabilirliği bir tercih değil bir kısıt.
Rampaların **anlamı** (soğuk→sıcak sıra, CONTRADICTED'ın rampa dışında durması, priority'nin
ayrı aile olması) dokunulmaz; kontrast bunun **üzerine** ton değil açıklık oynayarak sağlanır.

**Kural: bir rengin zemin/nokta/kenarlık hâli ile metin hâli ayrı tokenlardır.**

| Kullanım | Token | Eşik | Ölçüm zemini |
| --- | --- | --- | --- |
| Nokta, kenarlık, rail bloğu, kart kenarı | `--confidence-*`, `--priority-*` | 3:1 (WCAG 1.4.11, UI bileşeni) | `.glass-panel` (#1b1c1e) |
| Badge/etiket metni (`text-xs` = 12px) | `--confidence-*-text`, `--priority-*-text` | 4.5:1 | aşağıya bkz. |
| Link/vurgu metni | `--brand-accent-text` | 4.5:1 | cam + surface |
| Buton zemini | `--brand-accent` | — | metin `--brand-accent-foreground`'dan |

**Ölçüm zemini iki badge'de farklıdır — karıştırılmamalı:**
- `ConfidenceBadge` saydamdır; metin doğrudan cam/surface üzerindedir.
- `PriorityBadge` kendi rengiyle **%22 tint'lenmiş** bir pill'dir; metin o tint üzerindedir
  ve zemin renge yaklaştığı için kontrast belirgin şekilde düşer. Bu yüzden priority metin
  tokenları confidence'dakilerden daha açıktır. Tint'i düşürmek çözüm değildir: %10'a
  indirilse bile ham renkle tavan 4.15'tir.

**2026-09-06 denetiminde düzeltilenler.** Ölçülmeden önce yedi token kalıyordu; en kötüsü,
en çok görülmesi gereken iki durumun (CONTRADICTED 3.61, CRITICAL 4.10) en zor okunanlar
arasında olmasıydı. `UNKNOWN` ise nokta olarak 2.32 ile 3:1'i bile geçmiyordu — rampanın en
sönük ucu fiilen görünmezdi; ham değeri `#4B5768 → #5B697D` yükseltildi (luminans sırası
korunarak, tek ham değer değişikliği).

**Yeni renk eklerken:** `frontend/src/app/globals.css` içindeki tokenları okuyup her eşiği
yeniden ölçen doğrulama, Paket 1 çalışmasında kullanıldı; token eklendiğinde aynı ölçüm
tekrarlanmalı. Değerler elle tahmin edilmez.
