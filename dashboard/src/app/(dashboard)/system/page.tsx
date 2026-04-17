"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Card } from "@/components/ui/card";
import { Activity, CheckCircle2, XCircle, ShieldAlert, Loader2 } from "lucide-react";
import { API_BASE } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface ServiceStatus {
  name: string;
  status: "up" | "down" | "unknown";
  detail?: string;
}

export default function SystemPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [statuses, setStatuses] = useState<ServiceStatus[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (user && user.role !== "admin") {
      router.push("/overview");
    }
  }, [user, router]);

  useEffect(() => {
    (async () => {
      const checks: ServiceStatus[] = [];

      // Backend health
      try {
        const res = await fetch(`${API_BASE}/health`);
        if (!res.ok) {
          checks.push({ name: "Backend API", status: "down", detail: `HTTP ${res.status}` });
        } else {
          const data = await res.json();
          checks.push({
            name: "Backend API",
            status: "up",
            detail: `${data.service} v${data.version ?? "?"}`,
          });
        }
      } catch {
        checks.push({ name: "Backend API", status: "down", detail: "Unreachable" });
      }

      // Tenant list (implies DB connectivity + admin auth)
      try {
        const res = await fetch(`${API_BASE}/admin/tenants`, {
          credentials: "include",
        });
        if (!res.ok) {
          checks.push({
            name: "Supabase PostgreSQL",
            status: "down",
            detail: res.status === 401 || res.status === 403
              ? "Not authorized"
              : `HTTP ${res.status}`,
          });
        } else {
          const data = await res.json();
          const count = Array.isArray(data) ? data.length : 0;
          checks.push({
            name: "Supabase PostgreSQL",
            status: "up",
            detail: `${count} tenant${count === 1 ? "" : "s"} active`,
          });
        }
      } catch {
        checks.push({ name: "Supabase PostgreSQL", status: "down", detail: "Query failed" });
      }

      setStatuses(checks);
      setLoading(false);
    })();
  }, []);

  if (user?.role !== "admin") return null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold flex items-center gap-2">
          <Activity className="w-6 h-6" /> System Health
        </h1>
        <p className="text-sm text-muted-foreground mt-1 flex items-center gap-1">
          <ShieldAlert className="w-3 h-3" /> Admin view — infrastructure status
        </p>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-40">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          {statuses.map((s) => (
            <Card key={s.name} className="p-5">
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-medium">{s.name}</div>
                  {s.detail && (
                    <div className="text-xs text-muted-foreground mt-1">{s.detail}</div>
                  )}
                </div>
                {s.status === "up" ? (
                  <CheckCircle2 className="w-6 h-6 text-green-500" />
                ) : (
                  <XCircle className="w-6 h-6 text-red-500" />
                )}
              </div>
            </Card>
          ))}
        </div>
      )}

      <Card className="p-5">
        <h3 className="font-medium mb-3">Service Endpoints</h3>
        <div className="space-y-2 text-sm font-mono">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Backend API</span>
            <a href={API_BASE} target="_blank" rel="noopener" className="text-primary hover:underline">
              {API_BASE}
            </a>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Voice webhook</span>
            <span>{API_BASE}/voice/incoming-call</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">WebSocket stream</span>
            <span>{API_BASE.replace("https://", "wss://")}/ws/media-stream/{"{call_sid}"}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">SMS inbound</span>
            <span>{API_BASE}/sms/inbound</span>
          </div>
        </div>
      </Card>
    </div>
  );
}
