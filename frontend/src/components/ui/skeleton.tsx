import { cn } from "@/lib/utils";

function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      className={cn("animate-pulse rounded-md bg-zinc-200/70 dark:bg-zinc-800/60", className)}
      {...props}
    />
  );
}

/**
 * Row-shaped skeleton for the past-checks / past-analyses dashboard lists.
 * Mirrors the actual list item layout (title + meta on left, badge + score
 * on right) so the swap from skeleton → real data is layout-stable.
 */
function ListRowSkeleton() {
  return (
    <div className="flex items-center justify-between rounded-lg border border-zinc-200 bg-zinc-100/60 px-4 py-3 dark:border-zinc-800 dark:bg-zinc-800/30">
      <div className="min-w-0 flex-1 space-y-2">
        <Skeleton className="h-3.5 w-2/3" />
        <Skeleton className="h-3 w-1/4" />
      </div>
      <div className="flex items-center gap-3">
        <Skeleton className="h-5 w-16 rounded-full" />
        <Skeleton className="h-5 w-8" />
      </div>
    </div>
  );
}

function ListSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <ListRowSkeleton key={i} />
      ))}
    </div>
  );
}

export { Skeleton, ListRowSkeleton, ListSkeleton };
