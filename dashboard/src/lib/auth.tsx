"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { API_BASE } from "@/lib/api";

export type UserRole = "admin" | "client";

export interface User {
  email: string;
  role: UserRole;
  tenantId: string;
  tenantName: string;
}

interface AuthContextType {
  user: User | null;
  login: (email: string, password: string) => Promise<boolean>;
  logout: () => Promise<void>;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  login: async () => false,
  logout: async () => {},
  isLoading: true,
});

function normalizeUser(data: {
  email: string;
  role: UserRole;
  tenant_id: string;
  tenant_name: string;
}): User {
  return {
    email: data.email,
    role: data.role,
    tenantId: data.tenant_id,
    tenantName: data.tenant_name,
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const loadSession = async () => {
      try {
        const res = await fetch(`${API_BASE}/auth/session`, {
          credentials: "include",
        });
        if (!res.ok) {
          setUser(null);
          return;
        }
        const data = await res.json();
        setUser(normalizeUser(data));
      } catch {
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    };

    void loadSession();
  }, []);

  const login = async (email: string, password: string): Promise<boolean> => {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) return false;

    const data = await res.json();
    setUser(normalizeUser(data));
    return true;
  };

  const logout = async () => {
    try {
      await fetch(`${API_BASE}/auth/logout`, {
        method: "POST",
        credentials: "include",
      });
    } catch {
      // Even if the logout request fails, clear local state so the user
      // stops being treated as authenticated in the UI.
    } finally {
      setUser(null);
    }
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
