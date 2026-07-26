"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getSellerAudit } from "@/lib/api";
import type { SellerAudit } from "@/lib/types";

const DECISION_STYLE: Record<string, string> = {
  auto_approve: "bg-approve-dim text-approve",
  auto_reject: "bg-reject-dim text-reject",
  escalate_to_human: "bg-escalate-dim text-escalate",
};

function trustScoreTone(score: number): { color: string; label: string } {
  if (score <= 30) return { color: "text-reject", label: "Low trust" };
  if (score >= 70) return { color: "text-approve", label: "High trust" };
  return { color: "text-text-primary", label: "Neutral" };
}

export default function SellerAuditPage() {
  const params = useParams<{ id: string }>();
  const [audit, setAudit] = useState<SellerAudit | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getSellerAudit(params.id)
      .then(setAudit)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load seller"))
      .finally(() => setLoading(false));
  }, [params.id]);

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl px-8 py-8">
        <p className="font-mono text-xs text-text-faint">Loading…</p>
      </div>
    );
  }

  if (error || !audit) {
    return (
      <div className="mx-auto max-w-4xl px-8 py-8">
        <p className="text-sm text-reject">{error ?? "Seller not found."}</p>
      </div>
    );
  }

  const tone = trustScoreTone(audit.seller.trust_score);

  return (
    <div className="mx-auto max-w-4xl px-8 py-8">
      <h1 className="font-display text-lg font-semibold text-text-primary">{audit.seller.name}</h1>
      <p className="mt-0.5 font-mono text-xs text-text-faint">{audit.seller.id}</p>

      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-lg border border-hairline bg-panel p-4">
          <p className={`font-mono text-2xl font-semibold ${tone.color}`}>
            {audit.seller.trust_score.toFixed(1)}
          </p>
          <p className="mt-1 text-xs text-text-muted">Trust score — {tone.label}</p>
        </div>
        <div className="rounded-lg border border-hairline bg-panel p-4">
          <p className="font-mono text-2xl font-semibold text-text-primary">{audit.seller.violation_count}</p>
          <p className="mt-1 text-xs text-text-muted">Violations</p>
        </div>
        <div className="rounded-lg border border-hairline bg-panel p-4">
          <p className="font-mono text-2xl font-semibold text-text-primary">{audit.listing_count}</p>
          <p className="mt-1 text-xs text-text-muted">Listings</p>
        </div>
        <div className="rounded-lg border border-hairline bg-panel p-4">
          <p className="font-mono text-sm font-semibold text-text-primary">
            {audit.current_thresholds.reject_threshold} / {audit.current_thresholds.approve_threshold}
          </p>
          <p className="mt-1 text-xs text-text-muted">Reject / approve threshold now</p>
        </div>
      </div>

      <p className="mt-4 text-xs text-text-faint">
        These thresholds are computed live from the trust score above — they&apos;re what the
        Aggregator is currently using for this seller&apos;s listings, not a fixed system-wide value.
        A trust score of 50 uses the base thresholds; this seller&apos;s history has shifted them.
      </p>

      <h2 className="mb-3 mt-8 font-display text-sm font-semibold text-text-primary">
        Verdict history
      </h2>
      {audit.verdict_history.length === 0 ? (
        <p className="text-sm text-text-muted">No moderation runs recorded yet.</p>
      ) : (
        <div className="overflow-hidden rounded-lg border border-hairline bg-panel">
          {audit.verdict_history.map((entry) => (
            <div key={entry.verdict_id} className="border-b border-hairline px-4 py-3 last:border-b-0">
              <div className="flex items-center gap-3">
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${DECISION_STYLE[entry.decision]}`}
                >
                  {entry.decision.replace(/_/g, " ")}
                </span>
                <span className="flex-1 truncate text-sm text-text-primary">{entry.listing_title}</span>
                <span className="font-mono text-xs text-text-faint">
                  {Math.round(entry.confidence * 100)}%
                </span>
                <span className="font-mono text-xs text-text-faint">
                  {new Date(entry.created_at).toLocaleDateString()}
                </span>
              </div>
              <p className="mt-1 text-xs text-text-muted">{entry.reasoning}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
