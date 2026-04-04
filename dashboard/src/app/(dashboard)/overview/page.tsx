"use client";

import { StatCard } from "@/components/dashboard/stat-card";
import { Card } from "@/components/ui/card";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

const callVolumeData = [
  { month: "Jan", calls: 45, prev: 38 },
  { month: "Feb", calls: 62, prev: 45 },
  { month: "Mar", calls: 78, prev: 62 },
  { month: "Apr", calls: 91, prev: 70 },
  { month: "May", calls: 85, prev: 78 },
  { month: "Jun", calls: 110, prev: 85 },
  { month: "Jul", calls: 124, prev: 95 },
];

const outcomeData = [
  { name: "Contained", value: 65, color: "#6366f1" },
  { name: "Transferred", value: 15, color: "#8b5cf6" },
  { name: "Booked", value: 12, color: "#06b6d4" },
  { name: "Abandoned", value: 8, color: "#e5e7eb" },
];

const sentimentData = [
  { month: "Jan", positive: 72, neutral: 20, negative: 8 },
  { month: "Feb", positive: 68, neutral: 22, negative: 10 },
  { month: "Mar", positive: 75, neutral: 18, negative: 7 },
  { month: "Apr", positive: 80, neutral: 15, negative: 5 },
  { month: "May", positive: 77, neutral: 17, negative: 6 },
  { month: "Jun", positive: 82, neutral: 13, negative: 5 },
];

const channelData = [
  { name: "Voice", calls: 320 },
  { name: "SMS", calls: 145 },
  { name: "WhatsApp", calls: 89 },
];

export default function OverviewPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Overview</h1>
        <select className="text-sm border rounded-lg px-3 py-1.5 bg-background">
          <option>Today</option>
          <option>This Week</option>
          <option>This Month</option>
        </select>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard label="Total Calls" value="1,247" change={11.01} className="bg-primary/5" />
        <StatCard label="Active Customers" value="256" change={15.03} />
        <StatCard label="Bookings" value="48" change={6.08} />
        <StatCard label="Avg Response Time" value="0.8s" change={-23.5} />
      </div>

      {/* Charts Row 1 */}
      <div className="grid grid-cols-3 gap-4">
        {/* Call Volume Chart */}
        <Card className="col-span-2 p-5">
          <div className="flex items-center gap-4 mb-4">
            <h3 className="font-medium">Call Volume</h3>
            <div className="flex items-center gap-4 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-primary" /> This Year
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-muted-foreground/30" /> Last Year
              </span>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={callVolumeData}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="month" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Line type="monotone" dataKey="calls" stroke="hsl(var(--primary))" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="prev" stroke="hsl(var(--muted-foreground))" strokeWidth={1} strokeDasharray="4 4" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </Card>

        {/* Outcome Breakdown */}
        <Card className="p-5">
          <h3 className="font-medium mb-4">Call Outcomes</h3>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={outcomeData} innerRadius={50} outerRadius={80} dataKey="value" paddingAngle={2}>
                {outcomeData.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
          <div className="space-y-2 mt-2">
            {outcomeData.map((item) => (
              <div key={item.name} className="flex items-center justify-between text-sm">
                <span className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: item.color }} />
                  {item.name}
                </span>
                <span className="text-muted-foreground">{item.value}%</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Charts Row 2 */}
      <div className="grid grid-cols-2 gap-4">
        {/* Sentiment */}
        <Card className="p-5">
          <h3 className="font-medium mb-4">Sentiment Trend</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={sentimentData}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="month" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="positive" fill="#22c55e" radius={[4, 4, 0, 0]} />
              <Bar dataKey="neutral" fill="#a1a1aa" radius={[4, 4, 0, 0]} />
              <Bar dataKey="negative" fill="#ef4444" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        {/* Channel Distribution */}
        <Card className="p-5">
          <h3 className="font-medium mb-4">Channel Distribution</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={channelData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis type="number" tick={{ fontSize: 12 }} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 12 }} width={80} />
              <Tooltip />
              <Bar dataKey="calls" fill="hsl(var(--primary))" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>
    </div>
  );
}
