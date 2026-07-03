"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ChevronLeft, AlertTriangle, TrendingUp, TrendingDown, Minus } from "lucide-react";
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
import { NavHeader } from "@/components/NavHeader";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

// ── Chart data helpers ────────────────────────────────────────────────────────

const OPEN_CATS = new Set(["GOPENH", "GOPENS", "GOPENO"]);

interface ChartPoint {
  year: string;
  close: number | null;
  predicted: boolean;
}

function buildChartData(data: BranchDeepDive): ChartPoint[] {
  // Collect round-1, open-category historical data → min percentile per year
  const histByYear: Record<number, number> = {};
  for (const row of data.cutoff_trends) {
    if (row.round !== 1 || !OPEN_CATS.has(row.category)) continue;
    if (histByYear[row.year] == null || row.percentile < histByYear[row.year]) {
      histByYear[row.year] = row.percentile;
    }
  }

  // Round-1 open-category 2026 prediction → min predicted_pct
  let pred2026: number | null = null;
  for (const row of data.predictions_2026) {
    if (row.round !== 1 || !OPEN_CATS.has(row.category)) continue;
    if (pred2026 == null || row.predicted_pct < pred2026) {
      pred2026 = row.predicted_pct;
    }
  }

  const points: ChartPoint[] = [];
  for (const yr of [2023, 2024, 2025]) {
    if (histByYear[yr] != null) {
      points.push({ year: String(yr), close: histByYear[yr], predicted: false });
    }
  }
  // Always append 2026 prediction if available
  points.push({ year: "2026*", close: pred2026, predicted: true });
  return points;
}

// The point estimate is at its accuracy ceiling (backtest MAE ~8 pts globally) —
// showing it to 2 decimals implies precision the model doesn't have. Show 1 decimal
// plus the calibrated likely range instead (roadmap C2), same convention as the
// results page's closeText().
function predictedText(pct: number, low: number | null, high: number | null): string {
  const point = pct.toFixed(1);
  if (low == null || high == null) return point;
  return `${point} (likely ${low.toFixed(0)}–${high.toFixed(0)})`;
}

/** 3-year trend: latest historical vs. earliest historical, in percentile points. */
function computeTrend(chartData: ChartPoint[]): number | null {
  const hist = chartData.filter((p) => !p.predicted && p.close != null);
  if (hist.length < 2) return null;
  const first = hist[0].close!;
  const last = hist[hist.length - 1].close!;
  return Math.round((last - first) * 100) / 100;
}

// ── Category breakdown table ──────────────────────────────────────────────────

