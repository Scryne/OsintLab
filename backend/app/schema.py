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
    """
    CREATE NODE TABLE IF NOT EXISTS Evidence(
        id STRING,
        evidence_type STRING,
        file_path STRING,
        content_hash STRING,
        collected_at TIMESTAMP,
        created_at TIMESTAMP,
        PRIMARY KEY(id)
    )
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS Investigation(
        id STRING,
        title STRING,
        research_question STRING,
        status STRING,
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
]

REL_TABLES = [
    "CREATE REL TABLE IF NOT EXISTS ENTITY_RELATION(FROM Entity TO Entity, relation_type STRING, confidence DOUBLE, valid_from TIMESTAMP, valid_to TIMESTAMP, status STRING)",
    "CREATE REL TABLE IF NOT EXISTS SAME_AS(FROM Entity TO Entity, confidence DOUBLE, status STRING, created_at TIMESTAMP)",
    "CREATE REL TABLE IF NOT EXISTS INVOLVED_IN(FROM Entity TO Event, role STRING)",
    "CREATE REL TABLE IF NOT EXISTS REPORTED_BY(FROM Event TO Source)",
    "CREATE REL TABLE IF NOT EXISTS ASSERTS(FROM Source TO Claim)",
    "CREATE REL TABLE IF NOT EXISTS ABOUT_ENTITY(FROM Claim TO Entity)",
    "CREATE REL TABLE IF NOT EXISTS ABOUT_EVENT(FROM Claim TO Event)",
    "CREATE REL TABLE IF NOT EXISTS SUPPORTS(FROM Evidence TO Claim)",
    "CREATE REL TABLE IF NOT EXISTS CONTRADICTS(FROM Evidence TO Claim)",
    "CREATE REL TABLE IF NOT EXISTS INCLUDES(FROM Investigation TO Entity)",
    "CREATE REL TABLE IF NOT EXISTS INVESTIGATES(FROM Investigation TO Event)",
    "CREATE REL TABLE IF NOT EXISTS PRODUCED(FROM Observation TO Claim)",
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


def init_schema(conn) -> None:
    for stmt in NODE_TABLES:
        conn.execute(stmt)
    for stmt in REL_TABLES:
        conn.execute(stmt)
