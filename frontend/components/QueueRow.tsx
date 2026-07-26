"use client";

import { useState } from "react";
import Link from "next/link";
import { StatusBadge } from "./StatusBadge";
import { VerdictPanel } from "./VerdictPanel";
import { getListingVerdicts, getReviewVerdicts, streamModeration, submitFeedback } from "@/lib/api";
import type {
  AggregatorVerdict,
  FraudAgentVerdict,
  PolicyAgentVerdict,
  QueueItem,
  ToxicityAgentVerdict,
  VerdictHistoryEntry,
} from "@/lib/types";

interface QueueRowProps {
  item: QueueItem;
  onStatusChange: () => void;
}

export function QueueRow({ item, onStatusChange }: QueueRowProps) {
  const [expanded, setExpanded] = useState(false);
  const [history, setHistory] = useState<VerdictHistoryEntry[] | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(false);

  const [streaming, setStreaming] = useState(false);
  const [livePolicy, setLivePolicy] = useState<PolicyAgentVerdict | null>(null);
  const [liveToxicity, setLiveToxicity] = useState<ToxicityAgentVerdict | null>(null);
  const [liveFraud, setLiveFraud] = useState<FraudAgentVerdict | null>(null);
  const [liveAggregator, setLiveAggregator] = useState<AggregatorVerdict | null>(null);
  const [streamError, setStreamError] = useState<string | null>(null);

  const [feedbackSent, setFeedbackSent] = useState(false);

  const title = item.item_type === "listing" ? item.title : `Review by ${item.reviewer_name}`;
  const preview = item.item_type === "listing" ? item.description : item.text;
  const isReview = item.item_type === "review";

  async function loadHistory() {
    setLoadingHistory(true);
    try {
      const entries = isReview ? await getReviewVerdicts(item.id) : await getListingVerdicts(item.id);
      setHistory(entries);
    } finally {
      setLoadingHistory(false);
    }
  }

  function toggleExpand() {
    const next = !expanded;
    setExpanded(next);
    if (next && item.status !== "pending" && history === null) {
      void loadHistory();
    }
  }

  function runModeration() {
    setStreaming(true);
    setStreamError(null);
    setLivePolicy(null);
    setLiveToxicity(null);
    setLiveFraud(null);
    setLiveAggregator(null);
    setFeedbackSent(false);

    void streamModeration(
      isReview ? "review" : "listing",
      item.id,
      (evt) => {
        if (evt.agent === "policy") setLivePolicy(evt.data as unknown as PolicyAgentVerdict);
        else if (evt.agent === "toxicity") setLiveToxicity(evt.data as unknown as ToxicityAgentVerdict);
        else if (evt.agent === "fraud") setLiveFraud(evt.data as unknown as FraudAgentVerdict);
        else if (evt.agent === "aggregator") setLiveAggregator(evt.data as unknown as AggregatorVerdict);
        else if (evt.agent === "error") setStreamError((evt.data.detail as string) ?? "Moderation failed.");
      },
      () => {
        setStreaming(false);
        onStatusChange();
        void loadHistory();
      },
    );
  }

  async function handleFeedback(decision: string) {
    if (!history || history.length === 0) return;
    await submitFeedback(history[0].id, decision);
    setFeedbackSent(true);
  }

  const latest = history?.[0];

  return (
    <div className="border-b border-hairline">
      <button
        onClick={toggleExpand}
        className="flex w-full items-center gap-4 px-5 py-3 text-left transition hover:bg-panel-raised/50"
      >
        <StatusBadge status={item.status} />
        <span className="w-16 shrink-0 font-mono text-[11px] uppercase tracking-wide text-text-faint">
          {item.item_type}
        </span>
        <span className="flex-1 truncate text-sm text-text-primary">{title}</span>
        <span className="hidden max-w-xs flex-1 truncate text-xs text-text-muted sm:block">{preview}</span>
        <span className="shrink-0 font-mono text-xs text-text-faint">
          {new Date(item.created_at).toLocaleDateString()}
        </span>
      </button>

      {expanded && (
        <div className="border-t border-hairline bg-panel px-5 py-4">
          {streaming || livePolicy || liveAggregator ? (
            <>
              <VerdictPanel
                policy={livePolicy}
                toxicity={liveToxicity}
                fraud={liveFraud}
                aggregator={liveAggregator}
                expectFraud={isReview}
              />
              {streamError && <p className="mt-2 text-xs text-reject">{streamError}</p>}
              {streaming && !liveAggregator && (
                <p className="mt-2 font-mono text-xs text-text-faint">Running agents…</p>
              )}
            </>
          ) : loadingHistory ? (
            <p className="font-mono text-xs text-text-faint">Loading verdict history…</p>
          ) : latest ? (
            <>
              <VerdictPanel
                policy={latest.agent_scores.policy}
                toxicity={latest.agent_scores.toxicity}
                fraud={latest.agent_scores.fraud}
                aggregator={{
                  decision: latest.decision,
                  confidence: latest.confidence,
                  reasoning: latest.rationale.reasoning,
                  contributing_signals: latest.rationale.contributing_signals,
                }}
                expectFraud={isReview}
              />
              {history && history.length > 1 && (
                <p className="mt-2 font-mono text-xs text-text-faint">
                  +{history.length - 1} earlier verdict{history.length - 1 > 1 ? "s" : ""} for this item
                </p>
              )}
            </>
          ) : (
            <p className="text-xs text-text-muted">Not yet moderated.</p>
          )}

          <div className="mt-4 flex items-center gap-2">
            <button
              onClick={runModeration}
              disabled={streaming}
              className="rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-void transition hover:bg-accent/90 disabled:opacity-50"
            >
              {streaming ? "Running…" : latest ? "Re-moderate" : "Moderate"}
            </button>

            {latest && !streaming && (
              <>
                <button
                  onClick={() => handleFeedback(latest.decision)}
                  disabled={feedbackSent}
                  className="rounded-md border border-hairline px-3 py-1.5 text-xs text-text-muted transition hover:text-text-primary disabled:opacity-40"
                >
                  Confirm decision
                </button>
                <button
                  onClick={() => handleFeedback(latest.decision === "auto_reject" ? "auto_approve" : "auto_reject")}
                  disabled={feedbackSent}
                  className="rounded-md border border-hairline px-3 py-1.5 text-xs text-text-muted transition hover:text-text-primary disabled:opacity-40"
                >
                  Override
                </button>
                {feedbackSent && <span className="font-mono text-xs text-approve">Feedback recorded</span>}
              </>
            )}

            {item.item_type === "listing" && (
              <Link
                href={`/sellers/${item.seller_id}`}
                className="ml-auto font-mono text-xs text-text-faint transition hover:text-accent"
              >
                View seller →
              </Link>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
