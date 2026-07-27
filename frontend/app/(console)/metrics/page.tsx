"use client";

import { useEffect, useState } from "react";
import { fetchQueue, getAgreementSummary, getLatestEvalRun } from "@/lib/api";
import type { AgreementSummary, ContentStatus, EvalRun, QueueItem } from "@/lib/types";

const STATUS_ORDER: ContentStatus[] = ["pending", "escalated", "approved", "rejected"];

const STATUS_COLOR: Record<ContentStatus, string> = {
  pending: "bg-pending",
  escalated: "bg-escalate",
  approved: "bg-approve",
  rejected: "bg-reject",
};

function pct(value: number | null): string {
  return value !== null ? `${Math.round(value * 100)}%` : "—";
}

export default function MetricsPage() {
  const [items, setItems] = useState<QueueItem[]>([]);
  const [agreement, setAgreement] = useState<AgreementSummary | null>(null);
  const [evalRun, setEvalRun] = useState<EvalRun | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([fetchQueue(), getAgreementSummary(), getLatestEvalRun()])
      .then(([queueData, agreementData, evalData]) => {
        setItems(queueData);
        setAgreement(agreementData);
        setEvalRun(evalData);
      })
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
        Queue status computed live; agreement and precision/recall below reflect actual recorded
        outcomes, not projections.
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
                const pctWidth = total > 0 ? (count / total) * 100 : 0;
                return (
                  <div key={status} className="flex items-center gap-3">
                    <span className="w-20 shrink-0 font-mono text-[11px] uppercase tracking-wide text-text-muted">
                      {status}
                    </span>
                    <div className="h-2 flex-1 overflow-hidden rounded-full bg-panel-raised">
                      <div
                        className={`h-full rounded-full ${STATUS_COLOR[status]}`}
                        style={{ width: `${pctWidth}%` }}
                      />
                    </div>
                    <span className="w-8 shrink-0 text-right font-mono text-xs text-text-muted">{count}</span>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="mt-8 rounded-lg border border-hairline bg-panel p-5">
            <h2 className="font-display text-sm font-semibold text-text-primary">
              Moderator agreement (live)
            </h2>
            <p className="mt-1 text-xs text-text-muted">
              Of the feedback moderators have submitted, how often it matched the Aggregator&apos;s
              own decision.
            </p>
            {!agreement || agreement.total_feedback_entries === 0 ? (
              <p className="mt-3 text-sm text-text-muted">
                No feedback recorded yet — confirm or override a verdict from the Queue to start
                building this number.
              </p>
            ) : (
              <>
                <p className="mt-3 font-mono text-2xl font-semibold text-text-primary">
                  {pct(agreement.overall_agreement_rate)}
                  <span className="ml-2 text-xs font-normal text-text-faint">
                    ({agreement.total_feedback_entries} feedback entries)
                  </span>
                </p>
                <div className="mt-3 space-y-1.5">
                  {agreement.by_decision
                    .filter((b) => b.total_feedback > 0)
                    .map((b) => (
                      <div key={b.decision} className="flex items-center justify-between text-xs">
                        <span className="font-mono text-text-muted">{b.decision.replace(/_/g, " ")}</span>
                        <span className="text-text-muted">
                          {b.agreements}/{b.total_feedback} ({pct(b.agreement_rate)})
                        </span>
                      </div>
                    ))}
                </div>
              </>
            )}
          </div>

          <div className="mt-8 rounded-lg border border-hairline bg-panel p-5">
            <h2 className="font-display text-sm font-semibold text-text-primary">
              Adversarial dataset eval (offline)
            </h2>
            <p className="mt-1 text-xs text-text-muted">
              Precision/recall from the last full-pipeline run against the 36-case adversarial
              dataset. Run <code className="text-text-faint">python -m app.eval.run_full_eval</code>{" "}
              to refresh this.
            </p>
            {!evalRun ? (
              <p className="mt-3 text-sm text-text-muted">No eval run recorded yet.</p>
            ) : (
              <>
                <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <MiniStat label="Precision" value={pct(evalRun.precision)} />
                  <MiniStat label="Recall" value={pct(evalRun.recall)} />
                  <MiniStat label="F1" value={evalRun.f1 !== null ? evalRun.f1.toFixed(3) : "—"} />
                  <MiniStat label="Escalated" value={`${evalRun.escalated_count}/${evalRun.total_cases}`} />
                </div>
                <p className="mt-3 font-mono text-xs text-text-faint">
                  TP={evalRun.true_positives} FP={evalRun.false_positives} FN={evalRun.false_negatives}{" "}
                  TN={evalRun.true_negatives} · run at {new Date(evalRun.created_at).toLocaleString()}
                </p>
                <div className="mt-4 space-y-1.5">
                  {Object.entries(evalRun.per_category).map(([cat, stats]) => (
                    <div key={cat} className="flex items-center justify-between text-xs">
                      <span className="font-mono text-text-muted">{cat}</span>
                      <span className="text-text-muted">
                        {stats.correct}/{stats.scored} correct
                        {stats.escalated > 0 && `, ${stats.escalated} escalated`}
                      </span>
                    </div>
                  ))}
                </div>
              </>
            )}
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

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="font-mono text-lg font-semibold text-text-primary">{value}</p>
      <p className="text-xs text-text-muted">{label}</p>
    </div>
  );
}
