"use client";

import { useState, useEffect } from "react";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Filter, Loader2 } from "lucide-react";
import { getCustomers } from "@/lib/api";
import { useTenantId } from "@/lib/tenant";

interface Customer {
  customer_id: string;
  phone: string;
  name: string;
  email: string | null;
  tier: string;
  key_facts: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

function timeAgo(dateStr: string): string {
  if (!dateStr) return "—";
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default function CustomersPage() {
  const [customers, setCustomers] = useState<Customer[] | null>(null);
  const [search, setSearch] = useState("");

  const tenantId = useTenantId();

  useEffect(() => {
    if (!tenantId) return;
    getCustomers(tenantId)
      .then(setCustomers)
      .catch(console.error)
  }, [tenantId]);

  if (!customers) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const filtered = customers.filter(
    (c) =>
      !search ||
      c.name.toLowerCase().includes(search.toLowerCase()) ||
      c.phone.includes(search) ||
      (c.email || "").toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Customers</h1>

      <Card className="p-0">
        <div className="flex items-center justify-between p-4 border-b border-border">
          <div className="flex items-center gap-2">
            <button className="p-1.5 rounded hover:bg-muted"><Filter className="w-4 h-4" /></button>
          </div>
          <Input
            placeholder="Search customers..."
            className="w-56 h-8"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Customer</TableHead>
              <TableHead>Phone</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Last Activity</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((c) => (
              <TableRow key={c.customer_id} className="cursor-pointer hover:bg-muted/50">
                <TableCell>
                  <div className="flex items-center gap-2">
                    <Avatar className="w-8 h-8">
                      <AvatarFallback className="text-xs">
                        {c.name === "Guest" ? "?" : c.name.split(" ").map(n => n[0]).join("").slice(0, 2)}
                      </AvatarFallback>
                    </Avatar>
                    <span className="font-medium">{c.name}</span>
                  </div>
                </TableCell>
                <TableCell className="text-muted-foreground">{c.phone}</TableCell>
                <TableCell className="text-muted-foreground">{c.email || "—"}</TableCell>
                <TableCell className="text-muted-foreground">{timeAgo(c.updated_at)}</TableCell>
              </TableRow>
            ))}
            {filtered.length === 0 && (
              <TableRow>
                <TableCell colSpan={4} className="text-center text-muted-foreground py-8">
                  No customers found
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}
