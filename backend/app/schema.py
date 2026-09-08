"""
KùzuDB şema tanımı — Core Knowledge Model (docs/Proje-Fikri.md bölüm 6).

Alan isimlendirmesi denetim aşaması kararlarına dayanır:
- knowledge_state / confidence: Q3 (hibrit durum etiketi + sayısal confidence)
- valid_from / valid_to: Q9 (temporal versiyonlama — eski kayıt asla silinmez)
- status alanları (ör. ENTITY_RELATION.status): ACTIVE / CONTRADICTED / SUPERSEDED
"""

NODE_TABLES = [
    """
    CREATE NODE TABLE IF NOT EXISTS Entity(
        id STRING,
        entity_type STRING,
        name STRING,
        aliases STRING[],
        created_at TIMESTAMP,
        PRIMARY KEY(id)
    )
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS Event(
        id STRING,
        title STRING,
        event_type STRING,
        occurred_at TIMESTAMP,
        location STRING,
        knowledge_state STRING,
        confidence DOUBLE,
        created_at TIMESTAMP,
        PRIMARY KEY(id)
    )
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS Source(
        id STRING,
        name STRING,
        source_type STRING,
        url STRING,
        reliability DOUBLE,
        created_at TIMESTAMP,
        PRIMARY KEY(id)
    )
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS Claim(
        id STRING,
        text STRING,
        knowledge_state STRING,
        confidence DOUBLE,
        valid_from TIMESTAMP,
        valid_to TIMESTAMP,
        created_at TIMESTAMP,
        updated_at TIMESTAMP,
        PRIMARY KEY(id)
    )
    """,
    # Faz 15.1 (DOCINT): extraction_* alanlari belgenin ICINE bakmanin sonucu. Faz 13'te
    # Evidence yalnizca hash + yol tutuyordu, yani dosya sisteme giriyor ama icindeki bilgi
    # grafa hic ulasmiyordu.
    #
    # `extraction_status` neden ayri bir alan: Faz 15 spike'inin en onemli bulgusu, taranmis
    # (goruntu-only) bir PDF'in HATA VERMEDEN 0 karakter dondurmesiydi. Tek bir "metin var mi"
    # kontrolu, boyle bir belgeyi "islendi, metni bos" diye kaydederdi -- sessiz veri kaybi.
    # Durumlar `app/docint.py`de: DONE / NO_TEXT_LAYER / ENCRYPTED / CORRUPT / UNSUPPORTED /
    # FAILED, arti kuyruk durumlari PENDING / RUNNING.
    #
    # `pages_done` + `page_count` ilerleme icin: spike 492 sayfalik bir belgenin 29,9 sn
    # surdugunu olctu, bu sure boyunca kullanici nerede olundugunu gorebilmeli.
    """
    CREATE NODE TABLE IF NOT EXISTS Evidence(
        id STRING,
        evidence_type STRING,
        file_path STRING,
        content_hash STRING,
        collected_at TIMESTAMP,
        created_at TIMESTAMP,
        extraction_status STRING,
        extracted_text STRING,
        doc_metadata STRING,
        page_count INT64,
        pages_done INT64,
        extraction_error STRING,
        extracted_at TIMESTAMP,
        injection_hits STRING,
        text_source STRING,
        ocr_confidence DOUBLE,
        ocr_lang STRING,
        PRIMARY KEY(id)
    )
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS Investigation(
        id STRING,
        title STRING,
        research_question STRING,
        status STRING,
        analysis STRING,
        conclusion STRING,
        concluded_at TIMESTAMP,
        created_at TIMESTAMP,
        updated_at TIMESTAMP,
        PRIMARY KEY(id)
    )
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS Observation(
        id STRING,
        raw_content STRING,
        observed_at TIMESTAMP,
        promoted BOOLEAN,
        source_url STRING,
        created_at TIMESTAMP,
        injection_hits STRING,
        text_source STRING,
        PRIMARY KEY(id)
    )
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS Hypothesis(
        id STRING,
        text STRING,
        status STRING,
        created_at TIMESTAMP,
        PRIMARY KEY(id)
    )
    """,
    # Faz 13 (madde 30): `analysis` / `conclusion` / `concluded_at` Workspace zincirinin son
    # iki adımı. Mevcut veritabanlarına COLUMN_ADDITIONS ile ekleniyor (dosya sonuna bak) —
    # buradaki tanım yalnızca temiz kurulumda geçerli. (KùzuDB DDL'i satır içi yorum kabul
    # etmiyor, bu yüzden not tablonun dışında.)
    # Faz 7 — Continuous Monitoring (madde 22). target_type/target_id polimorfik referans:
    # KùzuDB'de heterojen FROM/TO tek bir rel table'da desteklenmediği için (Entity/Event/
    # Investigation'ın 3'ü de izlenebilir olduğundan), tip+id çiftini tutan bağımsız bir node
    # tercih edildi — tek kullanıcılı bir sistemde "kim izliyor" alanına gerek yok.
    """
    CREATE NODE TABLE IF NOT EXISTS Monitor(
        id STRING,
        target_type STRING,
        target_id STRING,
        label STRING,
        active BOOLEAN,
        created_at TIMESTAMP,
        PRIMARY KEY(id)
    )
    """,
    # Faz 12 — Zamanlanmış Otomatik Tarama. Bir ScanSchedule her zaman bir Source'a aittir
    # (SCANS_SOURCE): tarama sonucu Observation'ların provenance'ı o Source'tur ve Inbox
    # bildiriminin izlenen hedefi (Monitor target_type='Source') yine odur. Kaynaksız bir
    # zamanlanmış tarama, kimseye ait olmayan içerik üretirdi.
    #
    # Çalışma durumu (last_*) şemada tutuluyor, ayrı bir log dosyasında değil: "bu tarama
    # ne zaman çalıştı, ne buldu, neden patladı" sorusu arayüzden ve vault'tan
    # cevaplanabilir olmalı (Faz 11'in tekrar eden dersi: sistem yaptığı şeyi söyleyebilmeli).
    """
    CREATE NODE TABLE IF NOT EXISTS ScanSchedule(
        id STRING,
        url STRING,
        mode STRING,
        interval_minutes INT64,
        item_limit INT64,
        since_days INT64,
        label STRING,
        active BOOLEAN,
        last_run_at TIMESTAMP,
        last_status STRING,
        last_error STRING,
        last_new_count INT64,
        consecutive_failures INT64,
        created_at TIMESTAMP,
        PRIMARY KEY(id)
    )
    """,
    # Faz 7 — Intelligence Inbox (madde 27) + Q14 davranış loglama. status: NEW (varsayılan)
    # veya kullanıcının aksiyonu (IGNORED/CONFIRMED/REJECTED/INVESTIGATING/FOLLOWED) —
    # loglanır ama v1'de prioritization'ı otomatik etkilemez (Q13/Q14 kararı).
    """
    CREATE NODE TABLE IF NOT EXISTS InboxItem(
        id STRING,
        item_type STRING,
        priority STRING,
        title STRING,
        detail STRING,
        target_type STRING,
        target_id STRING,
        monitor_id STRING,
        status STRING,
        created_at TIMESTAMP,
        actioned_at TIMESTAMP,
        PRIMARY KEY(id)
    )
    """,
    # Faz 20 — entity adayı kararlarının hafızası. Adayların KENDİSİ burada saklanmaz;
    # onlar her seferinde claim metinlerinden yeniden çıkarılır (deterministik, bkz.
    # app/entityextract.py). Burada duran şey KARARDIR: elenen bir aday bir daha
    # önerilmemeli, yoksa aynı 40 gürültü her taramadan sonra yeniden karşına çıkar (Q17).
    #
    # Anahtar normalize edilmiş AD ("openai's" -> "openai"), uuid değil: aday yeniden
    # çıkarıldığında aynı anahtara düşmesi gerekiyor, aksi halde karar kaybolurdu.
    """
    CREATE NODE TABLE IF NOT EXISTS EntityCandidate(
        key STRING,
        name STRING,
        status STRING,
        decided_at TIMESTAMP,
        promoted_entity_id STRING,
        PRIMARY KEY(key)
    )
    """,
]

