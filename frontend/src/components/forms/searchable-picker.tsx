"use client";

import { useMemo, useState } from "react";
import { Check } from "lucide-react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export interface PickerItem {
  id: string;
  label: string;
  sublabel?: string;
}

type SingleProps = {
  multiple?: false;
  value: string | null;
  onChange: (id: string | null) => void;
};

type MultiProps = {
  multiple: true;
  value: string[];
  onChange: (ids: string[]) => void;
};

type SearchablePickerProps = {
  items: PickerItem[];
  placeholder?: string;
  emptyText?: string;
} & (SingleProps | MultiProps);

/** Select'in type-ahead desteklememesi için genellenmiş Input+filtre idiyomu (bkz.
 * EntitiesPage'in arama-filtre deseni) — Entity/Source/Claim/Evidence seçimlerinin hepsinde
 * kullanılır. Tek/çoklu seçim aynı component, `multiple` prop'una göre ayrışır. */
export function SearchablePicker(props: SearchablePickerProps) {
  const { items, placeholder = "Ara…", emptyText = "Sonuç yok" } = props;
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (i) => i.label.toLowerCase().includes(q) || i.sublabel?.toLowerCase().includes(q)
    );
  }, [items, query]);

  const selectedIds = props.multiple ? props.value : props.value ? [props.value] : [];

  function toggle(id: string) {
    if (props.multiple) {
      const has = props.value.includes(id);
      props.onChange(has ? props.value.filter((v) => v !== id) : [...props.value, id]);
    } else {
      props.onChange(props.value === id ? null : id);
    }
  }

  return (
    <div className="flex flex-col gap-1.5">
      <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={placeholder} />
      {selectedIds.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {selectedIds.map((id) => {
            const item = items.find((i) => i.id === id);
            if (!item) return null;
            return (
              <span
                key={id}
                className="glass-ring inline-flex items-center gap-1 rounded-full bg-white/10 px-2 py-0.5 text-xs text-foreground"
              >
                {item.label}
                <button
                  type="button"
                  onClick={() => toggle(id)}
                  aria-label={`${item.label} seçimini kaldır`}
                  className="text-text-tertiary hover:text-foreground"
                >
                  ×
                </button>
              </span>
            );
          })}
        </div>
      )}
      <div className="max-h-40 overflow-y-auto rounded-lg border border-border">
        {filtered.length === 0 ? (
          <p className="p-2 text-xs text-text-tertiary">{emptyText}</p>
        ) : (
          filtered.map((item) => {
            const active = selectedIds.includes(item.id);
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => toggle(item.id)}
                className={cn(
                  "flex w-full items-center justify-between gap-2 px-2.5 py-1.5 text-left text-sm transition-colors hover:bg-surface-raised",
                  active && "bg-white/10 text-foreground"
                )}
              >
                <span>
                  {item.label}
                  {item.sublabel && <span className="ml-1.5 text-xs text-text-tertiary">{item.sublabel}</span>}
                </span>
                {active && <Check aria-hidden className="h-3.5 w-3.5 shrink-0" />}
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
