"use client";

import { Logo } from "@/components/logo";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { LogOut, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { NAV_DATA } from "./data";
import { ArrowLeftIcon, ChevronUp } from "./icons";
import { MenuItem } from "./menu-item";
import { useSidebarContext } from "./sidebar-context";

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const isAdmin = user?.role === "admin";
  const { setIsOpen, isOpen, isMobile, toggleSidebar } = useSidebarContext();
  const [expandedItems, setExpandedItems] = useState<string[]>([]);

  const navData = NAV_DATA.filter((s) => !s.adminOnly || isAdmin);

  const toggleExpanded = (title: string) => {
    setExpandedItems((prev) => (prev.includes(title) ? [] : [title]));
  };

  useEffect(() => {
    navData.some((section) => {
      return section.items.some((item) => {
        return item.items.some((subItem) => {
          if (subItem.url === pathname) {
            if (!expandedItems.includes(item.title)) {
              toggleExpanded(item.title);
            }
            return true;
          }
        });
      });
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  return (
    <>
      {isMobile && isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 transition-opacity duration-300"
          onClick={() => setIsOpen(false)}
          aria-hidden="true"
        />
      )}

      <aside
        className={cn(
          "max-w-[290px] overflow-hidden border-r border-stroke bg-white transition-[width] duration-200 ease-linear dark:border-stroke-dark dark:bg-gray-dark",
          isMobile ? "fixed bottom-0 top-0 z-50" : "sticky top-0 h-screen",
          isOpen ? "w-full" : "w-0",
        )}
        aria-label="Main navigation"
        aria-hidden={!isOpen}
        inert={!isOpen}
      >
        <div className="flex h-full flex-col py-10 pl-[25px] pr-[7px]">
          <div className="relative pr-4.5">
            <Link
              href="/overview"
              onClick={() => isMobile && toggleSidebar()}
              className="px-0 py-2.5 min-[850px]:py-0"
            >
              <Logo />
            </Link>

            {isMobile && (
              <button
                onClick={toggleSidebar}
                className="absolute left-3/4 right-4.5 top-1/2 -translate-y-1/2 text-right"
              >
                <span className="sr-only">Close Menu</span>
                <ArrowLeftIcon className="ml-auto size-7" />
              </button>
            )}
          </div>

          <div className="custom-scrollbar mt-6 flex-1 overflow-y-auto pr-3 min-[850px]:mt-10">
            {navData.map((section) => (
              <div key={section.label} className="mb-6">
                <h2 className="mb-5 text-sm font-medium text-dark-4 dark:text-dark-6">
                  {section.label}
                </h2>

                <nav role="navigation" aria-label={section.label}>
                  <ul className="space-y-2">
                    {section.items.map((item) => (
                      <li key={item.title}>
                        {item.items.length ? (
                          <div>
                            <MenuItem
                              isActive={item.items.some(
                                ({ url }) => url === pathname,
                              )}
                              onClick={() => toggleExpanded(item.title)}
                            >
                              <item.icon className="size-6 shrink-0" aria-hidden="true" />
                              <span>{item.title}</span>
                              <ChevronUp
                                className={cn(
                                  "ml-auto rotate-180 transition-transform duration-200",
                                  expandedItems.includes(item.title) && "rotate-0",
                                )}
                                aria-hidden="true"
                              />
                            </MenuItem>

                            {expandedItems.includes(item.title) && (
                              <ul
                                className="ml-9 mr-0 space-y-1.5 pb-[15px] pr-0 pt-2"
                                role="menu"
                              >
                                {item.items.map((subItem) => (
                                  <li key={subItem.title} role="none">
                                    <MenuItem
                                      as="link"
                                      href={subItem.url}
                                      isActive={pathname === subItem.url}
                                    >
                                      <span>{subItem.title}</span>
                                    </MenuItem>
                                  </li>
                                ))}
                              </ul>
                            )}
                          </div>
                        ) : (
                          <MenuItem
                            className="flex items-center gap-3 py-3"
                            as="link"
                            href={item.url ?? "/"}
                            isActive={pathname === item.url}
                          >
                            <item.icon className="size-6 shrink-0" aria-hidden="true" />
                            <span>{item.title}</span>
                          </MenuItem>
                        )}
                      </li>
                    ))}
                  </ul>
                </nav>
              </div>
            ))}
          </div>

          {/* Profile + sign out */}
          <div className="mt-auto border-t border-stroke pt-5 dark:border-stroke-dark">
            <div className="flex items-center gap-3 px-2 pb-3">
              <div className="flex size-10 items-center justify-center rounded-full bg-primary/10 text-sm font-bold text-primary">
                {user?.tenantName?.charAt(0) ?? "?"}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-dark dark:text-white">
                  {user?.tenantName}
                </p>
                <p className="flex items-center gap-1 truncate text-xs text-dark-5 dark:text-dark-6">
                  {isAdmin && <ShieldCheck className="size-3" />}
                  {user?.email}
                </p>
              </div>
            </div>
            <button
              onClick={() => void logout()}
              className="flex w-full items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium text-dark-4 transition-colors hover:bg-gray-100 hover:text-red dark:text-dark-6 dark:hover:bg-[#FFFFFF1A] dark:hover:text-red"
            >
              <LogOut className="size-4" />
              Sign out
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
