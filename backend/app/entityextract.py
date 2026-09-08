"""
Faz 20 — claim metinlerinden deterministik entity adayı çıkarma.

**Neden deterministik, neden LLM değil (kullanıcı kararı, 2026-09-05).** Faz 4'te kurulan
Claude Code agent katmanı bu işi daha iyi yapardı, ama toplanan metni İLK KEZ bir modele
girdi yapardı ve Q22'nin uyardığı prompt injection yüzeyi tam orada açılır. Bu projede
toplanan içerik bugüne kadar hiçbir modele girdi olmadı, yalnızca desen eşleştirmesinden
geçti. Karar Faz 16'daki disiplinin aynısı: önce deterministik kurulur, **kaçırma oranı
gerçek veride ölçülür**, LLM kararı o sayıdan sonra verilir.

**Yöntem: büyük-harf öbeği taraması + filtreler.** Çıplak "ardışık büyük harfli kelimeler"
taraması 2026-09-05'te 79 aday üretmiş ve kalitesi kabaca yarı yarıya çıkmıştı. Aşağıdaki
filtrelerin **hepsi tek bir ilkeden türüyor**: *büyük harf, ancak küçük harfin de mümkün
olduğu yerde kanıttır.* Hiçbiri sezgisel bir eşik değil; her biri metinden okunan bir kanıta
dayanıyor.

1. **Title Case satırlar hiç taranmaz.** Bazı kaynakların başlıkları ("AI Agents Hijacked
   German Wiki to Cheat, OpenAI Delayed Disclosure") her kelimeyi büyük harfle yazıyor;
   orada küçük harf mümkün olmadığı için büyük harf sinyal taşımıyor ve tarama tüm başlığı
   tek bir "ad" sanıyordu. Bedeli: yalnızca başlıkta geçen bir ad kaçırılır — bu, fazın
   kaçırma ölçümünün ölçtüğü şeyin bir parçası.
2. **Cümle başı tek kelime, başka yerde büyük harfle geçmiyorsa elenir.** "Critical",
   "Shortly", "According", "Authorities" — hepsi cümle başındaki büyük harfin özel isim
   sanılmasıydı.
3. **Cümle başındaki taşıyıcı kelime öbekten atılır.** "Introducing GPT-6 Astra",
   "Meet GPT-5.6-Cyber", "In August OpenAI" — üçü de bir fiilin/edatın ardındaki gerçek adla
   birleşmesiydi. Baştaki kelime cümle ortasında hiç büyük harfle görülmemişse atılır.
4. **Tek kelimelik aday, korpusta küçük harfle de geçiyorsa elenir.** "Critical"/"critical".
   Çok kelimeliler bu kuralın dışında: "The New York Times"ın içindeki "times" küçük harfle
   geçiyor diye öbek elenmemeli.
5. **Kapalı bir gürültü listesi** — aylar, gün adları, zaman/atıf kalıpları. Kapalı ve kısa
   tutuldu bilerek: uzayan bir kara liste, ölçmek yerine yamamak olurdu.

**Sınır hataları** ayrıca düzeltildi: sahiplik eki öbeği KAPATIR ("OpenAI's ChatGPT" bir ad
değil, iki ad), noktalama öbeği kapatır ("OpenAI, AIRPPU" iki kurumdur), "and" bağlayıcı
DEĞİLDİR ("Seattle Times and Newsday" iki yayın), ve öbek içi "of/the/for" bağlayıcıları
korunur ("The New York Times" tek parça).

**Sıralama sinyali: kaç claim + kaç FARKLI kaynak.** İkincisi olmadan tek bir haberin özel
ismi ile beş kaynakta geçen bir kurum aynı ağırlıkta görünürdü. Skora çevrilmiyor, iki sayı
ayrı gösteriliyor — Faz 19'daki kararın aynısı.

**Ölçülen kaçırma oranı (2026-09-08, 14 claim'lik örnek): %7.4** — gözle bulunan 27 addan
2'si listede yok. İkisi de adı konabilir birer sınıf: (a) küçük harfle başlayan marka adları
(`xAI`), büyük-harf temelli bir taramanın yapısal körlüğü; (b) yalnızca tireli sıfat
biçiminde geçen adlar ("Israel-based" içindeki `Israel`). LLM kararının girdisi bu sayıdır.
"""
import re
import unicodedata

from app.db import fetch_all

# En az bu kadar harf/rakam içermeyen aday (tek harfli baş harfler, "A.", "I") değerlendirmeye
# girmez — Faz 12'nin MIN_ENTITY_MATCH_LENGTH'iyle aynı gerekçe: kısa desen her metinde tutar.
MIN_CANDIDATE_LENGTH = 3