REL_TABLES = [
    "CREATE REL TABLE IF NOT EXISTS ENTITY_RELATION(FROM Entity TO Entity, relation_type STRING, confidence DOUBLE, valid_from TIMESTAMP, valid_to TIMESTAMP, status STRING)",
    "CREATE REL TABLE IF NOT EXISTS SAME_AS(FROM Entity TO Entity, confidence DOUBLE, status STRING, created_at TIMESTAMP)",
    "CREATE REL TABLE IF NOT EXISTS INVOLVED_IN(FROM Entity TO Event, role STRING)",
    "CREATE REL TABLE IF NOT EXISTS REPORTED_BY(FROM Event TO Source)",
    "CREATE REL TABLE IF NOT EXISTS ASSERTS(FROM Source TO Claim)",
    "CREATE REL TABLE IF NOT EXISTS ABOUT_ENTITY(FROM Claim TO Entity)",
    # Faz 21 — claim'in DEĞDİĞİ entity'ler. `ABOUT_ENTITY`den ayrı bir ilişki olması bilinçli:
    # o, claim'in ÖZNESİ ve tekil (confidence, recall ve Faz 18'in olay türetmesi buna
    # dayanıyor). Ölçüldü (2026-09-08): bir claim ortalama 2.48 entity'ye değiyor, yani tek
    # bir bağ değmelerin %60'ını yapısal olarak temsil edemiyordu.
    #
    # `status` REJECTED de olabilir: reddedilen bir öneri SİLİNMEZ, işaretlenir — yoksa aynı
    # öneri her aday hesabında geri gelirdi (Faz 20'nin EntityCandidate kararının aynısı).
    # `matched_on` hangi ad/alias üzerinden eşleştiğini saklar (Auditability).
    "CREATE REL TABLE IF NOT EXISTS MENTIONS(FROM Claim TO Entity, matched_on STRING, status STRING, created_at TIMESTAMP)",
    "CREATE REL TABLE IF NOT EXISTS ABOUT_EVENT(FROM Claim TO Event)",
    "CREATE REL TABLE IF NOT EXISTS SUPPORTS(FROM Evidence TO Claim)",
    "CREATE REL TABLE IF NOT EXISTS CONTRADICTS(FROM Evidence TO Claim)",
    "CREATE REL TABLE IF NOT EXISTS INCLUDES(FROM Investigation TO Entity)",
    # Faz 15.3 (DOCINT): belge metadata'sindaki bir alanin (ornegin /Author) grafta bilinen
    # bir Entity'ye isaret ettigi, KULLANICI ONAYIYLA burada kaydedilir.
    #
    # `field` ve `value` kenarin uzerinde: hangi alanin bu bagi dogurdugu ve o andaki ham
    # degeri kaybolmamali. Yalnizca "bu belge su kuruma ait" demek, iddianin nereden
    # geldigini siler; "/Author alani 'Joint Task Force' diyordu" demek denetlenebilir.
    "CREATE REL TABLE IF NOT EXISTS FINGERPRINT_ENTITY(FROM Evidence TO Entity, field STRING, value STRING, created_at TIMESTAMP)",
    "CREATE REL TABLE IF NOT EXISTS INVESTIGATES(FROM Investigation TO Event)",
    "CREATE REL TABLE IF NOT EXISTS PRODUCED(FROM Observation TO Claim)",
    # Faz 15.2 (DOCINT): bir gozlem bir belgenin BELIRLI SAYFALARINDAN geldiyse bagi
    # burada durur. Sayfa bilgisi kenarin uzerinde: "hangi belgeden" yetmez, iddianin
    # 492 sayfalik bir raporun neresinden ciktigi kaybolursa kanit zinciri kopar
    # (Faz 6 lineage disiplininin belge tarafi).
    "CREATE REL TABLE IF NOT EXISTS EXTRACTED_FROM(FROM Observation TO Evidence, page_from INT64, page_to INT64, created_at TIMESTAMP)",
    # Faz 2 — Q4 confidence girdisi (corroboration) ve Q9 (temporal versiyonlama / çelişki)
    "CREATE REL TABLE IF NOT EXISTS CORROBORATES(FROM Claim TO Claim)",
    "CREATE REL TABLE IF NOT EXISTS CLAIM_CONTRADICTS(FROM Claim TO Claim, status STRING, detected_at TIMESTAMP)",
    "CREATE REL TABLE IF NOT EXISTS SUPERSEDES(FROM Claim TO Claim, at TIMESTAMP)",
    # Faz 3 — Investigation & Hypothesis System (Q16/Q17)
    "CREATE REL TABLE IF NOT EXISTS HAS_HYPOTHESIS(FROM Investigation TO Hypothesis)",
    "CREATE REL TABLE IF NOT EXISTS HYPOTHESIS_EVIDENCE(FROM Evidence TO Hypothesis, stance STRING)",
    "CREATE REL TABLE IF NOT EXISTS HAS_FINDING(FROM Investigation TO Claim)",
    # Q17: sadece kapanışta doğrulanmış (SUPPORTED/CORROBORATED/HIGH_CONFIDENCE) findings
    # bu ilişkiyi kazanır — "long-term memory'ye promote edildi" sinyali budur.
    "CREATE REL TABLE IF NOT EXISTS VALIDATED_FINDING(FROM Investigation TO Claim, promoted_at TIMESTAMP)",
    # Faz 6 — Q6 Source Independence Lineage Graph. FROM = türetilmiş (daha sonraki/downstream)
    # Source, TO = türetildiği (daha önceki/upstream) Source. Zincir: Site B -[:DERIVED_FROM]->
    # Site A -[:DERIVED_FROM]-> Agency.
    "CREATE REL TABLE IF NOT EXISTS DERIVED_FROM(FROM Source TO Source, method STRING, similarity DOUBLE, shared_agencies STRING, detected_at TIMESTAMP)",
    # Faz 12 — bir zamanlanmış taramanın hangi Source adına içerik topladığı.
    "CREATE REL TABLE IF NOT EXISTS SCANS_SOURCE(FROM ScanSchedule TO Source)",
]


