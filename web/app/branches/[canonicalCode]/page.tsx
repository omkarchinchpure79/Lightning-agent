"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Minus,
  Armchair,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  LabelList,
} from "recharts";

import { getBranchDeepDive, type BranchDeepDive } from "@/lib/api";
import { parseCategory } from "@/lib/categories";
import { fmtPercentile, cn } from "@/lib/utils";
import { NavHeader } from "@/components/NavHeader";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

// ── Constants ─────────────────────────────────────────────────────────────────

const OPEN_CATS = new Set(["GOPENH", "GOPENS", "GOPENO"]);
const HIST_YEARS = [2023, 2024, 2025];

interface PredCell {
  pct: number;
  low: number | null;
  high: number | null;
}

// ── Chart data helpers ────────────────────────────────────────────────────────

interface ChartPoint {
  year: string;
  close: number | null;
  predicted: boolean;
}

/** Round-1-style open-category trend for whichever CAP round is selected. */
function buildChartData(data: BranchDeepDive, round: number): ChartPoint[] {
  const histByYear: Record<number, number> = {};
  for (const row of data.cutoff_trends) {
    if (row.round !== round || !OPEN_CATS.has(row.category)) continue;
    if (histByYear[row.year] == null || row.percentile < histByYear[row.year]) {
      histByYear[row.year] = row.percentile;
    }
  }

  let pred2026: number | null = null;
  for (const row of data.predictions_2026) {
    if (row.round !== round || !OPEN_CATS.has(row.category)) continue;
    if (pred2026 == null || row.predicted_pct < pred2026) pred2026 = row.predicted_pct;
  }

  const points: ChartPoint[] = [];
  for (const yr of HIST_YEARS) {
    if (histByYear[yr] != null) points.push({ year: String(yr), close: histByYear[yr], predicted: false });
  }
  points.push({ year: "2026*", close: pred2026, predicted: true });
  return points;
}

// The point estimate is at its accuracy ceiling (backtest MAE ~8 pts) — showing
// 2 decimals implies precision the model doesn't have. One decimal (via
// fmtPercentile so a sub-100 value never renders as "100") + calibrated range.
function predictedText(pct: number, low: number | null, high: number | null): string {
  const point = fmtPercentile(pct);
  if (low == null || high == null) return point;
  return `${point} (likely ${fmtPercentile(low, 0)}–${fmtPercentile(high, 0)})`;
}

function computeTrend(chartData: ChartPoint[]): number | null {
  const hist = chartData.filter((p) => !p.predicted && p.close != null);
  if (hist.length < 2) return null;
  return Math.round((hist[hist.length - 1].close! - hist[0].close!) * 100) / 100;
}

// ── Category tree ─────────────────────────────────────────────────────────────

interface VariantRow {
  raw: string;
  label: string;
  order: number;
  audience: string;
  hist: Record<number, number>;
  pred: PredCell | null;
}
interface FamilyGroup {
  key: string;
  label: string;
  order: number;
  primary: boolean;
  variants: VariantRow[];
  repHist: Record<number, number | undefined>;
  repPred: PredCell | null;
}

