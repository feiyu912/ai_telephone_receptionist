"use client";

import { Sun, Moon, Bell, Building2, Check, ChevronDown } from "lucide-react";
import { useTheme } from "next-themes";
import { useState, useRef, useEffect } from "react";
import { useTenant } from "@/lib/tenant";
import { cn } from "@/lib/utils";

export function Topbar() {
  const { theme, setTheme } = useTheme();
  const { tenants, current, setCurrentId, isAdmin } = useTenant();
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  return (
    <header className="h-14 border-b border-border bg-card flex items-center justify-between px-6 sticky top-0 z-10">
      {/* Tenant context (admin: switcher dropdown; client: read-only label) */}
      <div className="flex items-center gap-2">
        {isAdmin && tenants.length > 1 ? (
          <div className="relative" ref={dropdownRef}>
            <button
              onClick={() => setOpen(!open)}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-border bg-muted/30 hover:bg-muted text-sm font-medium transition-colors"
            >
              <Building2 className="w-4 h-4 text-muted-foreground" />
              <span>{current?.company_name ?? "Select tenant"}</span>
              {current && (
                <span className="text-xs px-1.5 py-0.5 rounded bg-primary/10 text-primary uppercase">
                  {current.tier}
                </span>
              )}
              <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />
            </button>
            {open && (
              <div className="absolute top-full left-0 mt-1 w-72 rounded-lg border border-border bg-card shadow-lg z-50 overflow-hidden">
                <div className="px-3 py-2 text-xs font-medium text-muted-foreground uppercase border-b border-border">
                  Switch Tenant ({tenants.length})
                </div>
                {tenants.map((t) => (
                  <button
                    key={t.tenant_id}
                    onClick={() => {
                      setCurrentId(t.tenant_id);
                      setOpen(false);
                    }}
                    className={cn(
                      "w-full text-left px-3 py-2 hover:bg-muted transition-colors flex items-center justify-between",
                      current?.tenant_id === t.tenant_id && "bg-muted/50"
                    )}
                  >
                    <div>
                      <div className="text-sm font-medium">{t.company_name}</div>
                      <div className="text-xs text-muted-foreground">
                        {t.phone_number} · {t.tier}
                      </div>
                    </div>
                    {current?.tenant_id === t.tenant_id && (
                      <Check className="w-4 h-4 text-primary" />
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-center gap-2 text-sm">
            <Building2 className="w-4 h-4 text-muted-foreground" />
            <span className="font-medium">{current?.company_name ?? "Loading..."}</span>
            {current && (
              <span className="text-xs px-1.5 py-0.5 rounded bg-primary/10 text-primary uppercase">
                {current.tier}
              </span>
            )}
          </div>
        )}
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          className="p-2 rounded-lg hover:bg-muted transition-colors"
        >
          {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </button>
        <button className="p-2 rounded-lg hover:bg-muted transition-colors relative">
          <Bell className="w-4 h-4" />
          <span className="absolute top-1 right-1 w-2 h-2 bg-primary rounded-full" />
        </button>
      </div>
    </header>
  );
}
