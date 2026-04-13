"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export interface Tenant {
  tenant_id: string;
  company_name: string;
  slug: string;
  phone_number: string;
  tier: string;
}

interface TenantContextValue {
  tenants: Tenant[];
  current: Tenant | null;
  currentId: string;
  setCurrentId: (tid: string) => void;
  loading: boolean;
  isAdmin: boolean;
}

const TenantContext = createContext<TenantContextValue>({
  tenants: [],
  current: null,
  currentId: "",
  setCurrentId: () => {},
  loading: true,
  isAdmin: false,
});

const STORAGE_KEY = "pod6_admin_tenant_id";

export function TenantProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [adminSelectedId, setAdminSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const isAdmin = user?.role === "admin";

  useEffect(() => {
    if (!user) return;

    // Admins load all tenants for the switcher
    if (isAdmin) {
      api("/admin/tenants")
        .then((data: Tenant[]) => {
          setTenants(data);
          const saved = typeof window !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null;
          const validSaved = saved && data.some((t) => t.tenant_id === saved);
          setAdminSelectedId(validSaved ? saved : (data[0]?.tenant_id ?? null));
        })
        .catch((err) => console.error("Failed to load tenants:", err))
        .finally(() => setLoading(false));
    } else {
      // Clients only see their own tenant
      api(`/admin/settings/${user.tenantId}`)
        .then((data) => {
          setTenants([
            {
              tenant_id: user.tenantId,
              company_name: data.company_name || user.tenantName,
              slug: data.slug || "",
              phone_number: data.phone_number || "",
              tier: data.tier || "starter",
            },
          ]);
        })
        .catch((err) => console.error("Failed to load tenant:", err))
        .finally(() => setLoading(false));
    }
  }, [user, isAdmin]);

  // Admin picks from switcher; client is fixed to their tenantId
  const currentId = isAdmin ? (adminSelectedId ?? "") : (user?.tenantId ?? "");
  const current = tenants.find((t) => t.tenant_id === currentId) ?? null;

  const setCurrentId = (tid: string) => {
    if (!isAdmin) return; // Clients can't switch
    setAdminSelectedId(tid);
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY, tid);
    }
  };

  return (
    <TenantContext.Provider
      value={{ tenants, current, currentId, setCurrentId, loading, isAdmin }}
    >
      {children}
    </TenantContext.Provider>
  );
}

export function useTenant() {
  return useContext(TenantContext);
}

export function useTenantId(): string {
  const { currentId } = useTenant();
  return currentId;
}
