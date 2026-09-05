"use client";

import { useState } from "react";
import { ChevronDown, Fingerprint, Unlink } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { Badge } from "@/components/ui/badge";
import { FingerprintLinkDialog } from "@/components/forms/fingerprint-link-dialog";
import { InjectionWarning } from "@/components/provenance/injection-warning";
import { useToast } from "@/components/ui/toast";

/**
 * Faz 15.3 — belgenin üretildiği ortamın izi.
 *
 * Bu blok belgenin İÇERİĞİNİ göstermiyor: kim yazdı, hangi araçla, ne zaman, hangi kurumun
 * sisteminden geçti. Faz 15 spike'ı bunun ölçülebilir değerini gösterdi — NIST SP 800-53r5
 * `/Author: Joint Task Force`, `/Creator: Acrobat PDFMaker 20 for Word` ve bir SharePoint
 * `/ContentTypeId` GUID'i taşıyor; tarih damgasındaki `-05:00` ise belgeyi üreten makinenin
 * saat dilimini söylüyor.
 *
 * **Varsayılan kapalı.** Her kanıt satırında açık dursaydı Kanıt Kasası okunamazdı; parmak
 * izi çoğu zaman aranmayan, arandığındaysa tamamı istenen bir bilgi.
 *
 * **Q22:** buradaki her değer güvenilmeyen veridir — belgeyi kim ürettiyse o yazmıştır.
 * Gösterilir, asla yorumlanmaz.
 */
export function DocumentFingerprint({ evidenceId }: { evidenceId: string }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const { data, reload } = useApi(
    () => (open ? api.evidence.fingerprint(evidenceId) : Promise.resolve(null)),
    [evidenceId, open]
  );

  const alanSayisi = data?.groups.reduce((n, g) => n + g.fields.length, 0) ?? 0;

  async function unlink(entityId: string, field: string) {
    try {
      await api.evidence.unlinkFingerprint(evidenceId, entityId, field);
      toast("Bağ kaldırıldı", "success");
      reload();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Kaldırılamadı", "error");
    }
  }

  return (
    <div className="mt-3 border-t border-border pt-3">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1.5 text-xs text-text-tertiary hover:text-foreground"
        aria-expanded={open}
      >
        <Fingerprint aria-hidden className="h-3.5 w-3.5" />
        Belge parmak izi
        {open && alanSayisi > 0 && <span className="text-text-tertiary">({alanSayisi} alan)</span>}
        <ChevronDown
          aria-hidden
          className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <div className="mt-2 flex flex-col gap-3">
          {data === null && <p className="text-xs text-text-tertiary">Yükleniyor…</p>}

          {data && alanSayisi === 0 && (
            <p className="text-xs text-text-tertiary">
              Bu belgede metadata yok — üretildiği ortama dair bir iz taşımıyor.
            </p>
          )}

          {/* Metadata kaynaklı Q22 uyarıları bloğun BAŞINDA: aşağıdaki değerleri okumadan
              önce görülsün. */}
          {data && <InjectionWarning hits={data.injection_hits} />}

          {data?.groups.map((g) => (
            <div key={g.key} className="flex flex-col gap-1.5">
              <p className="text-[11px] uppercase tracking-wide text-text-tertiary">{g.label}</p>
              <div className="flex flex-col gap-1.5">
                {g.fields.map((f) => {
                  const bagli = data.links.filter((l) => l.field === f.field);
                  return (
                    <div
                      key={f.field}
                      className="flex flex-wrap items-start justify-between gap-2 rounded-md border border-border bg-black/20 px-2 py-1.5"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="font-mono text-[10px] text-text-tertiary">{f.field}</p>
                        <p className="break-words font-mono text-xs text-foreground">{f.value}</p>
                        {f.note && (
                          <p className="mt-0.5 text-[11px] text-text-secondary">{f.note}</p>
                        )}
                        {bagli.length > 0 && (
                          <div className="mt-1 flex flex-wrap items-center gap-1.5">
                            {bagli.map((l) => (
                              <span key={l.entity_id} className="inline-flex items-center gap-1">
                                <Badge variant="outline" className="text-[10px]">
                                  {l.entity_name} · {l.entity_type}
                                </Badge>
                                <button
                                  type="button"
                                  onClick={() => unlink(l.entity_id, l.field)}
                                  className="text-text-tertiary hover:text-priority-high-text"
                                  aria-label={`${l.entity_name} bağını kaldır`}
                                  title="Bağı kaldır"
                                >
                                  <Unlink aria-hidden className="h-3 w-3" />
                                </button>
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                      {f.linkable && bagli.length === 0 && (
                        <FingerprintLinkDialog
                          evidenceId={evidenceId}
                          field={f.field}
                          value={f.value}
                          onLinked={reload}
                        />
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