# Öbeğin İÇİNDE geçebilen küçük harfli bağlayıcılar. Yalnızca iki büyük harfli parçanın
# ARASINDA kabul edilir ("Bank of America"), başta veya sonda değil.
#
# **"and" bilerek YOK.** Ölçüldü: listeye alındığında "OpenAI and Microsoft",
# "Seattle Times and Newsday", "ChatGPT, Grok, and Claude" tek aday olarak çıkıyordu —
# hepsi aslında AYRI entity'ler. "Johnson and Johnson" gibi karşı örnekler var ama nadir;
# bir bağlacın iki adı birleştirme riski, ayırma riskinden büyük.
JOINERS = {"of", "the", "for", "de", "van", "von", "da", "du", "del"}

# Bu işaretlerden biriyle biten kelime öbeği KAPATIR. Ölçümün en sinsi hatası buydu:
# "Meet GPT-5.6-Cyber, OpenAI's cybersecurity model" cümlesinde virgül yok sayılınca
# "GPT-5.6-Cyber OpenAI" diye var olmayan bir ad üretiliyordu. Noktalama, iki özel ismin
# ayrı olduğunun metindeki en açık kanıtı.
_BREAKING_PUNCTUATION = (",", ";", ":", "—", "–", "(", ")", '"', "'", "’")

MONTHS = {
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
}
WEEKDAYS = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}

# Kapalı gürültü listesi: zaman/atıf kalıpları ve tek başına özel isim olamayacak genel
# sözcükler. 2026-09-05 ölçümünde fiilen çıkmış gürültüden türetildi, tahminle şişirilmedi.
NOISE = MONTHS | WEEKDAYS | {
    "according", "shortly", "authorities", "critical", "meanwhile", "however", "update",
    "breaking", "exclusive", "report", "reports", "news", "today", "yesterday", "tomorrow",
    "this", "that", "these", "those", "there", "here", "what", "when", "where", "which",
    "while", "after", "before", "during", "since", "both", "two", "three", "several",
    "new", "the", "and", "but", "for", "with", "from", "into", "over", "under",
}

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_TOKEN = re.compile(r"[A-Za-zÀ-ÿĞÜŞİÖÇğüşıöç0-9][\w&.'’\-]*")
_CAPITALIZED = re.compile(r"^[A-ZÀ-ÝĞÜŞİÖÇ]")
_POSSESSIVE = re.compile(r"['’]s$")


def normalize_key(name: str) -> str:
    """Aday kararlarının kalıcı anahtarı. Aynı ad yeniden çıkarıldığında AYNI anahtara
    düşmeli, yoksa elenmiş bir aday bir sonraki taramada geri gelirdi."""
    text = unicodedata.normalize("NFKC", name).strip()
    text = _POSSESSIVE.sub("", text)
    return re.sub(r"\s+", " ", text).casefold()


def _clean_token(raw: str) -> str:
    token = _POSSESSIVE.sub("", raw)
    return token.strip(".,;:!?()[]\"'’")


def _phrases_in_sentence(sentence: str) -> list[tuple[str, bool]]:
    """Bir cümledeki büyük-harf öbekleri. Dönen ikinci değer: öbek cümlenin BAŞINDA mı
    (orada büyük harf, özel isim olmanın değil, cümle başı olmanın sonucu olabilir)."""
    # Kelimenin KENDİSİ ile ARDINDAN gelen karakter ayrı tutuluyor: `_TOKEN` noktalamayı
    # yakalamıyor, dolayısıyla "OpenAI, AIRPPU" içindeki virgülü ancak sonraki karaktere
    # bakarak görebiliyoruz.
    tokens = [(m.group(0), sentence[m.end() : m.end() + 1]) for m in _TOKEN.finditer(sentence)]
    phrases: list[tuple[str, bool]] = []
    run: list[str] = []
    run_start_index: int | None = None
    pending_joiner: str | None = None

    for index, (raw, next_char) in enumerate(tokens):
        token = _clean_token(raw)
        if not token:
            continue
        if _CAPITALIZED.match(token):
            if pending_joiner is not None:
                run.append(pending_joiner)
                pending_joiner = None
            if not run:
                run_start_index = index
            run.append(token)
            # Öbeği kapatan iki durum:
            # 1. Noktalama ("OpenAI, AIRPPU" iki ayrı kurumdur).
            # 2. Sahiplik eki — "OpenAI's ChatGPT" bir ad değil, iki ad; ek, ismin bittiğinin
            #    dilbilgisel işaretidir. Bunlar birleşmeyince "OpenAI ChatGPT" ve
            #    "Anthropic Claude" gibi hiç var olmayan adlar üretiliyordu.
            if next_char in _BREAKING_PUNCTUATION or _POSSESSIVE.search(raw):
                phrases.append((" ".join(run), run_start_index == 0))
                run, run_start_index, pending_joiner = [], None, None
            continue
        if run and token.lower() in JOINERS and pending_joiner is None:
            # Bağlayıcı ancak ARDINDAN yine büyük harfli bir parça gelirse öbeğe katılır;
            # gelmezse öbek bağlayıcıdan önce kapanır ("Bank of America" vs "Astra of").
            pending_joiner = token.lower()
            continue
        if run:
            phrases.append((" ".join(run), run_start_index == 0))
        run, run_start_index, pending_joiner = [], None, None

    if run:
        phrases.append((" ".join(run), run_start_index == 0))
    return phrases


