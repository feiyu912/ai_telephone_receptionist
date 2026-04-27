"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Brain, Building2, Phone, ShieldAlert, Users } from "lucide-react";
import { OverviewCard } from "@/components/dashboard/overview-card";
import { PageSpinner, PanelCard } from "@/components/dashboard/loading";
import { api } from "@/lib/api";
import { useTenant, type Tenant } from "@/lib/tenant";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

interface TenantWithStats extends Tenant {
  total_calls?: number;
  total_customers?: number;
  total_memory_facts?: number;
}

const TIER_STYLES: Record<string, string> = {
  starter: "bg-gray-3 text-dark-5 dark:bg-dark-3 dark:text-dark-6",
  growth: "bg-blue-light-5 text-blue",
  pro: "bg-primary/10 text-primary",
};

export default function TenantsPage() {
  const { user } = useAuth();
  const router = useRouter();
  const { tenants, setCurrentId } = useTenant();
  const [stats, setStats] = useState<Record<string, TenantWithStats>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (user && user.role !== "admin") {
      router.push("/overview");
    }
  }, [user, router]);

  useEffect(() => {
    if (tenants.length === 0) return;
    (async () => {
      const results: Record<string, TenantWithStats> = {};
      for (const t of tenants) {
        try {
          const analytics = await api(`/admin/analytics/${t.tenant_id}`);
          results[t.tenant_id] = { ...t, ...analytics };
        } catch {
          results[t.tenant_id] = { ...t };
        }
      }
      setStats(results);
      setLoading(false);
    })();
  }, [tenants]);

  if (user?.role !== "admin") return null;

  const openTenant = (tid: string) => {
    setCurrentId(tid);
    router.push("/overview");
  };

  const totalCalls = Object.values(stats).reduce((a, b) => a + (b.total_calls ?? 0), 0);
  const totalCustomers = Object.values(stats).reduce(
    (a, b) => a + (b.total_customers ?? 0),
    0,
  );
  const totalMemories = Object.values(stats).reduce(
    (a, b) => a + (b.total_memory_facts ?? 0),
    0,
  );

  return (
    <div className="space-y-6">
      <p className="flex items-center gap-1.5 text-sm text-dark-5 dark:text-dark-6">
        <ShieldAlert className="size-3.5" /> Admin view — showing data for all clients
      </p>

      <div className="grid gap-4 sm:grid-cols-2 sm:gap-6 xl:grid-cols-4 2xl:gap-7.5">
        <OverviewCard
          label="Total Tenants"
          value={tenants.length}
          Icon={Building2}
          iconClassName="bg-primary/10 text-primary"
        />
        <OverviewCard
          label="Total Calls"
          value={totalCalls}
          Icon={Phone}
          iconClassName="bg-blue-light-5 text-blue"
        />
        <OverviewCard
          label="Total Customers"
          value={totalCustomers}
          Icon={Users}
          iconClassName="bg-green-light-7 text-green"
        />
        <OverviewCard
          label="Memory Facts"
          value={totalMemories}
          Icon={Brain}
          iconClassName="bg-yellow-light-4 text-yellow-dark"
        />
      </div>

      <PanelCard title={`${tenants.length} tenants`} className="overflow-hidden">
        {loading && tenants.length === 0 ? (
          <PageSpinner className="h-40" />
        ) : (
          <div className="-mx-6 -my-6 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-gray-2 text-xs uppercase tracking-wider text-dark-5 dark:bg-dark-2 dark:text-dark-6">
                <tr>
                  <th className="px-6 py-3 font-medium">Tenant</th>
                  <th className="px-6 py-3 font-medium">Phone</th>
                  <th className="px-6 py-3 font-medium">Tier</th>
                  <th className="px-6 py-3 font-medium">Calls</th>
                  <th className="px-6 py-3 font-medium">Customers</th>
                  <th className="px-6 py-3 font-medium">Memory Facts</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stroke dark:divide-stroke-dark">
                {tenants.map((t) => {
                  const s = stats[t.tenant_id];
                  return (
                    <tr
                      key={t.tenant_id}
                      className="cursor-pointer transition-colors hover:bg-gray-2/60 dark:hover:bg-dark-2/60"
                      onClick={() => openTenant(t.tenant_id)}
                    >
                      <td className="px-6 py-3">
                        <div className="flex items-center gap-3">
                          <span className="flex size-9 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
                            {t.company_name?.charAt(0) || "?"}
                          </span>
                          <div>
                            <div className="font-medium text-dark dark:text-white">
                              {t.company_name}
                            </div>
                            <div className="text-xs text-dark-5 dark:text-dark-6">
                              {t.slug}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-3 text-dark-5 dark:text-dark-6">
                        <div className="flex items-center gap-1">
                          <Phone className="size-3.5" />
                          {t.phone_number}
                        </div>
                      </td>
                      <td className="px-6 py-3">
                        <span
                          className={cn(
                            "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium capitalize",
                            TIER_STYLES[t.tier] ??
                              "bg-gray-3 text-dark-5 dark:bg-dark-3 dark:text-dark-6",
                          )}
                        >
                          {t.tier}
                        </span>
                      </td>
                      <td className="px-6 py-3 text-dark dark:text-white">
                        {s?.total_calls ?? "—"}
                      </td>
                      <td className="px-6 py-3 text-dark dark:text-white">
                        {s?.total_customers ?? "—"}
                      </td>
                      <td className="px-6 py-3 text-dark dark:text-white">
                        {s?.total_memory_facts ?? "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </PanelCard>
    </div>
  );
}
