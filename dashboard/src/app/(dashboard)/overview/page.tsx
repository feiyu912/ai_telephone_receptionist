"use client";

import { useCallback, useEffect, useState } from "react";
import { Brain, Phone, Users, Zap } from "lucide-react";
import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { ErrorCard } from "@/components/dashboard/error-card";
import { OverviewCard } from "@/components/dashboard/overview-card";
import { PageSpinner, PanelCard } from "@/components/dashboard/loading";
import { getAnalytics } from "@/lib/api";
import { useTenantId } from "@/lib/tenant";

interface Analytics {
  total_calls: number;
  total_customers: number;
  total_memory_facts: number;
  event_breakdown: { event_type: string; cnt: number }[];
}

const PIE_COLORS = ["#5750F1", "#22AD5C", "#0ABEF9", "#FFA70B", "#F23030", "#8155FF"];

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

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(load, [load]);

  if (error) return <ErrorCard message={error} onRetry={load} />;
  if (!data) return <PageSpinner />;

  const outcomeData = data.event_breakdown
    .filter((e) =>
      ["call_completed", "call_started", "sms_followup_sent", "transfer_requested"].includes(
        e.event_type,
      ),
    )
    .map((e, i) => ({
      name: e.event_type.replace(/_/g, " "),
      value: e.cnt,
      color: PIE_COLORS[i % PIE_COLORS.length],
    }));

  return (
    <div className="space-y-6 2xl:space-y-7.5">
      <div className="grid gap-4 sm:grid-cols-2 sm:gap-6 xl:grid-cols-4 2xl:gap-7.5">
        <OverviewCard
          label="Total Calls"
          value={data.total_calls.toLocaleString()}
          Icon={Phone}
          iconClassName="bg-primary/10 text-primary"
        />
        <OverviewCard
          label="Active Customers"
          value={data.total_customers.toLocaleString()}
          Icon={Users}
          iconClassName="bg-green-light-7 text-green"
        />
        <OverviewCard
          label="Memory Facts"
          value={data.total_memory_facts.toLocaleString()}
          Icon={Brain}
          iconClassName="bg-blue-light-5 text-blue"
        />
        <OverviewCard
          label="Event Types"
          value={data.event_breakdown.length}
          Icon={Zap}
          iconClassName="bg-yellow-light-4 text-yellow-dark"
        />
      </div>

      <div className="grid gap-4 sm:gap-6 lg:grid-cols-2 2xl:gap-7.5">
        <PanelCard title="Event Breakdown">
          {outcomeData.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie
                    data={outcomeData}
                    innerRadius={60}
                    outerRadius={95}
                    dataKey="value"
                    paddingAngle={2}
                    stroke="none"
                  >
                    {outcomeData.map((entry, i) => (
                      <Cell key={i} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      background: "#fff",
                      border: "1px solid #E6EBF1",
                      borderRadius: "8px",
                      fontSize: "12px",
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
              <ul className="mt-4 space-y-2">
                {data.event_breakdown.map((item) => (
                  <li
                    key={item.event_type}
                    className="flex items-center justify-between text-sm"
                  >
                    <span className="text-dark-5 dark:text-dark-6">
                      {item.event_type.replace(/_/g, " ")}
                    </span>
                    <span className="font-mono font-semibold text-dark dark:text-white">
                      {item.cnt}
                    </span>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="py-12 text-center text-sm text-dark-5 dark:text-dark-6">
              No events yet — calls will appear here as they come in.
            </p>
          )}
        </PanelCard>

        <PanelCard title="Quick Stats">
          <div className="space-y-3">
            <Stat label="Total Calls" value={data.total_calls} />
            <Stat label="Customers" value={data.total_customers} />
            <Stat label="Memory Facts Stored" value={data.total_memory_facts} />
          </div>
        </PanelCard>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center justify-between rounded-lg bg-gray-2 p-4 dark:bg-dark-2">
      <span className="text-sm font-medium text-dark-5 dark:text-dark-6">
        {label}
      </span>
      <span className="text-2xl font-bold text-dark dark:text-white">
        {value.toLocaleString()}
      </span>
    </div>
  );
}
