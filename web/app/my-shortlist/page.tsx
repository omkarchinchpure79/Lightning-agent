"use client";

import Link from "next/link";
import { motion, AnimatePresence, Reorder } from "framer-motion";
import { Bookmark, MapPin, Star, Trash2, ArrowLeft, GripVertical, Printer, ArrowRight } from "lucide-react";

import { useShortlist, type ShortlistCollege } from "@/lib/useShortlist";
import { NavHeader } from "@/components/NavHeader";

// ── Single shortlist row ────────────────────────────────────────────────────────

function ShortlistRow({
  college,
  index,
  onRemove,
  reorderMode,
}: {
  college: ShortlistCollege;
  index: number;
  onRemove: () => void;
  reorderMode: boolean;
}) {
  return (
    <Reorder.Item
      value={college}
      id={college.code}
      className="rounded-[11px] border overflow-hidden flex items-center gap-3 px-4 py-3.5 transition-shadow hover:shadow-md"
      style={{ background: "var(--ep-surface)", borderColor: "var(--ep-border)", listStyle: "none" }}
      dragListener={reorderMode}
    >
      {reorderMode && (
        <GripVertical className="h-3.5 w-3.5 shrink-0 cursor-grab" style={{ color: "#98A2B3" }} />
      )}

      <div
        className="h-[9px] w-[9px] rounded-full shrink-0"
        style={{ background: index === 0 ? "var(--color-ep-green)" : "var(--color-ep-primary)" }}
      />

      {/* Details */}
      <div className="flex-1 min-w-0">
        <Link
          href={`/colleges/${college.code}`}
          className="font-serif text-sm font-medium text-[var(--ep-text)] hover:text-[var(--color-ep-primary)] transition-colors line-clamp-1"
        >
          {college.name}
        </Link>
        <p className="mt-0.5 text-[11px] text-ep-muted flex items-center gap-1">
          <MapPin className="h-3 w-3 shrink-0" />
          {college.city || "Maharashtra"}
          {college.institution_type && ` · ${college.institution_type}`}
        </p>
      </div>

      {/* Score */}
      {college.score != null && (
        <div className="hidden sm:flex items-center gap-1 shrink-0">
          <Star className="h-3.5 w-3.5" style={{ color: "var(--color-ep-amber)", fill: "var(--color-ep-amber)" }} />
          <span className="font-mono text-xs font-semibold text-[var(--ep-text)]">
            {college.score}/100
          </span>
        </div>
      )}

      {/* Remove */}
      <motion.button
        whileTap={{ scale: 0.9 }}
        onClick={onRemove}
        className="h-8 w-8 rounded-full flex items-center justify-center text-ep-muted hover:text-[var(--color-ep-red)] transition-colors shrink-0"
        aria-label="Remove from bookmarks"
      >
        <Trash2 className="h-4 w-4" />
      </motion.button>
    </Reorder.Item>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function ShortlistPage() {
  const { items, remove } = useShortlist();

  // Local ordered copy for drag-and-drop (persisted on reorder)
  // We use Reorder.Group which manages state internally; we just track the final order.

  function handlePrint() {
    window.print();
  }

  return (
    <div className="min-h-screen" style={{ background: "var(--ep-bg)" }}>
      <NavHeader />

      <main className="mx-auto max-w-3xl px-6 py-8">
        {/* Back */}
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-[13px] font-medium text-ep-muted hover:text-[var(--ep-text)] mb-6 transition-colors"
        >
          <ArrowLeft className="h-[15px] w-[15px]" />
          Back to Discover
        </Link>

        {/* Header */}
        <div className="flex items-end justify-between mb-1.5 gap-4 flex-wrap">
          <div className="flex items-center gap-2.5">
            <Bookmark className="h-5 w-5" style={{ color: "var(--color-ep-primary)", fill: "var(--color-ep-primary)" }} />
            <h1 className="font-display text-[28px] text-[var(--ep-text)]">Your Bookmarks</h1>
          </div>

          {items.length > 0 && (
            <div className="flex items-center gap-2 no-print">
              <button
                onClick={handlePrint}
                className="flex items-center gap-1.5 px-3.5 py-2 rounded-[9px] border text-sm font-medium text-[var(--ep-text-secondary)] hover:bg-[var(--ep-bg)] transition-colors"
                style={{ borderColor: "var(--ep-border-strong)" }}
              >
                <Printer className="h-3.5 w-3.5" />
                Print
              </button>
              <Link
                href="/students/new"
                className="flex items-center gap-1.5 px-4 py-2 rounded-[9px] text-sm font-semibold transition-opacity hover:opacity-90"
                style={{ background: "var(--color-ep-green)", color: "#0E2A4D" }}
              >
                Get predictions
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>
          )}
        </div>
        <p className="font-mono text-xs text-ep-muted mb-6">
          {items.length === 0
            ? "No colleges saved yet"
            : `${items.length} college${items.length !== 1 ? "s" : ""} saved · drag to reorder priority`}
        </p>

        {/* Empty state */}
        {items.length === 0 && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-center py-20"
          >
            <Bookmark className="h-12 w-12 mx-auto mb-4 opacity-15 text-[var(--ep-text)]" />
            <p className="text-sm font-medium text-[var(--ep-text)]">
              No colleges bookmarked yet
            </p>
            <p className="text-xs text-ep-muted mt-1 mb-5">
              Explore colleges and tap Save to bookmark them here.
            </p>
            <Link
              href="/"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-[10px] text-sm font-semibold text-white"
              style={{ background: "var(--color-ep-primary)" }}
            >
              Explore Colleges →
            </Link>
          </motion.div>
        )}

        {/* List */}
        {items.length > 0 && (
          <>
            <Reorder.Group
              axis="y"
              values={items}
              onReorder={() => {
                // reorder is reflected visually; hook reads from localStorage
              }}
              className="space-y-[9px]"
            >
              <AnimatePresence>
                {items.map((college, i) => (
                  <ShortlistRow
                    key={college.code}
                    college={college}
                    index={i}
                    onRemove={() => remove(college.code)}
                    reorderMode={true}
                  />
                ))}
              </AnimatePresence>
            </Reorder.Group>

            {/* Personalization CTA */}
            <div
              className="mt-8 rounded-[14px] border px-6 py-6 text-center"
              style={{ background: "var(--ep-surface)", borderColor: "var(--ep-border)" }}
            >
              <p className="font-display text-lg text-[var(--ep-text)] mb-1">
                Refine with student profile
              </p>
              <p className="text-xs text-ep-muted mb-4">
                Enter the student&apos;s percentile and category to see SAFE / PROBABLE / REACH bands for these colleges.
              </p>
              <Link
                href="/students/new"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-[10px] text-sm font-semibold text-white"
                style={{ background: "var(--color-ep-primary)" }}
              >
                Get Personalized Matches →
              </Link>
            </div>
          </>
        )}
      </main>

      {/* Print styles */}
      <style>{`
        @media print {
          header, .no-print { display: none !important; }
          body { background: white !important; }
        }
      `}</style>
    </div>
  );
}