function buildCategoryTree(data: BranchDeepDive, round: number): FamilyGroup[] {
  const histByCat: Record<string, Record<number, number>> = {};
  for (const row of data.cutoff_trends) {
    if (row.round !== round) continue;
    (histByCat[row.category] ??= {})[row.year] = row.percentile;
  }
  const predByCat: Record<string, PredCell> = {};
  for (const row of data.predictions_2026) {
    if (row.round !== round) continue;
    const cur = predByCat[row.category];
    if (!cur || row.predicted_pct < cur.pct) {
      predByCat[row.category] = { pct: row.predicted_pct, low: row.predicted_low, high: row.predicted_high };
    }
  }

  const allCats = new Set([...Object.keys(histByCat), ...Object.keys(predByCat)]);
  const famMap: Record<string, FamilyGroup> = {};
  for (const cat of allCats) {
    const p = parseCategory(cat);
    const fam = (famMap[p.familyKey] ??= {
      key: p.familyKey,
      label: p.familyLabel,
      order: p.familyOrder,
      primary: p.primary,
      variants: [],
      repHist: {},
      repPred: null,
    });
    fam.variants.push({
      raw: cat,
      label: p.variantLabel,
      order: p.variantOrder,
      audience: p.audience,
      hist: histByCat[cat] ?? {},
      pred: predByCat[cat] ?? null,
    });
  }

  const families = Object.values(famMap);
  for (const fam of families) {
    fam.variants.sort((a, b) => a.order - b.order || a.raw.localeCompare(b.raw));
    // Representative row = the "general merit" seats (min = closing floor), so
    // the collapsed row shows the number counsellors quote for that category.
    const general = fam.variants.filter((v) => v.audience === "General" || v.audience === "Open");
    const src = general.length ? general : fam.variants;
    for (const yr of HIST_YEARS) {
      const vals = src.map((v) => v.hist[yr]).filter((x): x is number => x != null);
      fam.repHist[yr] = vals.length ? Math.min(...vals) : undefined;
    }
    const preds = src.map((v) => v.pred).filter((p): p is PredCell => p != null);
    fam.repPred = preds.length ? preds.reduce((m, p) => (p.pct < m.pct ? p : m)) : null;
  }
  families.sort((a, b) => a.order - b.order);
  return families;
}

