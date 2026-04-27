"use client";

import { cn } from "@/lib/utils";
import { useTheme } from "next-themes";
import { Moon, Sun } from "lucide-react";
import { useSyncExternalStore } from "react";

const THEMES = [
  { name: "light", Icon: Sun },
  { name: "dark", Icon: Moon },
];

function useMounted(): boolean {
  return useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );
}

export function ThemeToggleSwitch() {
  const { setTheme, theme } = useTheme();
  const mounted = useMounted();

  if (!mounted) return null;

  return (
    <button
      type="button"
      onClick={() => setTheme(theme === "light" ? "dark" : "light")}
      className="group rounded-full bg-gray-3 p-[5px] text-[#111928] outline-1 outline-primary focus-visible:outline dark:bg-[#020D1A] dark:text-current"
    >
      <span className="sr-only">
        Switch to {theme === "light" ? "dark" : "light"} mode
      </span>

      <span aria-hidden className="relative flex gap-2.5">
        <span className="absolute size-[38px] rounded-full border border-gray-200 bg-white transition-all dark:translate-x-[48px] dark:border-none dark:bg-dark-2 dark:group-hover:bg-dark-3" />

        {THEMES.map(({ name, Icon }) => (
          <span
            key={name}
            className={cn(
              "relative grid size-[38px] place-items-center rounded-full",
              name === "dark" && "dark:text-white",
            )}
          >
            <Icon className="size-5" />
          </span>
        ))}
      </span>
    </button>
  );
}
