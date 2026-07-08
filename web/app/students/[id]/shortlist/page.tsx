"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Reorder, useDragControls } from "framer-motion";
import { Trash2, ArrowLeft, Printer, GripVertical, ArrowUpDown } from "lucide-react";

import { getStudent, getShortlist, saveShortlist, type ShortlistItem } from "@/lib/api";
import { NavHeader } from "@/components/NavHeader";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { fmtPercentile, cn } from "@/lib/utils";

const BAND_COLOR: Record<string, string> = { SAFE: "safe", PROBABLE: "probable", REACH: "reach" };
const BAND_RANK: Record<string, number> = { SAFE: 0, PROBABLE: 1, REACH: 2 };

// Stable per-entry identity: a TFWS entry shares canonical_code with the general
// seat, so include seat_pool (and category) so reorder keys and removal target
// exactly one entry.
function itemKey(item: ShortlistItem): string {
  return `${item.canonical_code}__${item.seat_pool ?? "gen"}__${item.category_used ?? ""}`;
}

// Official CET Cell CAP option-form seat-type abbreviations (SL/HU/OHU — see
// the government portal's own "Choice Code" preview table). A reserved-pool
// entry (TFWS etc.) is its own quota, not an H/O/S split, so it's labelled by
// pool name instead.
const SEAT_TYPE_ABBR: Record<string, string> = { Home: "HU", Other: "OHU", State: "SL" };
function officialSeatLabel(item: ShortlistItem): string {
  if (item.seat_pool) return item.seat_pool;
  if (item.seat_type && SEAT_TYPE_ABBR[item.seat_type]) return SEAT_TYPE_ABBR[item.seat_type];
  return item.seat_type ?? "—";
}

type SortKey = "manual" | "percentile" | "score" | "band";

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: "manual", label: "Manual (drag to rank)" },
  { key: "percentile", label: "Predicted percentile" },
  { key: "score", label: "College score" },
  { key: "band", label: "Safety (Safe first)" },
];

function sortItems(items: ShortlistItem[], key: SortKey): ShortlistItem[] {
  const arr = [...items];
  switch (key) {
    case "percentile":
      return arr.sort((a, b) => (b.predicted_close ?? -1) - (a.predicted_close ?? -1));
    case "score":
      return arr.sort((a, b) => (b.college_score ?? -1) - (a.college_score ?? -1));
    case "band":
      return arr.sort(
        (a, b) =>
          (BAND_RANK[a.band ?? ""] ?? 9) - (BAND_RANK[b.band ?? ""] ?? 9) ||
          (b.predicted_close ?? -1) - (a.predicted_close ?? -1)
      );
    default:
      return arr;
  }
}

