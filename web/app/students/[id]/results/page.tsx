"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  BookmarkPlus,
  ChevronDown,
  ChevronUp,
  Pencil,
  Star,
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  X,
  ListX,
} from "lucide-react";

import {
  getStudentPredictions,
  getStudent,
  getShortlist,
  saveShortlist,
  type PredictionRow,
  type PredictionResult,
  type ShortlistItem,
} from "@/lib/api";
import { NavHeader } from "@/components/NavHeader";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Checkbox } from "@/components/ui/checkbox";

// ── Constants ─────────────────────────────────────────────────────────────────

const BAND_CONFIG = {
  safe: {
    label: "Safe",
    ink: "var(--color-ep-green-ink)",
    tintBg: "#EAF6EE",
    borderColor: "#B7E0C4",
    dot: "var(--color-ep-green)",
    badge: "safe" as const,
    description: "Strong chance of getting a seat — percentile comfortably above cutoff.",
  },
  probable: {
    label: "Probable",
    ink: "var(--color-ep-amber-ink)",
    tintBg: "#F8F0DD",
    borderColor: "#E8D6A8",
    dot: "var(--color-ep-amber)",
    badge: "probable" as const,
    description: "Within reach — cutoff may move up or down by round 3.",
  },
  reach: {
    label: "Reach",
    ink: "var(--color-ep-red-ink)",
    tintBg: "#F8E7E5",
    borderColor: "#E8BFBD",
    dot: "var(--color-ep-red)",
    badge: "reach" as const,
    description: "Aspirational — include 2–3 for negotiation leverage.",
  },
} as const;

type BandKey = keyof typeof BAND_CONFIG;
const CARDS_DEFAULT = 10;

// C — staggered band entrance: SAFE (i=0) first, then PROBABLE (+100ms), then REACH (+100ms).
// Each fades in and slides up from slightly below.
const BAND_REVEAL = {
  hidden: { opacity: 0, y: 18 },
  show: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.1, duration: 0.3, ease: "easeOut" as const },
  }),
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function feeText(row: PredictionRow): string {
  if (!row.fee.available) return "Fee N/A";
  return `₹${(row.fee.total_annual ?? 0).toLocaleString("en-IN")}/yr`;
}

// The point estimate is at its accuracy ceiling (backtest MAE ~8 pts globally) —
// displaying it to 2 decimals implies precision the model doesn't have. Show 1
// decimal plus the calibrated likely range instead (see roadmap item C2).
function closeText(row: PredictionRow): string {
  const point = row.predicted_close.toFixed(1);
  if (row.predicted_low == null || row.predicted_high == null) return point;
  return `${point} (likely ${row.predicted_low.toFixed(0)}–${row.predicted_high.toFixed(0)})`;
}

function intervalWidth(row: PredictionRow): number | null {
  if (row.predicted_low == null || row.predicted_high == null) return null;
  return row.predicted_high - row.predicted_low;
}

// Plain-language confidence explanation. R4 first ran in 2025, so every R4 row is
// single-year for a structural reason, not because the branch itself is shaky —
// say so instead of the generic "low confidence" (roadmap C2).
function confidenceTooltip(row: PredictionRow, roundNum: number): string {
  if (row.years_used === 1 && roundNum === 4) {
    return "CAP Round 4 first ran in 2025 — this is the only year of data for this round, not a volatile branch.";
  }
  const width = intervalWidth(row);
  if (width == null) return "";
  return `Branches like this have historically moved up to ±${Math.round(width / 2)} pts year-to-year.`;
}

function uniqueColleges(rows: PredictionRow[]): number {
  return new Set(rows.map((r) => r.college_code)).size;
}

type SortKey = "predicted_close" | "margin" | "college_score";
type SortDir = "asc" | "desc";

function sortedRows(rows: PredictionRow[], key: SortKey, dir: SortDir): PredictionRow[] {
  return [...rows].sort((a, b) => {
    const av = (a[key] ?? 0) as number;
    const bv = (b[key] ?? 0) as number;
    return dir === "desc" ? bv - av : av - bv;
  });
}

