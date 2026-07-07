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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";

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
      <div className="min-h-screen flex items-center justify-center px-6" style={{ background: "var(--ep-bg)" }}>
        <div
          className="w-full max-w-md rounded-[22px] border p-8 shadow-[0_20px_50px_-24px_rgba(36,28,21,0.25)]"
          style={{ background: "var(--ep-surface)", borderColor: "var(--ep-border)" }}
        >
          <h2 className="font-display text-xl text-[var(--ep-text)] mb-2">
            Save your bookmarks?
          </h2>
          <p className="text-sm text-ep-muted mb-6">
            You have <strong>{mergeItems.length} college{mergeItems.length !== 1 ? "s" : ""}</strong> saved before logging in. Save them to your account?
          </p>
          <div className="flex gap-3">
            <Button onClick={() => handleMerge(true)} disabled={merging} className="flex-1">
              {merging ? "Saving…" : "Yes, save them"}
            </Button>
            <Button onClick={() => handleMerge(false)} disabled={merging} variant="outline" className="flex-1">
              Start fresh
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // ── Login — split panel: trust/context left, focused task right ─────────────
  // A counselor logging in mid-call needs speed + zero doubt they're in the
  // right place. Left panel carries the brand + the "why trust this" signal;
  // it never competes with the form for attention.
  return (
    <div className="min-h-screen flex" style={{ background: "var(--ep-bg)" }}>
      {/* Trust panel */}
      <div
        className="hidden lg:flex lg:w-[46%] relative overflow-hidden flex-col justify-between p-12"
        style={{ background: "#0F2A21" }}
      >
        <svg
          viewBox="0 0 600 800"
          preserveAspectRatio="none"
          className="pointer-events-none absolute inset-0 h-full w-full opacity-40"
          aria-hidden="true"
        >
          <path
            d="M-20 700 C 120 380, 360 260, 620 300"
            fill="none"
            stroke="#3C5A4C"
            strokeWidth="2"
            strokeDasharray="2 9"
            strokeLinecap="round"
          />
        </svg>

        <EduPathLogo size={32} />

        <div className="relative">
          <div
            className="font-mono text-xs uppercase mb-4 flex items-center gap-2"
            style={{ letterSpacing: "0.18em", color: "#8FBFA3" }}
          >
            <span className="h-1.5 w-1.5 rounded-full" style={{ background: "var(--color-ep-green)" }} />
            MHT CET Counsellor Portal
          </div>
          <h1 className="font-display text-[38px] leading-[1.08] mb-4" style={{ color: "#F6F1E7" }}>
            Every seat allotment,<br />
            <span className="italic" style={{ color: "var(--color-ep-amber)" }}>backed by data.</span>
          </h1>
          <p className="text-[15px] leading-relaxed max-w-sm" style={{ color: "#B8C7BE" }}>
            Sign in to pick up your students right where you left off — predictions, shortlists, and CAP strategy in one place.
          </p>
        </div>

        <div className="relative flex items-center gap-6 text-[13px]" style={{ color: "#8FA895" }}>
          <span><b className="font-mono text-[15px] font-semibold" style={{ color: "#F6F1E7" }}>408</b> colleges</span>
          <span style={{ color: "#3C5A4C" }}>·</span>
          <span><b className="font-mono text-[15px] font-semibold" style={{ color: "#F6F1E7" }}>3 yrs</b> cutoff data</span>
        </div>
      </div>

      {/* Form panel */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 py-16 relative">
        <div className="absolute top-6 right-6">
          <ThemeToggle />
        </div>

        <div className="w-full max-w-[380px]">
          <div className="lg:hidden flex flex-col items-center mb-8">
            <EduPathLogo size={36} />
          </div>

          <h2 className="font-display text-2xl text-[var(--ep-text)] mb-1">Welcome back</h2>
          <p className="text-sm text-ep-muted mb-7">Log in to your counsellor account.</p>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                {...register("email")}
                placeholder="you@example.com"
              />
              {errors.email && (
                <p className="text-xs text-[var(--color-ep-red)]">{errors.email.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label htmlFor="password">Password</Label>
                <span className="text-xs font-medium cursor-default" style={{ color: "var(--color-ep-primary)" }}>
                  Forgot?
                </span>
              </div>
              <div className="relative">
                <Input
                  id="password"
                  type={showPw ? "text" : "password"}
                  autoComplete="current-password"
                  {...register("password")}
                  placeholder="••••••••"
                  className="pr-10"
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
                <p className="text-xs text-[var(--color-ep-red)]">{errors.password.message}</p>
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

            <Button type="submit" disabled={isSubmitting} className="w-full mt-2">
              {isSubmitting ? "Logging in…" : "Log in"}
              <ArrowRight className="h-4 w-4" />
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-ep-muted">
            No account yet?{" "}
            <Link href="/signup" className="font-semibold hover:underline" style={{ color: "var(--color-ep-primary)" }}>
              Create one
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
