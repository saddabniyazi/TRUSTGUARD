export interface User {
  id: string;
  email: string;
  full_name: string | null;
  role: "admin" | "moderator";
  is_active: boolean;
  created_at: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export type ContentStatus = "pending" | "approved" | "rejected" | "escalated";

export interface GuardrailInfo {
  injection_detected: boolean;
  injection_matches: string[];
  link_count: number;
}

export interface Listing {
  id: string;
  seller_id: string;
  title: string;
  description: string;
  category: string | null;
  status: ContentStatus;
  injection_detected: boolean;
  created_at: string;
  guardrail?: GuardrailInfo | null;
}

export interface Review {
  id: string;
  product_id: string;
  reviewer_name: string;
  text: string;
  rating: number;
  status: ContentStatus;
  injection_detected: boolean;
  created_at: string;
  guardrail?: GuardrailInfo | null;
}

export type QueueItem =
  | ({ item_type: "listing" } & Listing)
  | ({ item_type: "review" } & Review);

export interface PolicyAgentVerdict {
  compliant: boolean;
  violated_categories: string[];
  reasoning: string;
  confidence: number;
}

export interface ToxicityAgentVerdict {
  is_toxic: boolean;
  is_spam: boolean;
  reasoning: string;
  confidence: number;
}

export interface FraudAgentVerdict {
  is_likely_fake: boolean;
  fraud_indicators: string[];
  reasoning: string;
  confidence: number;
}

export type AggregatorDecision = "auto_approve" | "auto_reject" | "escalate_to_human";

export interface AggregatorVerdict {
  decision: AggregatorDecision;
  confidence: number;
  reasoning: string;
  contributing_signals: string[];
}

export interface VerdictHistoryEntry {
  id: string;
  decision: AggregatorDecision;
  confidence: number;
  rationale: {
    reasoning: string;
    contributing_signals: string[];
  };
  agent_scores: {
    policy?: PolicyAgentVerdict;
    toxicity?: ToxicityAgentVerdict;
    fraud?: FraudAgentVerdict;
  };
  created_at: string;
}

export interface PolicyRule {
  id: string;
  category: string;
  rule_text: string;
  version: number;
  active: boolean;
  created_at: string;
}

export interface SellerAuditVerdictEntry {
  verdict_id: string;
  listing_id: string;
  listing_title: string;
  decision: AggregatorDecision;
  confidence: number;
  reasoning: string;
  created_at: string;
}

export interface SellerAudit {
  seller: {
    id: string;
    name: string;
    trust_score: number;
    violation_count: number;
  };
  current_thresholds: {
    reject_threshold: number;
    approve_threshold: number;
  };
  listing_count: number;
  verdict_history: SellerAuditVerdictEntry[];
}

/** One live event received while streaming a moderation run via SSE. */
export interface StreamEvent {
  agent: "policy" | "toxicity" | "fraud" | "aggregator" | "done" | "error";
  data: Record<string, unknown>;
}

export interface AgreementBreakdown {
  decision: string;
  total_feedback: number;
  agreements: number;
  agreement_rate: number | null;
}

export interface AgreementSummary {
  total_feedback_entries: number;
  overall_agreement_rate: number | null;
  by_decision: AgreementBreakdown[];
}

export interface EvalRunCategoryStats {
  total: number;
  escalated: number;
  errors: number;
  correct: number;
  scored: number;
}

export interface EvalRun {
  id: string;
  total_cases: number;
  escalated_count: number;
  error_count: number;
  true_positives: number;
  false_positives: number;
  false_negatives: number;
  true_negatives: number;
  precision: number | null;
  recall: number | null;
  f1: number | null;
  accuracy_on_decided: number | null;
  per_category: Record<string, EvalRunCategoryStats>;
  created_at: string;
}
