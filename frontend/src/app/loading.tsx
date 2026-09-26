import { Skeleton } from "@/components/ui/Skeleton";

export default function RootLoading() {
  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-12 sm:px-6 lg:px-8 space-y-10 animate-fade-in">
      {/* Hero Section Skeleton */}
      <div className="text-center space-y-4 max-w-2xl mx-auto flex flex-col items-center">
        <Skeleton className="h-7 w-32 rounded-full" />
        <Skeleton className="h-12 w-3/4 rounded-2xl" />
        <Skeleton className="h-5 w-5/6" />
      </div>

      {/* Verify Box Skeleton */}
      <div className="rounded-3xl border border-border bg-bg-elevated p-6 sm:p-8 shadow-sm space-y-6 max-w-3xl mx-auto">
        <div className="flex gap-2 border-b border-border pb-4">
          <Skeleton className="h-9 w-28 rounded-xl" />
          <Skeleton className="h-9 w-28 rounded-xl" />
          <Skeleton className="h-9 w-28 rounded-xl" />
        </div>
        <Skeleton className="h-36 w-full rounded-2xl" />
        <div className="flex justify-between items-center pt-2">
          <Skeleton className="h-4 w-36" />
          <Skeleton className="h-11 w-44 rounded-xl" />
        </div>
      </div>

      {/* Feature / Stats Cards Skeleton */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-4xl mx-auto pt-6">
        <Skeleton className="h-28 rounded-2xl" />
        <Skeleton className="h-28 rounded-2xl" />
        <Skeleton className="h-28 rounded-2xl" />
      </div>
    </div>
  );
}
