/** Reusable skeleton placeholder components for loading states. */

function Bone({ className = "" }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded bg-slate-200 ${className}`}
    />
  );
}

export function MatchListSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div className="flex h-full flex-col gap-2 overflow-hidden p-2">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="flex items-start gap-3 rounded-lg border border-gray-200 bg-white p-3"
        >
          <Bone className="h-10 w-10 shrink-0 rounded" />
          <div className="flex flex-1 flex-col gap-2">
            <Bone className="h-4 w-3/4" />
            <Bone className="h-3 w-1/2" />
            <Bone className="h-3 w-1/3" />
          </div>
          <Bone className="h-8 w-16 rounded-full" />
        </div>
      ))}
    </div>
  );
}

export function MatchDetailSkeleton() {
  return (
    <div className="flex flex-col gap-4 p-6">
      <Bone className="h-6 w-2/3" />
      <Bone className="h-4 w-1/3" />
      <div className="mt-4 flex gap-3">
        <Bone className="h-10 w-28 rounded-md" />
        <Bone className="h-10 w-28 rounded-md" />
      </div>
      <div className="mt-6 flex flex-col gap-2">
        <Bone className="h-4 w-full" />
        <Bone className="h-4 w-full" />
        <Bone className="h-4 w-5/6" />
        <Bone className="h-4 w-4/6" />
      </div>
    </div>
  );
}

export function ProfileSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-3xl font-semibold">Profile</h1>
      {/* Basics card */}
      <div className="rounded-lg border border-slate-200 bg-white p-6">
        <div className="flex items-center gap-4">
          <Bone className="h-16 w-16 rounded-full" />
          <div className="flex flex-1 flex-col gap-2">
            <Bone className="h-5 w-48" />
            <Bone className="h-4 w-32" />
            <Bone className="h-3 w-56" />
          </div>
        </div>
      </div>
      {/* Skills card */}
      <div className="rounded-lg border border-slate-200 bg-white p-6">
        <Bone className="mb-3 h-5 w-24" />
        <div className="flex flex-wrap gap-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <Bone key={i} className="h-7 w-20 rounded-full" />
          ))}
        </div>
      </div>
      {/* Experience card */}
      <div className="rounded-lg border border-slate-200 bg-white p-6">
        <Bone className="mb-4 h-5 w-28" />
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="mb-4 flex flex-col gap-2">
            <Bone className="h-4 w-48" />
            <Bone className="h-3 w-36" />
            <Bone className="h-3 w-full" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function DashboardSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <Bone className="mb-2 h-8 w-48" />
        <Bone className="h-4 w-80" />
      </div>
      {/* Metric cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="rounded-lg border border-slate-200 bg-white p-4"
          >
            <Bone className="mb-2 h-3 w-24" />
            <Bone className="h-8 w-16" />
          </div>
        ))}
      </div>
      {/* Chart placeholder */}
      <div className="rounded-lg border border-slate-200 bg-white p-6">
        <Bone className="h-48 w-full rounded" />
      </div>
    </div>
  );
}
