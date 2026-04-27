"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Loader2, Pencil, Plus, Search, Trash2 } from "lucide-react";
import { ErrorCard } from "@/components/dashboard/error-card";
import { PageSpinner, PanelCard } from "@/components/dashboard/loading";
import { createFaq, deleteFaq, getFaqs, updateFaq } from "@/lib/api";
import { useTenantId } from "@/lib/tenant";
import { cn } from "@/lib/utils";

const INPUT =
  "block w-full rounded-lg border border-stroke bg-transparent px-4 py-2.5 text-sm text-dark outline-none transition-colors focus:border-primary dark:border-stroke-dark dark:bg-dark-2 dark:text-white dark:placeholder:text-dark-6";

interface FAQ {
  id: number;
  category: string;
  question: string;
  answer: string;
  is_coming_soon: boolean;
}

export default function FaqPage() {
  const [faqs, setFaqs] = useState<FAQ[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [activeCategory, setActiveCategory] = useState<string | null>(null);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingFaq, setEditingFaq] = useState<FAQ | null>(null);
  const [formCategory, setFormCategory] = useState("");
  const [formQuestion, setFormQuestion] = useState("");
  const [formAnswer, setFormAnswer] = useState("");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const tenantId = useTenantId();

  const fetchFaqs = useCallback(async () => {
    if (!tenantId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getFaqs(tenantId);
      setFaqs(data);
    } catch (err) {
      setError((err as Error).message || "Failed to load FAQs");
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    fetchFaqs();
  }, [fetchFaqs]);

  const categories = [...new Set(faqs.map((f) => f.category))].sort();

  const filtered = faqs.filter((f) => {
    const matchesSearch =
      !search ||
      f.question.toLowerCase().includes(search.toLowerCase()) ||
      f.answer.toLowerCase().includes(search.toLowerCase());
    const matchesCategory = !activeCategory || f.category === activeCategory;
    return matchesSearch && matchesCategory;
  });

  const openAdd = () => {
    setEditingFaq(null);
    setFormCategory("");
    setFormQuestion("");
    setFormAnswer("");
    setSaveError(null);
    setDialogOpen(true);
  };

  const openEdit = (faq: FAQ) => {
    setEditingFaq(faq);
    setFormCategory(faq.category);
    setFormQuestion(faq.question);
    setFormAnswer(faq.answer);
    setSaveError(null);
    setDialogOpen(true);
  };

  const handleSave = async () => {
    if (!tenantId) return;
    setSaving(true);
    setSaveError(null);
    const body = {
      category: formCategory,
      question: formQuestion,
      answer: formAnswer,
    };
    try {
      if (editingFaq) {
        await updateFaq(tenantId, editingFaq.id, body);
      } else {
        await createFaq(tenantId, body);
      }
      setDialogOpen(false);
      await fetchFaqs();
    } catch (err) {
      setSaveError((err as Error).message || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!tenantId) return;
    if (!confirm("Are you sure you want to delete this FAQ?")) return;
    try {
      await deleteFaq(tenantId, id);
      await fetchFaqs();
    } catch (err) {
      alert((err as Error).message || "Delete failed");
    }
  };

  if (error) return <ErrorCard message={error} onRetry={fetchFaqs} />;
  if (loading) return <PageSpinner />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div className="flex flex-wrap gap-2">
          <CategoryPill
            active={activeCategory === null}
            onClick={() => setActiveCategory(null)}
          >
            All ({faqs.length})
          </CategoryPill>
          {categories.map((cat) => (
            <CategoryPill
              key={cat}
              active={activeCategory === cat}
              onClick={() => setActiveCategory(activeCategory === cat ? null : cat)}
            >
              {cat} ({faqs.filter((f) => f.category === cat).length})
            </CategoryPill>
          ))}
        </div>
        <button
          type="button"
          onClick={openAdd}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-primary/90"
        >
          <Plus className="size-4" /> Add FAQ
        </button>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingFaq ? "Edit FAQ" : "Add new FAQ"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 pt-4">
            <Field label="Category">
              <input
                className={INPUT}
                placeholder="e.g. Services"
                value={formCategory}
                onChange={(e) => setFormCategory(e.target.value)}
              />
            </Field>
            <Field label="Question">
              <input
                className={INPUT}
                placeholder="What is…"
                value={formQuestion}
                onChange={(e) => setFormQuestion(e.target.value)}
              />
            </Field>
            <Field label="Answer">
              <textarea
                className={cn(INPUT, "min-h-28")}
                placeholder="The answer…"
                rows={4}
                value={formAnswer}
                onChange={(e) => setFormAnswer(e.target.value)}
              />
            </Field>
            {saveError && <p className="text-sm text-red">{saveError}</p>}
            <button
              type="button"
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-primary/90 disabled:opacity-50"
              onClick={handleSave}
              disabled={saving || !formCategory || !formQuestion || !formAnswer}
            >
              {saving ? <Loader2 className="size-4 animate-spin" /> : null}
              {editingFaq ? "Update FAQ" : "Save FAQ"}
            </button>
          </div>
        </DialogContent>
      </Dialog>

      <PanelCard
        title={`${filtered.length} entries`}
        action={
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-dark-5 dark:text-dark-6" />
            <input
              type="search"
              placeholder="Search FAQs…"
              className="w-56 rounded-lg border border-stroke bg-gray-2 py-2 pl-9 pr-3 text-sm outline-none focus:border-primary dark:border-stroke-dark dark:bg-dark-2"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        }
        className="overflow-hidden"
      >
        <div className="-mx-6 -my-6 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-2 text-xs uppercase tracking-wider text-dark-5 dark:bg-dark-2 dark:text-dark-6">
              <tr>
                <th className="px-6 py-3 font-medium">Category</th>
                <th className="px-6 py-3 font-medium">Question</th>
                <th className="px-6 py-3 font-medium">Answer</th>
                <th className="w-24 px-6 py-3 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stroke dark:divide-stroke-dark">
              {filtered.map((faq) => (
                <tr key={faq.id}>
                  <td className="px-6 py-3">
                    <span className="inline-flex rounded-full border border-stroke bg-gray-2 px-2.5 py-0.5 text-xs font-medium text-dark-5 dark:border-stroke-dark dark:bg-dark-2 dark:text-dark-6">
                      {faq.category}
                    </span>
                  </td>
                  <td className="px-6 py-3 font-medium text-dark dark:text-white">
                    {faq.question}
                  </td>
                  <td className="max-w-xs truncate px-6 py-3 text-dark-5 dark:text-dark-6">
                    {faq.answer}
                  </td>
                  <td className="px-6 py-3">
                    <div className="flex justify-end gap-1">
                      <button
                        type="button"
                        className="rounded p-1.5 text-dark-5 hover:bg-gray-2 hover:text-dark dark:text-dark-6 dark:hover:bg-dark-2 dark:hover:text-white"
                        onClick={() => openEdit(faq)}
                      >
                        <Pencil className="size-3.5" />
                      </button>
                      <button
                        type="button"
                        className="rounded p-1.5 text-red hover:bg-red-light-5 dark:hover:bg-red/10"
                        onClick={() => handleDelete(faq.id)}
                      >
                        <Trash2 className="size-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-6 py-12 text-center text-dark-5 dark:text-dark-6">
                    No FAQs found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </PanelCard>
    </div>
  );
}

function CategoryPill({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
        active
          ? "border-primary bg-primary text-white"
          : "border-stroke bg-white text-dark-5 hover:border-primary hover:text-primary dark:border-stroke-dark dark:bg-gray-dark dark:text-dark-6",
      )}
    >
      {children}
    </button>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-dark-5 dark:text-dark-6">
        {label}
      </span>
      {children}
    </label>
  );
}
