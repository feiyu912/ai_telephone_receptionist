"use client";

import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Filter, SlidersHorizontal } from "lucide-react";

const customers = [
  { id: "c001", name: "John Smith", phone: "+1 (312) 555-0142", email: "john@example.com", calls: 8, lastCall: "Just now", sentiment: "positive" },
  { id: "c002", name: "Sarah Johnson", phone: "+1 (773) 555-0198", email: "sarah@co.com", calls: 5, lastCall: "1 hour ago", sentiment: "positive" },
  { id: "c003", name: "Guest", phone: "+1 (847) 555-0163", email: "", calls: 2, lastCall: "Yesterday", sentiment: "neutral" },
  { id: "c004", name: "Mike Chen", phone: "+1 (630) 555-0177", email: "mike@startup.io", calls: 12, lastCall: "2 days ago", sentiment: "positive" },
  { id: "c005", name: "Guest", phone: "+1 (708) 555-0189", email: "", calls: 1, lastCall: "3 days ago", sentiment: "negative" },
  { id: "c006", name: "Emily Davis", phone: "+1 (312) 555-0155", email: "emily@agency.com", calls: 6, lastCall: "1 week ago", sentiment: "positive" },
];

const sentimentColors: Record<string, string> = {
  positive: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  neutral: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400",
  negative: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
};

export default function CustomersPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Customers</h1>

      <Card className="p-0">
        <div className="flex items-center justify-between p-4 border-b border-border">
          <div className="flex items-center gap-2">
            <button className="p-1.5 rounded hover:bg-muted"><Filter className="w-4 h-4" /></button>
            <button className="p-1.5 rounded hover:bg-muted"><SlidersHorizontal className="w-4 h-4" /></button>
          </div>
          <Input placeholder="Search customers..." className="w-56 h-8" />
        </div>

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Customer</TableHead>
              <TableHead>Phone</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Calls</TableHead>
              <TableHead>Last Call</TableHead>
              <TableHead>Sentiment</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {customers.map((c) => (
              <TableRow key={c.id} className="cursor-pointer hover:bg-muted/50">
                <TableCell>
                  <div className="flex items-center gap-2">
                    <Avatar className="w-8 h-8">
                      <AvatarFallback className="text-xs">
                        {c.name === "Guest" ? "?" : c.name.split(" ").map(n => n[0]).join("")}
                      </AvatarFallback>
                    </Avatar>
                    <span className="font-medium">{c.name}</span>
                  </div>
                </TableCell>
                <TableCell className="text-muted-foreground">{c.phone}</TableCell>
                <TableCell className="text-muted-foreground">{c.email || "—"}</TableCell>
                <TableCell>{c.calls}</TableCell>
                <TableCell className="text-muted-foreground">{c.lastCall}</TableCell>
                <TableCell>
                  <Badge variant="secondary" className={sentimentColors[c.sentiment]}>
                    {c.sentiment}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}
