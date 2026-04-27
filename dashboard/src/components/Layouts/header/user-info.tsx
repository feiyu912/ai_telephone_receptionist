"use client";

import {
  Dropdown,
  DropdownContent,
  DropdownTrigger,
} from "@/components/ui/dropdown";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { LogOut, Settings, ShieldCheck, User } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { ChevronUpIcon } from "./icons";

export function UserInfo() {
  const [isOpen, setIsOpen] = useState(false);
  const { user, logout } = useAuth();

  if (!user) return null;

  const initial = user.tenantName?.charAt(0) ?? user.email.charAt(0).toUpperCase();
  const isAdmin = user.role === "admin";

  return (
    <Dropdown isOpen={isOpen} setIsOpen={setIsOpen}>
      <DropdownTrigger className="rounded align-middle outline-none ring-primary ring-offset-2 focus-visible:ring-1 dark:ring-offset-gray-dark">
        <span className="sr-only">My Account</span>
        <figure className="flex items-center gap-3">
          <span className="flex size-12 items-center justify-center rounded-full bg-primary/10 text-base font-bold text-primary">
            {initial}
          </span>
          <figcaption className="flex items-center gap-1 font-medium text-dark dark:text-dark-6 max-[1024px]:sr-only">
            <span>{user.tenantName}</span>
            <ChevronUpIcon
              aria-hidden
              className={cn(
                "rotate-180 transition-transform",
                isOpen && "rotate-0",
              )}
              strokeWidth={1.5}
            />
          </figcaption>
        </figure>
      </DropdownTrigger>

      <DropdownContent
        className="border border-stroke bg-white shadow-md dark:border-dark-3 dark:bg-gray-dark min-[230px]:min-w-[17.5rem]"
        align="end"
      >
        <h2 className="sr-only">User information</h2>

        <figure className="flex items-center gap-2.5 px-5 py-3.5">
          <span className="flex size-12 items-center justify-center rounded-full bg-primary/10 text-base font-bold text-primary">
            {initial}
          </span>
          <figcaption className="space-y-1 text-base font-medium">
            <div className="mb-2 flex items-center gap-1.5 leading-none text-dark dark:text-white">
              {user.tenantName}
              {isAdmin && (
                <ShieldCheck className="size-3.5 text-primary" aria-label="Admin" />
              )}
            </div>
            <div className="leading-none text-gray-6">{user.email}</div>
          </figcaption>
        </figure>

        <hr className="border-[#E8E8E8] dark:border-dark-3" />

        <div className="p-2 text-base text-[#4B5563] dark:text-dark-6">
          <Link
            href="/settings"
            onClick={() => setIsOpen(false)}
            className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-[9px] hover:bg-gray-2 hover:text-dark dark:hover:bg-dark-3 dark:hover:text-white"
          >
            <User className="size-5" />
            <span className="mr-auto text-base font-medium">Profile</span>
          </Link>
          <Link
            href="/integrations"
            onClick={() => setIsOpen(false)}
            className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-[9px] hover:bg-gray-2 hover:text-dark dark:hover:bg-dark-3 dark:hover:text-white"
          >
            <Settings className="size-5" />
            <span className="mr-auto text-base font-medium">Integrations</span>
          </Link>
        </div>

        <hr className="border-[#E8E8E8] dark:border-dark-3" />

        <div className="p-2 text-base text-[#4B5563] dark:text-dark-6">
          <button
            type="button"
            className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-[9px] hover:bg-gray-2 hover:text-dark dark:hover:bg-dark-3 dark:hover:text-white"
            onClick={() => {
              setIsOpen(false);
              void logout();
            }}
          >
            <LogOut className="size-5" />
            <span className="text-base font-medium">Log out</span>
          </button>
        </div>
      </DropdownContent>
    </Dropdown>
  );
}
