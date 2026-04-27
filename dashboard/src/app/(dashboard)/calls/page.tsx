"use client";

import { useCallback, useEffect, useState } from "react";
import { Phone, Search } from "lucide-react";
import { ErrorCard } from "@/components/dashboard/error-card";
import { PageSpinner, PanelCard } from "@/components/dashboard/loading";
import { getCalls } from "@/lib/api";
import { useTenantId } from "@/lib/tenant";
import { cn } from "@/lib/utils";

interface Call {
  call_sid: string;
  caller_phone: string;
  called_number: string;
  tier: string;
  status: string;
  started_at: string;
  last_activity_at: string;
}

const STATUS_STYLES: Record<string, string> = {
  active: "bg-green-light-7 text-green",
  closed: "bg-blue-light-5 text-blue",
  voicemail: "bg-yellow-light-4 text-yellow-dark",
  transferred: "bg-primary/10 text-primary",
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
  const [calls, setCalls] = useState<Call[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const tenantId = useTenantId();

  const load = useCallback(() => {
    if (!tenantId) return;
    setError(null);
    setCalls(null);
    getCalls(tenantId)
      .then(setCalls)
      .catch((e: Error) => setError(e.message || "Request failed"));
  }, [tenantId]);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(load, [load]);

  if (error) return <ErrorCard message={error} onRetry={load} />;
  if (!calls) return <PageSpinner />;

  const filtered = calls.filter(
    (c) =>
      !search ||
      c.caller_phone.includes(search) ||
      c.call_sid.includes(search),
  );

  return (
    <PanelCard
      title={`${calls.length} calls`}
      action={
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-dark-5 dark:text-dark-6" />
          <input
            type="search"
            placeholder="Search calls…"
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
              <th className="px-6 py-3 font-medium">Call SID</th>
              <th className="px-6 py-3 font-medium">Caller</th>
              <th className="px-6 py-3 font-medium">Tier</th>
              <th className="px-6 py-3 font-medium">Date</th>
              <th className="px-6 py-3 font-medium">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-stroke dark:divide-stroke-dark">
            {filtered.map((call) => (
              <tr
                key={call.call_sid}
                className="cursor-pointer transition-colors hover:bg-gray-2/60 dark:hover:bg-dark-2/60"
              >
                <td className="px-6 py-3 font-mono text-xs text-dark-5 dark:text-dark-6">
                  #{call.call_sid.slice(0, 10)}
                </td>
                <td className="px-6 py-3">
                  <div className="flex items-center gap-2 font-medium text-dark dark:text-white">
                    <Phone className="size-3.5 text-dark-5 dark:text-dark-6" />
                    {call.caller_phone}
                  </div>
                </td>
                <td className="px-6 py-3 capitalize text-dark dark:text-white">
                  {call.tier}
                </td>
                <td className="px-6 py-3 text-dark-5 dark:text-dark-6">
                  {timeAgo(call.started_at)}
                </td>
                <td className="px-6 py-3">
                  <span
                    className={cn(
                      "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium capitalize",
                      STATUS_STYLES[call.status] ??
                        "bg-gray-3 text-dark-5 dark:bg-dark-3 dark:text-dark-6",
                    )}
                  >
                    {call.status}
                  </span>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={5} className="px-6 py-12 text-center text-dark-5 dark:text-dark-6">
                  No calls found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </PanelCard>
  );
}
