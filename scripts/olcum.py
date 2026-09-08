"""OsintLab — versiyon sonu ölçüm turu.

`py scripts/olcum.py` (backend ayakta olmalı). Çıktı doğrudan roadmap'e yapıştırılabilir.

**Neden bir script.** v3, v4 ve v5'in kapsamı bir dilek listesinden değil sistemin kendi
durumunun ölçümünden çıkarıldı ve üçü de doğru çıktı. Ama her tur ölçüm ELLE yazıldı, yani
her seferinde biraz farklı sayılar toplandı — v4'te bakılan bir şey v5'te unutulabilirdi ve
trend görünmezdi. Sabit bir ölçüm seti bunu önler: aynı sayılar, aynı sırayla, her turda.

Buradaki hiçbir sayı bir eşik/karar İÇERMEZ. Karar insanındır (Design Principle #7); bu
script yalnızca kararın dayanacağı tabloyu üretir.
"""
import collections
import json
import statistics
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8420"


def get(path: str):
    with urllib.request.urlopen(BASE + path, timeout=300) as r:
        return json.loads(r.read())


def main() -> int:
    try:
        get("/health")
    except (urllib.error.URLError, OSError) as exc:
        print(f"Backend'e ulasilamadi ({BASE}): {exc}\n.\\start.ps1 ile baslat.")
        return 1

    claims = get("/claims")
    ents = get("/entities")
    evs = get("/events")
    srcs = get("/sources")
    invs = get("/investigations")
    inbox = get("/inbox")
    graph = get("/entities/relations/graph")
    queue = get("/observations/queue?limit=1000")
    evidence = get("/evidence")

    print("## Ölçüm — %d claim, %d entity" % (len(claims), len(ents)))
    print()
    print("### Graf")
    print("entity=%d event=%d claim=%d kaynak=%d evidence=%d investigation=%d"
          % (len(ents), len(evs), len(claims), len(srcs), len(evidence), len(invs)))
    print("kenar=%d %s" % (len(graph["edges"]), dict(collections.Counter(e["kind"] for e in graph["edges"]))))
    print("baglantisiz dugum=%d / %d" % (sum(1 for n in graph["nodes"] if n["degree"] == 0), len(graph["nodes"])))

    print()
    print("### Claim ve confidence")
    print("durum=%s" % dict(collections.Counter(c["knowledge_state"] for c in claims)))
    # Confidence'in DÖRT bileşeni ayrı ayrı: hangisinin hiç açılmadığı v3-v5'in her turunda
    # bir faz doğurdu (Faz 17 doğrulama, Faz 24 bağımsızlık, Faz 26 kanıt).
    vals = collections.defaultdict(list)
    zero = collections.Counter()
    no_corroborator = 0
    for c in claims:
        ex = get(f"/claims/{c['id']}/explain")
        for key in ("source_quality", "independence", "evidence", "corroboration"):
            vals[key].append(ex[key])
            if ex[key] == 0:
                zero[key] += 1
        if not ex["corroborated_by"]:
            no_corroborator += 1
    if claims:
        print("ortalama: " + " ".join(f"{k}={statistics.mean(v):.2f}" for k, v in vals.items()))
        print("SIFIR olan claim: " + " ".join(f"{k}={zero[k]}" for k in vals))
        print("dogrulayani olmayan claim=%d / %d" % (no_corroborator, len(claims)))
        lens = sorted(len(c["text"]) for c in claims)
        print("claim metni uzunlugu: min=%d medyan=%d max=%d" % (lens[0], lens[len(lens) // 2], lens[-1]))

    print()
    print("### Kaynak")
    dist = {s["name"]: len(get(f"/sources/{s['id']}/claims")) for s in srcs}
    print("claim dagilimi=%s" % dist)
    if dist:
        top = max(dist.values())
        print("en baskin kaynagin payi=%d/%d (%%%d)" % (top, len(claims), (top * 100 // max(1, len(claims)))))

    print()
    print("### Kuyruk")
    stats = queue["stats"]
    print("bekleyen=%d toplam=%d elenmis=%d yuksek_sinyal=%d"
          % (stats["pending"], stats["total"], stats["dismissed"], stats["high_signal"]))
    scores = collections.Counter(round(i["signal_score"], 1) for i in queue["items"])
    print("skor dagilimi=%s" % dict(sorted(scores.items())))
    print("host=%s" % dict(collections.Counter(i.get("host") or "?" for i in queue["items"])))

    print()
    print("### Bekleyen kararlar (aday kuyruklari)")
    print("entity=%d event=%d iliski=%d bag=%d dogrulama=%d" % (
        len(get("/entities/candidates")),
        len(get("/events/candidates")),
        len(get("/entities/relations/candidates")),
        sum(len(g["candidates"]) for g in get("/claims/mentions/candidates")),
        len(get("/claims/corroboration/candidates?limit=500")),
    ))
    print("inbox=%s" % dict(collections.Counter(i["status"] for i in inbox)))
    print("investigation=%s" % dict(collections.Counter(i["status"] for i in invs)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
