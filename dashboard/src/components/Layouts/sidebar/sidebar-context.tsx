"use client";

import { useIsMobile } from "@/hooks/use-mobile";
import { createContext, useContext, useState } from "react";

type SidebarState = "expanded" | "collapsed";

type SidebarContextType = {
  state: SidebarState;
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
  isMobile: boolean;
  toggleSidebar: () => void;
};

const SidebarContext = createContext<SidebarContextType | null>(null);

export function useSidebarContext() {
  const ctx = useContext(SidebarContext);
  if (!ctx) {
    throw new Error("useSidebarContext must be used within a SidebarProvider");
  }
  return ctx;
}

export function SidebarProvider({
  children,
  defaultOpen = true,
}: {
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const isMobile = useIsMobile();
  // Track override along with the isMobile state it was set against, so the
  // override naturally clears when the viewport crosses the breakpoint.
  const [override, setOverride] = useState<{ isMobile: boolean; isOpen: boolean } | null>(
    null,
  );
  const isOpen =
    override && override.isMobile === isMobile
      ? override.isOpen
      : isMobile
        ? false
        : defaultOpen;

  const setIsOpen = (open: boolean) => setOverride({ isMobile, isOpen: open });
  const toggleSidebar = () => setOverride({ isMobile, isOpen: !isOpen });

  return (
    <SidebarContext.Provider
      value={{
        state: isOpen ? "expanded" : "collapsed",
        isOpen,
        setIsOpen,
        isMobile,
        toggleSidebar,
      }}
    >
      {children}
    </SidebarContext.Provider>
  );
}
