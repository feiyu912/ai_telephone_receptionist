import { Card } from "@/components/ui/card";
import { TrendingUp, TrendingDown } from "lucide-react";
import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: string | number;
  change?: number;
  className?: string;
}

export function StatCard({ label, value, change, className }: StatCardProps) {
  const isPositive = change && change > 0;
  return (
    <Card className={cn("p-5", className)}>
      <p className="text-sm text-muted-foreground mb-1">{label}</p>
      <div className="flex items-end gap-2">
        <span className="text-3xl font-semibold">{value}</span>
        {change !== undefined && (
          <span
            className={cn(
              "flex items-center gap-0.5 text-xs font-medium mb-1",
              isPositive ? "text-green-600" : "text-red-500"
            )}
          >
            {isPositive ? (
              <TrendingUp className="w-3 h-3" />
            ) : (
              <TrendingDown className="w-3 h-3" />
            )}
            {isPositive ? "+" : ""}
            {change}%
          </span>
        )}
      </div>
    </Card>
  );
}
