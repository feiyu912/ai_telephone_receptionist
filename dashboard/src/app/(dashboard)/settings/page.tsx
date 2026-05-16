"use client";

import { useState, useEffect } from "react";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { CheckCircle2, Loader2 } from "lucide-react";
import { PageSpinner } from "@/components/dashboard/loading";
import { API_BASE, getAIModels, getOAuthStatus, getTenantSettings, updateTenantSettings } from "@/lib/api";
import { useTenantId, useTenant } from "@/lib/tenant";

interface OAuthStatus {
  microsoft?: { connected: boolean; updated_at?: string };
  hubspot?: { connected: boolean; updated_at?: string };
}

interface AIModel {
  id: string;
  model_id: string;
  display_name: string;
  recommended: boolean;
}

const REALTIME_VOICES = [
  { value: "alloy", label: "Alloy" },
  { value: "ash", label: "Ash" },
  { value: "ballad", label: "Ballad" },
  { value: "coral", label: "Coral" },
  { value: "echo", label: "Echo" },
  { value: "sage", label: "Sage" },
  { value: "shimmer", label: "Shimmer" },
  { value: "verse", label: "Verse" },
  { value: "marin", label: "Marin (recommended)" },
  { value: "cedar", label: "Cedar (recommended)" },
];

const STARTER_VOICES = [
  { value: "Polly.Joanna-Neural", label: "Polly Joanna" },
  { value: "Polly.Matthew-Neural", label: "Polly Matthew" },
];

