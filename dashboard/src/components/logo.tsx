import { Phone } from "lucide-react";

export function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <div className="flex size-9 items-center justify-center rounded-xl bg-primary">
        <Phone className="size-4 text-white" />
      </div>
      <div className="leading-tight">
        <span className="block text-lg font-bold text-dark dark:text-white">
          AI Telephone Receptionist
        </span>
        <span className="block text-xs font-medium text-dark-5 dark:text-dark-6">
          Voice Receptionist
        </span>
      </div>
    </div>
  );
}