# Bir parçanın "Title Case" sayılması için gereken en az anlamlı kelime sayısı ve büyük
# harf oranı. Eşikler dar tutuldu: normal düzyazı cümlelerinde 3+ harfli kelimelerin çoğu
# küçük harflidir, bir cümlenin %80'inin büyük harfle başlaması pratikte başlıktır.
TITLE_CASE_MIN_WORDS = 4
TITLE_CASE_RATIO = 0.8


def is_title_case(segment: str) -> bool:
    """Bu parçada büyük harf bir SİNYAL Mİ, yoksa yazım kuralı mı?

    Faz 20'nin en büyük gürültü kaynağı buydu: `Security Affairs` gibi kaynakların
    başlıkları Title Case ("AI Agents Hijacked German Wiki to Cheat, OpenAI Delayed
    Disclosure") ve orada HER kelime büyük harfle başlıyor. Ardışık-büyük-harf taraması
    böyle bir satırda tüm başlığı tek bir "entity adayı" sanıyordu.

    Kural, modülün diğer iki filtresiyle aynı mantığın satır seviyesindeki hali:
    **büyük harf ancak küçük harfin de mümkün olduğu yerde kanıttır.** Title Case bir
    satırda küçük harf mümkün değil, dolayısıyla o satır hiç sinyal taşımıyor ve
    taranmıyor. Başlıkta geçip gövdede geçmeyen bir ad bu yüzden kaçırılır — bu bilinçli
    bir maliyet ve fazın kaçırma ölçümünün ölçtüğü şeyin bir parçası."""
    words = [
        _clean_token(m.group(0))
        for m in _TOKEN.finditer(segment)
    ]
    meaningful = [w for w in words if len(w) >= 3 and w.lower() not in JOINERS and any(ch.isalpha() for ch in w)]
    if len(meaningful) < TITLE_CASE_MIN_WORDS:
        return False
    capitalized = sum(1 for w in meaningful if _CAPITALIZED.match(w))
    return capitalized / len(meaningful) >= TITLE_CASE_RATIO


def extract_phrases(text: str) -> list[tuple[str, bool]]:
    out: list[tuple[str, bool]] = []
    for line in (text or "").split("\n"):
        if is_title_case(line):
            continue
        for sentence in _SENTENCE_SPLIT.split(line):
            if is_title_case(sentence):
                continue
            out.extend(_phrases_in_sentence(sentence))
    return out


def _letters(name: str) -> int:
    return sum(1 for ch in name if ch.isalnum())


def _lowercase_vocabulary(texts: list[str]) -> set[str]:
    """Korpusta KÜÇÜK harfle geçen kelimeler — 2. filtrenin kanıtı."""
    vocab: set[str] = set()
    for text in texts:
        for match in _TOKEN.finditer(text or ""):
            token = _clean_token(match.group(0))
            if token and token[:1].islower():
                vocab.add(token.casefold())
    return vocab


def _known_names(conn) -> set[str]:
    known: set[str] = set()
    for row in fetch_all(conn.execute("MATCH (e:Entity) RETURN e.name AS name, e.aliases AS aliases")):
        for name in [row["name"], *(row["aliases"] or [])]:
            if name:
                known.add(normalize_key(name))
    return known


def decided_keys(conn) -> dict[str, dict]:
    return {
        row["key"]: row
        for row in fetch_all(
            conn.execute(
                "MATCH (c:EntityCandidate) RETURN c.key AS key, c.name AS name, c.status AS status, "
                "c.decided_at AS decided_at, c.promoted_entity_id AS promoted_entity_id"
            )
        )
    }