# Faz 13 — şema göçü.
#
# `CREATE NODE TABLE IF NOT EXISTS` var olan bir tabloya kolon EKLEMEZ: tablo zaten varsa
# ifade sessizce hiçbir şey yapmaz. Yani yukarıdaki tanıma yeni bir alan yazmak, boş bir
# veritabanında çalışır ama mevcut veritabanında SESSİZCE etkisiz kalır — kod alanı okumaya
# çalıştığında patlar. Bu liste o boşluğu kapatıyor: `ALTER TABLE ... ADD IF NOT EXISTS`
# idempotent (gerçek KùzuDB'ye karşı doğrulandı) ve mevcut satırlara NULL yazar.
#
# Yeni bir alan eklerken: NODE_TABLES'taki tanımı da güncelle (temiz kurulum için) VE
# buraya bir satır ekle (mevcut veritabanları için). İkisi birden gerekiyor.
COLUMN_ADDITIONS = [
    # Faz 13 — Investigation Workspace'in son iki adımı (madde 30). Bunlar olmadan bir
    # investigation, "cevap neydi" hiç kaydedilmeden CLOSED'a geçebiliyordu.
    "ALTER TABLE Investigation ADD IF NOT EXISTS analysis STRING",
    "ALTER TABLE Investigation ADD IF NOT EXISTS conclusion STRING",
    "ALTER TABLE Investigation ADD IF NOT EXISTS concluded_at TIMESTAMP",
    # Faz 15.1 (DOCINT) -- belgeden cikarilan metin/metadata ve cikarma durumu.
    "ALTER TABLE Evidence ADD IF NOT EXISTS extraction_status STRING",
    "ALTER TABLE Evidence ADD IF NOT EXISTS extracted_text STRING",
    "ALTER TABLE Evidence ADD IF NOT EXISTS doc_metadata STRING",
    "ALTER TABLE Evidence ADD IF NOT EXISTS page_count INT64",
    "ALTER TABLE Evidence ADD IF NOT EXISTS pages_done INT64",
    "ALTER TABLE Evidence ADD IF NOT EXISTS extraction_error STRING",
    "ALTER TABLE Evidence ADD IF NOT EXISTS extracted_at TIMESTAMP",
    # Faz 15.2 (Q22): belgede/metadata'da bulunan talimat-gorunumlu ifadeler (JSON).
    "ALTER TABLE Evidence ADD IF NOT EXISTS injection_hits STRING",
    # Faz 15.2: uyari metinle birlikte seyahat etmeli. Promote karari gozlem uzerinde
    # veriliyor; uyari yalnizca kaynak belgede dursaydi, kullanici bir iddiayi Knowledge
    # Graph'a yukseltirken onu gormeyebilirdi.
    "ALTER TABLE Observation ADD IF NOT EXISTS injection_hits STRING",
    # Faz 15.4: metnin kaynagi -- "extracted" (belgenin kendi metin katmani) ya da "ocr"
    # (goruntuden TAHMIN). Ikisi ayni guvenilirlikte degil ve bu bilgi, 15.2'de injection
    # uyarisi icin ogrenilen dersle ayni sebeple gozleme kadar tasiniyor: isaret metinle
    # birlikte seyahat etmezse, promote kararinin verildigi yerde gorunmez olur.
    "ALTER TABLE Evidence ADD IF NOT EXISTS text_source STRING",
    "ALTER TABLE Evidence ADD IF NOT EXISTS ocr_confidence DOUBLE",
    "ALTER TABLE Evidence ADD IF NOT EXISTS ocr_lang STRING",
    "ALTER TABLE Observation ADD IF NOT EXISTS text_source STRING",
    # Faz 16 (Promote Kuyrugu): "degerlendirildi, bilgiye donusturulmedi". Elenen gozlem
    # SILINMEZ -- Faz 3'un Q17 disiplini (yukselmeyen sey de kaybolmaz) ve History Is
    # Immutable ilkesi geregi. Bu isaret ayrica elenmis gozlemin kuyruga geri dusmemesi
    # icin gerekli: promoted=false tek basina "henuz bakilmadi" demek zorundaydi, artik
    # "bakildi, gecmedi" ondan ayrilabiliyor.
    "ALTER TABLE Observation ADD IF NOT EXISTS dismissed BOOLEAN",
    "ALTER TABLE Observation ADD IF NOT EXISTS dismissed_at TIMESTAMP",
    "ALTER TABLE Observation ADD IF NOT EXISTS dismiss_reason STRING",
]


def init_schema(conn) -> None:
    for stmt in NODE_TABLES:
        conn.execute(stmt)
    for stmt in REL_TABLES:
        conn.execute(stmt)
    for stmt in COLUMN_ADDITIONS:
        conn.execute(stmt)
