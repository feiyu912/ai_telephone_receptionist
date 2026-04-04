"use client";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Separator } from "@/components/ui/separator";

const activities = [
  { action: "New call answered", time: "Just now", color: "bg-green-500" },
  { action: "Booking confirmed", time: "5 minutes ago", color: "bg-blue-500" },
  { action: "SMS follow-up sent", time: "12 minutes ago", color: "bg-purple-500" },
  { action: "Memory updated", time: "1 hour ago", color: "bg-yellow-500" },
  { action: "HubSpot synced", time: "2 hours ago", color: "bg-orange-500" },
];

export function RightPanel() {
  return (
    <aside className="w-72 border-l border-border bg-card h-screen sticky top-0 overflow-y-auto hidden xl:block">
      {/* Notifications */}
      <div className="p-5">
        <h3 className="font-semibold text-sm mb-3">Notifications</h3>
        <div className="space-y-3">
          {activities.slice(0, 3).map((a, i) => (
            <div key={i} className="flex items-start gap-2">
              <div className={`w-2 h-2 rounded-full mt-1.5 ${a.color}`} />
              <div>
                <p className="text-sm">{a.action}</p>
                <p className="text-xs text-muted-foreground">{a.time}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      <Separator />

      {/* Activities */}
      <div className="p-5">
        <h3 className="font-semibold text-sm mb-3">Recent Activities</h3>
        <div className="space-y-3">
          {activities.map((a, i) => (
            <div key={i} className="flex items-start gap-2">
              <div className={`w-2 h-2 rounded-full mt-1.5 ${a.color}`} />
              <div>
                <p className="text-sm">{a.action}</p>
                <p className="text-xs text-muted-foreground">{a.time}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      <Separator />

      {/* Quick Contacts */}
      <div className="p-5">
        <h3 className="font-semibold text-sm mb-3">Recent Callers</h3>
        <div className="space-y-2">
          {["+1 (312) 555-0142", "+1 (773) 555-0198", "+1 (847) 555-0163"].map((phone, i) => (
            <div key={i} className="flex items-center gap-2">
              <Avatar className="w-7 h-7">
                <AvatarFallback className="text-xs">{phone.slice(-2)}</AvatarFallback>
              </Avatar>
              <span className="text-sm text-muted-foreground">{phone}</span>
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}