function rowToShortlist(row: PredictionRow): ShortlistItem {
  return {
    canonical_code: row.canonical_code,
    college_name: row.college_name,
    branch_name: row.branch_name,
    band: row.band,
    predicted_close: row.predicted_close,
    margin: row.margin,
    confidence: row.confidence,
    category_used: row.category_used,
    seat_type: row.seat_type,
    fee_text: feeText(row),
  };
}

// ── College card ──────────────────────────────────────────────────────────────

function CollegeCard({
  row,
  onAdd,
  inShortlist,
  saving,
  roundNum,
}: {
  row: PredictionRow;
  onAdd: (row: PredictionRow) => void;
  inShortlist: boolean;
  saving: boolean;
  roundNum: number;
}) {
  const seatOk = row.seat_data_status === "exact" || row.seat_data_status === "state_only";
  return (
    <motion.div
      className="rounded-[10px] border p-[13px] space-y-[9px]"
      style={{ background: "#fff", borderColor: "var(--ep-border)" }}
      whileHover={{ scale: 1.02, y: -3, boxShadow: "0 10px 28px rgba(0,0,0,0.12)" }}
      transition={{ type: "spring", stiffness: 300, damping: 30 }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <Link
            href={`/colleges/${row.college_code}`}
            className="font-serif text-sm font-medium leading-snug hover:underline truncate block"
            style={{ color: "var(--color-ep-primary)" }}
          >
            {row.college_name}
          </Link>
          <Link
            href={`/branches/${encodeURIComponent(row.canonical_code)}`}
            className="text-[11px] text-ep-muted mt-0.5 truncate block hover:text-[var(--color-ep-primary)] transition-colors"
          >
            {row.branch_name} · {row.city}
          </Link>
        </div>
        <button
          onClick={() => onAdd(row)}
          disabled={saving}
          className="font-mono shrink-0 whitespace-nowrap inline-flex items-center gap-1 text-[11px] font-semibold border rounded-[7px] px-2 py-1 transition-colors disabled:opacity-50"
          style={
            inShortlist
              ? { color: "var(--color-ep-green-ink)", borderColor: "#B7E0C4", background: "#EAF6EE" }
              : { color: "var(--color-ep-primary)", borderColor: "var(--ep-border-strong)" }
          }
        >
          {/* D — animated icon swap + pulse when an item enters the shortlist */}
          <AnimatePresence mode="wait" initial={false}>
            {inShortlist ? (
              <motion.span
                key="saved"
                className="inline-flex items-center gap-1"
                initial={{ scale: 0.6, opacity: 0 }}
                animate={{ scale: [1.25, 1], opacity: 1 }}
                transition={{ type: "spring", stiffness: 400, damping: 18 }}
              >
                <CheckCircle2 className="h-3 w-3" />
                Saved
              </motion.span>
            ) : (
              <motion.span
                key="add"
                className="inline-flex items-center gap-1"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
              >
                <BookmarkPlus className="h-3 w-3" />
                Add
              </motion.span>
            )}
          </AnimatePresence>
        </button>
      </div>
      <div className="flex flex-wrap gap-[5px]">
        <Badge
          variant={row.confidence as "high" | "medium" | "low"}
          className="text-[9.5px] px-[7px] py-[3px] rounded-[5px] cursor-help"
          title={confidenceTooltip(row, roundNum)}
        >
          {row.years_used === 1 && roundNum === 4 ? "first year" : row.confidence} confidence
        </Badge>
        <Badge variant="muted" className="text-[9.5px] px-[7px] py-[3px] rounded-[5px]">
          {!seatOk && <AlertTriangle className="h-2.5 w-2.5 mr-0.5 inline" />}
          {row.seat_type}
          {row.seat_data_status === "fallback" && " (fallback)"}
        </Badge>
        {row.seat_pool && (
          <Badge
            variant="default"
            className="text-[9.5px] px-[7px] py-[3px] rounded-[5px]"
            title={`Shown because this student is eligible for the ${row.seat_pool} seat pool.`}
          >
            {row.seat_pool} pool
          </Badge>
        )}
        {row.college_score != null && (
          <Badge variant="muted" className="text-[9.5px] px-[7px] py-[3px] rounded-[5px]">
            <Star className="h-2.5 w-2.5 mr-0.5 inline" fill="currentColor" />
            {row.college_score}/100
          </Badge>
        )}
      </div>
      <div className="font-mono flex gap-3.5 text-[11px] text-[var(--ep-text-secondary)] flex-wrap">
        <span>
          Close: <strong className="text-[var(--ep-text)]">{closeText(row)}</strong>
        </span>
        <span>
          Margin:{" "}
          <strong style={{ color: row.margin >= 0 ? "var(--color-ep-green-ink)" : "var(--color-ep-red)" }}>
            {row.margin > 0 ? "+" : ""}
            {row.margin.toFixed(1)}
          </strong>
        </span>
        <span>{feeText(row)}</span>
      </div>
    </motion.div>
  );
}

// ── Full-width sortable table ─────────────────────────────────────────────────

function BandTable({
  band,
  rows,
  shortlistCodes,
  onAdd,
  onAddSelected,
  onClose,
  saving,
  roundNum,
}: {
  band: BandKey;
  rows: PredictionRow[];
  shortlistCodes: Set<string>;
  onAdd: (rows: PredictionRow[]) => void;
  onAddSelected: (rows: PredictionRow[]) => void;
  onClose: () => void;
  saving: boolean;
  roundNum: number;
}) {
  const cfg = BAND_CONFIG[band];
  const [sortKey, setSortKey] = useState<SortKey>("predicted_close");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const sorted = useMemo(() => sortedRows(rows, sortKey, sortDir), [rows, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    else { setSortKey(key); setSortDir("desc"); }
  }

  function SortIcon({ k }: { k: SortKey }) {
    if (sortKey !== k) return <span className="opacity-30 text-xs">↕</span>;
    return sortDir === "desc" ? (
      <ChevronDown className="h-3 w-3 inline" />
    ) : (
      <ChevronUp className="h-3 w-3 inline" />
    );
  }

  return (
    <div className="rounded-[13px] border overflow-hidden" style={{ borderColor: cfg.borderColor }}>
      {/* Header */}
      <div className="px-5 py-3 flex items-center justify-between" style={{ background: cfg.tintBg }}>
        <div className="flex items-center gap-2.5">
          <span className="h-2.5 w-2.5 rounded-full shrink-0" style={{ background: cfg.dot }} />
          <span className="font-semibold text-sm" style={{ color: cfg.ink }}>{cfg.label}</span>
          <span className="font-mono text-xs text-[var(--ep-text-secondary)]">
            {rows.length} across {uniqueColleges(rows)} colleges
          </span>
        </div>
        <Button size="sm" variant="ghost" onClick={onClose}>
          <X className="h-4 w-4" />
          Close table
        </Button>
      </div>

      {/* Multi-select bar */}
      {selected.size > 0 && (
        <div
          className="px-4 py-2 flex items-center gap-3 border-b border-[var(--ep-border)]"
          style={{ background: "var(--ep-surface)" }}
        >
          <span className="text-sm text-[var(--ep-text)]">{selected.size} selected</span>
          <Button
            size="sm"
            onClick={() => {
              onAddSelected(sorted.filter((r) => selected.has(r.canonical_code)));
              setSelected(new Set());
            }}
            disabled={saving}
          >
            <BookmarkPlus className="h-3.5 w-3.5" />
            Add selected to shortlist
          </Button>
          <button
            onClick={() => setSelected(new Set())}
            className="text-sm text-ep-muted hover:text-[var(--ep-text)]"
          >
            Clear
          </button>
        </div>
      )}

      {/* Table — full viewport width inside the panel */}
      <div className="overflow-x-auto" style={{ background: "var(--ep-bg)" }}>
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr
              className="border-b border-[var(--ep-border)]"
              style={{ background: "var(--ep-surface)" }}
            >
              <th className="py-2.5 px-3 text-left w-8">
                <Checkbox
                  checked={selected.size === sorted.length && sorted.length > 0}
                  onCheckedChange={(c) =>
                    setSelected(c ? new Set(sorted.map((r) => r.canonical_code)) : new Set())
                  }
                />
              </th>
              <th className="font-mono py-2.5 px-3 text-left font-semibold text-[10px] uppercase text-ep-muted w-[35%]" style={{ letterSpacing: "0.05em" }}>
                College / Branch
              </th>
              <th
                className="font-mono py-2.5 px-3 text-right font-semibold text-[10px] uppercase text-ep-muted cursor-pointer select-none"
                style={{ letterSpacing: "0.05em" }}
                onClick={() => toggleSort("predicted_close")}
              >
                Predicted close <SortIcon k="predicted_close" />
              </th>
              <th
                className="font-mono py-2.5 px-3 text-right font-semibold text-[10px] uppercase text-ep-muted cursor-pointer select-none"
                style={{ letterSpacing: "0.05em" }}
                onClick={() => toggleSort("margin")}
              >
                Margin <SortIcon k="margin" />
              </th>
              <th className="font-mono py-2.5 px-3 text-center font-semibold text-[10px] uppercase text-ep-muted" style={{ letterSpacing: "0.05em" }}>
                Confidence
              </th>
              <th className="font-mono py-2.5 px-3 text-left font-semibold text-[10px] uppercase text-ep-muted" style={{ letterSpacing: "0.05em" }}>
                Seat type
              </th>
              <th className="font-mono py-2.5 px-3 text-right font-semibold text-[10px] uppercase text-ep-muted" style={{ letterSpacing: "0.05em" }}>
                Fee/yr
              </th>
              <th
                className="font-mono py-2.5 px-3 text-right font-semibold text-[10px] uppercase text-ep-muted cursor-pointer select-none"
                style={{ letterSpacing: "0.05em" }}
                onClick={() => toggleSort("college_score")}
              >
                Score <SortIcon k="college_score" />
              </th>
              <th className="py-2.5 px-3 w-8" />
            </tr>
          </thead>
          <tbody>
            {sorted.map((row) => (
              <tr
                key={row.canonical_code}
                className="border-b border-[var(--ep-border)] hover:bg-[var(--ep-surface)] transition-colors"
              >
                <td className="py-2 px-3">
                  <Checkbox
                    checked={selected.has(row.canonical_code)}
                    onCheckedChange={(c) =>
                      setSelected((prev) => {
                        const next = new Set(prev);
                        c ? next.add(row.canonical_code) : next.delete(row.canonical_code);
                        return next;
                      })
                    }
                  />
                </td>
                <td className="py-2.5 px-3">
                  <Link
                    href={`/colleges/${row.college_code}`}
                    className="font-serif text-sm font-medium hover:underline leading-snug block"
                    style={{ color: "var(--color-ep-primary)" }}
                  >
                    {row.college_name}
                  </Link>
                  <Link
                    href={`/branches/${encodeURIComponent(row.canonical_code)}`}
                    className="text-ep-muted hover:text-[var(--color-ep-primary)] transition-colors text-xs"
                  >
                    {row.branch_name} · {row.city}
                  </Link>
                </td>
                <td className="font-mono py-2.5 px-3 text-right text-[var(--ep-text)] whitespace-nowrap">
                  {closeText(row)}
                </td>
                <td
                  className="font-mono py-2.5 px-3 text-right font-semibold"
                  style={{ color: row.margin >= 0 ? "var(--color-ep-green-ink)" : "var(--color-ep-red)" }}
                >
                  {row.margin > 0 ? "+" : ""}
                  {row.margin.toFixed(1)}
                </td>
                <td className="py-2.5 px-3 text-center">
                  <Badge
                    variant={row.confidence as "high" | "medium" | "low"}
                    className="cursor-help"
                    title={confidenceTooltip(row, roundNum)}
                  >
                    {row.years_used === 1 && roundNum === 4 ? "first year" : row.confidence}
                  </Badge>
                </td>
                <td className="py-2.5 px-3 text-[var(--ep-text-secondary)]">
                  {row.seat_type}
                  {row.seat_data_status === "fallback" && (
                    <AlertTriangle className="h-3 w-3 inline ml-0.5" style={{ color: "var(--color-ep-amber)" }} />
                  )}
                  {row.seat_pool && (
                    <Badge variant="default" className="ml-1.5 text-[9.5px] px-[6px] py-[2px]">
                      {row.seat_pool}
                    </Badge>
                  )}
                </td>
                <td className="font-mono py-2.5 px-3 text-right text-[var(--ep-text-secondary)]">
                  {feeText(row)}
                </td>
                <td className="font-mono py-2.5 px-3 text-right text-[var(--ep-text-secondary)]">
                  {row.college_score ?? "—"}
                </td>
                <td className="py-2.5 px-3">
                  <Button
                    size="icon"
                    variant={shortlistCodes.has(row.canonical_code) ? "success" : "ghost"}
                    onClick={() => onAdd([row])}
                    disabled={saving}
                    aria-label="Add to shortlist"
                  >
                    <BookmarkPlus className="h-3.5 w-3.5" />
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Band card column (normal mode) ────────────────────────────────────────────

function BandColumn({
  band,
  rows,
  shortlistCodes,
  onAdd,
  onExpand,
  saving,
  roundNum,
}: {
  band: BandKey;
  rows: PredictionRow[];
  shortlistCodes: Set<string>;
  onAdd: (rows: PredictionRow[]) => void;
  onExpand: () => void;
  saving: boolean;
  roundNum: number;
}) {
  const cfg = BAND_CONFIG[band];

  if (rows.length === 0) {
    return (
      <div className="rounded-[13px] border p-6 text-center" style={{ borderColor: cfg.borderColor, background: cfg.tintBg }}>
        <ListX className="mx-auto mb-2 h-8 w-8 opacity-40" style={{ color: cfg.ink }} />
        <p className="font-semibold text-sm text-[var(--ep-text)]">No {cfg.label} options</p>
        <p className="mt-1 text-xs text-ep-muted">
          {band === "safe"
            ? "No branches where your percentile clears the cutoff even in its historical worst-case (likely-range) scenario. Try removing branch preferences or adjusting the category."
            : band === "probable"
            ? "No branches where your percentile falls within the branch's likely cutoff range."
            : "No aspirational options just below the likely cutoff range for any branch."}
        </p>
      </div>
    );
  }

  const top = rows.slice(0, CARDS_DEFAULT);

  return (
    <div className="rounded-[13px] border overflow-hidden" style={{ borderColor: cfg.borderColor }}>
      {/* Header */}
      <div className="px-5 py-3 flex items-center justify-between" style={{ background: cfg.tintBg }}>
        <div className="flex items-center gap-2.5">
          <span className="h-2.5 w-2.5 rounded-full shrink-0" style={{ background: cfg.dot }} />
          <div>
            <span className="font-semibold text-sm" style={{ color: cfg.ink }}>{cfg.label}</span>
            <span className="font-mono ml-2 text-xs text-[var(--ep-text-secondary)]">
              {rows.length} across {uniqueColleges(rows)} colleges
            </span>
          </div>
        </div>
        <button
          onClick={onExpand}
          className="text-xs text-ep-muted hover:text-[var(--ep-text)] transition-colors flex items-center gap-1"
        >
          View all {rows.length} <ChevronDown className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="p-3 space-y-2.5" style={{ background: "var(--ep-bg)" }}>
        <p className="text-xs text-ep-muted px-1">{cfg.description}</p>
        {top.map((row) => (
          <CollegeCard
            key={row.canonical_code}
            row={row}
            inShortlist={shortlistCodes.has(row.canonical_code)}
            onAdd={(r) => onAdd([r])}
            saving={saving}
            roundNum={roundNum}
          />
        ))}
        {rows.length > CARDS_DEFAULT && (
          <button
            onClick={onExpand}
            className="w-full text-center text-sm hover:underline py-1.5"
            style={{ color: "var(--color-ep-primary)" }}
          >
            View all {rows.length} in table →
          </button>
        )}
      </div>
    </div>
  );
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

function ResultsSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
      {["safe", "probable", "reach"].map((b) => (
        <div key={b} className="space-y-3">
          <Skeleton className="h-12 w-full" />
          {[...Array(5)].map((_, i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
      ))}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ResultsPage() {
  const { id } = useParams<{ id: string }>();
  const studentId = Number(id);
  const queryClient = useQueryClient();

  // Which band (if any) is in full-width table mode
  const [expandedBand, setExpandedBand] = useState<BandKey | null>(null);

  const { data: student } = useQuery({
    queryKey: ["student", studentId],
    queryFn: () => getStudent(studentId),
    enabled: !isNaN(studentId),
  });

  const { data: predictions, isLoading, error } = useQuery({
    queryKey: ["predictions", studentId, 1],
    queryFn: () => getStudentPredictions(studentId, 1),
    enabled: !isNaN(studentId),
    staleTime: 5 * 60 * 1000,
  });

  const { data: shortlist } = useQuery({
    queryKey: ["shortlist", studentId],
    queryFn: () => getShortlist(studentId),
    enabled: !isNaN(studentId),
  });

  const shortlistCodes = useMemo(
    () => new Set((shortlist?.items ?? []).map((i) => i.canonical_code)),
    [shortlist]
  );

  const { mutate: mutateShortlist, isPending: saving } = useMutation({
    mutationFn: (items: ShortlistItem[]) => saveShortlist(studentId, items),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["shortlist", studentId] }),
  });

  function addToShortlist(rows: PredictionRow[]) {
    const current = shortlist?.items ?? [];
    const existingCodes = new Set(current.map((i) => i.canonical_code));
    const merged = [
      ...current,
      ...rows.map(rowToShortlist).filter((i) => !existingCodes.has(i.canonical_code)),
    ];
    mutateShortlist(merged);
  }

  const totalCount =
    (predictions?.counts.safe ?? 0) +
    (predictions?.counts.probable ?? 0) +
    (predictions?.counts.reach ?? 0);

  const bands: BandKey[] = ["safe", "probable", "reach"];

  return (
    <div className="min-h-screen" style={{ background: "var(--ep-bg)" }}>
      <NavHeader
        right={
          <>
            {student && (
              <span className="font-mono text-sm text-ep-muted">
                {student.name} · {student.percentile}%ile
              </span>
            )}
            <Link
              href={`/students/${studentId}/shortlist`}
              className="flex items-center gap-1.5 text-sm font-semibold hover:opacity-80 transition-opacity"
              style={{ color: "var(--color-ep-primary)" }}
            >
              <BookmarkPlus className="h-4 w-4" />
              Shortlist ({shortlist?.items.length ?? 0})
            </Link>
            <Link
              href={`/students/${studentId}/edit`}
              className="flex items-center gap-1.5 text-sm text-ep-muted hover:text-[var(--ep-text)] transition-colors"
            >
              <Pencil className="h-3.5 w-3.5" />
              Edit student
            </Link>
          </>
        }
      />

      <main className="mx-auto max-w-[1400px] px-6 py-8">
        {/* Title */}
        <div className="mb-6">
          <h1 className="font-display text-[32px] text-[var(--ep-text)] mb-1">Prediction results</h1>
          {predictions && (
            <p className="font-mono text-[13px] text-ep-muted flex items-center flex-wrap gap-x-2">
              <span>
                CAP Round {predictions.round_num} · {predictions.base_category}
                {predictions.student_university_name
                  ? ` · Home university: ${predictions.student_university_name}`
                  : ""}
              </span>
              {predictions.district_unresolved && (
                <span className="inline-flex items-center gap-1 font-semibold" style={{ color: "var(--color-ep-amber-ink)" }}>
                  <AlertTriangle className="h-3.5 w-3.5" />
                  District unresolved — showing Other-university seats only
                </span>
              )}
            </p>
          )}
        </div>

        {/* Budget warning */}
        {(predictions?.counts.over_budget_hidden ?? 0) > 0 && (
          <div
            className="mb-4 rounded-[8px] border px-4 py-2.5 text-sm flex items-center gap-2"
            style={{ borderColor: "#E8D6A8", background: "#F8F0DD", color: "var(--color-ep-amber-ink)" }}
          >
            <AlertTriangle className="h-4 w-4 shrink-0" />
            {predictions!.counts.over_budget_hidden} branches hidden (over fee budget).{" "}
            {predictions!.counts.fee_unknown_kept} branches with unknown fees are included.
          </div>
        )}

        {isLoading && <ResultsSkeleton />}

        {error && (
          <div
            className="rounded-[10px] border px-5 py-4 text-sm flex items-start gap-3"
            style={{ borderColor: "#E8BFBD", background: "#F8E7E5", color: "var(--color-ep-red-ink)" }}
          >
            <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">Could not load predictions</p>
              <p className="mt-0.5 opacity-80">
                {error instanceof Error ? error.message : "Unknown error"}
              </p>
            </div>
          </div>
        )}

        {predictions && totalCount === 0 && (
          <div className="text-center py-16">
            <BookOpen className="mx-auto mb-3 h-10 w-10 text-ep-muted" />
            <h2 className="text-lg font-semibold text-[var(--ep-text)]">
              No matching branches found
            </h2>
            <p className="mt-2 text-sm text-ep-muted max-w-md mx-auto">
              No predictions match the student&apos;s percentile, category, and filters. Try
              removing branch preferences, increasing the percentile, or checking the category.
            </p>
            <div className="mt-4">
              <Link href={`/students/${studentId}/edit`}>
                <Button variant="outline">Edit student profile</Button>
              </Link>
            </div>
          </div>
        )}

        {predictions && totalCount > 0 && (
          /* E — crossfade between full-width table mode and the 3-column card mode.
             mode="wait" lets the outgoing layout slide/fade out before the new one
             animates in, so the layout shift reads as intentional, not jarring. */
          <AnimatePresence mode="wait" initial={false}>
            {expandedBand !== null ? (
              <motion.div
                key="table-mode"
                className="space-y-5"
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.25, ease: "easeOut" }}
              >
                <BandTable
                  band={expandedBand}
                  rows={predictions[expandedBand]}
                  shortlistCodes={shortlistCodes}
                  onAdd={addToShortlist}
                  onAddSelected={addToShortlist}
                  onClose={() => setExpandedBand(null)}
                  saving={saving}
                  roundNum={predictions.round_num}
                />
                {/* The other two bands stay visible as collapsed column cards below */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                  {bands
                    .filter((b) => b !== expandedBand)
                    .map((b) => (
                      <BandColumn
                        key={b}
                        band={b}
                        rows={predictions[b]}
                        shortlistCodes={shortlistCodes}
                        onAdd={addToShortlist}
                        onExpand={() => setExpandedBand(b)}
                        saving={saving}
                        roundNum={predictions.round_num}
                      />
                    ))}
                </div>
              </motion.div>
            ) : (
              /* Normal 3-column card mode — bands stagger in SAFE → PROBABLE → REACH */
              <motion.div
                key="card-mode"
                className="grid grid-cols-1 md:grid-cols-3 gap-5 items-start"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.2, ease: "easeOut" }}
              >
                {bands.map((b, i) => (
                  <motion.div
                    key={b}
                    custom={i}
                    variants={BAND_REVEAL}
                    initial="hidden"
                    animate="show"
                  >
                    <BandColumn
                      band={b}
                      rows={predictions[b]}
                      shortlistCodes={shortlistCodes}
                      onAdd={addToShortlist}
                      onExpand={() => setExpandedBand(b)}
                      saving={saving}
                      roundNum={predictions.round_num}
                    />
                  </motion.div>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        )}
      </main>
    </div>
  );
}