export default function ShortlistPage() {
  const { id } = useParams<{ id: string }>();
  const studentId = Number(id);
  const queryClient = useQueryClient();

  const { data: student } = useQuery({
    queryKey: ["student", studentId],
    queryFn: () => getStudent(studentId),
    enabled: !isNaN(studentId),
  });

  const { data: shortlist, isLoading } = useQuery({
    queryKey: ["shortlist", studentId],
    queryFn: () => getShortlist(studentId),
    enabled: !isNaN(studentId),
  });

  const { mutate: mutateShortlist, isPending: saving } = useMutation({
    mutationFn: (items: ShortlistItem[]) => saveShortlist(studentId, items),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["shortlist", studentId] }),
  });

  // Local order the counsellor manipulates by drag/sort; synced from the server
  // copy whenever it changes. The server stores order by insertion, so saving
  // the reordered array persists the ranking.
  const [items, setItems] = useState<ShortlistItem[]>([]);
  const [sortKey, setSortKey] = useState<SortKey>("manual");
  useEffect(() => {
    if (shortlist?.items) setItems(shortlist.items);
  }, [shortlist]);

  function persist(next: ShortlistItem[]) {
    setItems(next);
    mutateShortlist(next);
  }

  function applySort(key: SortKey) {
    setSortKey(key);
    if (key !== "manual") persist(sortItems(items, key));
  }

  function removeItem(item: ShortlistItem) {
    persist(items.filter((i) => itemKey(i) !== itemKey(item)));
  }

  const hasItems = items.length > 0;

  return (
    <div className="min-h-screen" style={{ background: "var(--ep-bg)" }}>
      <div className="print:hidden">
        <NavHeader
          right={
            <Link
              href={`/students/${studentId}/results`}
              className="flex items-center gap-1.5 text-sm text-ep-muted hover:text-[var(--ep-text)] transition-colors"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to predictions
            </Link>
          }
        />
      </div>

      <main className="mx-auto max-w-3xl px-6 py-8 print:max-w-none print:px-0 print:py-0">
        {/* Print-only output — mirrors the official CET Cell CAP "Choice Code"
            option-form table (Preference No. / Institute Code / Institute Name /
            University Name / SL-HU-OHU / Course Name / Choice Code) so a
            student can copy these rows straight into the CAP portal. */}
        <div className="hidden print:block mb-4">
          <h1 className="text-lg font-semibold">
            {student ? `${student.name} — CAP Option Form Reference` : "CAP Option Form Reference"}
          </h1>
          {student && (
            <p className="text-xs mt-1">
              {student.admission_type === "dse"
                ? `${student.percentile}% diploma (DSE)`
                : `${student.percentile} percentile`}
              {" · "}{student.category_base}
              {student.home_district ? ` · ${student.home_district}` : ""}
            </p>
          )}
          <p className="text-[10px] mt-1 text-gray-600">
            Generated by EduPath — verify every code against the official CET Cell portal before submitting.
          </p>
        </div>
        <ChoiceCodeTable items={items} />

        <div className="mb-6 flex items-end justify-between gap-4 flex-wrap print:hidden">
          <div>
            <h1 className="font-display text-[28px] text-[var(--ep-text)] mb-0.5">Shortlist</h1>
            {student && (
              <p className="font-mono text-xs text-ep-muted">
                {student.name} · {items.length} saved options
              </p>
            )}
          </div>

          {hasItems && (
            <div className="flex items-center gap-2 flex-wrap">
              {/* Sort */}
              <div className="inline-flex items-center gap-1.5 rounded-[9px] border px-2.5 py-1.5" style={{ borderColor: "var(--ep-border)", background: "var(--ep-surface)" }}>
                <ArrowUpDown className="h-3.5 w-3.5 text-ep-muted" />
                <select
                  value={sortKey}
                  onChange={(e) => applySort(e.target.value as SortKey)}
                  className="bg-transparent text-[13px] font-medium text-[var(--ep-text)] outline-none cursor-pointer"
                >
                  {SORT_OPTIONS.map((o) => (
                    <option key={o.key} value={o.key}>{o.label}</option>
                  ))}
                </select>
              </div>
              <Button variant="outline" size="sm" onClick={() => window.print()}>
                <Printer className="h-3.5 w-3.5" />
                Print
              </Button>
            </div>
          )}
        </div>

        {saving && (
          <p className="text-[11px] text-ep-muted mb-2 print:hidden">Saving order…</p>
        )}
        {sortKey === "manual" && hasItems && (
          <p className="text-[11px] text-ep-muted mb-3 print:hidden">
            Drag rows by the handle to set the preference order — it saves automatically.
          </p>
        )}

        {isLoading && (
          <div className="space-y-3">
            {[...Array(5)].map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        )}

        {!isLoading && !hasItems && (
          <div className="text-center py-16 text-ep-muted">
            <p className="text-base font-semibold">No saved options yet</p>
            <p className="mt-1 text-sm">
              Go to predictions and click &quot;Add&quot; on colleges you want to save.
            </p>
            <div className="mt-4">
              <Link href={`/students/${studentId}/results`}>
                <Button variant="outline">View predictions</Button>
              </Link>
            </div>
          </div>
        )}

        {hasItems && (
          <Reorder.Group
            axis="y"
            values={items}
            onReorder={(next) => {
              setItems(next);
              setSortKey("manual");
            }}
            className="space-y-[9px] print:hidden"
          >
            {items.map((item, i) => (
              <ShortlistRow
                key={itemKey(item)}
                item={item}
                index={i}
                dragDisabled={sortKey !== "manual"}
                onRemove={() => removeItem(item)}
                onCommitOrder={() => mutateShortlist(items)}
                saving={saving}
              />
            ))}
          </Reorder.Group>
        )}
      </main>
    </div>
  );
}

