"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { SearchablePicker } from "@/components/forms/searchable-picker";
import { useToast } from "@/components/ui/toast";

interface RelatedClaim {
  id: string;
  text: string;
}

/** Entity/Event sayfalarından "Yeni Claim" — source seçimi + corroborates/contradicts/
 * supersedes ilişkilendirmesi dahil (Faz 10 B3). `relatedClaims`, çağıran sayfanın recall'undan
 * gelir (о entity/event'e ait claim'lerle sınırlı — tüm claim listesini çekmek gereksiz). */
export function NewClaimDialog({
  aboutEntityId,
  aboutEventId,
  relatedClaims,
  onCreated,
}: {
  aboutEntityId?: string;
  aboutEventId?: string;
  relatedClaims: RelatedClaim[];
  onCreated: () => void;
}) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const { data: sources } = useApi(() => (open ? api.sources.list() : Promise.resolve([])), [open]);

  const [text, setText] = useState("");
  const [sourceId, setSourceId] = useState<string | null>(null);
  const [corroborates, setCorroborates] = useState<string[]>([]);
  const [contradicts, setContradicts] = useState<string[]>([]);
  const [supersedes, setSupersedes] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sourceItems = (sources ?? []).map((s) => ({ id: s.id, label: s.name, sublabel: s.source_type }));
  const claimItems = relatedClaims.map((c) => ({ id: c.id, label: c.text.slice(0, 60) }));

  function reset() {
    setText("");
    setSourceId(null);
    setCorroborates([]);
    setContradicts([]);
    setSupersedes(null);
    setError(null);
  }

  async function submit() {
    if (!text.trim() || !sourceId) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.claims.create({
        text: text.trim(),
        source_id: sourceId,
        about_entity_id: aboutEntityId ?? null,
        about_event_id: aboutEventId ?? null,
        corroborates,
        contradicts,
        supersedes,
      });
      toast("Claim eklendi", "success");
      reset();
      setOpen(false);
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bilinmeyen hata");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) reset();
      }}
    >
      <DialogTrigger
        render={
          <Button size="sm" variant="outline">
            <Plus aria-hidden className="h-4 w-4" />
            Yeni Claim
          </Button>
        }
      />
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Yeni claim ekle</DialogTitle>
          <DialogDescription>Bir kaynağa dayanan yeni bir iddia kaydeder. Confidence, kaynağın güvenilirliğinden ve kurulan bağlardan hesaplanır.</DialogDescription>
        </DialogHeader>
        <div className="flex max-h-[60vh] flex-col gap-4 overflow-y-auto pr-1">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="claim-text">Metin</Label>
            <Textarea
              id="claim-text"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="İddia edilen bilgi…"
              rows={3}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="claim-form-kaynak-1">Kaynak</Label>
            <SearchablePicker id="claim-form-kaynak-1" items={sourceItems} value={sourceId} onChange={setSourceId} placeholder="Kaynak ara…" />
          </div>
          {claimItems.length > 0 && (
            <>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="claim-form-dog-ruladig-i-claimler-corro-2">Doğruladığı claim&apos;ler (corroborates)</Label>
                <SearchablePicker
                  id="claim-form-dog-ruladig-i-claimler-corro-2"
                  items={claimItems}
                  value={corroborates}
                  onChange={setCorroborates}
                  multiple
                  placeholder="Claim ara…"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="claim-form-c-elis-tig-i-claimler-contra-3">Çeliştiği claim&apos;ler (contradicts)</Label>
                <SearchablePicker
                  id="claim-form-c-elis-tig-i-claimler-contra-3"
                  items={claimItems}
                  value={contradicts}
                  onChange={setContradicts}
                  multiple
                  placeholder="Claim ara…"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="claim-form-yerini-aldig-i-claim-superse-4">Yerini aldığı claim (supersedes)</Label>
                <SearchablePicker id="claim-form-yerini-aldig-i-claim-superse-4" items={claimItems} value={supersedes} onChange={setSupersedes} placeholder="Claim ara…" />
              </div>
            </>
          )}
          {error && <p className="text-sm text-priority-critical-text">{error}</p>}
        </div>
        <DialogFooter>
          <Button onClick={submit} disabled={submitting || !text.trim() || !sourceId}>
            {submitting ? "Ekleniyor…" : "Ekle"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
