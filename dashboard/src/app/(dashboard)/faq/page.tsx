"use client";

import { useState, useEffect, useCallback } from "react";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Plus, Pencil, Trash2, Filter, Loader2 } from "lucide-react";
import { Label } from "@/components/ui/label";
import { ErrorCard } from "@/components/dashboard/error-card";
import { createFaq, deleteFaq, getFaqs, updateFaq } from "@/lib/api";
import { useTenantId } from "@/lib/tenant";

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

  // Add/Edit dialog state
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

  useEffect(() => { fetchFaqs(); }, [fetchFaqs]);

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

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">FAQ Management</h1>
        <Button onClick={openAdd}>
          <Plus className="w-4 h-4 mr-2" /> Add FAQ
        </Button>
      </div>

      {/* Add/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingFaq ? "Edit FAQ" : "Add New FAQ"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 pt-4">
            <div>
              <Label>Category</Label>
              <Input
                placeholder="e.g. Services"
                value={formCategory}
                onChange={(e) => setFormCategory(e.target.value)}
              />
            </div>
            <div>
              <Label>Question</Label>
              <Input
                placeholder="What is..."
                value={formQuestion}
                onChange={(e) => setFormQuestion(e.target.value)}
              />
            </div>
            <div>
              <Label>Answer</Label>
              <Textarea
                placeholder="The answer..."
                rows={4}
                value={formAnswer}
                onChange={(e) => setFormAnswer(e.target.value)}
              />
            </div>
            {saveError && (
              <p className="text-sm text-red-600 dark:text-red-400">{saveError}</p>
            )}
            <Button className="w-full" onClick={handleSave} disabled={saving || !formCategory || !formQuestion || !formAnswer}>
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
              {editingFaq ? "Update FAQ" : "Save FAQ"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Category badges */}
      <div className="flex gap-2 flex-wrap">
        <Badge
          variant={activeCategory === null ? "secondary" : "outline"}
          className="cursor-pointer"
          onClick={() => setActiveCategory(null)}
        >
          All ({faqs.length})
        </Badge>
        {categories.map((cat) => (
          <Badge
            key={cat}
            variant={activeCategory === cat ? "secondary" : "outline"}
            className="cursor-pointer"
            onClick={() => setActiveCategory(activeCategory === cat ? null : cat)}
          >
            {cat} ({faqs.filter((f) => f.category === cat).length})
          </Badge>
        ))}
      </div>

      <Card className="p-0">
        <div className="flex items-center justify-between p-4 border-b border-border">
          <button className="p-1.5 rounded hover:bg-muted"><Filter className="w-4 h-4" /></button>
          <Input
            placeholder="Search FAQs..."
            className="w-56 h-8"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Category</TableHead>
              <TableHead>Question</TableHead>
              <TableHead>Answer</TableHead>
              <TableHead className="w-20">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((faq) => (
              <TableRow key={faq.id}>
                <TableCell>
                  <Badge variant="outline">{faq.category}</Badge>
                </TableCell>
                <TableCell className="font-medium">{faq.question}</TableCell>
                <TableCell className="text-muted-foreground max-w-xs truncate">
                  {faq.answer}
                </TableCell>
                <TableCell>
                  <div className="flex gap-1">
                    <button
                      className="p-1.5 rounded hover:bg-muted"
                      onClick={() => openEdit(faq)}
                    >
                      <Pencil className="w-3.5 h-3.5 text-muted-foreground" />
                    </button>
                    <button
                      className="p-1.5 rounded hover:bg-red-50 dark:hover:bg-red-900/20"
                      onClick={() => handleDelete(faq.id)}
                    >
                      <Trash2 className="w-3.5 h-3.5 text-red-500" />
                    </button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
            {filtered.length === 0 && (
              <TableRow>
                <TableCell colSpan={4} className="text-center text-muted-foreground py-8">
                  No FAQs found
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}
