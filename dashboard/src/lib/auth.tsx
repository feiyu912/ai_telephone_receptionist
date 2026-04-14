"use client";

import { createContext, useContext, useState, useEffect, ReactNode } from "react";

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
  logout: () => void;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  login: async () => false,
  logout: () => {},
  isLoading: true,
});

// Demo users — replace with real API auth later
const DEMO_USERS: Record<string, { password: string; user: User }> = {
  "admin@360dmmc.com": {
    password: "admin360",
    user: {
      email: "admin@360dmmc.com",
      role: "admin",
      tenantId: "11111111-1111-1111-1111-111111111111",
      tenantName: "YourCompany",
    },
  },
  "emilio@360dmmc.com": {
    password: "360group",
    user: {
      email: "emilio@360dmmc.com",
      role: "client",
      tenantId: "11111111-1111-1111-1111-111111111111",
      tenantName: "YourCompany",
    },
  },
  "support@tenantb.com": {
    password: "aplus2026",
    user: {
      email: "support@tenantb.com",
      role: "client",
      tenantId: "22222222-2222-2222-2222-222222222222",
      tenantName: "TenantB",
    },
  },
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem("pod6_user");
    if (stored) {
      try {
        setUser(JSON.parse(stored));
      } catch {}
    }
    setIsLoading(false);
  }, []);

  const login = async (email: string, password: string): Promise<boolean> => {
    const entry = DEMO_USERS[email.toLowerCase()];
    if (entry && entry.password === password) {
      setUser(entry.user);
      localStorage.setItem("pod6_user", JSON.stringify(entry.user));
      return true;
    }
    return false;
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem("pod6_user");
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
