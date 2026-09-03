"use client";

import { useId, useMemo } from "react";
import { Input } from "@/components/ui/input";

/**
 * Serbest metin + öneri girişi tür alanları için.
 *
 * Faz 11 (dogfooding F8): entity/source/evidence formları türü sabit bir `<Select>`'e
 * kilitliyordu, oysa backend'de bu alanlar serbest string. Backend'in `examples=[...]`
 * listesi bir ÖNERİ listesiydi; frontend onu KURAL sanmıştı. Sonuç: kullanıcı "AI Model"
 * türünde bir entity giremiyordu ve graf'ı yanlışlamadan devam etmesi mümkün değildi.
 *
 * Gerçek kısıtı olan alanlar (ör. Monitor.target_type — backend'de MONITOR_TARGET_TYPES
 * tuple'ıyla zorlanır) `<Select>` olarak KALMALI; bu component sadece serbest alanlar için.
 */
export function TypeCombo({
  id,
  value,
  onChange,
  suggestions,
  placeholder,
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  suggestions: string[];
  placeholder?: string;
}) {
  const listId = useId();
  const unique = useMemo(
    () => Array.from(new Set(suggestions.map((s) => s.trim()).filter(Boolean))).sort((a, b) => a.localeCompare(b, "tr")),
    [suggestions]
  );

  return (
    <>
      <Input
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        list={listId}
        placeholder={placeholder}
        autoComplete="off"
      />
      <datalist id={listId}>
        {unique.map((s) => (
          <option key={s} value={s} />
        ))}
      </datalist>
    </>
  );
}
