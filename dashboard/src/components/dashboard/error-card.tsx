"use client";

import { AlertCircle, RefreshCw } from "lucide-react";

interface ErrorCardProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorCard({ message, onRetry }: ErrorCardProps) {
  return (
    <div className="flex items-start gap-4 rounded-[10px] border border-red/30 bg-red-light-5 p-6 shadow-1 dark:border-red/40 dark:bg-red/10">
      <AlertCircle className="mt-0.5 size-5 shrink-0 text-red" />
      <div className="flex-1">
        <div className="font-medium text-red dark:text-red-light-3">
          Couldn&apos;t load this page
        </div>
        <p className="mt-1 text-sm text-dark-5 dark:text-dark-6">{message}</p>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="mt-3 inline-flex items-center gap-1.5 rounded-md border border-stroke bg-white px-3 py-1.5 text-xs font-medium text-dark transition-colors hover:bg-gray-2 dark:border-dark-3 dark:bg-dark-2 dark:text-white dark:hover:bg-dark-3"
          >
            <RefreshCw className="size-3.5" /> Try again
          </button>
        )}
      </div>
    </div>
  );
}
