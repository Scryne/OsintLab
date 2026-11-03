/**
 * Ekranda görünen etiketler — veritabanında saklanan değerler DEĞİŞMEZ.
 *
 * Varlık türü (`entity_type`) backend'de serbest metin ve mevcut kayıtlar İngilizce değerlerle
 * duruyor ("Organization", "AI Model"…). Değerleri yeniden adlandırmak hem eski kayıtları hem
 * backend'in varsayılanlarını ("Organization") bölerdi; bu yüzden değer aynı kalır, ekranda
 * Türkçe etiketi gösterilir. Formda Türkçe etiket yazılırsa kayda bilinen değer gider — aynı
 * tür iki ayrı yazımla grafı ikiye bölmesin diye. Terimler: `docs/Terim-Sozlugu.md`.
 */
export const ENTITY_TYPE_LABELS: Record<string, string> = {
  Person: "Kişi",
  Organization: "Kurum",
  Company: "Şirket",
  Location: "Konum",
  "AI Model": "Yapay zekâ modeli",
  Product: "Ürün",
  Domain: "Alan adı",
  Vessel: "Gemi",
  Aircraft: "Hava aracı",
  Malware: "Zararlı yazılım",
  "Threat Actor": "Tehdit aktörü",
  "Tehdit Aktörü": "Tehdit aktörü",
  Entity: "Varlık",
};

/** Kayıtlı tür değerinin ekrandaki adı; bilinmeyen (kullanıcının serbest yazdığı) tür olduğu gibi. */
export function entityTypeLabel(value: string | null | undefined): string {
  if (!value) return "";
  return ENTITY_TYPE_LABELS[value] ?? value;
}

const LABEL_TO_VALUE: Record<string, string> = Object.fromEntries(
  Object.entries(ENTITY_TYPE_LABELS)
    .filter(([value]) => value !== "Threat Actor" && value !== "Entity")
    .map(([value, label]) => [label.toLocaleLowerCase("tr"), value])
);

/** Formdan gelen metni kayıt değerine çevirir: "Kurum" → "Organization". Tanınmayan metin aynen kalır. */
export function entityTypeValue(input: string): string {
  const t = input.trim();
  return LABEL_TO_VALUE[t.toLocaleLowerCase("tr")] ?? t;
}

/** Öneri listesi için: kayıt değerleri → Türkçe etiketler (tekrarsız). */
export function entityTypeSuggestions(values: string[]): string[] {
  return Array.from(new Set(values.filter(Boolean).map(entityTypeLabel)));
}

/**
 * Enum değerlerinin ekrandaki adları. Değerler (API alanı, veritabanı) değişmez; yalnızca
 * gösterim. Bilinmeyen bir değer gelirse olduğu gibi gösterilir — sessizce kaybolmasın.
 */
export const STATUS_LABELS = {
  investigation: {
    OPEN: "Açık",
    ACTIVE: "Sürüyor",
    PAUSED: "Duraklatıldı",
    RESOLVED: "Sonuçlandı",
    CLOSED: "Kapatıldı",
    ARCHIVED: "Arşivlendi",
  },
  hypothesis: {
    PROPOSED: "Önerildi",
    SUPPORTED: "Destekleniyor",
    WEAKENED: "Zayıfladı",
    REFUTED: "Çürütüldü",
    UNRESOLVED: "Belirsiz",
  },
  inbox: {
    NEW: "Yeni",
    IGNORED: "Yoksayıldı",
    CONFIRMED: "Onaylandı",
    REJECTED: "Reddedildi",
    INVESTIGATING: "Araştırılıyor",
    FOLLOWED: "Takipte",
  },
  inboxItem: {
    NEW_EVENT: "Yeni olay",
    NEW_RELATIONSHIP: "Yeni ilişki",
    SIGNIFICANT_CHANGE: "Önemli değişiklik",
    INVESTIGATION_UPDATE: "Soruşturma güncellemesi",
    CONTRADICTION: "Çelişki",
    CONFIDENCE_CHANGED: "Güven değişti",
    NEW_OBSERVATION: "Yeni gözlem",
    SCAN_FAILED: "Tarama başarısız",
    SELECTOR_ALERT: "Seçici uyarısı",
    SELECTOR_CHANGE: "Seçici değişikliği",
  },
  knowledge: {
    UNKNOWN: "Bilinmiyor",
    OBSERVED: "Gözlemlendi",
    REPORTED: "Bildirildi",
    SUPPORTED: "Destekleniyor",
    CORROBORATED: "Doğrulandı",
    HIGH_CONFIDENCE: "Yüksek güven",
    CONTRADICTED: "Çelişkili",
  },
  stance: {
    SUPPORTS: "destekliyor",
    WEAKENS: "zayıflatıyor",
    REFUTES: "çürütüyor",
  },
} as const satisfies Record<string, Record<string, string>>;

export function statusLabel(group: keyof typeof STATUS_LABELS, value: string | null | undefined): string {
  if (!value) return "";
  return (STATUS_LABELS[group] as Record<string, string>)[value] ?? value;
}
