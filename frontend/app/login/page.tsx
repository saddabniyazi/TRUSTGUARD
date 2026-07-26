"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { ApiError } from "@/lib/api";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      router.replace("/queue");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't reach the API. Is the backend running?");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-void px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <div className="mb-1 flex items-center justify-center gap-2">
            <span className="h-2 w-2 rounded-full bg-accent" />
            <h1 className="font-display text-xl font-semibold tracking-tight text-text-primary">
              TrustGuard
            </h1>
          </div>
          <p className="font-mono text-xs text-text-faint">Moderation console</p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="rounded-lg border border-hairline bg-panel p-6 shadow-[0_0_0_1px_rgba(0,0,0,0.2)]"
        >
          <div className="mb-4">
            <label htmlFor="email" className="mb-1.5 block text-xs font-medium text-text-muted">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-md border border-hairline bg-panel-raised px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
              placeholder="you@example.com"
            />
          </div>

          <div className="mb-5">
            <label htmlFor="password" className="mb-1.5 block text-xs font-medium text-text-muted">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-md border border-hairline bg-panel-raised px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
              placeholder="••••••••"
            />
          </div>

          {error && (
            <div className="mb-4 rounded-md border border-reject-dim bg-reject-dim/30 px-3 py-2 text-xs text-reject">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-md bg-accent px-3 py-2 text-sm font-medium text-void transition hover:bg-accent/90 disabled:opacity-50"
          >
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p className="mt-4 text-center font-mono text-xs text-text-faint">
          No account? Register via <span className="text-text-muted">POST /api/auth/register</span>
        </p>
      </div>
    </div>
  );
}
