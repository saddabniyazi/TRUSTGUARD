"use client";

import { useEffect, useState } from "react";
import { fetchQueue } from "@/lib/api";
import type { ContentStatus, QueueItem } from "@/lib/types";

const STATUS_ORDER: ContentStatus[] = ["pending", "escalated", "approved", "rejected"];

const STATUS_COLOR: Record<ContentStatus, string> = {
  pending: "bg-pending",
  escalated: "bg-escalate",
  approved: "bg-approve",
  rejected: "bg-reject",
};

export default function MetricsPage() {
  const [items, setItems] = useState<QueueItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchQueue()
      .then(setItems)
      .finally(() => setLoading(false));
  }, []);

  const total = items.length;
  const counts = STATUS_ORDER.reduce(
    (acc, s) => ({ ...acc, [s]: items.filter((i) => i.status === s).length }),
    {} as Record<ContentStatus, number>,
  );
  const listingCount = items.filter((i) => i.item_type === "listing").length;
  const reviewCount = items.filter((i) => i.item_type === "review").length;
  const decidedCount = counts.approved + counts.rejected;
  const rejectRate = decidedCount > 0 ? Math.round((counts.rejected / decidedCount) * 100) : null;

  return (
    <div className="mx-auto max-w-4xl px-8 py-8">
      <h1 className="font-display text-lg font-semibold text-text-primary">Metrics</h1>
      <p className="mt-0.5 text-sm text-text-muted">
        Computed live from the current queue. A dedicated evaluation harness with agent-accuracy
        metrics lands in a later drop.
      </p>

      {loading ? (
        <p className="mt-8 font-mono text-xs text-text-faint">Loading…</p>
      ) : (
        <>
          <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard label="Total items" value={total} />
            <StatCard label="Listings" value={listingCount} />
            <StatCard label="Reviews" value={reviewCount} />
            <StatCard label="Reject rate" value={rejectRate !== null ? `${rejectRate}%` : "—"} />
          </div>

          <div className="mt-8 rounded-lg border border-hairline bg-panel p-5">
            <h2 className="mb-4 font-display text-sm font-semibold text-text-primary">
              Status distribution
            </h2>
            <div className="space-y-3">
              {STATUS_ORDER.map((status) => {
                const count = counts[status];
                const pct = total > 0 ? (count / total) * 100 : 0;
                return (
                  <div key={status} className="flex items-center gap-3">
                    <span className="w-20 shrink-0 font-mono text-[11px] uppercase tracking-wide text-text-muted">
                      {status}
                    </span>
                    <div className="h-2 flex-1 overflow-hidden rounded-full bg-panel-raised">
                      <div
                        className={`h-full rounded-full ${STATUS_COLOR[status]}`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="w-8 shrink-0 text-right font-mono text-xs text-text-muted">{count}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-hairline bg-panel p-4">
      <p className="font-mono text-2xl font-semibold text-text-primary">{value}</p>
      <p className="mt-1 text-xs text-text-muted">{label}</p>
    </div>
  );
}
