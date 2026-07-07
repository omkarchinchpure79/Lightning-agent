"use client";

/**
 * PathMeter — the signature visual: literalizes the brand mark (a green start
 * dot, a path, a blue-ringed destination) as a real proportional bar instead
 * of decoration. Used illustratively in the Discover hero and, bound to real
 * counts, on the prediction results page.
 */
interface PathMeterProps {
  safe: number;
  probable: number;
  reach: number;
  /** Dark variant for use on the navy hero/auth panels. */
  dark?: boolean;
  className?: string;
}

export function PathMeter({ safe, probable, reach, dark, className }: PathMeterProps) {
  const total = Math.max(1, safe + probable + reach);
  const pct = (n: number) => (n / total) * 100;

  const trackBg = dark ? "rgba(255,255,255,0.14)" : "var(--ep-border)";
  const labelColor = dark ? "rgba(234,240,250,0.65)" : "var(--ep-text-secondary)";

  return (
    <div className={className}>
      <div className="flex items-center gap-3">
        <span
          className="h-3 w-3 rounded-full shrink-0"
          style={{ background: "var(--color-ep-green)" }}
          aria-hidden="true"
        />
        <div
          className="flex-1 h-2.5 rounded-full overflow-hidden flex"
          style={{ background: trackBg }}
        >
          {safe > 0 && (
            <div style={{ width: `${pct(safe)}%`, background: "var(--color-ep-green)" }} />
          )}
          {probable > 0 && (
            <div style={{ width: `${pct(probable)}%`, background: "var(--color-ep-amber)" }} />
          )}
          {reach > 0 && (
            <div style={{ width: `${pct(reach)}%`, background: "var(--color-ep-red)" }} />
          )}
        </div>
        <span
          className="h-3.5 w-3.5 rounded-full shrink-0"
          style={{ background: "transparent", border: `2px solid var(--color-ep-primary)` }}
          aria-hidden="true"
        />
      </div>
      <div className="flex items-center gap-4 mt-2 font-mono text-[11px]" style={{ color: labelColor }}>
        <span><b style={{ color: dark ? "#EAF0FA" : "var(--ep-text)" }}>{safe}</b> safe</span>
        <span><b style={{ color: dark ? "#EAF0FA" : "var(--ep-text)" }}>{probable}</b> probable</span>
        <span><b style={{ color: dark ? "#EAF0FA" : "var(--ep-text)" }}>{reach}</b> reach</span>
      </div>
    </div>
  );
}
