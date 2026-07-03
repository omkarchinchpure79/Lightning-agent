import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

// "The Path" signal system — exact tint/ink pairs, not opacity-modified brand colors.
const badgeVariants = cva(
  "font-mono inline-flex items-center rounded-[7px] px-2.5 py-1 text-[11px] font-semibold tracking-tight",
  {
    variants: {
      variant: {
        default: "text-[var(--color-ep-primary)]",
        safe: "text-[var(--color-ep-green-ink)]",
        probable: "text-[var(--color-ep-amber-ink)]",
        reach: "text-[var(--color-ep-red-ink)]",
        high: "text-[var(--color-ep-green-ink)]",
        medium: "text-[var(--color-ep-amber-ink)]",
        low: "text-[var(--color-ep-red-ink)]",
        muted: "text-[var(--ep-text-secondary)]",
        outline: "border text-[var(--ep-text)]",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

const bgByVariant: Record<string, string> = {
  default: "rgba(30,77,140,.08)",
  safe: "#E7F4EC",
  probable: "#F5EBD3",
  reach: "#F8E1DF",
  high: "#E7F4EC",
  medium: "#F5EBD3",
  low: "#F8E1DF",
  muted: "#EDEAE1",
  outline: "transparent",
};

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, style, ...props }: BadgeProps) {
  const v = variant ?? "default";
  return (
    <div
      className={cn(badgeVariants({ variant }), className)}
      style={{
        background: bgByVariant[v],
        borderColor: v === "outline" ? "var(--ep-border)" : undefined,
        ...style,
      }}
      {...props}
    />
  );
}

export { Badge, badgeVariants };
