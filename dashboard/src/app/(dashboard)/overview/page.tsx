"use client";

import { useCallback, useEffect, useState } from "react";
import { StatCard } from "@/components/dashboard/stat-card";
import { ErrorCard } from "@/components/dashboard/error-card";
import { Card } from "@/components/ui/card";
import { Loader2 } from "lucide-react";
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
} from "recharts";
import { getAnalytics } from "@/lib/api";
import { useTenantId } from "@/lib/tenant";

interface Analytics {
  total_calls: number;
  total_customers: number;
  total_memory_facts: number;
  event_breakdown: { event_type: string; cnt: number }[];
}

export default function OverviewPage() {
  const [data, setData] = useState<Analytics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const tenantId = useTenantId();

  const load = useCallback(() => {
    if (!tenantId) return;
    setError(null);
    setData(null);
    getAnalytics(tenantId)
      .then(setData)
      .catch((e: Error) => setError(e.message || "Request failed"));
  }, [tenantId]);

  useEffect(load, [load]);

  if (error) return <ErrorCard message={error} onRetry={load} />;

  if (!data) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const outcomeData = (data?.event_breakdown || [])
    .filter((e) => ["call_completed", "call_started", "sms_followup_sent", "transfer_requested"].includes(e.event_type))
    .map((e, i) => ({
      name: e.event_type.replace(/_/g, " "),
      value: e.cnt,
      color: ["#6366f1", "#8b5cf6", "#06b6d4", "#e5e7eb"][i % 4],
    }));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Overview</h1>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard label="Total Calls" value={String(data?.total_calls || 0)} className="bg-primary/5" />
        <StatCard label="Active Customers" value={String(data?.total_customers || 0)} />
        <StatCard label="Memory Facts" value={String(data?.total_memory_facts || 0)} />
        <StatCard label="Event Types" value={String(data?.event_breakdown?.length || 0)} />
      </div>

      {/* Event Breakdown */}
      <div className="grid grid-cols-2 gap-4">
        <Card className="p-5">
          <h3 className="font-medium mb-4">Event Breakdown</h3>
          {outcomeData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie data={outcomeData} innerRadius={50} outerRadius={80} dataKey="value" paddingAngle={2}>
                  {outcomeData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-muted-foreground text-sm py-8 text-center">No events yet</p>
          )}
          <div className="space-y-2 mt-2">
            {(data?.event_breakdown || []).map((item) => (
              <div key={item.event_type} className="flex items-center justify-between text-sm">
                <span>{item.event_type.replace(/_/g, " ")}</span>
                <span className="text-muted-foreground font-mono">{item.cnt}</span>
              </div>
            ))}
          </div>
        </Card>

        <Card className="p-5">
          <h3 className="font-medium mb-4">Quick Stats</h3>
          <div className="space-y-4">
            <div className="flex justify-between items-center p-3 bg-muted/50 rounded-lg">
              <span className="text-sm">Total Calls</span>
              <span className="text-2xl font-bold">{data?.total_calls || 0}</span>
            </div>
            <div className="flex justify-between items-center p-3 bg-muted/50 rounded-lg">
              <span className="text-sm">Customers</span>
              <span className="text-2xl font-bold">{data?.total_customers || 0}</span>
            </div>
            <div className="flex justify-between items-center p-3 bg-muted/50 rounded-lg">
              <span className="text-sm">Memory Facts Stored</span>
              <span className="text-2xl font-bold">{data?.total_memory_facts || 0}</span>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
