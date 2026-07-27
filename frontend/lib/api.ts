import type {
  AggregatorVerdict,
  AgreementSummary,
  EvalRun,
  Listing,
  PolicyRule,
  QueueItem,
  Review,
  SellerAudit,
  StreamEvent,
  TokenPair,
  User,
  VerdictHistoryEntry,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const ACCESS_TOKEN_KEY = "trustguard_access_token";
const REFRESH_TOKEN_KEY = "trustguard_refresh_token";

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function storeTokens(tokens: TokenPair): void {
  window.localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
  window.localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
}

export function clearTokens(): void {
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_TOKEN_KEY);
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Core request helper. Attaches the Bearer token when present, and on a
 * 401 tries exactly one silent refresh-and-retry before giving up — a
 * moderator mid-queue shouldn't get logged out just because their
 * access token expired 30 seconds into a session. If the refresh
 * itself fails, tokens are cleared and the 401 propagates so the UI
 * can redirect to /login.
 */
async function request<T>(path: string, options: RequestInit = {}, isRetry = false): Promise<T> {
  const token = getAccessToken();
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (res.status === 401 && !isRetry) {
    const refreshed = await tryRefresh();
    if (refreshed) return request<T>(path, options, true);
    clearTokens();
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // response body wasn't JSON — fall back to statusText
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

async function tryRefresh(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;
  try {
    const res = await fetch(`${API_BASE}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return false;
    const tokens: TokenPair = await res.json();
    storeTokens(tokens);
    return true;
  } catch {
    return false;
  }
}

// --- Auth ---

export function login(email: string, password: string): Promise<TokenPair> {
  return request<TokenPair>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function register(email: string, password: string, role: "admin" | "moderator"): Promise<User> {
  return request<User>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, role }),
  });
}

export function getCurrentUser(): Promise<User> {
  return request<User>("/api/auth/me");
}

// --- Queue (listings + reviews merged) ---

export async function fetchQueue(statusFilter?: string): Promise<QueueItem[]> {
  const qs = statusFilter ? `?status_filter=${statusFilter}` : "";
  const [listings, reviews] = await Promise.all([
    request<Listing[]>(`/api/listings${qs}`),
    request<Review[]>(`/api/reviews${qs}`),
  ]);
  const merged: QueueItem[] = [
    ...listings.map((l) => ({ item_type: "listing" as const, ...l })),
    ...reviews.map((r) => ({ item_type: "review" as const, ...r })),
  ];
  return merged.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
}

// --- Moderation (non-streaming) ---

export function moderateListing(id: string): Promise<AggregatorVerdict> {
  return request<AggregatorVerdict>(`/api/moderate/listing/${id}`, { method: "POST" });
}

export function moderateReview(id: string): Promise<AggregatorVerdict> {
  return request<AggregatorVerdict>(`/api/moderate/review/${id}`, { method: "POST" });
}

export function getListingVerdicts(id: string): Promise<VerdictHistoryEntry[]> {
  return request<VerdictHistoryEntry[]>(`/api/moderate/listing/${id}/verdicts`);
}

export function getReviewVerdicts(id: string): Promise<VerdictHistoryEntry[]> {
  return request<VerdictHistoryEntry[]>(`/api/moderate/review/${id}/verdicts`);
}

// --- Moderation (streaming) ---

/**
 * Consumes the SSE moderation stream via fetch + a manual reader
 * instead of the browser EventSource API, because EventSource can't
 * send an Authorization header — and these endpoints require one.
 * onEvent fires once per SSE event as it arrives; onDone fires when
 * the stream closes (whether via a "done" event or a network close).
 */
export async function streamModeration(
  itemType: "listing" | "review",
  id: string,
  onEvent: (event: StreamEvent) => void,
  onDone: () => void,
): Promise<void> {
  const token = getAccessToken();
  const res = await fetch(`${API_BASE}/api/moderate/stream/${itemType}/${id}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });

  if (!res.ok || !res.body) {
    onEvent({ agent: "error", data: { detail: `Stream request failed (${res.status})` } });
    onDone();
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE events are separated by a blank line; parse each complete
    // event out of the buffer as soon as it's fully arrived.
    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const rawEvent = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const eventLine = rawEvent.split("\n").find((line) => line.startsWith("event:"));
      const dataLine = rawEvent.split("\n").find((line) => line.startsWith("data:"));
      if (eventLine && dataLine) {
        const agent = eventLine.replace("event:", "").trim() as StreamEvent["agent"];
        const data = JSON.parse(dataLine.replace("data:", "").trim() || "{}");
        onEvent({ agent, data });
      }
      boundary = buffer.indexOf("\n\n");
    }
  }

  onDone();
}

// --- Policy rules ---

export function fetchRules(): Promise<PolicyRule[]> {
  return request<PolicyRule[]>("/api/rules");
}

export function createRule(category: string, ruleText: string): Promise<PolicyRule> {
  return request<PolicyRule>("/api/rules", {
    method: "POST",
    body: JSON.stringify({ category, rule_text: ruleText }),
  });
}

export function deactivateRule(id: string): Promise<PolicyRule> {
  return request<PolicyRule>(`/api/rules/${id}/deactivate`, { method: "PATCH" });
}

export function getSellerAudit(sellerId: string): Promise<SellerAudit> {
  return request<SellerAudit>(`/api/sellers/${sellerId}/audit`);
}

// --- Feedback ---

export function submitFeedback(
  verdictId: string,
  humanDecision: string,
  notes?: string,
): Promise<unknown> {
  return request("/api/feedback", {
    method: "POST",
    body: JSON.stringify({ verdict_id: verdictId, human_decision: humanDecision, notes }),
  });
}

// --- Evaluation ---

/** Live metric: how often moderator feedback (Day 6) agreed with the Aggregator's own decision. */
export function getAgreementSummary(): Promise<AgreementSummary> {
  return request<AgreementSummary>("/api/eval/agreement");
}

/** Offline metric: precision/recall from the last full-pipeline run against the adversarial dataset (Day 9's run_full_eval.py). Returns null if no run has been recorded yet, rather than throwing — this is a normal, expected state until someone runs the script. */
export async function getLatestEvalRun(): Promise<EvalRun | null> {
  try {
    return await request<EvalRun>("/api/eval/runs/latest");
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}