function CategoryTable({ data }: { data: BranchDeepDive }) {
  // Group round-1 historical data by category
  const cats: Record<string, Record<number, number>> = {};
  for (const row of data.cutoff_trends) {
    if (row.round !== 1) continue;
    if (!cats[row.category]) cats[row.category] = {};
    cats[row.category][row.year] = row.percentile;
  }

  // Add 2026 predictions (round 1) per category
  const pred: Record<string, { pct: number; low: number | null; high: number | null }> = {};
  for (const row of data.predictions_2026) {
    if (row.round !== 1) continue;
    if (pred[row.category] == null || row.predicted_pct < pred[row.category].pct) {
      pred[row.category] = { pct: row.predicted_pct, low: row.predicted_low, high: row.predicted_high };
    }
  }

  const allCats = Array.from(new Set([...Object.keys(cats), ...Object.keys(pred)])).sort();
  if (allCats.length === 0) return null;

  const years = [2023, 2024, 2025];

  return (
    <div className="overflow-x-auto -mx-[22px] -mb-[14px]">
      <table className="w-full text-[13px] border-collapse">
        <thead>
          <tr className="text-left" style={{ background: "var(--ep-bg)" }}>
            <th
              className="font-mono py-2.5 px-[22px] font-semibold text-[11px] uppercase text-ep-muted"
              style={{ letterSpacing: "0.05em" }}
            >
              Category
            </th>
            {years.map((y) => (
              <th
                key={y}
                className="font-mono py-2.5 px-4 font-semibold text-[11px] uppercase text-ep-muted text-right"
                style={{ letterSpacing: "0.05em" }}
              >
                {y}
              </th>
            ))}
            <th
              className="font-mono py-2.5 px-[22px] font-semibold text-[11px] uppercase text-right"
              style={{ letterSpacing: "0.05em", color: "var(--color-ep-primary)" }}
            >
              2026*
            </th>
          </tr>
        </thead>
        <tbody>
          {allCats.map((cat) => (
            <tr key={cat} className="border-t hover:bg-[var(--ep-bg)] transition-colors" style={{ borderColor: "#EEEAE0" }}>
              <td className="py-[11px] px-[22px] font-medium text-[13px] text-[var(--ep-text)]">{cat}</td>
              {years.map((y) => (
                <td key={y} className="font-mono py-[11px] px-4 text-right text-[var(--ep-text-secondary)]">
                  {cats[cat]?.[y] != null ? cats[cat][y].toFixed(2) : "—"}
                </td>
              ))}
              <td
                className="font-mono py-[11px] px-[22px] text-right font-semibold whitespace-nowrap"
                style={{ color: "var(--color-ep-primary)" }}
              >
                {pred[cat] != null ? predictedText(pred[cat].pct, pred[cat].low, pred[cat].high) : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="px-[22px] pt-3 pb-[14px] text-[11px] text-ep-muted border-t" style={{ borderColor: "var(--ep-border)" }}>
        * 2026 values are model forecasts based on 2023–2025 CAP data. Verify against official rounds before advising.
      </p>
    </div>
  );
}

// ── Branch detail view ────────────────────────────────────────────────────────

function BranchView({ data }: { data: BranchDeepDive }) {
  const chartData = buildChartData(data);
  const hasChartData = chartData.some((p) => p.close != null);
  const trend = computeTrend(chartData);

  // confidence for the round-1 open category prediction
  const primaryPred = data.predictions_2026.find(
    (p) => p.round === 1 && OPEN_CATS.has(p.category)
  );

  const yMin =
    chartData
      .filter((p) => p.close != null)
      .reduce((m, p) => Math.min(m, p.close!), Infinity) - 2;
  const yMax =
    chartData
      .filter((p) => p.close != null)
      .reduce((m, p) => Math.max(m, p.close!), -Infinity) + 2;

  const TrendIcon = trend == null ? Minus : trend > 0 ? TrendingUp : trend < 0 ? TrendingDown : Minus;
  const trendColor = trend == null ? "var(--ep-text-secondary)" : trend > 0 ? "var(--color-ep-red)" : "var(--color-ep-green-ink)";

  return (
    <div className="space-y-6">
      <div>
        <div
          className="font-mono text-xs uppercase mb-2.5"
          style={{ letterSpacing: "0.14em", color: "var(--color-ep-green)" }}
        >
          Branch forecast
        </div>
        <h1 className="font-display text-[36px] leading-[1.1] text-[var(--ep-text)] mb-1.5">
          {data.branch_name}
        </h1>
        <Link
          href={`/colleges/${data.college_code}`}
          className="text-sm text-ep-muted hover:text-[var(--color-ep-primary)] transition-colors"
        >
          {data.college_name} · Canonical {data.canonical_code}
        </Link>
      </div>

      {/* Summary strip ────────────────────────────────────────────────────────── */}
      <div
        className="rounded-[13px] border grid grid-cols-1 sm:grid-cols-3 overflow-hidden"
        style={{ background: "var(--ep-surface)", borderColor: "var(--ep-border)" }}
      >
        <div className="px-[22px] py-[18px] border-r sm:border-b-0 border-b" style={{ borderColor: "var(--ep-border)" }}>
          <p className="font-mono text-[10px] uppercase mb-1.5" style={{ letterSpacing: "0.08em", color: "#9A968B" }}>
            2026 predicted close
          </p>
          <p className="font-mono text-[22px] font-semibold text-[var(--ep-text)]">
            {primaryPred
              ? predictedText(primaryPred.predicted_pct, primaryPred.predicted_low, primaryPred.predicted_high)
              : "—"}
          </p>
        </div>
        <div className="px-[22px] py-[18px] border-r sm:border-b-0 border-b" style={{ borderColor: "var(--ep-border)" }}>
          <p className="font-mono text-[10px] uppercase mb-1.5" style={{ letterSpacing: "0.08em", color: "#9A968B" }}>
            3-yr trend
          </p>
          <div className="font-mono text-[26px] font-semibold flex items-center gap-1.5" style={{ color: trendColor }}>
            <TrendIcon className="h-[18px] w-[18px]" strokeWidth={1.8} />
            {trend == null ? "—" : `${trend > 0 ? "+" : ""}${trend.toFixed(1)}`}
          </div>
        </div>
        <div className="px-[22px] py-[18px]">
          <p className="font-mono text-[10px] uppercase mb-1.5" style={{ letterSpacing: "0.08em", color: "#9A968B" }}>
            Confidence
          </p>
          {primaryPred ? (
            <Badge
              variant={primaryPred.confidence as "high" | "medium" | "low"}
              className="cursor-help"
              title={
                primaryPred.predicted_low != null && primaryPred.predicted_high != null
                  ? `Branches like this have historically moved up to ±${Math.round(
                      (primaryPred.predicted_high - primaryPred.predicted_low) / 2
                    )} pts year-to-year.`
                  : undefined
              }
            >
              {primaryPred.confidence}
            </Badge>
          ) : (
            <span className="text-ep-muted text-sm">—</span>
          )}
        </div>
      </div>

      {/* Cutoff trend chart ───────────────────────────────────────────────────── */}
      <div
        className="rounded-[13px] border overflow-hidden"
        style={{ background: "var(--ep-surface)", borderColor: "var(--ep-border)" }}
      >
        <div className="px-[22px] py-3.5 border-b" style={{ borderColor: "var(--ep-border)" }}>
          <h2 className="font-semibold text-[13px] text-[var(--ep-text)]">
            Round-1 open-category closing percentile
          </h2>
        </div>
        <div className="px-[26px] pt-7 pb-5">
          {!hasChartData ? (
            <p className="text-sm text-ep-muted italic">
              No open-category round-1 data available for this branch.
            </p>
          ) : (
            <>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart
                  data={chartData}
                  margin={{ top: 20, right: 12, left: 0, bottom: 4 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#EEEAE0" vertical={false} />
                  <XAxis
                    dataKey="year"
                    tick={{ fontSize: 12, fill: "#8A867B", fontFamily: "var(--font-mono)" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    domain={[Math.max(0, Math.floor(yMin)), Math.min(100, Math.ceil(yMax))]}
                    tick={{ fontSize: 11, fill: "#9A968B", fontFamily: "var(--font-mono)" }}
                    axisLine={false}
                    tickLine={false}
                    width={38}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "var(--ep-surface)",
                      border: "1px solid var(--ep-border)",
                      borderRadius: 8,
                      fontSize: 12,
                      fontFamily: "var(--font-mono)",
                    }}
                    formatter={(value) => [typeof value === "number" ? value.toFixed(2) : value, "Closing %ile"]}
                    cursor={{ fill: "var(--ep-bg)", opacity: 0.5 }}
                  />
                  <Bar dataKey="close" radius={[4, 4, 0, 0]} maxBarSize={64}>
                    {chartData.map((entry, i) => (
                      <Cell key={i} fill={entry.predicted ? "#1E4D8C" : "#C6D2DF"} />
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
                  <span className="h-[11px] w-[11px] rounded-[3px]" style={{ background: "#C6D2DF" }} />
                  Historical (actual)
                </span>
                <span className="inline-flex items-center gap-[7px] text-xs text-ep-muted">
                  <span className="h-[11px] w-[11px] rounded-[3px]" style={{ background: "#1E4D8C" }} />
                  2026 forecast
                </span>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Category breakdown table ─────────────────────────────────────────────── */}
      <div
        className="rounded-[13px] border overflow-hidden"
        style={{ background: "var(--ep-surface)", borderColor: "var(--ep-border)" }}
      >
        <div className="px-[22px] py-3.5 border-b" style={{ borderColor: "var(--ep-border)" }}>
          <h2 className="font-semibold text-[13px] text-[var(--ep-text)]">
            Closing percentile by category · Round 1
          </h2>
        </div>
        <div className="pt-0">
          {data.cutoff_trends.length === 0 && data.predictions_2026.length === 0 ? (
            <p className="text-sm text-ep-muted italic p-5">
              No category data available for this branch.
            </p>
          ) : (
            <CategoryTable data={data} />
          )}
        </div>
      </div>

      {/* Seat matrix gap note ────────────────────────────────────────────────── */}
      <div
        className="rounded-[10px] border px-4 py-3 text-xs text-ep-muted"
        style={{ background: "var(--ep-surface)", borderColor: "var(--ep-border)" }}
      >
        <p className="font-semibold text-[var(--ep-text-secondary)] mb-0.5">Seat intake by round</p>
        <p>
          Intake data (number of seats per round) is not available in the current dataset — the
          engine uses cutoff percentiles only. Check the college&apos;s official prospectus for
          seat matrix details.
        </p>
      </div>
    </div>
  );
}

// ── Page shell ────────────────────────────────────────────────────────────────

export default function BranchPage() {
  const { canonicalCode: rawCanonicalCode } = useParams<{ canonicalCode: string }>();
  const router = useRouter();
  // Route params arrive still URL-encoded (e.g. "CODE%3A%3A3036511") — decode once
  // here so getBranchDeepDive's encodeURIComponent() doesn't double-encode it.
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
          <div
            className="rounded-[10px] border px-5 py-4 text-sm flex items-start gap-3"
            style={{ borderColor: "#E8BFBD", background: "#F8E7E5", color: "var(--color-ep-red-ink)" }}
          >
            <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">Could not load branch data</p>
              <p className="mt-0.5 opacity-80">
                {error instanceof Error ? error.message : "Unknown error"}
              </p>
            </div>
          </div>
        )}

        {data && <BranchView data={data} />}
      </main>
    </div>
  );
}
