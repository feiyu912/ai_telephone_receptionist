"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Plus, Pencil, Trash2, Filter } from "lucide-react";
import { Label } from "@/components/ui/label";

const faqs = [
  { id: 1, category: "Company Overview", question: "What is YourCompany?", answer: "YourCompany is a digital technology consulting agency..." },
  { id: 2, category: "Company Overview", question: "Where is YourCompany located?", answer: "We are headquartered in Chicago, Illinois." },
  { id: 3, category: "Services", question: "What services do you offer?", answer: "We offer AI consulting, digital transformation, and marketing automation." },
  { id: 4, category: "Services", question: "Do you build custom AI solutions?", answer: "Yes, we build custom AI solutions tailored to your business needs." },
  { id: 5, category: "Pricing", question: "How much do your services cost?", answer: "Pricing is customized based on your needs. Contact us for a quote." },
  { id: 6, category: "Support", question: "How do I contact support?", answer: "You can call us or email support@360dmmc.com." },
];

const categories = ["Company Overview", "Services", "Pricing", "Support"];

export default function FaqPage() {
  const [search, setSearch] = useState("");
  const filtered = faqs.filter(
    (f) =>
      f.question.toLowerCase().includes(search.toLowerCase()) ||
      f.answer.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">FAQ Management</h1>
        <Dialog>
          <DialogTrigger>
            <Button><Plus className="w-4 h-4 mr-2" /> Add FAQ</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add New FAQ</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 pt-4">
              <div>
                <Label>Category</Label>
                <Input placeholder="e.g. Services" />
              </div>
              <div>
                <Label>Question</Label>
                <Input placeholder="What is..." />
              </div>
              <div>
                <Label>Answer</Label>
                <Textarea placeholder="The answer..." rows={4} />
              </div>
              <Button className="w-full">Save FAQ</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Category badges */}
      <div className="flex gap-2">
        <Badge variant="secondary" className="cursor-pointer bg-primary/10 text-primary">All ({faqs.length})</Badge>
        {categories.map((cat) => (
          <Badge key={cat} variant="outline" className="cursor-pointer">
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
                    <button className="p-1.5 rounded hover:bg-muted">
                      <Pencil className="w-3.5 h-3.5 text-muted-foreground" />
                    </button>
                    <button className="p-1.5 rounded hover:bg-red-50 dark:hover:bg-red-900/20">
                      <Trash2 className="w-3.5 h-3.5 text-red-500" />
                    </button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}
