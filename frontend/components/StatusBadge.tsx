import type { ContentStatus } from "@/lib/types";

const STYLES: Record<ContentStatus, { bg: string; text: string; dot: string; label: string }> = {
  pending: { bg: "bg-panel-raised", text: "text-text-muted", dot: "bg-pending", label: "Pending" },
  approved: { bg: "bg-approve-dim", text: "text-approve", dot: "bg-approve", label: "Approved" },
  rejected: { bg: "bg-reject-dim", text: "text-reject", dot: "bg-reject", label: "Rejected" },
  escalated: { bg: "bg-escalate-dim", text: "text-escalate", dot: "bg-escalate", label: "Escalated" },
};

export function StatusBadge({ status }: { status: ContentStatus }) {
  const s = STYLES[status];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${s.bg} ${s.text}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} />
      {s.label}
    </span>
  );
}
