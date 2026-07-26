/**
 * The signature visual element of the console: each agent's verdict
 * rendered as a labeled meter, not a wall of JSON. The domain's own
 * vocabulary calls these "signals" (see aggregator.py's
 * contributing_signals) — this renders that idea literally, the way
 * an audio console or instrument panel would show multiple channels
 * at a glance: a label, a fill proportional to confidence, and a
 * color that reads as clean/flagged before you even read the number.
 */

type Tone = "clean" | "flagged" | "neutral";

interface SignalMeterProps {
  label: string;
  tone: Tone;
  confidence: number;
  detail: string;
  reasoning?: string;
}

const TONE_STYLES: Record<Tone, { fill: string; text: string }> = {
  clean: { fill: "bg-approve", text: "text-approve" },
  flagged: { fill: "bg-reject", text: "text-reject" },
  neutral: { fill: "bg-accent", text: "text-accent" },
};

export function SignalMeter({ label, tone, confidence, detail, reasoning }: SignalMeterProps) {
  const style = TONE_STYLES[tone];
  const pct = Math.round(confidence * 100);

  return (
    <div className="py-2.5">
      <div className="flex items-center gap-3">
        <span className="w-20 shrink-0 font-mono text-[11px] uppercase tracking-wide text-text-muted">
          {label}
        </span>
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-panel-raised">
          <div
            className={`h-full rounded-full ${style.fill} transition-all`}
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className={`w-11 shrink-0 text-right font-mono text-xs ${style.text}`}>{pct}%</span>
      </div>
      <p className="mt-1 pl-[92px] text-xs text-text-muted">{detail}</p>
      {reasoning && <p className="mt-0.5 pl-[92px] text-xs text-text-faint">{reasoning}</p>}
    </div>
  );
}
