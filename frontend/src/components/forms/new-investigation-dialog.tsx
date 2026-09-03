"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/toast";

/**
 * Yeni investigation açar (Faz 11 tarama bulgusu F38).
 *
 * `POST /investigations` backend'de baştan beri vardı; arayüzde ne api metodu ne buton vardı,
 * yani bir investigation UI'dan hiç açılamıyordu. Faz 3 roadmap'te ✅ ama graf'ta 0
 * investigation olmasının sebebi buydu.
 */
export function NewInvestigationDialog({ onCreated }: { onCreated: () => void }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [question, setQuestion] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!title.trim() || !question.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.investigations.create({
        title: title.trim(),
        research_question: question.trim(),
      });
      toast(`"${title.trim()}" açıldı`, "success");
      setTitle("");
      setQuestion("");
      setOpen(false);
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bilinmeyen hata");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button size="sm">
            <Plus aria-hidden className="h-4 w-4" />
            Yeni investigation
          </Button>
        }
      />
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Yeni investigation aç</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="inv-title">Başlık</Label>
            <Input
              id="inv-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="ör. Astra güvenlik eşiği"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="inv-question">Araştırma sorusu</Label>
            <Input
              id="inv-question"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Cevaplanabilir tek bir soru yaz"
            />
            <p className="text-xs text-text-tertiary">
              Investigation OPEN olarak başlar; kapanışta yalnızca doğrulanmış finding&apos;ler
              kalıcı bilgiye yükselir.
            </p>
          </div>
          {error && <p className="text-sm text-priority-critical">{error}</p>}
        </div>
        <DialogFooter>
          <Button onClick={submit} disabled={submitting || !title.trim() || !question.trim()}>
            {submitting ? "Açılıyor…" : "Aç"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
