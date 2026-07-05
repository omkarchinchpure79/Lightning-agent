"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Eye, EyeOff, ArrowRight } from "lucide-react";

import { authLogin, bulkAddToShortlist } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import { readLocalShortlist } from "@/lib/useShortlist";
import { ThemeToggle } from "@/components/ThemeToggle";
import { EduPathLogo } from "@/components/EduPathLogo";

const schema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});
type FormData = z.infer<typeof schema>;

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [showPw, setShowPw] = useState(false);
  const [mergeItems, setMergeItems] = useState<ReturnType<typeof readLocalShortlist> | null>(null);
  const [pendingAuth, setPendingAuth] = useState<{ token: string; counselor: { counselor_id: number; name: string; email: string } } | null>(null);
  const [merging, setMerging] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    setError,
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  async function onSubmit(data: FormData) {
    try {
      const res = await authLogin(data.email, data.password);
      const counselor = { counselor_id: res.counselor_id, name: res.name, email: res.email };

      // Check for pre-login shortlist items to merge
      const local = readLocalShortlist();
      if (local.length > 0) {
        setPendingAuth({ token: res.token, counselor });
        setMergeItems(local);
      } else {
        login(res.token, counselor);
        router.push("/");
      }
    } catch (e: unknown) {
      setError("root", { message: (e as Error).message ?? "Login failed" });
    }
  }

  async function handleMerge(save: boolean) {
    if (!pendingAuth) return;
    setMerging(true);
    try {
      if (save && mergeItems && mergeItems.length > 0) {
        // Temporarily set token so the bulk API call authenticates
        localStorage.setItem("edupath_token", pendingAuth.token);
        await bulkAddToShortlist(
          mergeItems.map((c) => ({
            college_code: c.code,
            college_name: c.name,
            city: c.city,
            score: c.score,
            institution_type: c.institution_type,
          }))
        );
      }
      // Clear localStorage shortlist either way
      localStorage.removeItem("edupath_shortlist_v1");
      login(pendingAuth.token, pendingAuth.counselor);
      router.push("/");
    } catch {
      setMerging(false);
    }
  }

  // ── Merge dialog ────────────────────────────────────────────────────────────
  if (mergeItems !== null) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--ep-bg)" }}>
        <div
          className="w-full max-w-md rounded-[16px] border border-[var(--ep-border)] p-8"
          style={{ background: "var(--ep-surface)" }}
        >
          <h2 className="font-display text-xl text-[var(--ep-text)] mb-2">
            Save your bookmarks?
          </h2>
          <p className="text-sm text-ep-muted mb-6">
            You have <strong>{mergeItems.length} college{mergeItems.length !== 1 ? "s" : ""}</strong> saved before logging in. Save them to your account?
          </p>
          <div className="flex gap-3">
            <button
              onClick={() => handleMerge(true)}
              disabled={merging}
              className="flex-1 py-2.5 rounded-[10px] text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
              style={{ background: "var(--color-ep-primary)" }}
            >
              {merging ? "Saving…" : "Yes, save them"}
            </button>
            <button
              onClick={() => handleMerge(false)}
              disabled={merging}
              className="flex-1 py-2.5 rounded-[10px] text-sm font-medium border border-[var(--ep-border-strong)] text-[var(--ep-text-secondary)] hover:bg-[var(--ep-bg)] transition-colors disabled:opacity-50"
            >
              Start fresh
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── Login form ──────────────────────────────────────────────────────────────
  return (
    <div
      className="relative min-h-screen flex flex-col items-center justify-center px-6 py-16 overflow-hidden"
      style={{ background: "var(--ep-bg)" }}
    >
      <svg
        viewBox="0 0 600 520"
        preserveAspectRatio="none"
        className="pointer-events-none absolute inset-0 h-full w-full"
        aria-hidden="true"
      >
        <path
          d="M-20 470 C 80 180, 360 120, 640 150"
          fill="none"
          stroke="#DED8CA"
          strokeWidth="2"
          strokeDasharray="2 9"
          strokeLinecap="round"
        />
      </svg>

      <div className="absolute top-6 right-6">
        <ThemeToggle />
      </div>

      <div className="relative w-full max-w-[460px] flex flex-col items-center mb-8">
        <EduPathLogo size={40} />
        <p
          className="font-mono mt-3 text-[11px] uppercase"
          style={{ letterSpacing: "0.14em", color: "#9A968B" }}
        >
          MHT CET Counsellor Portal
        </p>
      </div>

      <div
        className="relative w-full max-w-[460px] rounded-[16px] border p-[30px]"
        style={{ background: "var(--ep-surface)", borderColor: "var(--ep-border)" }}
      >
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-[var(--ep-text-secondary)] mb-1.5">
              Email
            </label>
            <input
              type="email"
              autoComplete="email"
              {...register("email")}
              className="w-full rounded-[10px] border px-4 py-3 text-sm text-[var(--ep-text)] outline-none focus:border-[var(--color-ep-primary)] transition-colors"
              style={{ background: "var(--ep-input)", borderColor: "var(--ep-border-strong)" }}
              placeholder="you@example.com"
            />
            {errors.email && (
              <p className="mt-1 text-xs text-[var(--color-ep-red)]">{errors.email.message}</p>
            )}
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="block text-xs font-medium text-[var(--ep-text-secondary)]">
                Password
              </label>
              <span className="text-xs font-medium cursor-default" style={{ color: "var(--color-ep-primary)" }}>
                Forgot?
              </span>
            </div>
            <div className="relative">
              <input
                type={showPw ? "text" : "password"}
                autoComplete="current-password"
                {...register("password")}
                className="w-full rounded-[10px] border px-4 py-3 pr-10 text-sm text-[var(--ep-text)] outline-none focus:border-[var(--color-ep-primary)] transition-colors"
                style={{ background: "var(--ep-input)", borderColor: "var(--ep-border-strong)" }}
                placeholder="••••••••"
              />
              <button
                type="button"
                onClick={() => setShowPw((p) => !p)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-ep-muted hover:text-[var(--ep-text)]"
                tabIndex={-1}
              >
                {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            {errors.password && (
              <p className="mt-1 text-xs text-[var(--color-ep-red)]">{errors.password.message}</p>
            )}
          </div>

          {errors.root && (
            <p
              className="text-xs rounded-[8px] px-3 py-2"
              style={{ color: "var(--color-ep-red-ink)", background: "#F8E1DF" }}
            >
              {errors.root.message}
            </p>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full flex items-center justify-center gap-2 py-3 rounded-[10px] text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50 mt-2"
            style={{ background: "var(--color-ep-primary)" }}
          >
            {isSubmitting ? "Logging in…" : "Log in"}
            <ArrowRight className="h-4 w-4" />
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-ep-muted">
          No account yet?{" "}
          <Link href="/signup" className="font-semibold hover:underline" style={{ color: "var(--color-ep-primary)" }}>
            Create one
          </Link>
        </p>
      </div>
    </div>
  );
}