function ShortlistRow({
  item,
  index,
  dragDisabled,
  onRemove,
  onCommitOrder,
  saving,
}: {
  item: ShortlistItem;
  index: number;
  dragDisabled: boolean;
  onRemove: () => void;
  onCommitOrder: () => void;
  saving: boolean;
}) {
  const controls = useDragControls();
  return (
    <Reorder.Item
      value={item}
      dragListener={false}
      dragControls={controls}
      onDragEnd={onCommitOrder}
      className="rounded-[11px] border flex items-center gap-[11px] px-4 py-[13px] print:break-inside-avoid"
      style={{ background: "var(--ep-surface)", borderColor: "var(--ep-border)" }}
    >
      {!dragDisabled && (
        <button
          onPointerDown={(e) => controls.start(e)}
          className="cursor-grab active:cursor-grabbing touch-none text-ep-muted hover:text-[var(--ep-text)] print:hidden"
          aria-label="Drag to reorder"
        >
          <GripVertical className="h-4 w-4" />
        </button>
      )}
      <span className="font-display text-base w-5 shrink-0 text-center" style={{ color: "#B7B1A2" }}>
        {index + 1}
      </span>
      <div className="flex-1 min-w-0">
        <p className="font-serif text-sm font-medium text-[var(--ep-text)] truncate">
          {item.college_name ?? item.canonical_code}
        </p>
        <p className="text-[11px] text-ep-muted truncate">
          {item.branch_name}
          {item.seat_type && ` · ${item.seat_type}`}
          {item.branch_code && ` · Code ${item.branch_code}`}
          {item.fee_text && ` · ${item.fee_text}`}
        </p>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {item.seat_pool && (
          <Badge variant="default" className="text-[9.5px] px-[7px] py-[2px]">
            {item.seat_pool}
          </Badge>
        )}
        {item.college_score != null && (
          <span className="font-mono text-[11px] text-ep-muted" title="College score">
            {item.college_score}/100
          </span>
        )}
        {item.band && (
          <Badge variant={(BAND_COLOR[item.band] ?? "muted") as "safe" | "probable" | "reach" | "muted"}>
            {item.band.charAt(0) + item.band.slice(1).toLowerCase()}
          </Badge>
        )}
        {item.predicted_close != null && (
          <span className="font-mono text-xs text-ep-muted">{fmtPercentile(item.predicted_close)}</span>
        )}
        <Button
          size="icon"
          variant="ghost"
          onClick={onRemove}
          disabled={saving}
          aria-label="Remove from shortlist"
          className="print:hidden"
        >
          <Trash2 className="h-4 w-4" style={{ color: "var(--color-ep-red)" }} />
        </Button>
      </div>
    </Reorder.Item>
  );
}

// Print-only table mirroring the official CET Cell CAP "Choice Code" preview
// page's column set and order exactly, so a student can transcribe rows
// straight into the government portal. institute_code/choice_code/
// university_name are computed fresh server-side on every fetch (never a
// stale client snapshot) — see api/routes/students.py::_attach_university_names.
function ChoiceCodeTable({ items }: { items: ShortlistItem[] }) {
  if (items.length === 0) return null;
  return (
    <table className="hidden print:table w-full border-collapse text-[10px]">
      <thead>
        <tr>
          {["Pref. No.", "Institute Code", "Institute Name", "University Name", "SL/HU/OHU", "Course Name", "Choice Code"].map(
            (h) => (
              <th key={h} className="border border-gray-400 px-1.5 py-1 text-left font-semibold bg-gray-100">
                {h}
              </th>
            )
          )}
        </tr>
      </thead>
      <tbody>
        {items.map((item, i) => (
          <tr key={itemKey(item)} className="print:break-inside-avoid">
            <td className="border border-gray-400 px-1.5 py-1 text-center">{i + 1}</td>
            <td className="border border-gray-400 px-1.5 py-1 font-mono">{item.institute_code ?? "—"}</td>
            <td className="border border-gray-400 px-1.5 py-1">{item.college_name ?? "—"}</td>
            <td className="border border-gray-400 px-1.5 py-1">{item.university_name ?? "—"}</td>
            <td className="border border-gray-400 px-1.5 py-1 text-center">{officialSeatLabel(item)}</td>
            <td className="border border-gray-400 px-1.5 py-1">{item.branch_name ?? "—"}</td>
            <td className="border border-gray-400 px-1.5 py-1 font-mono">{item.choice_code ?? "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
