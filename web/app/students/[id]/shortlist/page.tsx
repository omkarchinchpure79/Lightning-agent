"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Trash2, ArrowLeft } from "lucide-react";

import { getStudent, getShortlist, saveShortlist, type ShortlistItem } from "@/lib/api";
import { NavHeader } from "@/components/NavHeader";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

const BAND_COLOR: Record<string, string> = {
  SAFE: "safe",
  PROBABLE: "probable",
  REACH: "reach",
};

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

  function removeItem(canonicalCode: string) {
    const remaining = (shortlist?.items ?? []).filter(
      (i) => i.canonical_code !== canonicalCode
    );
    mutateShortlist(remaining);
  }

  return (
    <div className="min-h-screen" style={{ background: "var(--ep-bg)" }}>
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

      <main className="mx-auto max-w-3xl px-6 py-8">
        <div className="mb-6 flex items-end justify-between gap-4 flex-wrap">
          <div>
            <h1 className="font-display text-[28px] text-[var(--ep-text)] mb-0.5">Shortlist</h1>
            {student && (
              <p className="font-mono text-xs text-ep-muted">
                {student.name} · {shortlist?.items.length ?? 0} saved options
              </p>
            )}
          </div>
        </div>

        {isLoading && (
          <div className="space-y-3">
            {[...Array(5)].map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        )}

        {!isLoading && (shortlist?.items ?? []).length === 0 && (
          <div className="text-center py-16 text-ep-muted">
            <p className="text-base font-semibold">No saved options yet</p>
            <p className="mt-1 text-sm">
              Go to predictions and click &quot;Add to shortlist&quot; on colleges you want to
              save.
            </p>
            <div className="mt-4">
              <Link href={`/students/${studentId}/results`}>
                <Button variant="outline">View predictions</Button>
              </Link>
            </div>
          </div>
        )}

        {shortlist && shortlist.items.length > 0 && (
          <div className="space-y-[9px]">
            {shortlist.items.map((item, i) => (
              <div
                key={item.canonical_code}
                className="rounded-[11px] border flex items-center gap-[13px] px-4 py-[13px]"
                style={{ background: "var(--ep-surface)", borderColor: "var(--ep-border)" }}
              >
                <span className="font-display text-base w-5 shrink-0" style={{ color: "#B7B1A2" }}>
                  {i + 1}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="font-serif text-sm font-medium text-[var(--ep-text)] truncate">
                    {item.college_name ?? item.canonical_code}
                  </p>
                  <p className="text-[11px] text-ep-muted truncate">
                    {item.branch_name}
                    {item.seat_type && ` · ${item.seat_type}`}
                    {item.fee_text && ` · ${item.fee_text}`}
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {item.band && (
                    <Badge
                      variant={
                        (BAND_COLOR[item.band] ?? "muted") as
                          | "safe"
                          | "probable"
                          | "reach"
                          | "muted"
                      }
                    >
                      {item.band.charAt(0) + item.band.slice(1).toLowerCase()}
                    </Badge>
                  )}
                  {item.predicted_close != null && (
                    <span className="font-mono text-xs text-ep-muted">
                      {item.predicted_close.toFixed(1)}
                    </span>
                  )}
                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={() => removeItem(item.canonical_code)}
                    disabled={saving}
                    aria-label="Remove from shortlist"
                  >
                    <Trash2 className="h-4 w-4" style={{ color: "var(--color-ep-red)" }} />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
