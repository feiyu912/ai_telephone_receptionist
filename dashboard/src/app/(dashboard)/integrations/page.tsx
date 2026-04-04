"use client";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Check, ExternalLink } from "lucide-react";

const integrations = [
  {
    name: "HubSpot CRM",
    description: "Sync contacts, create engagement notes, and track meetings.",
    icon: "🟠",
    connected: false,
    href: "/oauth/hubspot/authorize/",
  },
  {
    name: "Microsoft Outlook",
    description: "Calendar booking and email follow-ups via Microsoft Graph.",
    icon: "🔵",
    connected: false,
    href: "/oauth/microsoft/authorize/",
  },
  {
    name: "Twilio",
    description: "Voice calls, SMS, and WhatsApp messaging.",
    icon: "🔴",
    connected: true,
    href: null,
  },
  {
    name: "OpenAI",
    description: "GPT Realtime API for sub-second voice AI responses.",
    icon: "⚫",
    connected: true,
    href: null,
  },
];

export default function IntegrationsPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Integrations</h1>
      <p className="text-muted-foreground">
        Connect your accounts to enable features like CRM sync, calendar booking, and email notifications.
      </p>

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
              ) : integration.href ? (
                <Button size="sm">
                  <ExternalLink className="w-3.5 h-3.5 mr-1.5" />
                  Connect {integration.name}
                </Button>
              ) : null}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
