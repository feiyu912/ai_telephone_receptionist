"use client";

import { useSidebarContext } from "../sidebar/sidebar-context";
import { MenuIcon, SearchIcon } from "./icons";
import { Notification } from "./notification";
import { TenantSwitcher } from "./tenant-switcher";
import { ThemeToggleSwitch } from "./theme-toggle";
import { UserInfo } from "./user-info";
import { usePathname } from "next/navigation";

const PAGE_TITLES: Record<string, { title: string; subtitle: string }> = {
  "/overview": { title: "Overview", subtitle: "Live snapshot of your AI receptionist." },
  "/calls": { title: "Call History", subtitle: "Every call, transcript, and outcome." },
  "/customers": { title: "Customers", subtitle: "Caller memory and recurring contacts." },
  "/faq": { title: "FAQ", subtitle: "Answers your AI gives the most." },
  "/settings": { title: "Settings", subtitle: "Tune voice, prompt, and behavior." },
  "/integrations": { title: "Integrations", subtitle: "Per-tenant Twilio, Outlook, HubSpot." },
  "/tenants": { title: "All Tenants", subtitle: "Multi-tenant administration." },
  "/system": { title: "System Health", subtitle: "Platform-wide diagnostics." },
};

export function Header() {
  const { toggleSidebar, isMobile } = useSidebarContext();
  const pathname = usePathname();
  const meta = PAGE_TITLES[pathname] ?? { title: "Dashboard", subtitle: "AI Telephone Receptionist" };

  return (
    <header className="sticky top-0 z-30 flex items-center justify-between border-b border-stroke bg-white px-4 py-5 shadow-1 dark:border-stroke-dark dark:bg-gray-dark md:px-5 2xl:px-10">
      {isMobile && (
        <button
          type="button"
          onClick={toggleSidebar}
          className="rounded-lg border border-stroke px-1.5 py-1 dark:border-stroke-dark dark:bg-[#020D1A] hover:dark:bg-[#FFFFFF1A]"
        >
          <MenuIcon />
          <span className="sr-only">Toggle Sidebar</span>
        </button>
      )}

      <div className="max-xl:hidden">
        <h1 className="mb-0.5 text-heading-5 font-bold text-dark dark:text-white">
          {meta.title}
        </h1>
        <p className="text-sm font-medium text-dark-5 dark:text-dark-6">{meta.subtitle}</p>
      </div>

      <div className="flex flex-1 items-center justify-end gap-2 min-[375px]:gap-4">
        <TenantSwitcher />

        <div className="relative hidden w-full max-w-[300px] sm:block">
          <input
            type="search"
            placeholder="Search"
            className="flex w-full items-center gap-3.5 rounded-full border border-stroke bg-gray-2 py-3 pl-[53px] pr-5 text-sm outline-none transition-colors focus-visible:border-primary dark:border-dark-3 dark:bg-dark-2 dark:hover:border-dark-4 dark:hover:bg-dark-3 dark:hover:text-dark-6 dark:focus-visible:border-primary"
          />
          <SearchIcon className="pointer-events-none absolute left-5 top-1/2 -translate-y-1/2 max-[1015px]:size-5 text-dark-5 dark:text-dark-6" />
        </div>

        <ThemeToggleSwitch />
        <Notification />

        <div className="shrink-0">
          <UserInfo />
        </div>
      </div>
    </header>
  );
}
