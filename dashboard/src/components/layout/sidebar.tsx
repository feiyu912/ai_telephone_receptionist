"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Phone,
  Users,
  HelpCircle,
  Settings,
  Link2,
  ChevronDown,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  {
    label: "Dashboards",
    items: [
      { name: "Overview", href: "/overview", icon: LayoutDashboard },
      { name: "Call History", href: "/calls", icon: Phone },
    ],
  },
  {
    label: "Management",
    items: [
      { name: "Customers", href: "/customers", icon: Users },
      { name: "FAQ", href: "/faq", icon: HelpCircle },
    ],
  },
  {
    label: "Configuration",
    items: [
      { name: "Settings", href: "/settings", icon: Settings },
      { name: "Integrations", href: "/integrations", icon: Link2 },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-60 border-r border-border bg-card h-screen sticky top-0 flex flex-col">
      {/* Logo */}
      <div className="p-5 border-b border-border">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center">
            <Phone className="w-4 h-4 text-primary-foreground" />
          </div>
          <span className="font-semibold text-lg">POD6 Voice</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-4 px-3">
        {navItems.map((section) => (
          <div key={section.label} className="mb-6">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider px-3 mb-2">
              {section.label}
            </p>
            {section.items.map((item) => {
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors mb-0.5",
                    isActive
                      ? "bg-primary/10 text-primary font-medium"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted"
                  )}
                >
                  <item.icon className="w-4 h-4" />
                  {item.name}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Tenant Selector */}
      <div className="p-3 border-t border-border">
        <button className="flex items-center gap-2 w-full px-3 py-2 rounded-lg text-sm text-muted-foreground hover:bg-muted transition-colors">
          <div className="w-6 h-6 rounded bg-primary/20 flex items-center justify-center text-xs font-bold text-primary">
            3
          </div>
          <span className="flex-1 text-left">360 Group</span>
          <ChevronDown className="w-4 h-4" />
        </button>
      </div>
    </aside>
  );
}
