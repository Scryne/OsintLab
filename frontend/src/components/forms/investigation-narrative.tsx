"use client";

import { useState } from "react";
import { Check, PenLine } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";

/** Analiz ve Sonuç editörü (madde 30'un son iki adımı).
 *
 * Görüntüleme ve düzenleme aynı bileşende: bir araştırmada analiz metni sürekli büyüyen bir
 * defter, sonuç ise sonda bir kez yazılıp sonra rötuşlanan bir cümle. Ayrı bir "düzenle"
 * sayfasına göndermek, yazmanın önüne bir adım daha koyardı — ve yazılmayan analiz, hiç
 * yapılmamış analizle aynı şey. */
export function InvestigationNarrative({
  investigationId,
  field,
  value,
  label,
  placeholder,
  hint,
  readOnly = false,
  onSaved,
}: {
  investigationId: string;
  field: "analysis" | "conclusion";
  value: string | null;
  label: string;
  placeholder: string;
  hint?: string;
  /** Kapanmış (CLOSED/ARCHIVED) araştırmada metin değişmez — backend de 409 döner. */
  readOnly?: boolean;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value ?? "");
  const [saving, setSaving] = useState(false);

  // Taslak yalnızca düzenleme modunda okunuyor (görünen dal `value`'yu gösteriyor), o
  // yüzden onu sunucu değeriyle senkron tutan bir effect'e gerek yok: düzenleme
  // başladığı anda tohumlamak yeterli ve daha güvenli. Eski effect `value` her
  // tazelendiğinde çalışıyordu ve "kullanıcı yazarken üzerine yazma" endişesini bir
  // `editing` kontrolüyle savuşturmaya çalışıyordu — o kontrolün gerekmediği bir yapı
  // bu riski tamamen ortadan kaldırıyor.
  async function save() {
    setSaving(true);
    try {
      await api.investigations.updateNarrative(investigationId, { [field]: draft });
      toast(`${label} kaydedildi`, "success");
      setEditing(false);
      onSaved();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Kaydedilemedi", "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="mb-2 flex items-center justify-between gap-3">
        <h3 className="text-sm font-medium uppercase tracking-wide text-text-tertiary">{label}</h3>
        {!editing && !readOnly && (
          <Button
            size="sm"
            variant="outline"
            className="h-7 px-2 text-xs"
            onClick={() => {
              setDraft(value ?? "");
              setEditing(true);
            }}
          >
            <PenLine aria-hidden className="h-3.5 w-3.5" />
            {value ? "Düzenle" : "Yaz"}
          </Button>
        )}
      </div>

      {editing ? (
        <div className="flex flex-col gap-2">
          <Textarea
            aria-label={label}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={placeholder}
            rows={field === "analysis" ? 8 : 4}
            autoFocus
          />
          <div className="flex items-center gap-1.5">
            <Button size="sm" onClick={save} disabled={saving}>
              <Check aria-hidden className="h-3.5 w-3.5" />
              {saving ? "Kaydediliyor…" : "Kaydet"}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setDraft(value ?? "");
                setEditing(false);
              }}
            >
              Vazgeç
            </Button>
          </div>
        </div>
      ) : value ? (
        <p className="whitespace-pre-wrap text-sm text-foreground">{value}</p>
      ) : (
        <p className="text-sm text-text-tertiary">{hint ?? placeholder}</p>
      )}
    </div>
  );
}
