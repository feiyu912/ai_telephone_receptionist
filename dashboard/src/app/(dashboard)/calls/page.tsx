"use client";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Phone, Filter, SlidersHorizontal, Plus } from "lucide-react";

const calls = [
  { sid: "CA4064d0", phone: "+1 (312) 555-0142", tier: "Growth", date: "Just now", status: "active", duration: "2:34" },
  { sid: "CA8e6cac", phone: "+1 (773) 555-0198", tier: "Starter", date: "5 min ago", status: "closed", duration: "4:12" },
  { sid: "CA29df17", phone: "+1 (847) 555-0163", tier: "Growth", date: "1 hour ago", status: "closed", duration: "1:45" },
  { sid: "CAcf99c4", phone: "+1 (630) 555-0177", tier: "Pro", date: "2 hours ago", status: "closed", duration: "6:21" },
  { sid: "CA5a396d", phone: "+1 (312) 555-0155", tier: "Growth", date: "Yesterday", status: "closed", duration: "3:08" },
  { sid: "CA0dbc17", phone: "+1 (708) 555-0189", tier: "Starter", date: "Yesterday", status: "voicemail", duration: "0:45" },
  { sid: "CA73fe75", phone: "+1 (312) 555-0142", tier: "Growth", date: "Feb 2, 2026", status: "closed", duration: "5:33" },
  { sid: "CA180cb1", phone: "+1 (847) 555-0163", tier: "Pro", date: "Feb 2, 2026", status: "transferred", duration: "2:15" },
];

const statusColors: Record<string, string> = {
  active: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  closed: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  voicemail: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
  transferred: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
};

export default function CallHistoryPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Call History</h1>

      <Card className="p-0">
        {/* Toolbar */}
        <div className="flex items-center justify-between p-4 border-b border-border">
          <div className="flex items-center gap-2">
            <button className="p-1.5 rounded hover:bg-muted"><Plus className="w-4 h-4" /></button>
            <button className="p-1.5 rounded hover:bg-muted"><Filter className="w-4 h-4" /></button>
            <button className="p-1.5 rounded hover:bg-muted"><SlidersHorizontal className="w-4 h-4" /></button>
          </div>
          <Input placeholder="Search calls..." className="w-56 h-8" />
        </div>

        {/* Table */}
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10"><input type="checkbox" className="rounded" /></TableHead>
              <TableHead>Call SID</TableHead>
              <TableHead>Caller</TableHead>
              <TableHead>Tier</TableHead>
              <TableHead>Duration</TableHead>
              <TableHead>Date</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {calls.map((call) => (
              <TableRow key={call.sid} className="cursor-pointer hover:bg-muted/50">
                <TableCell><input type="checkbox" className="rounded" /></TableCell>
                <TableCell className="font-mono text-sm">#{call.sid}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <Phone className="w-3.5 h-3.5 text-muted-foreground" />
                    {call.phone}
                  </div>
                </TableCell>
                <TableCell>{call.tier}</TableCell>
                <TableCell>{call.duration}</TableCell>
                <TableCell className="text-muted-foreground">{call.date}</TableCell>
                <TableCell>
                  <Badge variant="secondary" className={statusColors[call.status]}>
                    {call.status}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>

        {/* Pagination */}
        <div className="flex items-center justify-center gap-1 p-4 border-t border-border">
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              className={`px-3 py-1 rounded text-sm ${
                n === 1 ? "bg-primary/10 text-primary font-medium" : "hover:bg-muted text-muted-foreground"
              }`}
            >
              {n}
            </button>
          ))}
          <button className="px-2 py-1 rounded hover:bg-muted text-muted-foreground">&gt;</button>
        </div>
      </Card>
    </div>
  );
}