def entity_candidates(conn, *, include_decided: bool = False) -> list[dict]:
    """Claim metinlerinden çıkarılan entity adayları — sinyale göre sıralı.

    Adaylar SAKLANMAZ, her çağrıda yeniden çıkarılır (deterministik olmasının anlamı bu:
    aynı veri aynı listeyi verir). Saklanan tek şey KARARDIR — elenen bir aday listeye geri
    gelmez. `include_decided=True` ise karar verilmişler de döner (durumlarıyla), çünkü
    "elenen kaybolmaz, işaretlenir" (Q17)."""
    rows = fetch_all(
        conn.execute(
            "MATCH (c:Claim) OPTIONAL MATCH (s:Source)-[:ASSERTS]->(c) "
            "RETURN c.id AS claim_id, c.text AS text, s.id AS source_id, s.name AS source_name"
        )
    )
    if not rows:
        return []

    lowercase_vocab = _lowercase_vocabulary([r["text"] for r in rows])
    known = _known_names(conn)
    decided = decided_keys(conn)

    # --- 1. geçiş: ham öbekler + "hangi kelimeler cümle ORTASINDA büyük harfle geçti"
    #
    # Bu küme filtrelerin ortak kanıtı. Cümle ortasındaki büyük harf, yazım kuralının değil
    # özel ismin sonucudur; bir kelime hiç orada görülmediyse büyük harfi kanıt sayılamaz.
    extracted: list[tuple[dict, list[str], bool]] = []
    mid_sentence_tokens: set[str] = set()
    for row in rows:
        for phrase, at_sentence_start in extract_phrases(row["text"] or ""):
            tokens = phrase.split()
            if not tokens:
                continue
            for token in (tokens[1:] if at_sentence_start else tokens):
                mid_sentence_tokens.add(token.casefold())
            extracted.append((row, tokens, at_sentence_start))

    # --- 2. geçiş: cümle başındaki taşıyıcı kelimeyi öbekten AT
    #
    # "Introducing GPT-6 Astra", "Meet GPT-5.6-Cyber", "In August OpenAI" — üçü de cümle
    # başındaki bir fiilin/edatın ardındaki gerçek adla birleşmesiydi. Baştaki kelime cümle
    # ortasında hiç büyük harfle görülmemişse ya da gürültü listesindeyse atılır; kalan kısım
    # gerçek addır. Tek kelime kalırsa filtreler onu ayrıca değerlendirir.
    buckets: dict[str, dict] = {}
    seen_mid_sentence: set[str] = set()
    for row, tokens, at_sentence_start in extracted:
        if at_sentence_start:
            while len(tokens) > 1 and (
                tokens[0].casefold() not in mid_sentence_tokens or normalize_key(tokens[0]) in NOISE
            ):
                tokens = tokens[1:]
                at_sentence_start = False  # kalan parça artık cümlenin başında değil
        phrase = " ".join(tokens)
        key = normalize_key(phrase)
        if not key or _letters(key) < MIN_CANDIDATE_LENGTH:
            continue
        if not at_sentence_start:
            seen_mid_sentence.add(key)
        text = row["text"] or ""
        bucket = buckets.setdefault(
            key,
            {"name": phrase, "claims": {}, "sources": set(), "source_names": set()},
        )
        bucket["claims"][row["claim_id"]] = {
            "claim_id": row["claim_id"],
            "excerpt": text.split("\n")[0].strip()[:160],
        }
        if row["source_id"]:
            bucket["sources"].add(row["source_id"])
            bucket["source_names"].add(row["source_name"])
        # Öbeğin gösterilecek hali: cümle ortasında görülen yazım tercih edilir.
        if not at_sentence_start:
            bucket["name"] = phrase

    candidates = []
    for key, bucket in buckets.items():
        decision = decided.get(key)
        # Zaten bilinen bir ad aday değildir — AMA hakkında karar verilmiş bir aday, kararın
        # kendisi kayıt olduğu için listede kalabilmeli. Aksi halde "entity'ye çevirdim"
        # kaydı, çevirme işleminin kendisi yüzünden görünmez olurdu (denetim izi kaybı).
        if key in known and decision is None:
            continue
        word_count = len(key.split())
        if key in NOISE and word_count == 1:
            continue
        if word_count == 1:
            # Filtre 1: cümle başı dışında hiç görülmediyse, büyük harf cümle başı
            # olmanın sonucu olabilir — özel isim olduğuna dair kanıt yok.
            if key not in seen_mid_sentence:
                continue
            # Filtre 2: aynı kelime korpusta küçük harfle de geçiyorsa genel bir sözcük.
            if key in lowercase_vocab:
                continue
        if decision and not include_decided:
            continue
        claims = list(bucket["claims"].values())
        candidates.append(
            {
                "key": key,
                "name": bucket["name"],
                "claim_count": len(claims),
                "source_count": len(bucket["sources"]),
                "source_names": sorted(bucket["source_names"]),
                "evidence": claims[:3],
                "status": decision["status"] if decision else "PENDING",
                "promoted_entity_id": decision["promoted_entity_id"] if decision else None,
            }
        )
    candidates.sort(key=lambda c: (-c["source_count"], -c["claim_count"], c["name"].lower()))
    return candidates
