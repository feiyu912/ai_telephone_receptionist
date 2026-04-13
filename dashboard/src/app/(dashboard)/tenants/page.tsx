"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Loader2, Building2, Phone, ShieldAlert } from "lucide-react";
import { api } from "@/lib/api";
import { useTenant, type Tenant } from "@/lib/tenant";
import { useAuth } from "@/lib/auth";

interface TenantWithStats extends Tenant {
  total_calls?: number;
  total_customers?: number;
  total_memory_facts?: number;
}

const tierColors: Record<string, string> = {
  starter: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
  growth: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  pro: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
};

export default function TenantsPage() {
  const { user } = useAuth();
  const router = useRouter();
  const { tenants, setCurrentId } = useTenant();
  const [stats, setStats] = useState<Record<string, TenantWithStats>>({});
  const [loading, setLoading] = useState(true);

  // Gate: admin-only
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
  const totalCustomers = Object.values(stats).reduce((a, b) => a + (b.total_customers ?? 0), 0);
  const totalMemories = Object.values(stats).reduce((a, b) => a + (b.total_memory_facts ?? 0), 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <Building2 className="w-6 h-6" /> All Tenants
          </h1>
          <p className="text-sm text-muted-foreground mt-1 flex items-center gap-1">
            <ShieldAlert className="w-3 h-3" /> Admin view — showing data for all clients
          </p>
        </div>
      </div>

      {/* Aggregate stats */}
      <div className="grid grid-cols-4 gap-4">
        <Card className="p-5">
          <div className="text-sm text-muted-foreground">Total Tenants</div>
          <div className="text-3xl font-bold mt-1">{tenants.length}</div>
        </Card>
        <Card className="p-5">
          <div className="text-sm text-muted-foreground">Total Calls</div>
          <div className="text-3xl font-bold mt-1">{totalCalls}</div>
        </Card>
        <Card className="p-5">
          <div className="text-sm text-muted-foreground">Total Customers</div>
          <div className="text-3xl font-bold mt-1">{totalCustomers}</div>
        </Card>
        <Card className="p-5">
          <div className="text-sm text-muted-foreground">Memory Facts</div>
          <div className="text-3xl font-bold mt-1">{totalMemories}</div>
        </Card>
      </div>

      <Card className="p-0">
        {loading && tenants.length === 0 ? (
          <div className="flex items-center justify-center h-40">
            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Tenant</TableHead>
                <TableHead>Phone</TableHead>
                <TableHead>Tier</TableHead>
                <TableHead>Calls</TableHead>
                <TableHead>Customers</TableHead>
                <TableHead>Memory Facts</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tenants.map((t) => {
                const s = stats[t.tenant_id];
                return (
                  <TableRow
                    key={t.tenant_id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => openTenant(t.tenant_id)}
                  >
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-xs font-bold">
                          {t.company_name?.charAt(0) || "?"}
                        </div>
                        <div>
                          <div className="font-medium">{t.company_name}</div>
                          <div className="text-xs text-muted-foreground">{t.slug}</div>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      <div className="flex items-center gap-1">
                        <Phone className="w-3.5 h-3.5" />
                        {t.phone_number}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary" className={tierColors[t.tier] || ""}>
                        {t.tier}
                      </Badge>
                    </TableCell>
                    <TableCell>{s?.total_calls ?? "—"}</TableCell>
                    <TableCell>{s?.total_customers ?? "—"}</TableCell>
                    <TableCell>{s?.total_memory_facts ?? "—"}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </Card>
    </div>
  );
}