function CategoryTree({ data, round }: { data: BranchDeepDive; round: number }) {
  const families = useMemo(() => buildCategoryTree(data, round), [data, round]);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [showMore, setShowMore] = useState(false);

  if (families.length === 0) {
    return (
      <p className="text-sm text-ep-muted italic p-5">
        No category data for CAP Round {round} at this branch.
      </p>
    );
  }

  const primary = families.filter((f) => f.primary);
  const more = families.filter((f) => !f.primary);
  const visible = showMore ? families : primary;

  const toggle = (k: string) => setExpanded((s) => ({ ...s, [k]: !s[k] }));

  return (
    <div className="overflow-x-auto -mx-[22px] -mb-[14px]">
      <table className="w-full text-[13px] border-collapse">
        <thead>
          <tr className="text-left" style={{ background: "var(--ep-bg)" }}>
            <th className="font-mono py-2.5 px-[22px] font-semibold text-[11px] uppercase text-ep-muted" style={{ letterSpacing: "0.05em" }}>
              Category
            </th>
            {HIST_YEARS.map((y) => (
              <th key={y} className="font-mono py-2.5 px-4 font-semibold text-[11px] uppercase text-ep-muted text-right" style={{ letterSpacing: "0.05em" }}>
                {y}
              </th>
            ))}
            <th className="font-mono py-2.5 px-[22px] font-semibold text-[11px] uppercase text-right" style={{ letterSpacing: "0.05em", color: "var(--color-ep-primary)" }}>
              2026*
            </th>
          </tr>
        </thead>
        <tbody>
          {visible.map((fam) => {
            const isOpen = !!expanded[fam.key];
            const single = fam.variants.length === 1;
            return (
              <FamilyRows
                key={fam.key}
                fam={fam}
                isOpen={isOpen}
                single={single}
                onToggle={() => !single && toggle(fam.key)}
              />
            );
          })}
        </tbody>
      </table>

      {more.length > 0 && (
        <button
          onClick={() => setShowMore((s) => !s)}
          className="flex items-center gap-1.5 mx-[22px] my-3 text-[12px] font-medium text-[var(--color-ep-primary)] hover:underline"
        >
          {showMore ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
          {showMore ? "Hide extra categories" : `More categories (${more.length})`}
        </button>
      )}

      <p className="px-[22px] pt-2 pb-[14px] text-[11px] text-ep-muted border-t" style={{ borderColor: "var(--ep-border)" }}>
        Click a category to see its Home / Other / State and Ladies variants. * 2026 values are model
        forecasts based on 2023–2025 CAP data — verify against official rounds before advising.
      </p>
    </div>
  );
}

function FamilyRows({
  fam,
  isOpen,
  single,
  onToggle,
}: {
  fam: FamilyGroup;
  isOpen: boolean;
  single: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      <tr
        className={cn("border-t transition-colors", !single && "cursor-pointer hover:bg-[var(--ep-bg)]")}
        style={{ borderColor: "var(--ep-border)" }}
        onClick={onToggle}
      >
        <td className="py-[11px] px-[22px]">
          <span className="flex items-center gap-1.5 font-semibold text-[13px] text-[var(--ep-text)]">
            {!single ? (
              isOpen ? <ChevronDown className="h-3.5 w-3.5 text-ep-muted" /> : <ChevronRight className="h-3.5 w-3.5 text-ep-muted" />
            ) : (
              <span className="w-3.5" />
            )}
            {fam.label}
            {!single && (
              <span className="font-mono text-[10px] font-normal text-ep-muted">
                {fam.variants.length}
              </span>
            )}
          </span>
        </td>
        {HIST_YEARS.map((y) => (
          <td key={y} className="font-mono py-[11px] px-4 text-right text-[var(--ep-text-secondary)]">
            {fam.repHist[y] != null ? fmtPercentile(fam.repHist[y]!, 2) : "—"}
          </td>
        ))}
        <td className="font-mono py-[11px] px-[22px] text-right font-semibold whitespace-nowrap" style={{ color: "var(--color-ep-primary)" }}>
          {fam.repPred ? predictedText(fam.repPred.pct, fam.repPred.low, fam.repPred.high) : "—"}
        </td>
      </tr>

      {isOpen &&
        !single &&
        fam.variants.map((v) => (
          <tr key={v.raw} className="border-t" style={{ borderColor: "var(--ep-border)", background: "var(--ep-bg)" }}>
            <td className="py-2 pl-[46px] pr-[22px]">
              <span className="flex items-center gap-2 text-[12.5px] text-[var(--ep-text-secondary)]">
                {v.label || v.raw}
                <span className="font-mono text-[10px] text-ep-muted">{v.raw}</span>
              </span>
            </td>
            {HIST_YEARS.map((y) => (
              <td key={y} className="font-mono py-2 px-4 text-right text-[var(--ep-text-secondary)]">
                {v.hist[y] != null ? fmtPercentile(v.hist[y], 2) : "—"}
              </td>
            ))}
            <td className="font-mono py-2 px-[22px] text-right whitespace-nowrap" style={{ color: "var(--color-ep-primary)" }}>
              {v.pred ? predictedText(v.pred.pct, v.pred.low, v.pred.high) : "—"}
            </td>
          </tr>
        ))}
    </>
  );
}

// ── Branch detail view ────────────────────────────────────────────────────────

function BranchView({ data }: { data: BranchDeepDive }) {
  // Rounds this branch actually has data for (cutoffs or predictions).
  const availableRounds = useMemo(() => {
    const rs = new Set<number>();
    for (const r of data.cutoff_trends) rs.add(r.round);
    for (const r of data.predictions_2026) rs.add(r.round);
    return [...rs].sort((a, b) => a - b);
  }, [data]);

  const [round, setRound] = useState<number>(availableRounds.includes(1) ? 1 : (availableRounds[0] ?? 1));

  const chartData = useMemo(() => buildChartData(data, round), [data, round]);
  const hasChartData = chartData.some((p) => p.close != null);
  const trend = computeTrend(chartData);

  const primaryPred = data.predictions_2026.find((p) => p.round === round && OPEN_CATS.has(p.category));

  // Actual latest-year (2025) open-category close for the selected round.
  const close2025 = useMemo(() => {
    let m: number | null = null;
    for (const r of data.cutoff_trends) {
      if (r.round !== round || r.year !== 2025 || !OPEN_CATS.has(r.category)) continue;
      if (m == null || r.percentile < m) m = r.percentile;
    }
    return m;
  }, [data, round]);

  const hasIntake = data.general_intake != null;

  const yMin = chartData.filter((p) => p.close != null).reduce((m, p) => Math.min(m, p.close!), Infinity) - 2;
  const yMax = chartData.filter((p) => p.close != null).reduce((m, p) => Math.max(m, p.close!), -Infinity) + 2;

  const TrendIcon = trend == null ? Minus : trend > 0 ? TrendingUp : trend < 0 ? TrendingDown : Minus;
  const trendColor = trend == null ? "var(--ep-text-secondary)" : trend > 0 ? "var(--color-ep-red)" : "var(--color-ep-green-ink)";

  return (
    <div className="space-y-6">
      <div>
        <div className="font-mono text-xs uppercase mb-2.5" style={{ letterSpacing: "0.14em", color: "var(--color-ep-green)" }}>
          Branch forecast
        </div>
        <h1 className="font-display text-[36px] leading-[1.1] text-[var(--ep-text)] mb-1.5">{data.branch_name}</h1>
        <Link href={`/colleges/${data.college_code}`} className="text-sm text-ep-muted hover:text-[var(--color-ep-primary)] transition-colors">
          {data.college_name} · Canonical {data.canonical_code}
        </Link>
      </div>

      {/* CAP round selector ─────────────────────────────────────────────────── */}
      {availableRounds.length > 1 && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-mono text-[11px] uppercase text-ep-muted" style={{ letterSpacing: "0.08em" }}>
            CAP Round
          </span>
          <div className="inline-flex rounded-[9px] border p-0.5" style={{ borderColor: "var(--ep-border)", background: "var(--ep-surface)" }}>
            {availableRounds.map((r) => (
              <button
                key={r}
                onClick={() => setRound(r)}
                className={cn(
                  "px-3.5 py-1.5 rounded-[7px] text-[13px] font-semibold font-mono transition-colors",
                  r === round ? "text-white" : "text-[var(--ep-text-secondary)] hover:bg-[var(--ep-bg)]"
                )}
                style={r === round ? { background: "var(--color-ep-primary)" } : undefined}
              >
                R{r}
              </button>
            ))}
          </div>
          <span className="text-[12px] text-ep-muted">
            Showing closing percentiles for CAP Round {round}
          </span>
        </div>
      )}

      {/* Summary strip ─────────────────────────────────────────────────────── */}
      <div className="rounded-[13px] border grid grid-cols-2 lg:grid-cols-4 overflow-hidden" style={{ background: "var(--ep-surface)", borderColor: "var(--ep-border)" }}>
        <div className="px-[22px] py-[18px] border-r border-b lg:border-b-0" style={{ borderColor: "var(--ep-border)" }}>
          <p className="font-mono text-[10px] uppercase mb-1.5" style={{ letterSpacing: "0.08em", color: "var(--color-ep-muted)" }}>
            2026 predicted close
          </p>
          <p className="font-mono text-[20px] font-semibold text-[var(--ep-text)]">
            {primaryPred ? predictedText(primaryPred.predicted_pct, primaryPred.predicted_low, primaryPred.predicted_high) : "—"}
          </p>
        </div>
        <div className="px-[22px] py-[18px] border-b lg:border-b-0 lg:border-r" style={{ borderColor: "var(--ep-border)" }}>
          <p className="font-mono text-[10px] uppercase mb-1.5" style={{ letterSpacing: "0.08em", color: "var(--color-ep-muted)" }}>
            2025 actual close
          </p>
          <p className="font-mono text-[20px] font-semibold text-[var(--ep-text)]">
            {close2025 != null ? fmtPercentile(close2025, 2) : "—"}
          </p>
        </div>
        <div className="px-[22px] py-[18px] border-r" style={{ borderColor: "var(--ep-border)" }}>
          <p className="font-mono text-[10px] uppercase mb-1.5" style={{ letterSpacing: "0.08em", color: "var(--color-ep-muted)" }}>
            Seat intake
          </p>
          {hasIntake ? (
            <p className="font-mono text-[20px] font-semibold text-[var(--ep-text)] flex items-baseline gap-1.5">
              <Armchair className="h-4 w-4 self-center text-ep-muted" />
              {data.tfws_intake != null ? `${data.general_intake} + ${data.tfws_intake}` : `${data.general_intake}`}
              {data.tfws_intake != null && <span className="text-[11px] font-sans text-ep-muted">gen + TFWS</span>}
            </p>
          ) : (
            <p className="text-[13px] text-ep-muted">Not available</p>
          )}
        </div>
        <div className="px-[22px] py-[18px]">
          <p className="font-mono text-[10px] uppercase mb-1.5" style={{ letterSpacing: "0.08em", color: "var(--color-ep-muted)" }}>
            3-yr trend · confidence
          </p>
          <div className="flex items-center gap-2.5">
            <span className="font-mono text-[20px] font-semibold flex items-center gap-1" style={{ color: trendColor }}>
              <TrendIcon className="h-[16px] w-[16px]" strokeWidth={1.8} />
              {trend == null ? "—" : `${trend > 0 ? "+" : ""}${trend.toFixed(1)}`}
            </span>
            {primaryPred ? (
              <Badge variant={primaryPred.confidence as "high" | "medium" | "low"}>{primaryPred.confidence}</Badge>
            ) : null}
          </div>
        </div>
      </div>

      {/* Cutoff trend chart ─────────────────────────────────────────────────── */}
      <div className="rounded-[13px] border overflow-hidden" style={{ background: "var(--ep-surface)", borderColor: "var(--ep-border)" }}>
        <div className="px-[22px] py-3.5 border-b" style={{ borderColor: "var(--ep-border)" }}>
          <h2 className="font-semibold text-[13px] text-[var(--ep-text)]">
            Round-{round} open-category closing percentile
          </h2>
        </div>
        <div className="px-[26px] pt-7 pb-5">
          {!hasChartData ? (
            <p className="text-sm text-ep-muted italic">No open-category data for CAP Round {round} at this branch.</p>
          ) : (
            <>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={chartData} margin={{ top: 20, right: 12, left: 0, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--ep-border)" vertical={false} />
                  <XAxis dataKey="year" tick={{ fontSize: 12, fill: "var(--color-ep-muted)", fontFamily: "var(--font-mono)" }} axisLine={false} tickLine={false} />
                  <YAxis
                    domain={[Math.max(0, Math.floor(yMin)), Math.min(100, Math.ceil(yMax))]}
                    tick={{ fontSize: 11, fill: "var(--color-ep-muted)", fontFamily: "var(--font-mono)" }}
                    axisLine={false}
                    tickLine={false}
                    width={38}
                  />
                  <Tooltip
                    contentStyle={{ background: "var(--ep-surface)", border: "1px solid var(--ep-border)", borderRadius: 8, fontSize: 12, fontFamily: "var(--font-mono)" }}
                    formatter={(value) => [typeof value === "number" ? value.toFixed(2) : value, "Closing %ile"]}
                    cursor={{ fill: "var(--ep-bg)", opacity: 0.5 }}
                  />
                  <Bar dataKey="close" radius={[4, 4, 0, 0]} maxBarSize={64}>
                    {chartData.map((entry, i) => (
                      <Cell key={i} fill={entry.predicted ? "var(--color-ep-primary)" : "var(--ep-border-strong)"} />
                    ))}
                    <LabelList
                      dataKey="close"
                      position="top"
                      formatter={(v: React.ReactNode) => (typeof v === "number" ? v.toFixed(2) : "")}
                      style={{ fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 600 }}
                      fill="var(--ep-text)"
                    />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <div className="flex items-center gap-[18px] mt-1.5 pl-2">
                <span className="inline-flex items-center gap-[7px] text-xs text-ep-muted">
                  <span className="h-[11px] w-[11px] rounded-[3px]" style={{ background: "var(--ep-border-strong)" }} />
                  Historical (actual)
                </span>
                <span className="inline-flex items-center gap-[7px] text-xs text-ep-muted">
                  <span className="h-[11px] w-[11px] rounded-[3px]" style={{ background: "var(--color-ep-primary)" }} />
                  2026 forecast
                </span>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Category tree ──────────────────────────────────────────────────────── */}
      <div className="rounded-[13px] border overflow-hidden" style={{ background: "var(--ep-surface)", borderColor: "var(--ep-border)" }}>
        <div className="px-[22px] py-3.5 border-b" style={{ borderColor: "var(--ep-border)" }}>
          <h2 className="font-semibold text-[13px] text-[var(--ep-text)]">
            Closing percentile by category · CAP Round {round}
          </h2>
        </div>
        <div className="pt-0">
          <CategoryTree data={data} round={round} />
        </div>
      </div>

      {/* Seat intake note ───────────────────────────────────────────────────── */}
      <div className="rounded-[10px] border px-4 py-3 text-xs text-ep-muted" style={{ background: "var(--ep-surface)", borderColor: "var(--ep-border)" }}>
        <p className="font-semibold text-[var(--ep-text-secondary)] mb-0.5">About seat intake</p>
        <p>
          {hasIntake
            ? "Sanctioned intake (general + TFWS) is the fixed institutional capacity from the official CET Cell CAP Round-I seat matrix; it does not change round to round."
            : "Sanctioned seat intake is not available in the current dataset for this branch — check the college's official prospectus or the CET Cell seat matrix."}
        </p>
      </div>
    </div>
  );
}

// ── Page shell ────────────────────────────────────────────────────────────────

export default function BranchPage() {
  const { canonicalCode: rawCanonicalCode } = useParams<{ canonicalCode: string }>();
  const router = useRouter();
  const canonicalCode = rawCanonicalCode ? decodeURIComponent(rawCanonicalCode) : rawCanonicalCode;

  const { data, isLoading, error } = useQuery({
    queryKey: ["branch", canonicalCode],
    queryFn: () => getBranchDeepDive(canonicalCode),
    enabled: !!canonicalCode,
    staleTime: 10 * 60 * 1000,
  });

  return (
    <div className="min-h-screen" style={{ background: "var(--ep-bg)" }}>
      <NavHeader />

      <main className="mx-auto max-w-3xl px-6 py-8">
        {!isLoading && (
          <button
            onClick={() => router.back()}
            className="inline-flex items-center gap-1.5 text-[13px] font-medium text-ep-muted hover:text-[var(--ep-text)] mb-4 transition-colors"
          >
            <ChevronLeft className="h-[15px] w-[15px]" />
            Back to college
          </button>
        )}

        {isLoading && (
          <div className="space-y-6">
            <Skeleton className="h-36 w-full" />
            <Skeleton className="h-64 w-full" />
            <Skeleton className="h-48 w-full" />
          </div>
        )}

        {error && (
          <div className="rounded-[10px] border px-5 py-4 text-sm flex items-start gap-3" style={{ borderColor: "var(--color-ep-red-border)", background: "var(--color-ep-red-tint)", color: "var(--color-ep-red-ink)" }}>
            <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">Could not load branch data</p>
              <p className="mt-0.5 opacity-80">{error instanceof Error ? error.message : "Unknown error"}</p>
            </div>
          </div>
        )}

        {data && <BranchView data={data} />}
      </main>
    </div>
  );
}
