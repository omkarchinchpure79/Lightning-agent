import { cn } from "@/lib/utils";

function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "animate-pulse rounded-[8px] bg-[var(--ep-border)]/60",
        className
      )}
      {...props}
    />
  );
}

export { Skeleton };
