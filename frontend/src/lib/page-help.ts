/**
 * Sayfa başına kullanım rehberi — sağ üstteki (?) düğmesinin içeriği.
 *
 * **Neden var.** Nav 17 satıra çıktı ve sayfaların çoğu tek başına anlaşılır bir liste
 * değil, bir iş akışının bir adımı: "aday" ile "karar", "arşiv" ile "kanıt", "eleme" ile
 * "silme" arasındaki farkları bilmeyen biri ekranı yanlış kullanır. Bu araç tek kullanıcılı
 * ve aylarca ara verilebiliyor; üç ay sonra kendi aracına dönen biri için bu metinler
 * dokümantasyondan daha erişilebilir bir yerde durmalı.
 *
 * **Sayfa başlığındaki paragrafı TEKRAR ETMEZ.** Başlıktaki metin "bu sayfa nedir" sorusunu
 * cevaplıyor; buradaki metin "nasıl kullanılır" ve "hangi tuzak var" sorularını. İkisi aynı
 * şeyi söylerse ikisi de okunmaz olur.
 *
 * `dikkat` maddeleri özellikle kıymetli: her biri gerçek kullanımda yaşanmış bir yanlış
 * anlamadan ya da roadmap'te alınmış bir karardan geliyor.
 */
export interface PageHelp {
  title: string;
  /** Sırayla yapılacak işler. Numaralı liste olarak gösterilir. */
  steps: string[];
  /** Tuzaklar ve bilinmesi gereken kararlar. */
  warnings?: string[];
}

/**
 * Anahtar = sayfanın pathname'i. Eşleşme en uzun önekle yapılır (`/entities/candidates`,
 * `/entities`ten önce gelir), böylece detay sayfaları da üst sayfanın rehberini alır.
 */
