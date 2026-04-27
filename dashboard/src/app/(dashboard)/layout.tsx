"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/Layouts/header";
import { Sidebar } from "@/components/Layouts/sidebar";
import { SidebarProvider } from "@/components/Layouts/sidebar/sidebar-context";
import { useAuth } from "@/lib/auth";
import { TenantProvider } from "@/lib/tenant";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !user) {
      router.push("/login");
    }
  }, [user, isLoading, router]);

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-2 dark:bg-[#020D1A]">
        <div className="size-10 animate-spin rounded-full border-2 border-stroke border-t-primary" />
      </div>
    );
  }

  if (!user) return null;

  return (
    <TenantProvider>
      <SidebarProvider>
        <div className="flex min-h-screen bg-gray-2 dark:bg-[#020D1A]">
          <Sidebar />
          <div className="flex w-full flex-col overflow-hidden">
            <Header />
            <main className="isolate mx-auto w-full max-w-screen-2xl flex-1 overflow-y-auto p-4 md:p-6 2xl:p-10">
              {children}
            </main>
          </div>
        </div>
      </SidebarProvider>
    </TenantProvider>
  );
}
