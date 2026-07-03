import * as React from "react";
import { cn } from "@/lib/utils";

const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => (
    <input
      type={type}
      className={cn(
        "flex h-9 w-full rounded-[9px] border border-[var(--ep-border-strong)] bg-[var(--ep-input)] px-3 py-1 text-sm text-[var(--ep-text)] transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-ep-muted focus-visible:outline-none focus-visible:border-[var(--color-ep-primary)] focus-visible:bg-white focus-visible:ring-0 disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      ref={ref}
      {...props}
    />
  )
);
Input.displayName = "Input";

export { Input };