export default function SettingsPage() {
  const [settings, setSettings] = useState<Record<string, unknown> | null>(null);
  const [oauthStatus, setOAuthStatus] = useState<OAuthStatus>({});
  const [aiModels, setAiModels] = useState<AIModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const tenantId = useTenantId();
  const { isAdmin } = useTenant();
  const tier = String(settings?.tier || "starter");

  useEffect(() => {
    if (!tenantId) return;
    setLoading(true);
    Promise.all([
      getTenantSettings(tenantId),
      getOAuthStatus(tenantId).catch(() => ({})),
    ])
      .then(([s, o]) => {
        setSettings(s);
        setOAuthStatus(o);
        const tierVal = String(s?.tier || "starter");
        if (tierVal !== "starter") {
          getAIModels(tierVal)
            .then((m) => setAiModels(Array.isArray(m) ? m : []))
            .catch(() => setAiModels([]));
        } else {
          setAiModels([]);
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [tenantId]);

  const connectOutlook = () => {
    if (!tenantId) return;
    window.location.href = `${API_BASE}/oauth/microsoft/authorize/${tenantId}`;
  };

  const update = (key: string, value: unknown) => {
    setSettings((prev) => (prev ? { ...prev, [key]: value } : prev));
    setSaved(false);
  };

  const handleSave = async () => {
    if (!settings || !tenantId) return;
    setSaving(true);
    try {
      await updateTenantSettings(tenantId, settings);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      console.error("Failed to save:", err);
    } finally {
      setSaving(false);
    }
  };

  if (loading || !settings) return <PageSpinner />;

  const voiceOptions = tier === "starter" ? STARTER_VOICES : REALTIME_VOICES;

  return (
    <div className="space-y-6">
      <Tabs defaultValue="general">
        <TabsList>
          <TabsTrigger value="general">General</TabsTrigger>
          <TabsTrigger value="voice">Voice & Greetings</TabsTrigger>
          <TabsTrigger value="hours">Business Hours</TabsTrigger>
          <TabsTrigger value="integrations">Integrations</TabsTrigger>
          <TabsTrigger value="advanced">Advanced</TabsTrigger>
        </TabsList>

        <TabsContent value="general" className="space-y-4 mt-4">
          <Card className="p-6 space-y-4">
            <h3 className="font-medium">Company Information</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Company Name</Label>
                <Input
                  value={String(settings.company_name || "")}
                  onChange={(e) => update("company_name", e.target.value)}
                />
              </div>
              <div>
                <Label>Phone Number</Label>
                <Input value={String(settings.phone_number || "")} disabled />
              </div>
              <div>
                <Label>Slug</Label>
                <Input
                  value={String(settings.slug || "")}
                  onChange={(e) => update("slug", e.target.value)}
                />
              </div>
              <div>
                <Label>Voicemail Email</Label>
                <Input
                  value={String(settings.voicemail_email || "")}
                  onChange={(e) => update("voicemail_email", e.target.value)}
                />
              </div>
            </div>
          </Card>

          {isAdmin && (
            <Card className="p-6 space-y-4">
              <h3 className="font-medium flex items-center gap-2">
                Tier
                <span className="text-xs px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400">
                  Admin only
                </span>
              </h3>
              <Select
                value={String(settings.tier || "starter")}
                onValueChange={(v) => update("tier", v)}
              >
                <SelectTrigger className="w-48">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="starter">Starter</SelectItem>
                  <SelectItem value="growth">Growth</SelectItem>
                  <SelectItem value="pro">Pro</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-sm text-muted-foreground">
                Growth/Pro tiers use OpenAI Realtime for sub-second voice latency.
              </p>
            </Card>
          )}

          <div className="flex justify-end gap-2">
            {saved && <span className="text-sm text-green-600 self-center">Saved!</span>}
            <Button onClick={handleSave} disabled={saving}>
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
              Save Changes
            </Button>
          </div>
        </TabsContent>

        <TabsContent value="voice" className="space-y-4 mt-4">
          <Card className="p-6 space-y-4">
            <h3 className="font-medium">AI Voice</h3>
            <Select
              value={String(settings.selected_voice || (tier === "starter" ? "Polly.Joanna-Neural" : "alloy"))}
              onValueChange={(v) => update("selected_voice", v)}
            >
              <SelectTrigger className="w-64">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {voiceOptions.map((v) => (
                  <SelectItem key={v.value} value={v.value}>
                    {v.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-sm text-muted-foreground">
              {tier === "starter"
                ? "Starter tier uses Amazon Polly voices via Twilio."
                : "Growth/Pro tiers use OpenAI Realtime built-in voices."}
            </p>
          </Card>

          {tier !== "starter" && (
            <Card className="p-6 space-y-4">
              <h3 className="font-medium">Realtime Model</h3>
              <Select
                value={String(settings.selected_model || "gpt-realtime-mini")}
                onValueChange={(v) => update("selected_model", v)}
              >
                <SelectTrigger className="w-64">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {aiModels.map((m) => (
                    <SelectItem key={m.model_id} value={m.model_id}>
                      {m.display_name} {m.recommended ? "(recommended)" : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-sm text-muted-foreground">
                The OpenAI Realtime model used for calls. New models can be synced from the admin panel.
              </p>
            </Card>
          )}

          <Card className="p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-medium">Call Recording</h3>
              <Switch
                checked={Boolean(settings.call_recording_enabled)}
                onCheckedChange={(v) => update("call_recording_enabled", v)}
              />
            </div>
            <p className="text-sm text-muted-foreground">
              When enabled, calls are recorded on Twilio and a compliance disclosure is played before the greeting.
            </p>
            {settings.call_recording_enabled && (
              <div>
                <Label>Disclosure Message</Label>
                <Textarea
                  value={String(settings.recording_disclosure_message || "")}
                  onChange={(e) => update("recording_disclosure_message", e.target.value)}
                  rows={2}
                  placeholder="This call may be recorded for quality assurance purposes."
                />
              </div>
            )}
          </Card>

          <Card className="p-6 space-y-4">
            <h3 className="font-medium">Greetings</h3>
            <div>
              <Label>New Caller Greeting</Label>
              <Textarea
                value={String(settings.greeting_new || "")}
                onChange={(e) => update("greeting_new", e.target.value)}
                rows={2}
              />
            </div>
            <div>
              <Label>Returning Caller Greeting</Label>
              <Textarea
                value={String(settings.greeting_returning || "")}
                onChange={(e) => update("greeting_returning", e.target.value)}
                rows={2}
                placeholder="Welcome back, {name}! How can I help you today?"
              />
            </div>
          </Card>

          <Card className="p-6 space-y-4">
            <h3 className="font-medium">System Prompt</h3>
            <Textarea
              value={String(settings.system_prompt || "")}
              onChange={(e) => update("system_prompt", e.target.value)}
              rows={8}
              className="font-mono text-sm"
              placeholder="Enter the AI system prompt..."
            />
            <p className="text-sm text-muted-foreground">
              This prompt controls the AI&apos;s personality and behavior during calls.
            </p>
          </Card>

          <div className="flex justify-end gap-2">
            {saved && <span className="text-sm text-green-600 self-center">Saved!</span>}
            <Button onClick={handleSave} disabled={saving}>
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
              Save Changes
            </Button>
          </div>
        </TabsContent>

        <TabsContent value="hours" className="space-y-4 mt-4">
          <Card className="p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-medium">24/7 AI Answering</h3>
              <Switch defaultChecked />
            </div>
            <p className="text-sm text-muted-foreground">
              AI answers all calls 24/7. Business hours are informational only.
            </p>
          </Card>

          <Card className="p-6 space-y-4">
            <h3 className="font-medium">Business Hours (informational)</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Start Hour</Label>
                <Input
                  type="number"
                  value={Number(settings.business_hours_start || 9)}
                  onChange={(e) => update("business_hours_start", parseInt(e.target.value))}
                  min={0} max={23}
                />
              </div>
              <div>
                <Label>End Hour</Label>
                <Input
                  type="number"
                  value={Number(settings.business_hours_end || 17)}
                  onChange={(e) => update("business_hours_end", parseInt(e.target.value))}
                  min={0} max={23}
                />
              </div>
              <div>
                <Label>Timezone</Label>
                <Input
                  value={String(settings.business_hours_timezone || "America/Chicago")}
                  onChange={(e) => update("business_hours_timezone", e.target.value)}
                />
              </div>
            </div>
          </Card>

          <div className="flex justify-end gap-2">
            {saved && <span className="text-sm text-green-600 self-center">Saved!</span>}
            <Button onClick={handleSave} disabled={saving}>
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
              Save Changes
            </Button>
          </div>
        </TabsContent>

        <TabsContent value="integrations" className="space-y-4 mt-4">
          <Card className="p-6 space-y-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="font-medium flex items-center gap-2">
                  Microsoft Outlook
                  {oauthStatus.microsoft?.connected ? (
                    <span className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
                      <CheckCircle2 className="w-3 h-3" /> Connected
                    </span>
                  ) : (
                    <span className="text-xs px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                      Not connected
                    </span>
                  )}
                </h3>
                <p className="text-sm text-muted-foreground mt-1">
                  Connect your Microsoft 365 account so calendar bookings and emails come from <em>your</em> mailbox. Without connecting, we fall back to the shared platform mailbox.
                </p>
              </div>
              <Button variant={oauthStatus.microsoft?.connected ? "outline" : "default"} onClick={connectOutlook}>
                {oauthStatus.microsoft?.connected ? "Reconnect" : "Connect Outlook"}
              </Button>
            </div>
          </Card>

          <Card className="p-6 space-y-4">
            <div>
              <h3 className="font-medium">Outlook mailbox</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Per-tenant mailbox for outbound mail and calendar bookings. Leave blank to fall back to the shared <code>MS_SENDER_EMAIL</code> / <code>MS_CALENDAR_EMAIL</code> env vars.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Sender email</Label>
                <Input
                  placeholder="voice@yourcompany.com"
                  value={String(settings.sender_email || "")}
                  onChange={(e) => update("sender_email", e.target.value)}
                />
              </div>
              <div>
                <Label>Calendar email</Label>
                <Input
                  placeholder="bookings@yourcompany.com"
                  value={String(settings.calendar_email || "")}
                  onChange={(e) => update("calendar_email", e.target.value)}
                />
              </div>
            </div>
          </Card>

          <Card className="p-6 space-y-4">
            <div>
              <h3 className="font-medium">Twilio (own subaccount)</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Used for inbound webhook signature validation, outbound SMS, and the browser test dialer. Leave any blank to share the platform account.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Account SID</Label>
                <Input
                  placeholder="AC…"
                  value={String(settings.twilio_account_sid || "")}
                  onChange={(e) => update("twilio_account_sid", e.target.value)}
                />
              </div>
              <div>
                <Label>Auth token {settings.twilio_auth_token_set ? <span className="text-xs text-muted-foreground">(saved — leave blank to keep)</span> : null}</Label>
                <Input
                  type="password"
                  placeholder={settings.twilio_auth_token_set ? "••••••••" : "paste token"}
                  value={String(settings.twilio_auth_token || "")}
                  onChange={(e) => update("twilio_auth_token", e.target.value)}
                />
              </div>
              <div>
                <Label>API Key SID</Label>
                <Input
                  placeholder="SK…"
                  value={String(settings.twilio_api_key_sid || "")}
                  onChange={(e) => update("twilio_api_key_sid", e.target.value)}
                />
              </div>
              <div>
                <Label>API Key Secret {settings.twilio_api_key_secret_set ? <span className="text-xs text-muted-foreground">(saved — leave blank to keep)</span> : null}</Label>
                <Input
                  type="password"
                  placeholder={settings.twilio_api_key_secret_set ? "••••••••" : "paste secret"}
                  value={String(settings.twilio_api_key_secret || "")}
                  onChange={(e) => update("twilio_api_key_secret", e.target.value)}
                />
              </div>
              <div className="col-span-2">
                <Label>TwiML App SID</Label>
                <Input
                  placeholder="AP…"
                  value={String(settings.twilio_twiml_app_sid || "")}
                  onChange={(e) => update("twilio_twiml_app_sid", e.target.value)}
                />
              </div>
            </div>
          </Card>

          <Card className="p-6 space-y-4">
            <div>
              <h3 className="font-medium">HubSpot CRM</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Private-app access token for this tenant&apos;s HubSpot portal. Leave blank to share the platform portal.
              </p>
            </div>
            <div>
              <Label>Access token {settings.hubspot_access_token_set ? <span className="text-xs text-muted-foreground">(saved — leave blank to keep)</span> : null}</Label>
              <Input
                type="password"
                placeholder={settings.hubspot_access_token_set ? "••••••••" : "paste token"}
                value={String(settings.hubspot_access_token || "")}
                onChange={(e) => update("hubspot_access_token", e.target.value)}
              />
            </div>
          </Card>

          <div className="flex justify-end gap-2">
            {saved && <span className="text-sm text-green-600 self-center">Saved!</span>}
            <Button onClick={handleSave} disabled={saving}>
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
              Save Changes
            </Button>
          </div>
        </TabsContent>

        <TabsContent value="advanced" className="space-y-4 mt-4">
          <Card className="p-6 space-y-4">
            <h3 className="font-medium">Transfer Settings</h3>
            <div>
              <Label>Hunt Group Numbers (comma-separated)</Label>
              <Input
                value={Array.isArray(settings.hunt_group_numbers) ? (settings.hunt_group_numbers as string[]).join(", ") : ""}
                onChange={(e) => update("hunt_group_numbers", e.target.value.split(",").map((s) => s.trim()).filter(Boolean))}
              />
            </div>
            <div>
              <Label>Transfer Timeout (seconds)</Label>
              <Input
                type="number"
                value={Number(settings.transfer_timeout || 20)}
                onChange={(e) => update("transfer_timeout", parseInt(e.target.value))}
              />
            </div>
          </Card>

          <Card className="p-6 space-y-4">
            <h3 className="font-medium">Memory Settings</h3>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">Require Memory Consent</p>
                <p className="text-xs text-muted-foreground">Ask callers before storing data</p>
              </div>
              <Switch
                checked={Boolean(settings.memory_consent_required)}
                onCheckedChange={(v) => update("memory_consent_required", v)}
              />
            </div>
            <div>
              <Label>Memory Expiry (days)</Label>
              <Input
                type="number"
                value={Number(settings.memory_expiry_days || 90)}
                onChange={(e) => update("memory_expiry_days", parseInt(e.target.value))}
              />
            </div>
          </Card>

          <Card className="p-6 space-y-4">
            <h3 className="font-medium">Booking</h3>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">Enable Booking</p>
                <p className="text-xs text-muted-foreground">Allow AI to book appointments</p>
              </div>
              <Switch
                checked={Boolean(settings.booking_enabled)}
                onCheckedChange={(v) => update("booking_enabled", v)}
              />
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <Label>Duration (min)</Label>
                <Input
                  type="number"
                  value={Number(settings.booking_duration_minutes || 60)}
                  onChange={(e) => update("booking_duration_minutes", parseInt(e.target.value))}
                />
              </div>
              <div>
                <Label>Buffer (min)</Label>
                <Input
                  type="number"
                  value={Number(settings.booking_buffer_minutes || 15)}
                  onChange={(e) => update("booking_buffer_minutes", parseInt(e.target.value))}
                />
              </div>
              <div>
                <Label>Advance (days)</Label>
                <Input
                  type="number"
                  value={Number(settings.booking_advance_days || 30)}
                  onChange={(e) => update("booking_advance_days", parseInt(e.target.value))}
                />
              </div>
            </div>
          </Card>

          <div className="flex justify-end gap-2">
            {saved && <span className="text-sm text-green-600 self-center">Saved!</span>}
            <Button onClick={handleSave} disabled={saving}>
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
              Save Changes
            </Button>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
