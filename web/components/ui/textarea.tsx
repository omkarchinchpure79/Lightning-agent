import * as React from "react";
import { cn } from "@/lib/utils";

const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    className={cn(
      "flex min-h-[80px] w-full rounded-[8px] border border-[var(--ep-border)] bg-[var(--ep-input)] px-3 py-2 text-sm text-[var(--ep-text)] shadow-sm placeholder:text-ep-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ep-primary disabled:cursor-not-allowed disabled:opacity-50 resize-y",
      className
    )}
    ref={ref}
    {...props}
  />
));
Textarea.displayName = "Textarea";

export { Textarea };
