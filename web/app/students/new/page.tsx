import { NavHeader } from "@/components/NavHeader";
import { StudentForm } from "@/components/StudentForm";

export const metadata = { title: "New student — EduPath" };

export default function NewStudentPage() {
  return (
    <div className="min-h-screen" style={{ background: "var(--ep-bg)" }}>
      <NavHeader />
      <main className="mx-auto max-w-2xl px-6 py-8">
        <div className="mb-6">
          <h1 className="font-display text-[30px] text-[var(--ep-text)] mb-1">New student</h1>
          <p className="text-sm text-ep-muted">
            Fill in the details. After saving, predictions run automatically.
          </p>
        </div>
        <StudentForm />
      </main>
    </div>
  );
}
