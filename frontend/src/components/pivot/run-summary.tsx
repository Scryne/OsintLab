"use client";

/* eslint-disable @typescript-eslint/no-explicit-any --
 * Zenginleştirme özeti modüle göre şekil değiştiren bir JSON (backend'de de katı bir modele
 * bağlanmadı). Her görünüm kendi modülünün alanlarını okur; bilinmeyen modül ham JSON'a düşer. */

import { useState } from "react";
import { AlertTriangle, ExternalLink, Plus } from "lucide-react";
import { api } from "@/lib/api";
import type { EnrichmentRun } from "@/lib/types-pivot";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";

type S = Record<string, any>;

function fmtDate(value: unknown): string | null {
  if (!value || typeof value !== "string") return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString("tr-TR", { dateStyle: "medium", timeStyle: "short" });
}

function fmtDay(value: unknown): string | null {
  if (!value || typeof value !== "string") return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleDateString("tr-TR", { dateStyle: "medium" });
}

export function Facts({ rows }: { rows: [string, React.ReactNode][] }) {
  const shown = rows.filter(([, v]) => v !== null && v !== undefined && v !== "" && !(Array.isArray(v) && v.length === 0));
  if (!shown.length) return null;
  return (
    <dl className="grid grid-cols-[minmax(7rem,auto)_1fr] gap-x-4 gap-y-1.5 text-sm">
      {shown.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-text-tertiary">{k}</dt>
          <dd className="min-w-0 break-words text-foreground">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function Mono({ children }: { children: React.ReactNode }) {
  return <span className="font-mono text-xs">{children}</span>;
}

function Chips({ items, mono = true }: { items: (string | number)[]; mono?: boolean }) {
  if (!items?.length) return <span className="text-text-tertiary">—</span>;
  return (
    <span className="flex flex-wrap gap-1">
      {items.map((it) => (
        <span key={String(it)} className={cn("rounded border border-border bg-surface px-1.5 py-0.5 text-xs", mono && "font-mono")}>
          {it}
        </span>
      ))}
    </span>
  );
}

function ExtLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer nofollow"
      className="inline-flex items-center gap-1 text-brand-accent-text underline decoration-brand-accent/30 underline-offset-2 hover:decoration-brand-accent"
    >
      {children}
      <ExternalLink aria-hidden className="h-3 w-3" />
    </a>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <h4 className="text-[11px] font-medium uppercase tracking-wide text-text-tertiary">{title}</h4>
      {children}
    </div>
  );
}

function ScrollList({ items, max = "max-h-48" }: { items: string[]; max?: string }) {
  if (!items?.length) return <span className="text-sm text-text-tertiary">—</span>;
  return (
    <ul className={cn("overflow-y-auto rounded-md border border-border bg-black/20 p-2 font-mono text-xs leading-relaxed", max)}>
      {items.map((it) => (
        <li key={it} className="truncate" title={it}>
          {it}
        </li>
      ))}
    </ul>
  );
}

function Table({ head, rows }: { head: string[]; rows: React.ReactNode[][] }) {
  if (!rows.length) return <p className="text-sm text-text-tertiary">Kayıt yok.</p>;
  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="w-full text-left text-xs">
        <thead className="bg-white/[0.03] text-text-tertiary">
          <tr>
            {head.map((h) => (
              <th key={h} className="px-2 py-1.5 font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t border-border align-top">
              {r.map((c, j) => (
                <td key={j} className="px-2 py-1.5 text-foreground">
                  {c}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Dış kaynaktan gelen metin (NVD açıklaması, GDELT başlığı, sayfa başlığı) güvenilmeyen veridir
 * (Q22). Görsel olarak ayrı bir kutuda ve kaynağıyla gösterilir. */
function Untrusted({ children, source }: { children: React.ReactNode; source?: string }) {
  return (
    <div className="rounded-md border border-dashed border-white/15 bg-black/20 p-2.5 text-sm leading-relaxed text-text-secondary">
      {children}
      {source && <p className="mt-1 text-[10px] uppercase tracking-wide text-text-tertiary">kaynak metni · {source}</p>}
    </div>
  );
}

// --- Modül görünümleri ---------------------------------------------------------------

function Dns({ s }: { s: S }) {
  if (s.nxdomain) return <p className="text-sm text-priority-high-text">Alan adı çözülmüyor (NXDOMAIN).</p>;
  const records = (s.records ?? {}) as Record<string, string[]>;
  return (
    <div className="flex flex-col gap-3">
      <Facts rows={[["Çözümleyici", s.resolver], ["DNSSEC", s.dnssec_validated ? "doğrulandı" : "yok / doğrulanmadı"]]} />
      <Table head={["Tür", "Değer"]} rows={Object.entries(records).map(([t, vals]) => [<Mono key="t">{t}</Mono>, <Chips key="v" items={vals} />])} />
      {s.verification_tokens?.length > 0 && (
        <Section title="Site doğrulama belirteçleri (ortak sahiplik pivotu)">
          <Table head={["Servis", "Belirteç"]} rows={s.verification_tokens.map((v: any) => [v.service, <Mono key="k">{v.token}</Mono>])} />
        </Section>
      )}
      {s.spf_includes?.length > 0 && (
        <Section title="SPF ile yetkilendirilen gönderenler">
          <Chips items={s.spf_includes} />
        </Section>
      )}
    </div>
  );
}

function Rdap({ s }: { s: S }) {
  if (s.registered === false) return <p className="text-sm text-priority-high-text">{s.note}</p>;
  const ev = s.events ?? {};
  return (
    <div className="flex flex-col gap-3">
      <Facts
        rows={[
          ["Ad", <Mono key="n">{s.name}</Mono>],
          ["Kayıt şirketi", s.registrar],
          ["Kayıt", fmtDay(ev.registration)],
          ["Yaş", s.age_days != null ? `${s.age_days} gün` : null],
          ["Bitiş", fmtDay(ev.expiration)],
          ["Son değişiklik", fmtDay(ev["last changed"])],
          ["Durum", s.status?.length ? <Chips key="st" items={s.status} mono={false} /> : null],
          ["Blok", s.start ? <Mono key="b">{`${s.start} – ${s.end}`}</Mono> : null],
          ["CIDR", s.cidrs?.length ? <Chips key="c" items={s.cidrs} /> : null],
          ["Ülke", s.country],
          ["Ad sunucuları", s.nameservers?.length ? <Chips key="ns" items={s.nameservers} /> : null],
          ["DNSSEC", s.secure_dns === undefined ? null : s.secure_dns ? "imzalı" : "imzasız"],
          ["Sunucu", <Mono key="srv">{s.server}</Mono>],
        ]}
      />
      {s.entities?.length > 0 && (
        <Section title="Kayıttaki taraflar">
          <Table
            head={["Rol", "Ad / kurum", "İletişim"]}
            rows={s.entities
              .filter((e: any) => e.name || e.org || e.email)
              .slice(0, 12)
              .map((e: any) => [e.roles?.join(", "), e.org || e.name || e.handle, e.email ? <Mono key="e">{e.email}</Mono> : "—"])}
          />
        </Section>
      )}
    </div>
  );
}

function Crtsh({ s }: { s: S }) {
  return (
    <div className="flex flex-col gap-3">
      <Facts
        rows={[
          ["Kaynak", s.provider],
          ["Sertifika", s.certificate_count],
          ["İlk", fmtDay(s.first_issued)],
          ["Son", fmtDay(s.last_issued)],
          ["Joker sertifika", s.wildcard ? "var" : "yok"],
          ["Yayıncılar", s.issuers?.length ? <Chips key="i" mono={false} items={s.issuers.map((i: any) => `${i[0]} · ${i[1]}`)} /> : null],
        ]}
      />
      <Section title={`Alt alan adları (${s.subdomain_count})${s.pivots_capped ? " — ilk 100'ü seçici olarak eklendi" : ""}`}>
        <ScrollList items={s.subdomains ?? []} max="max-h-64" />
      </Section>
    </div>
  );
}

function Wayback({ s }: { s: S }) {
  return (
    <div className="flex flex-col gap-3">
      <Facts
        rows={[
          ["İlk kopya", fmtDate(s.first_capture)],
          ["Son kopya", fmtDate(s.last_capture)],
          ["En yakın kopya", s.closest?.url ? <ExtLink key="c" href={s.closest.url}>{fmtDate(s.closest.timestamp) ?? "aç"}</ExtLink> : null],
          ["Türler", s.mimetypes?.length ? <Chips key="m" items={s.mimetypes.map((m: any) => `${m[0]} · ${m[1]}`)} /> : null],
        ]}
      />
      {s.notes?.length > 0 && <p className="text-xs text-priority-medium-text">{s.notes.join(" ")}</p>}
      {s.sample_urls?.length > 0 && (
        <Section title={`Arşivlenmiş adresler${s.sample_capped ? " (ilk 150)" : ""}`}>
          <ScrollList items={s.sample_urls.map((u: any) => u.url)} max="max-h-64" />
        </Section>
      )}
    </div>
  );
}

function InternetDb({ s }: { s: S }) {
  if (s.found === false) return <p className="text-sm text-text-secondary">Shodan bu IP için kayıt tutmuyor.</p>;
  return (
    <Facts
      rows={[
        ["Açık portlar", <Chips key="p" items={s.ports} />],
        ["Bilinen açıklar", s.vulns?.length ? <Chips key="v" items={s.vulns} /> : "yok"],
        ["Ana makine adları", <Chips key="h" items={s.hostnames} />],
        ["Yazılım (CPE)", <Chips key="c" items={s.cpes} />],
        ["Etiketler", <Chips key="t" items={s.tags} mono={false} />],
      ]}
    />
  );
}

function RipeIp({ s }: { s: S }) {
  const loc = s.locations?.[0];
  return (
    <Facts
      rows={[
        ["Önek", <Mono key="p">{s.prefix}</Mono>],
        ["Duyuruluyor", s.announced ? "evet" : "hayır"],
        ["ASN", s.asns?.length ? <Chips key="a" mono={false} items={s.asns.map((a: any) => `AS${a.asn} · ${a.holder}`)} /> : null],
        ["Blok", s.block],
        ["Konum (GeoLite)", loc ? [loc.city, loc.country].filter(Boolean).join(", ") : null],
        ["Kötüye kullanım", s.abuse_contacts?.length ? <Chips key="ab" items={s.abuse_contacts} /> : null],
      ]}
    />
  );
}

function RipeAsn({ s }: { s: S }) {
  return (
    <div className="flex flex-col gap-3">
      <Facts
        rows={[
          ["Sahibi", s.holder],
          ["Duyuruluyor", s.announced ? "evet" : "hayır"],
          ["Blok", s.block],
          ["Önek sayısı", `${s.prefix_count?.ipv4 ?? 0} IPv4 · ${s.prefix_count?.ipv6 ?? 0} IPv6`],
        ]}
      />
      <Section title="IPv4 önekleri">
        <ScrollList items={s.prefixes_v4 ?? []} />
      </Section>
    </div>
  );
}

function Urlscan({ s }: { s: S }) {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-text-tertiary">
        {s.total ?? 0} herkese açık tarama{s.has_more ? " (daha fazlası var)" : ""} · sorgu <Mono>{s.query}</Mono>
      </p>
      <Table
        head={["Zaman", "Sayfa", "IP / ülke", "Sunucu"]}
        rows={(s.results ?? []).slice(0, 25).map((r: any) => [
          fmtDate(r.time),
          r.result ? <ExtLink key="r" href={r.result}>{r.title || r.domain || "tarama"}</ExtLink> : r.title,
          <Mono key="i">{[r.ip, r.country].filter(Boolean).join(" · ")}</Mono>,
          r.server,
        ])}
      />
    </div>
  );
}

function Http({ s }: { s: S }) {
  return (
    <div className="flex flex-col gap-3">
      <Facts
        rows={[
          ["Başlık", s.title ? <Untrusted key="t">{s.title}</Untrusted> : null],
          ["Generator", s.generator],
          [
            "Favicon (mmh3)",
            s.favicon_mmh3 != null ? (
              <span key="f" className="flex flex-wrap items-center gap-2">
                <Mono>{s.favicon_mmh3}</Mono>
                <ExtLink href={`https://www.shodan.io/search?query=http.favicon.hash%3A${s.favicon_mmh3}`}>Shodan&apos;da aynı favicon</ExtLink>
              </span>
            ) : (
              s.favicon_note
            ),
          ],
          ["Analytics kimlikleri", s.analytics_ids?.length ? <Chips key="a" items={s.analytics_ids} /> : "yok"],
        ]}
      />
      {s.external_hosts?.length > 0 && (
        <Section title="Bağlantı verilen dış host'lar">
          <Chips items={s.external_hosts.map((h: any) => `${h[0]} · ${h[1]}`)} />
        </Section>
      )}
    </div>
  );
}

function Kev({ s }: { s: S }) {
  if (!s.in_kev)
    return (
      <p className="text-sm text-text-secondary">
        KEV kataloğunda yok — CISA bu açığın gerçekte sömürüldüğünü kayda geçirmemiş (katalog sürümü {s.catalog_version}).
      </p>
    );
  return (
    <div className="flex flex-col gap-3">
      <p className="flex items-center gap-2 text-sm font-medium text-priority-critical-text">
        <AlertTriangle aria-hidden className="h-4 w-4" />
        Gerçekte sömürülüyor — CISA KEV kataloğunda
      </p>
      <Facts
        rows={[
          ["Ürün", [s.vendor, s.product].filter(Boolean).join(" · ")],
          ["Ad", s.name],
          ["Eklenme", fmtDay(s.date_added)],
          ["Son tarih (ABD federal)", fmtDay(s.due_date)],
          ["Fidye yazılımı", s.known_ransomware === "Known" ? "biliniyor" : "bilinmiyor"],
          ["CWE", s.cwes?.length ? <Chips key="c" items={s.cwes} /> : null],
        ]}
      />
      {s.required_action && <Untrusted source="CISA">{s.required_action}</Untrusted>}
    </div>
  );
}

function Epss({ s }: { s: S }) {
  if (!s.found) return <p className="text-sm text-text-secondary">EPSS bu CVE için puan üretmemiş.</p>;
  const pct = Math.round(s.epss * 1000) / 10;
  const per = Math.round(s.percentile * 1000) / 10;
  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm text-foreground">
        30 gün içinde sömürülme olasılığı <strong className="font-mono tabular-nums">%{pct}</strong> — CVE&apos;lerin{" "}
        <strong className="font-mono tabular-nums">%{per}</strong>&apos;inden yüksek.
      </p>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/10" aria-hidden>
        <div className="h-full rounded-full bg-priority-high" style={{ width: `${Math.max(2, s.percentile * 100)}%` }} />
      </div>
      <p className="text-xs text-text-tertiary">FIRST EPSS · {s.date}</p>
    </div>
  );
}

function Nvd({ s }: { s: S }) {
  if (!s.found) return <p className="text-sm text-text-secondary">NVD bu CVE&apos;yi henüz yayımlamamış.</p>;
  return (
    <div className="flex flex-col gap-3">
      {s.description && <Untrusted source="NVD">{s.description}</Untrusted>}
      <Facts
        rows={[
          ["Durum", s.status],
          ["Yayın", fmtDay(s.published)],
          ["Kaynak", s.source],
          ["CWE", s.cwes?.length ? <Chips key="c" items={s.cwes} /> : null],
          ["Etkilenen", s.affected?.length ? <Chips key="a" mono={false} items={s.affected.slice(0, 15)} /> : null],
        ]}
      />
      {s.cvss?.length > 0 && (
        <Table
          head={["CVSS", "Puan", "Şiddet", "Vektör", "Kaynak"]}
          rows={s.cvss.map((c: any) => [c.version, <Mono key="s">{c.score}</Mono>, c.severity, <Mono key="v">{c.vector}</Mono>, c.source])}
        />
      )}
      {s.references?.length > 0 && (
        <Section title="Referanslar">
          <ul className="flex flex-col gap-1 text-xs">
            {s.references.slice(0, 15).map((r: any) => (
              <li key={r.url} className="truncate">
                <ExtLink href={r.url}>{r.url}</ExtLink> {r.tags?.length ? <span className="text-text-tertiary">· {r.tags.join(", ")}</span> : null}
              </li>
            ))}
          </ul>
        </Section>
      )}
    </div>
  );
}

function Attack({ s }: { s: S }) {
  return (
    <div className="flex flex-col gap-3">
      <Facts
        rows={[
          ["Teknik", <span key="n" className="font-medium">{s.name}</span>],
          ["Üst teknik", s.parent ? `${s.parent.id} · ${s.parent.name}` : null],
          ["Taktikler", <Chips key="t" mono={false} items={s.tactics ?? []} />],
          ["Platformlar", <Chips key="p" mono={false} items={s.platforms ?? []} />],
          ["MITRE", s.url ? <ExtLink key="u" href={s.url}>{s.id}</ExtLink> : null],
        ]}
      />
      {s.description && <Untrusted source="MITRE ATT&CK">{s.description.slice(0, 900)}</Untrusted>}
      {s.groups?.length > 0 && (
        <Section title={`Bu tekniği kullanan gruplar (${s.groups.length})`}>
          <Chips mono={false} items={s.groups.map((g: any) => `${g.id} ${g.name}`)} />
        </Section>
      )}
      {s.software?.length > 0 && (
        <Section title={`Yazılımlar (${s.software.length})`}>
          <Chips mono={false} items={s.software.slice(0, 40).map((g: any) => `${g.id} ${g.name}`)} />
        </Section>
      )}
      {s.mitigations?.length > 0 && (
        <Section title="Önlemler">
          <Chips mono={false} items={s.mitigations.map((g: any) => `${g.id} ${g.name}`)} />
        </Section>
      )}
    </div>
  );
}

function Gdelt({ s }: { s: S }) {
  const toast = useToast();
  const [added, setAdded] = useState<Set<string>>(new Set());
  async function addObservation(a: any) {
    try {
      await api.observations.create({ raw_content: a.title, source_url: a.url, observed_at: a.seen_at });
      setAdded((prev) => new Set(prev).add(a.url));
      toast("Gözlem olarak eklendi — Promote Kuyruğu'nda", "success");
    } catch (err) {
      toast(err instanceof Error ? err.message : "Eklenemedi", "error");
    }
  }
  if (!s.articles?.length) return <p className="text-sm text-text-secondary">Son 3 ayda bu değeri geçiren haber bulunamadı.</p>;
  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-text-tertiary">
        {s.count} haber · {s.distinct_sources} farklı kaynak · {s.window}. Bir haberi gözleme çevirmek onu doğrulama hattına sokar.
      </p>
      <ul className="flex flex-col divide-y divide-border rounded-md border border-border">
        {s.articles.slice(0, 40).map((a: any) => (
          <li key={a.url} className="flex items-start justify-between gap-3 px-2.5 py-2">
            <div className="min-w-0">
              <a href={a.url} target="_blank" rel="noopener noreferrer nofollow" className="text-sm text-foreground hover:underline">
                {a.title}
              </a>
              <p className="font-mono text-[11px] text-text-tertiary">
                {[a.domain, a.source_country, a.language, fmtDate(a.seen_at)].filter(Boolean).join(" · ")}
              </p>
            </div>
            <Button size="sm" variant="ghost" disabled={added.has(a.url)} onClick={() => addObservation(a)} aria-label="Gözlem olarak ekle">
              <Plus aria-hidden className="h-3.5 w-3.5" />
              {added.has(a.url) ? "Eklendi" : "Gözlem"}
            </Button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Wikidata({ s, onSuggest }: { s: S; onSuggest?: (kind: string, value: string) => void }) {
  if (!s.best) return <p className="text-sm text-text-secondary">Wikidata&apos;da eşleşen öğe yok.</p>;
  const facts = s.best.facts ?? {};
  const val = (k: string) =>
    (facts[k] ?? []).map((x: any) => (typeof x === "object" ? x.label ?? x.qid : String(x))).join(", ") || null;
  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs text-text-tertiary">En iyi aday — ad eşleşmesi kimlik değildir, doğru kurum olduğunu kontrol et.</p>
      <Facts
        rows={[
          ["Öğe", <ExtLink key="q" href={s.best.url}>{`${s.best.label} (${s.best.qid})`}</ExtLink>],
          ["Açıklama", s.best.description],
          ["Tür", val("instance_of")],
          ["Ülke", val("country")],
          ["Merkez", val("headquarters")],
          ["Kuruluş", val("inception")],
          ["Ana kurum", val("parent_organization")],
          ["Sektör", val("industry")],
          ["Resmi site", val("official_website")],
          ["LEI", val("lei")],
          ["Çalışan", val("employees")],
          ["Diğer adlar", s.best.aliases?.length ? s.best.aliases.join(", ") : null],
        ]}
      />
      {s.suggested_selectors?.length > 0 && (
        <Section title="Önerilen seçiciler">
          <div className="flex flex-wrap gap-2">
            {s.suggested_selectors.map((sg: any) => (
              <Button key={sg.value} size="sm" variant="outline" onClick={() => onSuggest?.(sg.kind, sg.value)} disabled={!onSuggest}>
                <Plus aria-hidden className="h-3.5 w-3.5" />
                <Mono>{sg.value}</Mono> bağla
              </Button>
            ))}
          </div>
        </Section>
      )}
      {s.candidates?.length > 1 && (
        <Section title="Diğer adaylar">
          <ul className="flex flex-col gap-0.5 text-xs text-text-secondary">
            {s.candidates.slice(1).map((c: any) => (
              <li key={c.qid}>
                <Mono>{c.qid}</Mono> {c.label} — {c.description}
              </li>
            ))}
          </ul>
        </Section>
      )}
    </div>
  );
}

function Gleif({ s }: { s: S }) {
  return (
    <Table
      head={["Yasal ad", "LEI", "Yargı", "Adres", "Durum"]}
      rows={(s.records ?? []).map((r: any) => [
        r.legal_name,
        <ExtLink key="l" href={r.url}>{r.lei}</ExtLink>,
        r.jurisdiction,
        r.legal_address,
        [r.status, r.registration_status].filter(Boolean).join(" · "),
      ])}
    />
  );
}

function Sanctions({ s }: { s: S }) {
  if ("listed" in s) {
    return s.listed ? (
      <div className="flex flex-col gap-2">
        <p className="flex items-center gap-2 text-sm font-medium text-priority-critical-text">
          <AlertTriangle aria-hidden className="h-4 w-4" />
          Bu adres OFAC SDN listesinde ({s.currency})
        </p>
        <Facts rows={[["Kayıt", s.entry?.name], ["Program", s.entry?.programs], ["SDN no", s.entry?.ent_num]]} />
      </div>
    ) : (
      <p className="text-sm text-text-secondary">Adres OFAC SDN listesinde geçmiyor (liste: {fmtDate(s.list_downloaded_at)}).</p>
    );
  }
  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-priority-medium-text">{s.caution}</p>
      {s.match_count === 0 ? (
        <p className="text-sm text-text-secondary">OFAC SDN listesinde eşleşme yok (liste: {fmtDate(s.list_downloaded_at)}).</p>
      ) : (
        <Table
          head={["Skor", "Listedeki ad", "Eşleşen", "Tür", "Program"]}
          rows={s.matches.map((m: any) => [
            <Mono key="s">{m.score.toFixed(2)}</Mono>,
            m.name,
            m.matched_name,
            m.type,
            m.programs,
          ])}
        />
      )}
    </div>
  );
}

function Nominatim({ s }: { s: S }) {
  if (!s.found) return <p className="text-sm text-text-secondary">Bu koordinatta adres bulunamadı.</p>;
  return (
    <Facts
      rows={[
        ["Adres", s.display_name],
        ["Nesne", [s.category, s.type].filter(Boolean).join(" · ")],
        ["OSM", s.osm_url ? <ExtLink key="o" href={s.osm_url}>{`${s.osm?.type}/${s.osm?.id}`}</ExtLink> : null],
        ["Atıf", <span key="a" className="text-xs text-text-tertiary">{s.attribution}</span>],
      ]}
    />
  );
}

function Adsb({ s }: { s: S }) {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-text-tertiary">
        {s.count} uçak · {s.military_count} askeri işaretli · {s.radius_nm} NM · {fmtDate(s.snapshot_at)}. {s.note}
      </p>
      <Table
        head={["Hex", "Çağrı", "Tescil", "Tip", "İrtifa", "Hız"]}
        rows={(s.aircraft ?? []).slice(0, 60).map((a: any) => [
          <ExtLink key="h" href={`https://globe.adsbexchange.com/?icao=${a.hex}`}>{a.hex}</ExtLink>,
          <Mono key="f">{a.flight ?? "—"}</Mono>,
          a.registration ?? "—",
          a.type ?? "—",
          a.altitude_ft ?? "—",
          a.ground_speed_kt != null ? `${Math.round(a.ground_speed_kt)} kt` : "—",
        ])}
      />
    </div>
  );
}

function Ptr({ s }: { s: S }) {
  return <Facts rows={[["PTR", s.ptr?.length ? <Chips key="p" items={s.ptr} /> : "kayıt yok"], ["Çözümleyici", s.resolver]]} />;
}

const VIEWS: Record<string, (p: { s: S; onSuggest?: (kind: string, value: string) => void }) => React.ReactNode> = {
  dns: Dns,
  ptr: Ptr,
  rdap: Rdap,
  crtsh: Crtsh,
  wayback: Wayback,
  internetdb: InternetDb,
  "ripestat-ip": RipeIp,
  "ripestat-asn": RipeAsn,
  urlscan: Urlscan,
  http: Http,
  kev: Kev,
  epss: Epss,
  nvd: Nvd,
  attack: Attack,
  gdelt: Gdelt,
  "gdelt-entity": Gdelt,
  wikidata: Wikidata,
  gleif: Gleif,
  sanctions: Sanctions,
  "sanctions-crypto": Sanctions,
  nominatim: Nominatim,
  adsb: Adsb,
};

export function RunSummary({ run, onSuggest }: { run: EnrichmentRun; onSuggest?: (kind: string, value: string) => void }) {
  if (run.status === "FAILED") {
    return <p className="text-sm text-priority-critical-text">{run.error}</p>;
  }
  if (!run.summary) return null;
  const View = VIEWS[run.module];
  if (!View) {
    return <pre className="max-h-64 overflow-auto rounded-md bg-black/30 p-2 font-mono text-xs">{JSON.stringify(run.summary, null, 2)}</pre>;
  }
  return <View s={run.summary} onSuggest={onSuggest} />;
}
