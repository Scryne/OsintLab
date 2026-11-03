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
      "Üstteki sayaçlar sistemin nabzı: bekleyen gözlem, açık aday kuyrukları ve iddia durumları.",
      "Bir sayı beklenmedik biçimde büyüdüyse o kuyruğun sayfasına git — kuyruklar birikince kararlar pahalılaşır.",
      "Günlük akış genelde şu: Terfi Kuyruğu → Doğrulama → Varlık Adayları.",
    ],
  },
  "/entities": {
    title: "Varlıklar",
    steps: [
      "Bir varlığa tıklayınca hakkındaki iddialar, ilişkiler, olaylar ve zaman çizelgesi açılır.",
      "Diğer ad eklemek önemlidir: gözlem eşleştirmesi ad VE diğer adlar üzerinden çalışır, eksik diğer ad sinyali kaybettirir.",
      "Yeni varlığı elle yaratmak yerine Varlık Adayları sayfasından onaylamak daha iyi — orası sistemin kendi çıkardığı adları taşır.",
    ],
    warnings: [
      "Aynı şeyin iki kaydı varsa silme; Olası Eşleşmeler sayfasından birleştir. Silmek geçmişi yok eder (geçmiş değişmez ilkesi).",
    ],
  },
  "/entities/candidates": {
    title: "Varlık Adayları",
    steps: [
      "Liste, iddia metinlerinden çıkarılmış özel isim adaylarıdır — kaç iddiada ve kaç FARKLI kaynakta geçtiğine göre sıralı.",
      "Gerçek bir kurum/kişi/ürün olanları seç, türünü ver ve varlığa çevir.",
      "Geri kalanı toplu ele. Elenen aday bir daha önerilmez ama silinmez — ikinci sekmeden geri alınabilir.",
    ],
    warnings: [
      "Bu sayfa bir 'temizlik işi' değil, kuyruk sinyalinin GİRDİSİ. Bir ad varlık olmadan, o addan bahseden gözlemler Terfi Kuyruğu'nda sinyalsiz görünür — 2026-09-09'da 14 aday onaylanınca kuyruğun yüksek sinyalli öğe sayısı 5'ten 21'e çıktı.",
      "Kısaltma ve bülten kalıpları (KEV, FCEB, CVE ID) ile abonelik katmanları (Pro, Plus, Edu) varlık değildir; ele.",
    ],
  },
  "/entities/relations": {
    title: "İlişki Adayları",
    steps: [
      "Aynı iddiada birlikte geçen varlık çiftleri önerilir. Öneri, ilişkinin VAR olduğunu söylemez — birlikte anıldıklarını söyler.",
      "İlişkinin TÜRÜNÜ sen verirsin (satın aldı, ortak, rakip…); sistem tür tahmin etmez.",
      "İlişkisiz olduğuna karar verdiklerini ele — o çift bir daha önerilmez.",
    ],
  },
  "/entities/same-as": {
    title: "Olası Eşleşmeler",
    steps: [
      "Aynı şeyin iki ayrı kaydı olabilecek varlık çiftleri gösterilir (ad benzerliği + ortak bağlam).",
      "Gerçekten aynıysa birleştir; değilse ele.",
    ],
    warnings: [
      "Birleştirme kayıt silmez, bir aynılık bağı kurar. İki kaydın geçmişi de durmaya devam eder.",
    ],
  },
  "/events": {
    title: "Olaylar",
    steps: [
      "Olaylar, birden çok iddianın anlattığı tek bir gerçek dünya olayıdır (bir sızıntı, bir duyuru, bir dava).",
      "\"Olay adayı\" sekmesi, birbirini doğrulayan iddia kümelerinden türetilir — hazır bir olay önerisidir.",
      "Bir olaya iddia bağlamak, o iddianın güven skorunu olaya taşır.",
    ],
    warnings: [
      "Bir iddia ya bir varlık ya bir olay hakkındadır, ikisi birden değil. İddiayı olaya bağlamak varlık bağını siler; sistem varlığı olaya katılımcı olarak bağlayarak bunu telafi eder.",
      "Olayın güven skoru elle girilmez — en iyi desteklenen iddiasından türetilir.",
    ],
  },
  "/sources": {
    title: "Kaynaklar",
    steps: [
      "Her kaynağın bir güvenilirlik değeri var ve güven skorunun %40'ı doğrudan buradan gelir.",
      "Bir kaynak başka bir kaynaktan türüyorsa (içerik paylaşımı, ajans) bunu köken olarak işaretle.",
    ],
    warnings: [
      "Köken kozmetik değil: aynı köke inen iki kaynak bağımsız doğrulama SAYILMAZ. İşaretlenmemiş bir türetme güven skorunu sahte yükseltir.",
    ],
  },
  "/observations": {
    title: "Gözlemler",
    steps: [
      "Ham veri katmanı: toplayıcıların getirdiği ve belgelerden çıkarılan her şey burada, hiçbir yorum katılmadan.",
      "Bir gözlemi bilgiye çevirmek için terfi ettir; toplu iş için Terfi Kuyruğu'nu kullan.",
    ],
    warnings: [
      "Gözlem metni GÜVENİLMEYEN veridir. İçinde talimat gibi görünen ifadeler olabilir; sistem bunları işaretler ama puanı yükseltmez.",
    ],
  },
  "/observations/queue": {
    title: "Terfi Kuyruğu",
    steps: [
      "Bekleyen gözlemler sinyale göre sıralıdır. Sinyal bir olasılık değil, 'insan bakışını ne kadar hak ediyor' sıralamasıdır.",
      "Önce bandı ve kaynağı daralt (üstteki filtreler), sonra görünenleri toplu seç.",
      "İlgisizleri gerekçesiyle toplu ele; kalanları terfi ettir — öneriler (kaynak, varlık) hazır gelir.",
      "\"Neden bu sırada?\" satırını aç: her puan gerekçesini ve ağırlığını taşır.",
    ],
    warnings: [
      "Önerilen varlık, metinde İLK geçen addır ve yanlış olabilir. Yanlış 'hakkında' bağı kalıcı bir yanlış atıftır — terfi ettirmeden önce kontrol et.",
      "Eleme silme değildir: 'değerlendirildi, bilgiye dönüştürülmedi' işaretidir ve 'Geri al' ile dönülebilir.",
    ],
  },
  "/corroboration": {
    title: "Doğrulama",
    steps: [
      "\"Doğrulama adayları\": bağımsız iki kaynağın aynı olayı anlattığı iddia çiftleri. Bağlarsan ikisinin de güven skoru yükselir.",
      "\"Gözlemden doğrulama\": doğrulayan henüz iddia değil, hâlâ ham gözlem. Terfi + bağlama tek adımda yapılır.",
      "\"Uyarılar\": bağlanmaması gereken çiftler — aynı kaynak, ortak kök, türetme şüphesi.",
    ],
    warnings: [
      "Skor tek başına karar vermez. Ölçüldü: 0.12–0.13 bandında hem gerçek hem yanlış çiftler var — başlıkları okumadan bağlama.",
      "Uyarı kategorilerini 'iki kaynak' sanıp bağlamak güven skorunu sahte yükseltir; sunucu zaten reddeder.",
      "Gözlemden doğrulama, grafta YENİ BİR İDDİA doğurur ve iddia silinemez. Onay düğmesi bu yüzden var.",
    ],
  },
  "/claims/mentions": {
    title: "Bağ Adayları",
    steps: [
      "Bir iddia birden çok varlığa 'değebilir' — özne bağı (hakkında) tekil kalır, değme bağları çoğul.",
      "Adaylar iddia metninden kurala dayalı (deterministik) olarak çıkarılır; toplu onaylanır.",
    ],
  },
  "/evidence": {
    title: "Kanıt Kasası",
    steps: [
      "Elle yüklediğin belgeler burada: PDF, görsel, veri seti.",
      "Yüklenen belgeden metin ve üst veri çıkarılır; taranmış belgeler OCR'a düşer.",
      "Belgenin bir sayfa aralığından gözlem üretip terfi ettirebilirsin.",
      "Belge parmak izi (yazar, üretici yazılım, şirket) OSINT sinyalidir — oradan bir varlığa bağ kurabilirsin.",
    ],
    warnings: [
      "Kaynak arşivleri bu listede GÖRÜNMEZ. Kasa senin eklediğin kanıtın yeri; arşivler her terfide kendiliğinden oluşur ve Kaynak Arşivi sayfasında durur.",
      "OCR metni tahmindir, belgenin kendi metin katmanıyla aynı güvenilirlikte değildir; sistem bunu işaretler.",
    ],
  },
  "/archive": {
    title: "Kaynak Arşivi",
    steps: [
      "Her iddia terfi ettirilirken dayandığı metnin kopyası (hash + URL + zaman) otomatik saklanır. Bu ağ kullanmaz.",
      "\"Doğrula\" düğmesi kaynak sayfayı yeniden indirir ve arşivin başlığının hâlâ orada olup olmadığına bakar.",
      "Durum filtreleriyle hangi kaynakların ayakta, hangilerinin değiştiğini gör.",
    ],
    warnings: [
      "Arşiv bir KAYIT, doğrulama bir KANITTIR. Arşivin varlığı güven skoruna dokunmaz; skora ancak canlı sayfaya karşı doğrulanınca girer.",
      "\"Değişmiş\" bir arıza değil, bulgudur: kaynak yazıyı düzenlemiş ya da geri çekmiş demektir ve orijinal metnin tek kaydı artık senin arşivin.",
      "Doğrulama her kayıt için bir dış istek atar; onlarca kayıt dakikalar sürer.",
    ],
  },
  "/collectors": {
    title: "Toplayıcılar",
    steps: [
      "Önce sunucu adını izin listesine ekle — izin listesi dışındaki hiçbir adrese istek atılmaz.",
      "Tek seferlik toplama için adres + mod (rss/web) ver; sürekli izleme için zamanlanmış tarama kur.",
      "Tarama durumunu (son çalışma, hata, yeni içerik) buradan izle.",
    ],
    warnings: [
      "'rss' besleme getirir, 'web' tek bir sayfayı okur. Bir besleme adresine 'web' demek sayfanın tamamını tek bir gözleme çevirir.",
      "Zamanlanmış tarama yalnızca backend ayaktayken çalışır.",
    ],
  },
  "/graph": {
    title: "Graf",
    steps: [
      "Daireler varlık, kareler olay. Boyut bağ sayısıyla, renk olayın durumuyla değişir.",
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
    title: "Soruşturmalar",
    steps: [
      "Bir araştırma sorusuyla başlar, kapsam (varlık/olay) seçilir, hipotezler kurulur.",
      "Bulgular iddia olarak eklenir, kanıtlar hipotezleri destekler ya da çürütür.",
      "Sonuçta analiz ve vargı yazılır — soruyu cevaplamadan kapatma.",
      "İki ya da daha fazla hipotez ve kanıt olunca ACH (rakip hipotezler analizi) matrisi açılır: en olası hipotez en az tutarsız olandır; boş hücreleri doldur.",
      "Rapor: TLP etiketini seç, yazdırılabilir raporu aç (tarayıcıdan PDF'e) ya da Markdown indir.",
    ],
    warnings: ["Rapor deterministiktir; yorum yalnızca senin Analiz ve Sonuç metnindir — orada kaynağın söylediğiyle kendi çıkarımını ayır."],
  },
  "/selectors": {
    title: "Seçiciler",
    steps: [
      "Üstteki Çapraz sorgula kutusuna herhangi bir değer yapıştır: alan adı, IP, hash, CVE, ATT&CK tekniği, kripto adresi ya da 'enlem, boylam'. Türü kendisi tanır.",
      "Toplanan her gözlem ve yüklenen her belge kendiliğinden taranır; liste en çok görülenden başlar.",
      "Bir türü seçince 'Bu türün hepsine uygula' çıkar: ör. bütün CVE'lere KEV ve EPSS'i tek seferde uygulamak için.",
      "'Bir metinden seçici çıkar' grafa yazmadan önce ne bulunduğunu gösterir — bir güvenlik bültenini yapıştırıp göstergelerini toplamanın yolu.",
    ],
    warnings: [
      "Düz yazılmış dörtlü sayılar çoğu zaman sürüm numarasıdır; sürüm bağlamındakiler IP sayılmaz. Zararsızlaştırılmış yazım (1.2.3[.]4) her zaman gösterge sayılır.",
      "Yanlış pozitif silinmez, 'yanlış pozitif' olarak işaretlenir — yeniden taramada geri gelmesin diye.",
    ],
  },
  "/selectors/view": {
    title: "Seçici",
    steps: [
      "Zenginleştirme sekmesinde 'Pasif modüllerin hepsini çalıştır' hedefe dokunmadan bilinen her şeyi toplar.",
      "Bir modülün bulduğu yeni seçiciler (IP, alt alan adı, ad sunucusu…) Bağlantılar sekmesinde ve grafta belirir; tıklayıp devam et.",
      "Görüldüğü yerler sekmesi bu değerin hangi kaynakta, hangi cümlede geçtiğini gösterir — bağımsız kaynak sayısı burada.",
      "Dış araçlar sekmesi değeri 100'ü aşkın araçta ve arama operatörleriyle açar.",
      "Bir sonucu iddiaya çevirmek istersen koşunun altındaki 'Gözleme çevir' onu Terfi Kuyruğu'na sokar.",
    ],
    warnings: [
      "Aktif modüller (HTTP parmak izi) hedefin sunucusuna istek atar ve iki adımlı onay ister.",
      "Önbellekteki sonuç tekrar sorulmaz; 'Yeniden sor' bir OPSEC kararıdır — her sorgu ilgini o servise yeniden gösterir.",
      "Varlık bağı bir iddiadır: 'bu altyapı şu kuruma ait'. Zenginleştirme bunu kendisi kurmaz.",
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
  "/claims/view": {
    title: "İddia",
    steps: [
      "Üstteki rozetler: doğrulama durumu ve NATO/Admiralty kodu (harf kaynağın güvenilirliği, rakam bilginin teyit düzeyi).",
      "\"Bu skor nereden geliyor?\" güven skorunun dört bileşenini açar.",
      "\"Bu iddiayı başka kim söylüyor?\" haber araması yapar; bağımsız bir yayıncının haberini Gözlem düğmesiyle ekle — Doğrulama ekranı onu bu iddiaya önerir.",
    ],
    warnings: ["İddia metni toplanan kaynaktan gelir ve güvenilmeyen veridir; içindeki talimat-benzeri ifadeler uygulanmaz."],
  },
  "/inbox": {
    title: "Gelen Kutusu",
    steps: [
      "İzlediğin varlık/olay/kaynakla ilgili bir şey değiştiğinde buraya bildirim düşer.",
      "Her öğeyi bir karara bağla: takip et, araştır, yoksay.",
    ],
    warnings: [
      "Verdiğin kararlar loglanır. Kaynak bazında eleme oranın Terfi Kuyruğu'nun sıralamasına girer — ama yalnızca pozitif yönde ve gerekçesi açık yazılarak.",
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
