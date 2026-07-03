"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { MotionConfig } from "framer-motion";
import { useState } from "react";
import { AuthProvider } from "@/lib/AuthProvider";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 60_000, retry: 1 },
        },
      })
  );

  return (
    <AuthProvider>
      <ThemeProvider attribute="class" defaultTheme="light" disableTransitionOnChange>
        <MotionConfig reducedMotion="user">
          <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
        </MotionConfig>
      </ThemeProvider>
    </AuthProvider>
  );
}
