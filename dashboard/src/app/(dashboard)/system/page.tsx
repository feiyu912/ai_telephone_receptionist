"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, ShieldAlert, XCircle } from "lucide-react";
import { PageSpinner, PanelCard } from "@/components/dashboard/loading";
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

      try {
        const res = await fetch(`${API_BASE}/admin/tenants`, { credentials: "include" });
        if (!res.ok) {
          checks.push({
            name: "Supabase PostgreSQL",
            status: "down",
            detail:
              res.status === 401 || res.status === 403
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
      <p className="flex items-center gap-1.5 text-sm text-dark-5 dark:text-dark-6">
        <ShieldAlert className="size-3.5" /> Admin view — infrastructure status
      </p>

      {loading ? (
        <PageSpinner className="h-40" />
      ) : (
        <div className="grid gap-4 sm:gap-6 lg:grid-cols-2 2xl:gap-7.5">
          {statuses.map((s) => (
            <article
              key={s.name}
              className="rounded-[10px] bg-white p-6 shadow-1 dark:bg-gray-dark"
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-semibold text-dark dark:text-white">{s.name}</div>
                  {s.detail && (
                    <div className="mt-1 text-xs text-dark-5 dark:text-dark-6">
                      {s.detail}
                    </div>
                  )}
                </div>
                {s.status === "up" ? (
                  <CheckCircle2 className="size-6 text-green" />
                ) : (
                  <XCircle className="size-6 text-red" />
                )}
              </div>
            </article>
          ))}
        </div>
      )}

      <PanelCard title="Service endpoints">
        <div className="space-y-3 font-mono text-sm">
          <Endpoint label="Backend API" value={API_BASE} link={API_BASE} />
          <Endpoint label="Voice webhook" value={`${API_BASE}/voice/incoming-call`} />
          <Endpoint
            label="WebSocket stream"
            value={`${API_BASE.replace("https://", "wss://")}/ws/media-stream/{call_sid}`}
          />
          <Endpoint label="SMS inbound" value={`${API_BASE}/sms/inbound`} />
        </div>
      </PanelCard>
    </div>
  );
}

function Endpoint({
  label,
  value,
  link,
}: {
  label: string;
  value: string;
  link?: string;
}) {
  return (
    <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
      <span className="text-dark-5 dark:text-dark-6">{label}</span>
      {link ? (
        <a
          href={link}
          target="_blank"
          rel="noopener"
          className="text-primary hover:underline"
        >
          {value}
        </a>
      ) : (
        <span className="text-dark dark:text-white">{value}</span>
      )}
    </div>
  );
}
