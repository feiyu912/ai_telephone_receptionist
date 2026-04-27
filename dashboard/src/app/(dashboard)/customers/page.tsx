"use client";

import { useCallback, useEffect, useState } from "react";
import { Search } from "lucide-react";
import { ErrorCard } from "@/components/dashboard/error-card";
import { PageSpinner, PanelCard } from "@/components/dashboard/loading";
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

function initials(name: string): string {
  if (!name || name === "Guest") return "?";
  return name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

export default function CustomersPage() {
  const [customers, setCustomers] = useState<Customer[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const tenantId = useTenantId();

  const load = useCallback(() => {
    if (!tenantId) return;
    setError(null);
    setCustomers(null);
    getCustomers(tenantId)
      .then(setCustomers)
      .catch((e: Error) => setError(e.message || "Request failed"));
  }, [tenantId]);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(load, [load]);

  if (error) return <ErrorCard message={error} onRetry={load} />;
  if (!customers) return <PageSpinner />;

  const filtered = customers.filter(
    (c) =>
      !search ||
      c.name.toLowerCase().includes(search.toLowerCase()) ||
      c.phone.includes(search) ||
      (c.email || "").toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <PanelCard
      title={`${customers.length} customers`}
      action={
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-dark-5 dark:text-dark-6" />
          <input
            type="search"
            placeholder="Search customers…"
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
              <th className="px-6 py-3 font-medium">Customer</th>
              <th className="px-6 py-3 font-medium">Phone</th>
              <th className="px-6 py-3 font-medium">Email</th>
              <th className="px-6 py-3 font-medium">Last Activity</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-stroke dark:divide-stroke-dark">
            {filtered.map((c) => (
              <tr
                key={c.customer_id}
                className="cursor-pointer transition-colors hover:bg-gray-2/60 dark:hover:bg-dark-2/60"
              >
                <td className="px-6 py-3">
                  <div className="flex items-center gap-3">
                    <span className="flex size-9 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
                      {initials(c.name)}
                    </span>
                    <span className="font-medium text-dark dark:text-white">
                      {c.name}
                    </span>
                  </div>
                </td>
                <td className="px-6 py-3 text-dark-5 dark:text-dark-6">{c.phone}</td>
                <td className="px-6 py-3 text-dark-5 dark:text-dark-6">{c.email || "—"}</td>
                <td className="px-6 py-3 text-dark-5 dark:text-dark-6">
                  {timeAgo(c.updated_at)}
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={4} className="px-6 py-12 text-center text-dark-5 dark:text-dark-6">
                  No customers found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </PanelCard>
  );
}
