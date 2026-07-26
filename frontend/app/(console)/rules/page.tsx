"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useAuth } from "@/lib/auth-context";
import { createRule, deactivateRule, fetchRules } from "@/lib/api";
import type { PolicyRule } from "@/lib/types";

export default function RulesPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [rules, setRules] = useState<PolicyRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [category, setCategory] = useState("");
  const [ruleText, setRuleText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function load() {
    setLoading(true);
    try {
      setRules(await fetchRules());
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!category.trim() || !ruleText.trim()) return;
    setSubmitting(true);
    try {
      await createRule(category.trim(), ruleText.trim());
      setCategory("");
      setRuleText("");
      await load();
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDeactivate(id: string) {
    await deactivateRule(id);
    await load();
  }

  const grouped = rules.reduce<Record<string, PolicyRule[]>>((acc, rule) => {
    (acc[rule.category] ??= []).push(rule);
    return acc;
  }, {});

  return (
    <div className="mx-auto max-w-4xl px-8 py-8">
      <h1 className="font-display text-lg font-semibold text-text-primary">Policy rules</h1>
      <p className="mt-0.5 text-sm text-text-muted">
        Structured, versioned rules the Policy Compliance Agent reasons against directly — not a
        document it searches over.
      </p>

      {isAdmin && (
        <form
          onSubmit={handleCreate}
          className="mt-6 rounded-lg border border-hairline bg-panel p-5"
        >
          <h2 className="mb-3 font-display text-sm font-semibold text-text-primary">Add a rule</h2>
          <div className="grid gap-3 sm:grid-cols-[1fr_2fr_auto]">
            <input
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              placeholder="category (e.g. prohibited_items)"
              className="rounded-md border border-hairline bg-panel-raised px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
            />
            <input
              value={ruleText}
              onChange={(e) => setRuleText(e.target.value)}
              placeholder="rule text"
              className="rounded-md border border-hairline bg-panel-raised px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
            />
            <button
              type="submit"
              disabled={submitting}
              className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-void transition hover:bg-accent/90 disabled:opacity-50"
            >
              Add
            </button>
          </div>
        </form>
      )}

      <div className="mt-6 space-y-6">
        {loading ? (
          <p className="font-mono text-xs text-text-faint">Loading rules…</p>
        ) : (
          Object.entries(grouped).map(([cat, catRules]) => (
            <div key={cat}>
              <h3 className="mb-2 font-mono text-xs uppercase tracking-wide text-text-faint">{cat}</h3>
              <div className="overflow-hidden rounded-lg border border-hairline bg-panel">
                {catRules.map((rule) => (
                  <div
                    key={rule.id}
                    className="flex items-center gap-3 border-b border-hairline px-4 py-3 last:border-b-0"
                  >
                    <span className="flex-1 text-sm text-text-primary">{rule.rule_text}</span>
                    <span className="font-mono text-xs text-text-faint">v{rule.version}</span>
                    {isAdmin && (
                      <button
                        onClick={() => handleDeactivate(rule.id)}
                        className="font-mono text-xs text-text-faint transition hover:text-reject"
                      >
                        deactivate
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
