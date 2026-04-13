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
import { Loader2 } from "lucide-react";
import { getTenantSettings, updateTenantSettings } from "@/lib/api";
import { useTenantId, useTenant } from "@/lib/tenant";

export default function SettingsPage() {
  const [settings, setSettings] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const tenantId = useTenantId();
  const { isAdmin } = useTenant();

  useEffect(() => {
    if (!tenantId) return;
    setLoading(true);
    getTenantSettings(tenantId)
      .then(setSettings)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [tenantId]);

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

  if (loading || !settings) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Settings</h1>

      <Tabs defaultValue="general">
        <TabsList>
          <TabsTrigger value="general">General</TabsTrigger>
          <TabsTrigger value="voice">Voice & Greetings</TabsTrigger>
          <TabsTrigger value="hours">Business Hours</TabsTrigger>
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
              value={String(settings.selected_voice || "Polly.Joanna-Neural")}
              onValueChange={(v) => update("selected_voice", v)}
            >
              <SelectTrigger className="w-48">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="alloy">Alloy (Realtime)</SelectItem>
                <SelectItem value="echo">Echo (Realtime)</SelectItem>
                <SelectItem value="nova">Nova (Realtime)</SelectItem>
                <SelectItem value="shimmer">Shimmer (Realtime)</SelectItem>
                <SelectItem value="Polly.Joanna-Neural">Polly Joanna (Starter)</SelectItem>
                <SelectItem value="Polly.Matthew-Neural">Polly Matthew (Starter)</SelectItem>
              </SelectContent>
            </Select>
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
