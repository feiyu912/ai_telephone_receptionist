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
  LogOut,
  Shield,
  Building2,
  Activity,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const isAdmin = user?.role === "admin";

  const navItems = [
    ...(isAdmin
      ? [
          {
            label: "Admin",
            items: [
              { name: "All Tenants", href: "/tenants", icon: Building2 },
              { name: "System Health", href: "/system", icon: Activity },
            ],
          },
        ]
      : []),
    {
      label: isAdmin ? "Tenant View" : "Dashboards",
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

  return (
    <aside className="w-60 border-r border-border bg-card h-screen sticky top-0 flex flex-col">
      <div className="p-5 border-b border-border">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center">
            <Phone className="w-4 h-4 text-primary-foreground" />
          </div>
          <span className="font-semibold text-lg">POD6 Voice</span>
        </div>
      </div>

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

      <div className="p-3 border-t border-border space-y-2">
        <div className="flex items-center gap-2 px-3 py-2">
          <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-xs font-bold">
            {user?.tenantName?.charAt(0) || "?"}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">{user?.tenantName}</p>
            <p className="text-xs text-muted-foreground truncate flex items-center gap-1">
              {user?.role === "admin" && <Shield className="w-3 h-3" />}
              {user?.email}
            </p>
          </div>
        </div>
        <button
          onClick={logout}
          className="flex items-center gap-2 w-full px-3 py-2 rounded-lg text-sm text-muted-foreground hover:bg-muted hover:text-red-500 transition-colors"
        >
          <LogOut className="w-4 h-4" />
          Sign out
        </button>
      </div>
    </aside>
  );
}
