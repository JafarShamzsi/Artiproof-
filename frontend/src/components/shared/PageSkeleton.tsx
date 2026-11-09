"use client";

import { Skeleton } from "@/components/ui/skeleton";

export function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-8 w-40 bg-zinc-800" />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[...Array(4)].map((_, i) => (
          <Skeleton key={i} className="h-20 rounded-lg bg-zinc-800" />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Skeleton className="h-48 rounded-lg bg-zinc-800" />
        <Skeleton className="h-48 rounded-lg bg-zinc-800" />
      </div>
      <Skeleton className="h-64 rounded-lg bg-zinc-800" />
    </div>
  );
}

export function ResultsSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-8 w-56 bg-zinc-800" />
      <Skeleton className="h-40 rounded-lg bg-zinc-800" />
      <Skeleton className="h-32 rounded-lg bg-zinc-800" />
      <Skeleton className="h-32 rounded-lg bg-zinc-800" />
      <Skeleton className="h-24 rounded-lg bg-zinc-800" />
    </div>
  );
}

export function ListSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {[...Array(rows)].map((_, i) => (
        <Skeleton key={i} className="h-16 rounded-lg bg-zinc-800" />
      ))}
    </div>
  );
}
