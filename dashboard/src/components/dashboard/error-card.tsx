"use client";

import { AlertCircle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

interface ErrorCardProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorCard({ message, onRetry }: ErrorCardProps) {
  return (
    <Card className="p-6 flex items-start gap-4 border-red-200 bg-red-50/50 dark:border-red-900/40 dark:bg-red-950/20">
      <AlertCircle className="w-5 h-5 text-red-500 mt-0.5 shrink-0" />
      <div className="flex-1">
        <div className="font-medium text-red-700 dark:text-red-300">
          Couldn&apos;t load this page
        </div>
        <div className="text-sm text-muted-foreground mt-1">{message}</div>
        {onRetry && (
          <Button variant="outline" size="sm" className="mt-3" onClick={onRetry}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Try again
          </Button>
        )}
      </div>
    </Card>
  );
}
