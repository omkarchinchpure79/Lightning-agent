"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ChevronLeft } from "lucide-react";

import { getStudent } from "@/lib/api";
import { NavHeader } from "@/components/NavHeader";
import { StudentForm } from "@/components/StudentForm";
import { Skeleton } from "@/components/ui/skeleton";

export default function EditStudentPage() {
  const { id } = useParams<{ id: string }>();
  const studentId = Number(id);

  const { data: student, isLoading, error } = useQuery({
    queryKey: ["student", studentId],
    queryFn: () => getStudent(studentId),
    enabled: !isNaN(studentId),
  });

  return (
    <div className="min-h-screen" style={{ background: "var(--ep-bg)" }}>
      <NavHeader
        right={
          <Link
            href={`/students/${studentId}/results`}
            className="flex items-center gap-1 text-sm text-ep-muted hover:text-[var(--ep-text)] transition-colors"
          >
            <ChevronLeft className="h-4 w-4" />
            Back to results
          </Link>
        }
      />

      <main className="mx-auto max-w-2xl px-6 py-8">
        <div className="mb-6">
          <h1 className="font-display text-[30px] text-[var(--ep-text)] mb-1">Edit student</h1>
          {student && (
            <p className="text-sm text-ep-muted">Editing profile for {student.name}</p>
          )}
        </div>

        {isLoading && (
          <div className="space-y-4">
            {[...Array(4)].map((_, i) => (
              <Skeleton key={i} className="h-32 w-full" />
            ))}
          </div>
        )}

        {error && (
          <div
            className="rounded-[8px] border px-4 py-3 text-sm"
            style={{ borderColor: "var(--color-ep-red-border)", background: "var(--color-ep-red-tint)", color: "var(--color-ep-red-ink)" }}
          >
            Failed to load student.{" "}
            {error instanceof Error ? error.message : "Unknown error."}
          </div>
        )}

        {student && <StudentForm student={student} />}
      </main>
    </div>
  );
}
