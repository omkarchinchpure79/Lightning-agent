"use client";

import { GitCompareArrows, Check } from "lucide-react";
import { useCompare, type CompareCollege, MAX_COMPARE } from "@/lib/useCompare";
import { cn } from "@/lib/utils";

interface CompareButtonProps {
  college: CompareCollege;
  variant?: "chip" | "full";
  className?: string;
}

/**
 * "Add to compare" toggle — mirrors the Save/Bookmark button's shape so the
 * two actions read as siblings. `chip` is for dense contexts (discovery list
 * rows, search results); `full` matches the profile sidebar's Save button.
 */
export function CompareButton({ college, variant = "chip", className }: CompareButtonProps) {
  const { toggle, isComparing, count, canAddMore } = useCompare();
  const active = isComparing(college.code);
  const disabled = !active && !canAddMore;

  function handleClick(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (disabled) return;
    toggle(college);
  }

  if (variant === "full") {
    return (
      <button
        type="button"
        onClick={handleClick}
        disabled={disabled}
        title={disabled ? `Compare up to ${MAX_COMPARE} colleges at a time` : undefined}
        className={cn(
          "w-full flex items-center justify-center gap-2 py-3 rounded-[10px] text-[13px] font-medium border transition-all disabled:opacity-40 disabled:cursor-not-allowed",
          active
            ? "border-[var(--color-ep-primary)] text-[var(--color-ep-primary)]"
            : "text-[var(--ep-text-secondary)] hover:bg-[var(--ep-bg)]",
          className
        )}
        style={{
          borderColor: active ? "var(--color-ep-primary)" : "var(--ep-border-strong)",
          background: active ? "rgba(30,77,140,0.08)" : "transparent",
        }}
      >
        {active ? <Check className="h-4 w-4" /> : <GitCompareArrows className="h-4 w-4" />}
        {active ? `Comparing (${count})` : "Add to compare"}
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={disabled}
      title={
        disabled
          ? `Compare up to ${MAX_COMPARE} colleges at a time`
          : active
          ? "Remove from compare"
          : "Add to compare"
      }
      aria-label={active ? "Remove from compare" : "Add to compare"}
      className={cn(
        "inline-flex items-center gap-1 rounded-[7px] border px-2 py-1 text-[11px] font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed",
        className
      )}
      style={
        active
          ? { borderColor: "var(--color-ep-primary)", color: "var(--color-ep-primary)", background: "rgba(30,77,140,0.08)" }
          : { borderColor: "var(--ep-border-strong)", color: "var(--ep-text-secondary)" }
      }
    >
      {active ? <Check className="h-3 w-3" /> : <GitCompareArrows className="h-3 w-3" />}
      {active ? "Comparing" : "Compare"}
    </button>
  );
}
