interface LoadingSkeletonProps {
  rows?: number
  type?: 'card' | 'table' | 'detail'
}

function Pulse({ className }: { className: string }) {
  return (
    <div className={`animate-pulse rounded bg-zinc-200 dark:bg-[#1a1a30] ${className}`} />
  )
}

export default function LoadingSkeleton({ rows = 5, type = 'table' }: LoadingSkeletonProps) {
  if (type === 'card') {
    return (
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="rounded-xl border border-zinc-200 dark:border-[#1e1e38] bg-white dark:bg-[#0d0d1c] p-5 flex flex-col gap-2.5">
            <Pulse className="h-3 w-20" />
            <Pulse className="h-8 w-28" />
          </div>
        ))}
      </div>
    )
  }

  if (type === 'detail') {
    return (
      <div className="flex flex-col gap-4 p-5">
        <Pulse className="h-5 w-36" />
        <Pulse className="h-3 w-full" />
        <Pulse className="h-3 w-3/4" />
        <Pulse className="h-3 w-1/2" />
        <Pulse className="h-28 w-full mt-2" />
        <Pulse className="h-28 w-full" />
      </div>
    )
  }

  return (
    <div className="flex flex-col divide-y divide-zinc-100 dark:divide-[#1a1a30]">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="py-3 px-4 flex gap-4 items-center">
          <Pulse className="h-3 w-32" />
          <Pulse className="h-3 w-20 hidden sm:block" />
          <Pulse className="h-3 w-12 ml-auto" />
        </div>
      ))}
    </div>
  )
}
