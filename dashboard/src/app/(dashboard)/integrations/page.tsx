"use client";

import { useState, useEffect, useCallback } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Check, ExternalLink, Loader2 } from "lucide-react";
import { getOAuthStatus, API_BASE } from "@/lib/api";
import { useTenantId } from "@/lib/tenant";

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
      icon: "🟠",
      connected: status.hubspot?.connected ?? false,
      connectUrl: `${API_BASE}/oauth/hubspot/authorize/${tenantId}`,
      env: "Shared: HUBSPOT_ACCESS_TOKEN",
    },
    {
      name: "Microsoft Outlook",
      description: "Calendar booking and email follow-ups via Microsoft Graph.",
      icon: "🔵",
      connected: status.microsoft?.connected ?? false,
      connectUrl: `${API_BASE}/oauth/microsoft/authorize/${tenantId}`,
      env: "Shared: MS_TENANT_ID / MS_CLIENT_ID / MS_CLIENT_SECRET",
    },
    {
      name: "Twilio",
      description: "Voice calls, SMS, and WhatsApp messaging.",
      icon: "🔴",
      connected: true,
      connectUrl: null,
      env: "Shared: TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN",
    },
    {
      name: "OpenAI",
      description: "GPT Realtime API for sub-second voice AI responses.",
      icon: "⚫",
      connected: true,
      connectUrl: null,
      env: "Shared: OPENAI_API_KEY",
    },
    {
      name: "Cartesia",
      description: "Fallback TTS/STT (not used when OpenAI Realtime active).",
      icon: "🟢",
      connected: true,
      connectUrl: null,
      env: "Shared: CARTESIA_API_KEY",
    },
    {
      name: "Supabase",
      description: "PostgreSQL database for multi-tenant storage.",
      icon: "🟢",
      connected: true,
      connectUrl: null,
      env: "Shared: DATABASE_URL",
    },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Integrations</h1>
        <p className="text-muted-foreground mt-1">
          Connect your accounts to enable features like CRM sync, calendar booking, and email notifications.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {integrations.map((integration) => (
          <Card key={integration.name} className="p-6">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <span className="text-2xl">{integration.icon}</span>
                <div>
                  <h3 className="font-medium">{integration.name}</h3>
                  <p className="text-sm text-muted-foreground mt-0.5">
                    {integration.description}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1 font-mono">
                    {integration.env}
                  </p>
                </div>
              </div>
              {integration.connected ? (
                <Badge className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
                  <Check className="w-3 h-3 mr-1" /> Connected
                </Badge>
              ) : (
                <Badge variant="outline">Not connected</Badge>
              )}
            </div>
            <div className="mt-4">
              {integration.connected ? (
                <Button variant="outline" size="sm" disabled>
                  Connected
                </Button>
              ) : integration.connectUrl ? (
                <a href={integration.connectUrl}>
                  <Button size="sm">
                    <ExternalLink className="w-3.5 h-3.5 mr-1.5" />
                    Connect {integration.name}
                  </Button>
                </a>
              ) : null}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
