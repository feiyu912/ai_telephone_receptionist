"use client";

import { useState, useEffect } from "react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Separator } from "@/components/ui/separator";
import { getCalls, getCustomers } from "@/lib/api";

const TENANT_ID = process.env.NEXT_PUBLIC_TENANT_ID || "11111111-1111-1111-1111-111111111111";

interface Call {
  call_sid: string;
  caller_phone: string;
  status: string;
  started_at: string;
}

interface Customer {
  phone: string;
  name: string;
}

function timeAgo(dateStr: string): string {
  if (!dateStr) return "";
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

const statusColors: Record<string, string> = {
  active: "bg-green-500",
  closed: "bg-blue-500",
  voicemail: "bg-yellow-500",
};

export function RightPanel() {
  const [calls, setCalls] = useState<Call[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);

  useEffect(() => {
    getCalls(TENANT_ID).then((data) => setCalls(data.slice(0, 5))).catch(() => {});
    getCustomers(TENANT_ID).then((data) => setCustomers(data.slice(0, 5))).catch(() => {});
  }, []);

  return (
    <aside className="w-72 border-l border-border bg-card h-screen sticky top-0 overflow-y-auto hidden xl:block">
      {/* Recent Calls */}
      <div className="p-5">
        <h3 className="font-semibold text-sm mb-3">Recent Calls</h3>
        <div className="space-y-3">
          {calls.length > 0 ? calls.map((c, i) => (
            <div key={i} className="flex items-start gap-2">
              <div className={`w-2 h-2 rounded-full mt-1.5 ${statusColors[c.status] || "bg-gray-400"}`} />
              <div>
                <p className="text-sm">{c.caller_phone}</p>
                <p className="text-xs text-muted-foreground">{c.status} · {timeAgo(c.started_at)}</p>
              </div>
            </div>
          )) : (
            <p className="text-xs text-muted-foreground">No recent calls</p>
          )}
        </div>
      </div>

      <Separator />

      {/* Recent Customers */}
      <div className="p-5">
        <h3 className="font-semibold text-sm mb-3">Recent Customers</h3>
        <div className="space-y-2">
          {customers.length > 0 ? customers.map((c, i) => (
            <div key={i} className="flex items-center gap-2">
              <Avatar className="w-7 h-7">
                <AvatarFallback className="text-xs">
                  {c.name === "Guest" ? "?" : c.name.split(" ").map(n => n[0]).join("").slice(0, 2)}
                </AvatarFallback>
              </Avatar>
              <div>
                <p className="text-sm">{c.name}</p>
                <p className="text-xs text-muted-foreground">{c.phone}</p>
              </div>
            </div>
          )) : (
            <p className="text-xs text-muted-foreground">No customers yet</p>
          )}
        </div>
      </div>
    </aside>
  );
}