export const PAGE_HELP: Record<string, PageHelp> = {
  "/": {
    title: "Ana Çalışma Alanı",
    steps: [
      "Üstteki sayaçlar sistemin nabzı: bekleyen gözlem, açık aday kuyrukları ve claim durumları.",
      "Bir sayı beklenmedik biçimde büyüdüyse o kuyruğun sayfasına git — kuyruklar birikince kararlar pahalılaşır.",
      "Günlük akış genelde şu: Promote Kuyruğu → Doğrulama → Entity Adayları.",
    ],
  },
  "/entities": {
    title: "Entity'ler",
    steps: [
      "Bir entity'ye tıklayınca hakkındaki claim'ler, ilişkiler, olaylar ve zaman çizgisi açılır.",
      "Alias eklemek önemlidir: gözlem eşleştirmesi ad VE alias üzerinden çalışır, eksik alias sinyali kaybettirir.",
      "Yeni entity'yi elle yaratmak yerine Entity Adayları sayfasından onaylamak daha iyi — orası sistemin kendi çıkardığı adları taşır.",
    ],
    warnings: [
      "Aynı şeyin iki kaydı varsa silme; Olası Eşleşmeler sayfasından birleştir. Silmek geçmişi yok eder (History Is Immutable).",
    ],
  },
  "/entities/candidates": {
    title: "Entity Adayları",
    steps: [
      "Liste, claim metinlerinden çıkarılmış özel isim adaylarıdır — kaç claim ve kaç FARKLI kaynakta geçtiğine göre sıralı.",
      "Gerçek bir kurum/kişi/ürün olanları seç, türünü ver ve entity'ye çevir.",
      "Geri kalanı toplu ele. Elenen aday bir daha önerilmez ama silinmez — ikinci sekmeden geri alınabilir.",
    ],
    warnings: [
      "Bu sayfa bir 'temizlik işi' değil, kuyruk sinyalinin GİRDİSİ. Bir ad entity olmadan, o addan bahseden gözlemler Promote Kuyruğu'nda sinyalsiz görünür — 2026-09-09'da 14 aday onaylanınca kuyruğun yüksek sinyalli öğe sayısı 5'ten 21'e çıktı.",
      "Kısaltma ve bülten kalıpları (KEV, FCEB, CVE ID) ile abonelik katmanları (Pro, Plus, Edu) entity değildir; ele.",
    ],
  },
  "/entities/relations": {
    title: "İlişki Adayları",
    steps: [
      "Aynı claim'de birlikte geçen entity çiftleri önerilir. Öneri, ilişkinin VAR olduğunu söylemez — birlikte anıldıklarını söyler.",
      "İlişkinin TÜRÜNÜ sen verirsin (satın aldı, ortak, rakip…); sistem tür tahmin etmez.",
      "İlişkisiz olduğuna karar verdiklerini ele — o çift bir daha önerilmez.",
    ],
  },
  "/entities/same-as": {
    title: "Olası Eşleşmeler",
    steps: [
      "Aynı şeyin iki ayrı kaydı olabilecek entity çiftleri gösterilir (ad benzerliği + ortak bağlam).",
      "Gerçekten aynıysa birleştir; değilse ele.",
    ],
    warnings: [
      "Birleştirme kayıt silmez, bir SAME_AS bağı kurar. İki kaydın geçmişi de durmaya devam eder.",
    ],
  },
  "/events": {
    title: "Olaylar",
    steps: [
      "Olaylar, birden çok claim'in anlattığı tek bir gerçek dünya olayıdır (bir sızıntı, bir duyuru, bir dava).",
      "\"Olay adayı\" sekmesi, birbirini doğrulayan claim kümelerinden türetilir — hazır bir olay önerisidir.",
      "Bir olaya claim bağlamak, o claim'in confidence'ını olaya taşır.",
    ],
    warnings: [
      "Bir claim ya bir entity ya bir olay hakkındadır, ikisi birden değil. Claim'i olaya bağlamak entity bağını siler; sistem entity'yi olaya INVOLVED_IN ile taşıyarak bunu telafi eder.",
      "Olayın confidence'ı elle girilmez — en iyi desteklenen claim'inden türetilir.",
    ],
  },
  "/sources": {
    title: "Kaynaklar",
    steps: [
      "Her kaynağın bir güvenilirlik değeri var ve confidence'ın %40'ı doğrudan buradan gelir.",
      "Bir kaynak başka bir kaynaktan türüyorsa (syndication, ajans) bunu lineage olarak işaretle.",
    ],
    warnings: [
      "Lineage kozmetik değil: aynı köke inen iki kaynak bağımsız doğrulama SAYILMAZ. İşaretlenmemiş bir türetme confidence'ı sahte yükseltir.",
    ],
  },
  "/observations": {
    title: "Gözlemler",
    steps: [
      "Ham veri katmanı: toplayıcıların getirdiği ve belgelerden çıkarılan her şey burada, hiçbir yorum katılmadan.",
      "Bir gözlemi bilgiye çevirmek için promote et; toplu iş için Promote Kuyruğu'nu kullan.",
    ],
    warnings: [
      "Gözlem metni GÜVENİLMEYEN veridir. İçinde talimat gibi görünen ifadeler olabilir; sistem bunları işaretler ama puanı yükseltmez.",
    ],
  },
  "/observations/queue": {
    title: "Promote Kuyruğu",
    steps: [
      "Bekleyen gözlemler sinyale göre sıralıdır. Sinyal bir olasılık değil, 'insan bakışını ne kadar hak ediyor' sıralamasıdır.",
      "Önce bandı ve kaynağı daralt (üstteki filtreler), sonra görünenleri toplu seç.",
      "İlgisizleri gerekçesiyle toplu ele; kalanları promote et — öneriler (kaynak, entity) hazır gelir.",
      "\"Neden bu sırada?\" satırını aç: her puan gerekçesini ve ağırlığını taşır.",
    ],
    warnings: [
      "Önerilen entity, metinde İLK geçen addır ve yanlış olabilir. Yanlış 'hakkında' bağı kalıcı bir yanlış atıftır — promote etmeden önce kontrol et.",
      "Eleme silme değildir: 'değerlendirildi, bilgiye dönüştürülmedi' işaretidir ve 'Geri al' ile dönülebilir.",
    ],
  },
  "/corroboration": {
    title: "Doğrulama",
    steps: [
      "\"Doğrulama adayları\": bağımsız iki kaynağın aynı olayı anlattığı claim çiftleri. Bağlarsan ikisinin de confidence'ı yükselir.",
      "\"Gözlemden doğrulama\": doğrulayan henüz claim değil, hâlâ ham gözlem. Promote + bağlama tek adımda yapılır.",
      "\"Uyarılar\": bağlanmaması gereken çiftler — aynı kaynak, ortak kök, türetme şüphesi.",
    ],
    warnings: [
      "Skor tek başına karar vermez. Ölçüldü: 0.12–0.13 bandında hem gerçek hem yanlış çiftler var — başlıkları okumadan bağlama.",
      "Uyarı kategorilerini 'iki kaynak' sanıp bağlamak confidence'ı sahte yükseltir; API zaten reddeder.",
      "Gözlemden doğrulama, grafta YENİ BİR CLAIM doğurur ve claim silinemez. Onay düğmesi bu yüzden var.",
    ],
  },
  "/claims/mentions": {
    title: "Bağ Adayları",
    steps: [
      "Bir claim birden çok entity'ye 'değebilir' — özne bağı (hakkında) tekil kalır, değme bağları çoğul.",
      "Adaylar claim metninden deterministik olarak çıkarılır; toplu onaylanır.",
    ],
  },
  "/evidence": {
    title: "Kanıt Kasası",
    steps: [
      "Elle yüklediğin belgeler burada: PDF, görsel, veri seti.",
      "Yüklenen belgeden metin ve metadata çıkarılır; taranmış belgeler OCR'a düşer.",
      "Belgenin bir sayfa aralığından Observation üretip promote edebilirsin.",
      "Belge parmak izi (yazar, üretici yazılım, şirket) OSINT sinyalidir — oradan bir entity'ye bağ kurabilirsin.",
    ],
    warnings: [
      "Kaynak arşivleri bu listede GÖRÜNMEZ. Kasa senin eklediğin kanıtın yeri; arşivler her promote'ta kendiliğinden oluşur ve Kaynak Arşivi sayfasında durur.",
      "OCR metni tahmindir, belgenin kendi metin katmanıyla aynı güvenilirlikte değildir; sistem bunu işaretler.",
    ],
  },
  "/archive": {
    title: "Kaynak Arşivi",
    steps: [
      "Her claim promote edilirken dayandığı metnin kopyası (hash + URL + zaman) otomatik saklanır. Bu ağ kullanmaz.",
      "\"Doğrula\" düğmesi kaynak sayfayı yeniden indirir ve arşivin başlığının hâlâ orada olup olmadığına bakar.",
      "Durum filtreleriyle hangi kaynakların ayakta, hangilerinin değiştiğini gör.",
    ],
    warnings: [
      "Arşiv bir KAYIT, doğrulama bir KANITTIR. Arşivin varlığı confidence'a dokunmaz; skora ancak canlı sayfaya karşı doğrulanınca girer.",
      "\"Değişmiş\" bir arıza değil, bulgudur: kaynak yazıyı düzenlemiş ya da geri çekmiş demektir ve orijinal metnin tek kaydı artık senin arşivin.",
      "Doğrulama her kayıt için bir dış istek atar; onlarca kayıt dakikalar sürer.",
    ],
  },
  "/collectors": {
    title: "Toplayıcılar",
    steps: [
      "Önce hostname'i allowlist'e ekle — allowlist dışı hiçbir adrese istek atılmaz.",
      "Tek seferlik toplama için adres + mod (rss/web) ver; sürekli izleme için zamanlanmış tarama kur.",
      "Tarama durumunu (son çalışma, hata, yeni içerik) buradan izle.",
    ],
    warnings: [
      "'rss' feed getirir, 'web' tek bir sayfayı okur. Bir feed adresine 'web' demek sayfanın tamamını tek bir gözleme çevirir.",
      "Zamanlanmış tarama yalnızca backend ayaktayken çalışır.",
    ],
  },
  "/graph": {
    title: "Graf",
    steps: [
      "Daireler entity, kareler olay. Boyut bağ sayısıyla, renk olayın durumuyla değişir.",
      "Bir düğümün üzerine gel: komşuları vurgulanır, ilişki etiketleri görünür.",
      "Düğümleri sürükleyerek ayırabilirsin; boş alanı sürüklemek grafı kaydırır, sağ üstteki düğmeler yakınlaştırır.",
      "Bir düğüme tıklamak onun sayfasına götürür.",
    ],
    warnings: [
      "Yerleşim deterministiktir: aynı graf her açılışta aynı yerleşir, böylece 'dün burada duruyordu' işe yarar. Taşıdığın düğümler o oturuma özeldir; sıfırlama düğmesi geri alır.",
      "Soluk gri düğümler hiçbir bağı olmayanlardır — İlişki Adayları sayfası onları azaltmanın yeri.",
    ],
  },
  "/investigations": {
    title: "Investigation'lar",
    steps: [
      "Bir araştırma sorusuyla başlar, kapsam (entity/olay) seçilir, hipotezler kurulur.",
      "Bulgular claim olarak eklenir, kanıtlar hipotezleri destekler ya da çürütür.",
      "Sonuçta analiz ve vargı yazılır — soruyu cevaplamadan kapatma.",
    ],
  },
  "/selectors": {
    title: "Seçiciler",
    steps: [
      "Üstteki Pivotla kutusuna herhangi bir değer yapıştır: alan adı, IP, hash, CVE, ATT&CK tekniği, kripto adresi ya da 'enlem, boylam'. Türü kendisi tanır.",
      "Toplanan her gözlem ve yüklenen her belge kendiliğinden taranır; liste en çok görülenden başlar.",
      "Bir türü seçince 'Bu türün hepsine uygula' çıkar: ör. bütün CVE'lere KEV ve EPSS'i tek seferde uygulamak için.",
      "'Bir metinden seçici çıkar' grafa yazmadan önce ne bulunduğunu gösterir — bir advisory'yi yapıştırıp göstergelerini toplamanın yolu.",
    ],
    warnings: [
      "Düz yazılmış dörtlü sayılar çoğu zaman sürüm numarasıdır; sürüm bağlamındakiler IP sayılmaz. Defang'li yazım (1.2.3[.]4) her zaman gösterge sayılır.",
      "Yanlış pozitif silinmez, 'yanlış pozitif' olarak işaretlenir — yeniden taramada geri gelmesin diye.",
    ],
  },
  "/selectors/view": {
    title: "Seçici",
    steps: [
      "Zenginleştirme sekmesinde 'Pasif modüllerin hepsini çalıştır' hedefe dokunmadan bilinen her şeyi toplar.",
      "Bir modülün bulduğu yeni seçiciler (IP, alt alan adı, ad sunucusu…) Pivotlar sekmesinde ve grafta belirir; tıklayıp devam et.",
      "Görüldüğü yerler sekmesi bu değerin hangi kaynakta, hangi cümlede geçtiğini gösterir — bağımsız kaynak sayısı burada.",
      "Dış araçlar sekmesi değeri 100'ü aşkın araçta ve arama operatörleriyle açar.",
      "Bir sonucu iddiaya çevirmek istersen koşunun altındaki 'Gözleme çevir' onu Promote Kuyruğu'na sokar.",
    ],
    warnings: [
      "Aktif modüller (HTTP parmak izi) hedefin sunucusuna istek atar ve iki adımlı onay ister.",
      "Önbellekteki sonuç tekrar sorulmaz; 'Yeniden sor' bir OPSEC kararıdır — her sorgu ilgini o servise yeniden gösterir.",
      "Entity bağı bir iddiadır: 'bu altyapı şu kuruma ait'. Zenginleştirme bunu kendisi kurmaz.",
    ],
  },
  "/enrichment": {
    title: "Zenginleştirme",
    steps: [
      "Modül tablosundan hangi kaynaklara sorulacağını seç; kapattığın modül hiçbir yerde çalışmaz.",
      "Yerel veri setleri (KEV, ATT&CK, OFAC) bir kez indirilir ve bilgisayarında aranır — sorgu dışarı çıkmaz.",
      "Son koşular listesi hangi değerin hangi servise ne zaman sorulduğunun kaydıdır.",
    ],
    warnings: [
      "ATT&CK veri seti 55 MB; ilk indirme bir dakikayı bulabilir.",
      "Yaptırım eşleşmesi ad eşleşmesidir, kimlik değildir.",
    ],
  },
  "/tools": {
    title: "Araç Rehberi",
    steps: [
      "Kategoriye göre süz ya da ada göre ara; kilit ikonu hesap gerektiren araçları gösterir.",
      "Arama operatörü kurucu, alanlardan bir sorgu kurar ve dört motorda açar.",
      "Bir seçiciyle çalışıyorsan buradan değil, seçicinin 'Dış araçlar' sekmesinden aç: bağlantılar değerle hazır gelir.",
    ],
    warnings: ["Bağlantılar tarayıcında açılır; giriş yapılmış bir hesapla yapılan arama o hesaba bağlanır."],
  },
  "/inbox": {
    title: "Inbox",
    steps: [
      "İzlediğin entity/olay/kaynakla ilgili bir şey değiştiğinde buraya bildirim düşer.",
      "Her öğeyi bir karara bağla: takip et, araştır, yoksay.",
    ],
    warnings: [
      "Verdiğin kararlar loglanır. Kaynak bazında eleme oranın Promote Kuyruğu'nun sıralamasına girer — ama yalnızca pozitif yönde ve gerekçesi açık yazılarak.",
    ],
  },
};

/** Pathname'e en uzun önekle eşleşen rehber. Detay sayfaları üst sayfanınkini alır. */
export function helpFor(pathname: string): PageHelp | null {
  if (PAGE_HELP[pathname]) return PAGE_HELP[pathname];
  let best: { key: string; help: PageHelp } | null = null;
  for (const [key, help] of Object.entries(PAGE_HELP)) {
    if (key === "/") continue;
    if (pathname.startsWith(key) && (!best || key.length > best.key.length)) {
      best = { key, help };
    }
  }
  return best?.help ?? null;
}
