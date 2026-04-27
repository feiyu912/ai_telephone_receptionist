"use client";

import {
  Dropdown,
  DropdownContent,
  DropdownTrigger,
} from "@/components/ui/dropdown";
import { cn } from "@/lib/utils";
import { useTenant } from "@/lib/tenant";
import { Building2, Check, ChevronDown } from "lucide-react";
import { useState } from "react";

export function TenantSwitcher() {
  const { tenants, current, setCurrentId, isAdmin } = useTenant();
  const [isOpen, setIsOpen] = useState(false);

  if (!isAdmin || tenants.length <= 1) {
    if (!current) return null;
    return (
      <div className="hidden items-center gap-2 rounded-lg border border-stroke bg-gray-2 px-3 py-2 text-sm dark:border-dark-3 dark:bg-dark-3 lg:flex">
        <Building2 className="size-4 text-dark-5 dark:text-dark-6" />
        <span className="font-medium text-dark dark:text-white">
          {current.company_name}
        </span>
        <span className="rounded bg-primary/10 px-1.5 py-0.5 text-xs uppercase text-primary">
          {current.tier}
        </span>
      </div>
    );
  }

  return (
    <Dropdown isOpen={isOpen} setIsOpen={setIsOpen}>
      <DropdownTrigger className="hidden items-center gap-2 rounded-lg border border-stroke bg-gray-2 px-3 py-2 text-sm font-medium text-dark transition-colors hover:bg-gray-3 dark:border-dark-3 dark:bg-dark-3 dark:text-white dark:hover:bg-dark-4 lg:flex">
        <Building2 className="size-4 text-dark-5 dark:text-dark-6" />
        <span>{current?.company_name ?? "Select tenant"}</span>
        {current && (
          <span className="rounded bg-primary/10 px-1.5 py-0.5 text-xs uppercase text-primary">
            {current.tier}
          </span>
        )}
        <ChevronDown className="size-3.5 text-dark-5 dark:text-dark-6" />
      </DropdownTrigger>

      <DropdownContent
        align="start"
        className="w-72 overflow-hidden border border-stroke bg-white shadow-md dark:border-dark-3 dark:bg-gray-dark"
      >
        <div className="border-b border-stroke px-3 py-2 text-xs font-medium uppercase text-dark-5 dark:border-dark-3 dark:text-dark-6">
          Switch tenant ({tenants.length})
        </div>
        {tenants.map((t) => (
          <button
            key={t.tenant_id}
            type="button"
            onClick={() => {
              setCurrentId(t.tenant_id);
              setIsOpen(false);
            }}
            className={cn(
              "flex w-full items-center justify-between px-3 py-2 text-left transition-colors hover:bg-gray-2 dark:hover:bg-dark-3",
              current?.tenant_id === t.tenant_id && "bg-gray-2 dark:bg-dark-3",
            )}
          >
            <div>
              <div className="text-sm font-medium text-dark dark:text-white">
                {t.company_name}
              </div>
              <div className="text-xs text-dark-5 dark:text-dark-6">
                {t.phone_number} · {t.tier}
              </div>
            </div>
            {current?.tenant_id === t.tenant_id && (
              <Check className="size-4 text-primary" />
            )}
          </button>
        ))}
      </DropdownContent>
    </Dropdown>
  );
}
