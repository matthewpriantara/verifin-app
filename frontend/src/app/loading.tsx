import { Skeleton } from "@/components/ui/Skeleton";

export default function RootLoading() {
  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-14 sm:px-6 lg:py-20 animate-fade-in">
      {/* Hero 2-Column Skeleton */}
      <div className="flex flex-col items-center gap-10 lg:flex-row lg:items-start lg:gap-16">
        {/* Left Column: Headline & Info */}
        <div className="w-full flex-1 space-y-5">
          <Skeleton className="h-4 w-28 rounded-md" />
          <div className="space-y-3">
            <Skeleton className="h-10 w-3/4 rounded-xl sm:h-12" />
            <Skeleton className="h-10 w-1/2 rounded-xl sm:h-12" />
          </div>
          <div className="space-y-2 max-w-lg pt-1">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
            <Skeleton className="h-4 w-4/6" />
          </div>
          {/* Metric Badges */}
          <div className="flex gap-6 pt-3">
            <Skeleton className="h-12 w-24 rounded-xl" />
            <Skeleton className="h-12 w-24 rounded-xl" />
            <Skeleton className="h-12 w-28 rounded-xl" />
          </div>
        </div>

        {/* Right Column: Verify Box */}
        <div className="w-full lg:max-w-lg lg:w-[480px] space-y-4">
          <div className="rounded-3xl border border-border bg-bg-elevated p-6 sm:p-7 space-y-5">
            <div className="flex justify-between items-center border-b border-border/50 pb-3">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-4 w-20" />
            </div>
            <Skeleton className="h-32 w-full rounded-2xl" />
            <div className="flex justify-between items-center pt-1">
              <Skeleton className="h-4 w-36" />
              <Skeleton className="h-10 w-36 rounded-xl" />
            </div>
          </div>
          <div className="rounded-2xl border border-border bg-bg-elevated p-4 space-y-3">
            <Skeleton className="h-4 w-28" />
            <Skeleton className="h-8 w-full rounded-xl" />
          </div>
        </div>
      </div>

      {/* Step Cards Skeleton */}
      <div className="mt-20 border-t border-border pt-12 space-y-6">
        <div className="space-y-2">
          <Skeleton className="h-3 w-28" />
          <Skeleton className="h-7 w-64 rounded-xl" />
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-44 rounded-2xl" />
          ))}
        </div>
      </div>
    </div>
  );
}
