"use client";

import { useState, useEffect, useCallback } from "react";
import { Check, ExternalLink } from "lucide-react";
import { PageSpinner } from "@/components/dashboard/loading";
import { getOAuthStatus, API_BASE } from "@/lib/api";
import { useTenantId } from "@/lib/tenant";
import { cn } from "@/lib/utils";

interface OAuthStatus {
  hubspot?: { connected: boolean; updated_at?: string };
  microsoft?: { connected: boolean; updated_at?: string };
}

export default function IntegrationsPage() {
  const tenantId = useTenantId();
  const [status, setStatus] = useState<OAuthStatus>({});
  const [loading, setLoading] = useState(true);

  const fetchStatus = useCallback(async () => {
    if (!tenantId) return;
    try {
      const data = await getOAuthStatus(tenantId);
      setStatus(data);
    } catch (err) {
      console.error("Failed to load OAuth status:", err);
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  const integrations = [
    {
      name: "HubSpot CRM",
      description: "Sync contacts, create engagement notes, and track meetings.",
      tone: "bg-orange-light/15 text-orange-light",
      connected: status.hubspot?.connected ?? false,
      connectUrl: `${API_BASE}/oauth/hubspot/authorize/${tenantId}`,
      env: "Shared: HUBSPOT_ACCESS_TOKEN",
    },
    {
      name: "Microsoft Outlook",
      description: "Calendar booking and email follow-ups via Microsoft Graph.",
      tone: "bg-blue-light-5 text-blue",
      connected: status.microsoft?.connected ?? false,
      connectUrl: `${API_BASE}/oauth/microsoft/authorize/${tenantId}`,
      env: "Shared: MS_TENANT_ID / MS_CLIENT_ID / MS_CLIENT_SECRET",
    },
    {
      name: "Twilio",
      description: "Voice calls, SMS, and WhatsApp messaging.",
      tone: "bg-red-light-5 text-red",
      connected: true,
      connectUrl: null,
      env: "Shared: TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN",
    },
    {
      name: "OpenAI",
      description: "GPT Realtime API for sub-second voice AI responses.",
      tone: "bg-dark-2 text-white dark:bg-white dark:text-dark",
      connected: true,
      connectUrl: null,
      env: "Shared: OPENAI_API_KEY",
    },
    {
      name: "Cartesia",
      description: "Fallback TTS/STT (not used when OpenAI Realtime active).",
      tone: "bg-green-light-7 text-green",
      connected: true,
      connectUrl: null,
      env: "Shared: CARTESIA_API_KEY",
    },
    {
      name: "Supabase",
      description: "PostgreSQL database for multi-tenant storage.",
      tone: "bg-green-light-7 text-green",
      connected: true,
      connectUrl: null,
      env: "Shared: DATABASE_URL",
    },
  ];

  if (loading) return <PageSpinner />;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:gap-6 lg:grid-cols-2 2xl:gap-7.5">
        {integrations.map((integration) => (
          <article
            key={integration.name}
            className="rounded-[10px] bg-white p-6 shadow-1 dark:bg-gray-dark"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <span
                  className={cn(
                    "flex size-11 items-center justify-center rounded-full text-base font-bold uppercase",
                    integration.tone,
                  )}
                >
                  {integration.name.charAt(0)}
                </span>
                <div>
                  <h3 className="font-semibold text-dark dark:text-white">
                    {integration.name}
                  </h3>
                  <p className="mt-0.5 text-sm text-dark-5 dark:text-dark-6">
                    {integration.description}
                  </p>
                  <p className="mt-1 font-mono text-xs text-dark-5 dark:text-dark-6">
                    {integration.env}
                  </p>
                </div>
              </div>
              {integration.connected ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-green-light-7 px-2.5 py-0.5 text-xs font-medium text-green dark:bg-green/15">
                  <Check className="size-3" /> Connected
                </span>
              ) : (
                <span className="inline-flex items-center rounded-full border border-stroke px-2.5 py-0.5 text-xs font-medium text-dark-5 dark:border-stroke-dark dark:text-dark-6">
                  Not connected
                </span>
              )}
            </div>
            <div className="mt-4">
              {integration.connected ? (
                <button
                  type="button"
                  disabled
                  className="rounded-lg border border-stroke px-3 py-1.5 text-xs font-medium text-dark-5 opacity-60 dark:border-stroke-dark dark:text-dark-6"
                >
                  Connected
                </button>
              ) : integration.connectUrl ? (
                <a
                  href={integration.connectUrl}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-white hover:bg-primary/90"
                >
                  <ExternalLink className="size-3.5" />
                  Connect {integration.name}
                </a>
              ) : null}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
