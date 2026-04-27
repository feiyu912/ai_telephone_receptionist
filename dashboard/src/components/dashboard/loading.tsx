import { cn } from "@/lib/utils";

export function PageSpinner({ className }: { className?: string }) {
  return (
    <div className={cn("flex h-64 items-center justify-center", className)}>
      <div className="size-8 animate-spin rounded-full border-2 border-stroke border-t-primary dark:border-stroke-dark dark:border-t-primary" />
    </div>
  );
}

export function PanelCard({
  title,
  action,
  children,
  className,
}: {
  title?: React.ReactNode;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "rounded-[10px] border border-stroke bg-white shadow-1 dark:border-stroke-dark dark:bg-gray-dark",
        className,
      )}
    >
      {(title || action) && (
        <header className="flex items-center justify-between border-b border-stroke px-6 py-4 dark:border-stroke-dark">
          {title ? (
            <h2 className="text-base font-semibold text-dark dark:text-white">
              {title}
            </h2>
          ) : (
            <span />
          )}
          {action}
        </header>
      )}
      <div className="p-6">{children}</div>
    </section>
  );
}
