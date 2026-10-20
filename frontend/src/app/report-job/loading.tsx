import { Skeleton } from "@/components/ui/Skeleton";

export default function ReportJobLoading() {
  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 sm:py-10 lg:py-12 space-y-8 animate-fade-in">
      {/* Top Bar Navigasi Skeleton */}
      <div className="flex items-center justify-between border-b border-border/60 pb-4">
        <Skeleton className="h-8 w-36 rounded-lg" />
        <Skeleton className="h-4 w-28 rounded-md" />
      </div>

      {/* Header */}
      <div className="space-y-2.5 max-w-3xl">
        <Skeleton className="h-4 w-28 rounded-full" />
        <Skeleton className="h-8 w-72 rounded-xl" />
        <Skeleton className="h-4 w-full max-w-xl" />
      </div>
      {/* Categories Grid */}
      <div className="space-y-3">
        <Skeleton className="h-4 w-36" />
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Skeleton className="h-20 rounded-2xl" />
          <Skeleton className="h-20 rounded-2xl" />
          <Skeleton className="h-20 rounded-2xl" />
          <Skeleton className="h-20 rounded-2xl" />
        </div>
      </div>

      {/* Form Fields */}
      <div className="rounded-2xl border border-border bg-bg-elevated p-6 space-y-5">
        <div className="space-y-2">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-10 w-full rounded-xl" />
        </div>
        <div className="space-y-2">
          <Skeleton className="h-4 w-40" />
          <Skeleton className="h-28 w-full rounded-2xl" />
        </div>
        <div className="space-y-2">
          <Skeleton className="h-4 w-36" />
          <Skeleton className="h-14 w-full rounded-2xl" />
        </div>
        <Skeleton className="h-12 w-full rounded-xl" />
      </div>
    </div>
  );
}
