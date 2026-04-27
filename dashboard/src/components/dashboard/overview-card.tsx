import { cn } from "@/lib/utils";
import { ArrowDown, ArrowUp, type LucideIcon } from "lucide-react";

type Props = {
  label: string;
  value: number | string;
  growthRate?: number;
  Icon: LucideIcon;
  iconClassName?: string;
};

export function OverviewCard({ label, value, growthRate, Icon, iconClassName }: Props) {
  const isDecreasing = (growthRate ?? 0) < 0;

  return (
    <div className="rounded-[10px] bg-white p-6 shadow-1 dark:bg-gray-dark">
      <div
        className={cn(
          "flex size-14 items-center justify-center rounded-full",
          iconClassName ?? "bg-primary/10 text-primary",
        )}
      >
        <Icon className="size-7" />
      </div>

      <div className="mt-6 flex items-end justify-between">
        <dl>
          <dt className="mb-1.5 text-heading-6 font-bold text-dark dark:text-white">
            {value}
          </dt>
          <dd className="text-sm font-medium text-dark-6">{label}</dd>
        </dl>

        {growthRate !== undefined && (
          <dl
            className={cn(
              "text-sm font-medium",
              isDecreasing ? "text-red" : "text-green",
            )}
          >
            <dt className="flex items-center gap-1.5">
              {growthRate}%
              {isDecreasing ? (
                <ArrowDown className="size-4" aria-hidden />
              ) : (
                <ArrowUp className="size-4" aria-hidden />
              )}
            </dt>
            <dd className="sr-only">
              {label} {isDecreasing ? "decreased" : "increased"} by {growthRate}%
            </dd>
          </dl>
        )}
      </div>
    </div>
  );
}
