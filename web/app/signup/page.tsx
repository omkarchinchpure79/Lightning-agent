"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Eye, EyeOff, Plus } from "lucide-react";

import { authSignup } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import { ThemeToggle } from "@/components/ThemeToggle";
import { EduPathLogo } from "@/components/EduPathLogo";

const schema = z.object({
  name: z.string().min(2, "Name must be at least 2 characters"),
  email: z.string().email("Enter a valid email"),
  password: z.string().min(8, "Password must be at least 8 characters"),
  confirmPassword: z.string(),
}).refine((d) => d.password === d.confirmPassword, {
  message: "Passwords don't match",
  path: ["confirmPassword"],
});
type FormData = z.infer<typeof schema>;

export default function SignupPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [showPw, setShowPw] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    setError,
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  async function onSubmit(data: FormData) {
    try {
      const res = await authSignup(data.name, data.email, data.password);
      login(res.token, { counselor_id: res.counselor_id, name: res.name, email: res.email });
      router.push("/");
    } catch (e: unknown) {
      setError("root", { message: (e as Error).message ?? "Signup failed" });
    }
  }

  return (
    <div
      className="relative min-h-screen flex flex-col items-center justify-center px-6 py-16 overflow-hidden"
      style={{ background: "var(--ep-bg)" }}
    >
      <svg
        viewBox="0 0 600 560"
        preserveAspectRatio="none"
        className="pointer-events-none absolute inset-0 h-full w-full"
        aria-hidden="true"
      >
        <path
          d="M-20 500 C 80 220, 360 150, 640 180"
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

      <div className="relative w-full max-w-[460px] flex flex-col items-center mb-6">
        <EduPathLogo size={36} />
        <h1 className="font-display text-[27px] text-[var(--ep-text)] leading-none mt-3">
          Start your path
        </h1>
        <p className="text-sm text-ep-muted mt-2">Create a free counsellor account.</p>
      </div>

      <div
        className="relative w-full max-w-[460px] rounded-[16px] border p-[28px]"
        style={{ background: "var(--ep-surface)", borderColor: "var(--ep-border)" }}
      >
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-[var(--ep-text-secondary)] mb-1.5">
              Full name
            </label>
            <input
              type="text"
              autoComplete="name"
              {...register("name")}
              className="w-full rounded-[10px] border px-4 py-3 text-sm text-[var(--ep-text)] outline-none focus:border-[var(--color-ep-primary)] transition-colors"
              style={{ background: "var(--ep-input)", borderColor: "var(--ep-border-strong)" }}
              placeholder="Priya Deshmukh"
            />
            {errors.name && (
              <p className="mt-1 text-xs text-[var(--color-ep-red)]">{errors.name.message}</p>
            )}
          </div>

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

          <div className="flex gap-3">
            <div className="flex-1">
              <label className="block text-xs font-medium text-[var(--ep-text-secondary)] mb-1.5">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPw ? "text" : "password"}
                  autoComplete="new-password"
                  {...register("password")}
                  className="w-full rounded-[10px] border px-4 py-3 pr-9 text-sm text-[var(--ep-text)] outline-none focus:border-[var(--color-ep-primary)] transition-colors"
                  style={{ background: "var(--ep-input)", borderColor: "var(--ep-border-strong)" }}
                  placeholder="Min. 8 chars"
                />
                <button
                  type="button"
                  onClick={() => setShowPw((p) => !p)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-ep-muted hover:text-[var(--ep-text)]"
                  tabIndex={-1}
                >
                  {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {errors.password && (
                <p className="mt-1 text-xs text-[var(--color-ep-red)]">{errors.password.message}</p>
              )}
            </div>

            <div className="flex-1">
              <label className="block text-xs font-medium text-[var(--ep-text-secondary)] mb-1.5">
                Confirm
              </label>
              <input
                type={showPw ? "text" : "password"}
                autoComplete="new-password"
                {...register("confirmPassword")}
                className="w-full rounded-[10px] border px-4 py-3 text-sm text-[var(--ep-text)] outline-none focus:border-[var(--color-ep-primary)] transition-colors"
                style={{ background: "var(--ep-input)", borderColor: "var(--ep-border-strong)" }}
                placeholder="••••••••"
              />
              {errors.confirmPassword && (
                <p className="mt-1 text-xs text-[var(--color-ep-red)]">{errors.confirmPassword.message}</p>
              )}
            </div>
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
            className="w-full flex items-center justify-center gap-2 py-3 rounded-[10px] text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50 mt-1"
            style={{ background: "var(--color-ep-primary)" }}
          >
            {isSubmitting ? "Creating account…" : "Create account"}
            <Plus className="h-4 w-4" />
          </button>
        </form>

        <p className="mt-5 text-center text-sm text-ep-muted">
          Already have an account?{" "}
          <Link href="/login" className="font-semibold hover:underline" style={{ color: "var(--color-ep-primary)" }}>
            Log in
          </Link>
        </p>
      </div>
    </div>
  );
}
