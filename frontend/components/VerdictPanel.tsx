import type { AggregatorVerdict, FraudAgentVerdict, PolicyAgentVerdict, ToxicityAgentVerdict } from "@/lib/types";
import { SignalMeter } from "./SignalMeter";

interface VerdictPanelProps {
  policy?: PolicyAgentVerdict | null;
  toxicity?: ToxicityAgentVerdict | null;
  fraud?: FraudAgentVerdict | null;
  aggregator?: AggregatorVerdict | null;
  /** Reserves space for a signal that hasn't arrived yet during live streaming. */
  expectFraud?: boolean;
}

function SkeletonRow({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 py-2.5 opacity-40">
      <span className="w-20 shrink-0 font-mono text-[11px] uppercase tracking-wide text-text-muted">
        {label}
      </span>
      <div className="h-2 flex-1 animate-pulse rounded-full bg-panel-raised" />
      <span className="w-11 shrink-0 text-right font-mono text-xs text-text-faint">···</span>
    </div>
  );
}

export function VerdictPanel({ policy, toxicity, fraud, aggregator, expectFraud }: VerdictPanelProps) {
  return (
    <div className="divide-y divide-hairline/60">
      {policy ? (
        <SignalMeter
          label="Policy"
          tone={policy.compliant ? "clean" : "flagged"}
          confidence={policy.confidence}
          detail={policy.compliant ? "Compliant" : policy.violated_categories.join(", ") || "Violation"}
          reasoning={policy.reasoning}
        />
      ) : (
        <SkeletonRow label="Policy" />
      )}

      {toxicity ? (
        <SignalMeter
          label="Toxicity"
          tone={toxicity.is_toxic || toxicity.is_spam ? "flagged" : "clean"}
          confidence={toxicity.confidence}
          detail={toxicity.is_toxic ? "Toxic" : toxicity.is_spam ? "Spam" : "Clean"}
          reasoning={toxicity.reasoning}
        />
      ) : (
        <SkeletonRow label="Toxicity" />
      )}

      {fraud !== undefined &&
        (fraud ? (
          <SignalMeter
            label="Fraud"
            tone={fraud.is_likely_fake ? "flagged" : "clean"}
            confidence={fraud.confidence}
            detail={fraud.is_likely_fake ? fraud.fraud_indicators.join(", ") || "Likely fake" : "No indicators"}
            reasoning={fraud.reasoning}
          />
        ) : expectFraud ? (
          <SkeletonRow label="Fraud" />
        ) : null)}

      {aggregator && (
        <div className="pt-3">
          <div className="flex items-center gap-3">
            <span className="w-20 shrink-0 font-mono text-[11px] uppercase tracking-wide text-text-primary">
              Decision
            </span>
            <span
              className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                aggregator.decision === "auto_approve"
                  ? "bg-approve-dim text-approve"
                  : aggregator.decision === "auto_reject"
                    ? "bg-reject-dim text-reject"
                    : "bg-escalate-dim text-escalate"
              }`}
            >
              {aggregator.decision.replace(/_/g, " ")}
            </span>
            <span className="font-mono text-xs text-text-muted">
              {Math.round(aggregator.confidence * 100)}%
            </span>
          </div>
          <p className="mt-1.5 pl-[92px] text-xs text-text-muted">{aggregator.reasoning}</p>
        </div>
      )}
    </div>
  );
}
