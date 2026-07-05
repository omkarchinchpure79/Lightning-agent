"use client";

import { usePathname, useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { X, GitCompareArrows, ArrowRight } from "lucide-react";
import { useCompare, MIN_COMPARE } from "@/lib/useCompare";

const HIDDEN_ON = ["/login", "/signup", "/compare"];

/** Global floating tray — mounted once in Providers so a pick made on the
 * discovery list or a college profile stays visible while browsing to more
 * colleges, exactly like a shopping-cart tray. Hidden on auth pages and on
 * the compare page itself (redundant there). */
export function CompareTray() {
  const pathname = usePathname();
  const router = useRouter();
  const { items, remove, clear, count, hydrated } = useCompare();

  if (!hydrated || count === 0) return null;
  if (HIDDEN_ON.some((p) => pathname?.startsWith(p))) return null;

  function openCompare() {
    router.push(`/compare?codes=${items.map((i) => i.code).join(",")}`);
  }

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 24 }}
        transition={{ type: "spring", stiffness: 320, damping: 30 }}
        className="fixed bottom-5 left-1/2 -translate-x-1/2 z-40 flex items-center gap-3 rounded-full border pl-2 pr-2 py-2 shadow-lg max-w-[92vw]"
        style={{ background: "var(--ep-surface)", borderColor: "var(--ep-border-strong)" }}
      >
        <div className="flex items-center -space-x-2 pl-1">
          {items.map((c) => (
            <div
              key={c.code}
              title={c.name}
              className="group relative h-8 w-8 rounded-full border-2 flex items-center justify-center shrink-0"
              style={{ borderColor: "var(--ep-surface)", background: "var(--ep-bg)" }}
            >
              <span className="font-mono text-[10px] font-semibold text-[var(--ep-text-secondary)]">
                {c.name
                  .split(/\s+/)
                  .filter(Boolean)
                  .slice(0, 2)
                  .map((w) => w[0])
                  .join("")
                  .toUpperCase()}
              </span>
              <button
                onClick={() => remove(c.code)}
                aria-label={`Remove ${c.name} from compare`}
                className="absolute -top-1.5 -right-1.5 h-4 w-4 rounded-full flex items-center justify-center text-white opacity-0 group-hover:opacity-100 transition-opacity"
                style={{ background: "var(--color-ep-red)" }}
              >
                <X className="h-2.5 w-2.5" />
              </button>
            </div>
          ))}
        </div>

        <span className="hidden sm:flex items-center gap-1.5 text-sm font-semibold text-[var(--ep-text)] whitespace-nowrap">
          <GitCompareArrows className="h-4 w-4" style={{ color: "var(--color-ep-primary)" }} />
          {count} to compare
        </span>

        <button
          onClick={clear}
          className="text-xs text-ep-muted hover:text-[var(--ep-text)] transition-colors whitespace-nowrap px-1"
        >
          Clear
        </button>

        <button
          onClick={openCompare}
          disabled={count < MIN_COMPARE}
          title={count < MIN_COMPARE ? `Pick at least ${MIN_COMPARE} colleges` : undefined}
          className="inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed whitespace-nowrap"
          style={{ background: "var(--color-ep-primary)" }}
        >
          Compare Now
          <ArrowRight className="h-3.5 w-3.5" />
        </button>
      </motion.div>
    </AnimatePresence>
  );
}
