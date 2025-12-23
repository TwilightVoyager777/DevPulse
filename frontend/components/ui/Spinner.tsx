import { cn } from "@/lib/cn";

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-block h-6 w-6 animate-spin rounded-full border-2 border-gray-600 border-t-brand-500",
        className
      )}
    />
  );
}
