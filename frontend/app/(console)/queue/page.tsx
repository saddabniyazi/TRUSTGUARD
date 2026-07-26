"use client";

import { useCallback, useEffect, useState } from "react";
import { QueueRow } from "@/components/QueueRow";
import { fetchQueue } from "@/lib/api";
import type { ContentStatus, QueueItem } from "@/lib/types";

const FILTERS: { label: string; value: ContentStatus | "all" }[] = [
  { label: "All", value: "all" },
  { label: "Pending", value: "pending" },
  { label: "Escalated", value: "escalated" },
  { label: "Approved", value: "approved" },
  { label: "Rejected", value: "rejected" },
];

export default function QueuePage() {
  const [items, setItems] = useState<QueueItem[]>([]);
  const [filter, setFilter] = useState<ContentStatus | "all">("all");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (f: ContentStatus | "all") => {
    setLoading(true);
    try {
      const data = await fetchQueue(f === "all" ? undefined : f);
      setItems(data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(filter);
  }, [filter, load]);

  return (
    <div className="mx-auto max-w-4xl px-8 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="font-display text-lg font-semibold text-text-primary">Moderation queue</h1>
          <p className="mt-0.5 text-sm text-text-muted">
            Listings and reviews submitted for review, newest first.
          </p>
        </div>
      </div>

      <div className="mb-4 flex gap-1.5">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => setFilter(f.value)}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${
              filter === f.value
                ? "bg-panel-raised text-text-primary"
                : "text-text-muted hover:bg-panel-raised/50"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="overflow-hidden rounded-lg border border-hairline bg-panel">
        {loading ? (
          <p className="px-5 py-8 text-center font-mono text-xs text-text-faint">Loading queue…</p>
        ) : items.length === 0 ? (
          <div className="px-5 py-10 text-center">
            <p className="text-sm text-text-muted">Nothing here yet.</p>
            <p className="mt-1 text-xs text-text-faint">
              Submit a listing or review via the API to see it appear.
            </p>
          </div>
        ) : (
          items.map((item) => (
            <QueueRow key={`${item.item_type}-${item.id}`} item={item} onStatusChange={() => load(filter)} />
          ))
        )}
      </div>
    </div>
  );
}
