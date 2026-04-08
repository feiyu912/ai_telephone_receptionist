"use client";

import { useState, useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Phone, Filter, Loader2 } from "lucide-react";
import { getCalls } from "@/lib/api";

const TENANT_ID = process.env.NEXT_PUBLIC_TENANT_ID || "11111111-1111-1111-1111-111111111111";

interface Call {
  call_sid: string;
  caller_phone: string;
  called_number: string;
  tier: string;
  status: string;
  started_at: string;
  last_activity_at: string;
}

const statusColors: Record<string, string> = {
  active: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  closed: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  voicemail: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
  transferred: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
};

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} hour${hours > 1 ? "s" : ""} ago`;
  const days = Math.floor(hours / 24);
  return `${days} day${days > 1 ? "s" : ""} ago`;
}

export default function CallHistoryPage() {
  const [calls, setCalls] = useState<Call[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    getCalls(TENANT_ID)
      .then(setCalls)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const filtered = calls.filter(
    (c) =>
      !search ||
      c.caller_phone.includes(search) ||
      c.call_sid.includes(search)
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Call History</h1>

      <Card className="p-0">
        <div className="flex items-center justify-between p-4 border-b border-border">
          <div className="flex items-center gap-2">
            <button className="p-1.5 rounded hover:bg-muted"><Filter className="w-4 h-4" /></button>
          </div>
          <Input
            placeholder="Search calls..."
            className="w-56 h-8"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Call SID</TableHead>
              <TableHead>Caller</TableHead>
              <TableHead>Tier</TableHead>
              <TableHead>Date</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((call) => (
              <TableRow key={call.call_sid} className="cursor-pointer hover:bg-muted/50">
                <TableCell className="font-mono text-sm">#{call.call_sid.slice(0, 10)}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <Phone className="w-3.5 h-3.5 text-muted-foreground" />
                    {call.caller_phone}
                  </div>
                </TableCell>
                <TableCell>{call.tier}</TableCell>
                <TableCell className="text-muted-foreground">{timeAgo(call.started_at)}</TableCell>
                <TableCell>
                  <Badge variant="secondary" className={statusColors[call.status] || ""}>
                    {call.status}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
            {filtered.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-muted-foreground py-8">
                  No calls found
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}
