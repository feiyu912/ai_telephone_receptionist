"use client";

import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";

export default function SettingsPage() {
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
                <Input defaultValue="360 Group" />
              </div>
              <div>
                <Label>Phone Number</Label>
                <Input defaultValue="+1-555-0100" disabled />
              </div>
              <div>
                <Label>Slug</Label>
                <Input defaultValue="360-group" />
              </div>
              <div>
                <Label>Voicemail Email</Label>
                <Input defaultValue="emilio@360dmmc.com" />
              </div>
            </div>
          </Card>

          <Card className="p-6 space-y-4">
            <h3 className="font-medium">Tier</h3>
            <Select defaultValue="growth">
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
              Growth tier uses OpenAI Realtime for sub-second voice latency.
            </p>
          </Card>

          <div className="flex justify-end">
            <Button>Save Changes</Button>
          </div>
        </TabsContent>

        <TabsContent value="voice" className="space-y-4 mt-4">
          <Card className="p-6 space-y-4">
            <h3 className="font-medium">AI Voice</h3>
            <Select defaultValue="alloy">
              <SelectTrigger className="w-48">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="alloy">Alloy</SelectItem>
                <SelectItem value="echo">Echo</SelectItem>
                <SelectItem value="fable">Fable</SelectItem>
                <SelectItem value="onyx">Onyx</SelectItem>
                <SelectItem value="nova">Nova</SelectItem>
                <SelectItem value="shimmer">Shimmer</SelectItem>
              </SelectContent>
            </Select>
          </Card>

          <Card className="p-6 space-y-4">
            <h3 className="font-medium">Greetings</h3>
            <div>
              <Label>New Caller Greeting</Label>
              <Textarea
                defaultValue="Thank you for calling 360 Group. How can I help you today?"
                rows={2}
              />
            </div>
            <div>
              <Label>Returning Caller Greeting</Label>
              <Textarea
                defaultValue="Welcome back, {name}! How can I help you today?"
                rows={2}
              />
            </div>
          </Card>

          <Card className="p-6 space-y-4">
            <h3 className="font-medium">System Prompt</h3>
            <Textarea
              placeholder="Enter the AI system prompt..."
              rows={8}
              className="font-mono text-sm"
            />
            <p className="text-sm text-muted-foreground">
              This prompt controls the AI&apos;s personality and behavior during calls.
            </p>
          </Card>

          <div className="flex justify-end">
            <Button>Save Changes</Button>
          </div>
        </TabsContent>

        <TabsContent value="hours" className="space-y-4 mt-4">
          <Card className="p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-medium">24/7 AI Answering</h3>
              <Switch defaultChecked />
            </div>
            <p className="text-sm text-muted-foreground">
              AI answers all calls 24/7. Disable to route after-hours calls to voicemail.
            </p>
          </Card>

          <Card className="p-6 space-y-4">
            <h3 className="font-medium">Business Hours (informational)</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Start Hour</Label>
                <Input type="number" defaultValue={9} min={0} max={23} />
              </div>
              <div>
                <Label>End Hour</Label>
                <Input type="number" defaultValue={17} min={0} max={23} />
              </div>
              <div>
                <Label>Timezone</Label>
                <Input defaultValue="America/Chicago" />
              </div>
            </div>
          </Card>

          <div className="flex justify-end">
            <Button>Save Changes</Button>
          </div>
        </TabsContent>

        <TabsContent value="advanced" className="space-y-4 mt-4">
          <Card className="p-6 space-y-4">
            <h3 className="font-medium">Transfer Settings</h3>
            <div>
              <Label>Hunt Group Numbers (comma-separated)</Label>
              <Input defaultValue="+17732005177, +12162638731" />
            </div>
            <div>
              <Label>Transfer Timeout (seconds)</Label>
              <Input type="number" defaultValue={20} />
            </div>
          </Card>

          <Card className="p-6 space-y-4">
            <h3 className="font-medium">Memory Settings</h3>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">Require Memory Consent</p>
                <p className="text-xs text-muted-foreground">Ask callers before storing data</p>
              </div>
              <Switch defaultChecked />
            </div>
            <div>
              <Label>Memory Expiry (days)</Label>
              <Input type="number" defaultValue={90} />
            </div>
          </Card>

          <Card className="p-6 space-y-4">
            <h3 className="font-medium">Booking</h3>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">Enable Booking</p>
                <p className="text-xs text-muted-foreground">Allow AI to book appointments</p>
              </div>
              <Switch />
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <Label>Duration (min)</Label>
                <Input type="number" defaultValue={60} />
              </div>
              <div>
                <Label>Buffer (min)</Label>
                <Input type="number" defaultValue={15} />
              </div>
              <div>
                <Label>Advance (days)</Label>
                <Input type="number" defaultValue={30} />
              </div>
            </div>
          </Card>

          <div className="flex justify-end">
            <Button>Save Changes</Button>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
