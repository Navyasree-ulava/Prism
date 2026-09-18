interface StatusBadgeProps {
  status: string
  fallback?: boolean
}

const LIGHT: Record<string, string> = {
  success: 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-600/20',
  error: 'bg-red-50 text-red-700 ring-1 ring-red-600/20',
  timeout: 'bg-amber-50 text-amber-700 ring-1 ring-amber-600/20',
}
const DARK: Record<string, string> = {
  success: 'dark:bg-emerald-500/10 dark:text-emerald-400 dark:ring-emerald-500/25',
  error: 'dark:bg-red-500/10 dark:text-red-400 dark:ring-red-500/25',
  timeout: 'dark:bg-amber-500/10 dark:text-amber-400 dark:ring-amber-500/25',
}

export default function StatusBadge({ status, fallback }: StatusBadgeProps) {
  const light = LIGHT[status] ?? 'bg-zinc-100 text-zinc-600 ring-1 ring-zinc-500/20'
  const dark = DARK[status] ?? 'dark:bg-zinc-500/10 dark:text-zinc-300 dark:ring-zinc-500/25'
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium font-mono uppercase tracking-wide ring-1 ${light} ${dark}`}>
        {status}
      </span>
      {fallback && (
        <span className="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ring-1
          bg-amber-50 text-amber-700 ring-amber-600/20
          dark:bg-amber-500/10 dark:text-amber-400 dark:ring-amber-500/25
          font-mono uppercase tracking-wide">
          fallback
        </span>
      )}
    </span>
  )
}
