import { cn } from "@/lib/cn";
import { DocumentStatus } from "@/lib/types";

const statusStyles: Record<DocumentStatus, string> = {
  PENDING: "bg-yellow-900/50 text-yellow-300 border-yellow-700",
  PROCESSING: "bg-blue-900/50 text-blue-300 border-blue-700",
  INDEXED: "bg-green-900/50 text-green-300 border-green-700",
  FAILED: "bg-red-900/50 text-red-300 border-red-700",
};

export function StatusBadge({ status }: { status: DocumentStatus }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium",
        statusStyles[status]
      )}
    >
      {status}
    </span>
  );
}
