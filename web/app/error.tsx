"use client";

import { useEffect } from "react";
import { AlertTriangle, RotateCw } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * App Router route-level error boundary. Catches render/runtime errors
 * (including failed data loads that throw) anywhere in the route subtree and
 * shows a human message instead of a blank white screen or raw stack trace.
 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Surface to the console for debugging; no external reporting in local build.
    console.error(error);
  }, [error]);

  const looksLikeNetwork =
    /fetch|network|load failed|econnrefused|failed to fetch/i.test(error.message);

  return (
    <div
      className="min-h-screen flex items-center justify-center px-6"
      style={{ background: "var(--ep-bg)" }}
    >
      <div
        className="max-w-md w-full rounded-[12px] border border-[var(--ep-border)] px-6 py-7 text-center"
        style={{ background: "var(--ep-surface)" }}
      >
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-ep-red/10">
          <AlertTriangle className="h-6 w-6 text-ep-red" />
        </div>
        <h1 className="text-lg font-semibold text-[var(--ep-text)]">
          Can&apos;t load this page
        </h1>
        <p className="mt-2 text-sm text-ep-muted">
          {looksLikeNetwork
            ? "Couldn't reach the prediction backend. Make sure the backend is running, then try again."
            : "Something went wrong while loading this page. Try again, and if it keeps happening, restart the backend."}
        </p>
        <div className="mt-5 flex justify-center">
          <Button onClick={reset} variant="outline">
            <RotateCw className="h-4 w-4" />
            Try again
          </Button>
        </div>
      </div>
    </div>
  );
}
