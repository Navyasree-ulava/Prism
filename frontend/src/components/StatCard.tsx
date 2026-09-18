interface StatCardProps {
  label: string
  value: string | number
  unit?: string
  sub?: string
  accent?: boolean
}

export default function StatCard({ label, value, unit, sub, accent }: StatCardProps) {
  return (
    <div className={`
      rounded-xl p-5 flex flex-col gap-1.5 transition-all duration-200
      ${accent
        ? `border border-indigo-200 bg-white shadow-sm
           dark:border-indigo-500/30 dark:bg-indigo-500/5 dark:glow-indigo`
        : `border border-zinc-200 bg-white shadow-sm
           dark:border-[#1e1e38] dark:bg-[#0d0d1c]`
      }
    `}>
      <p className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-500">
        {label}
      </p>
      <p className={`text-3xl font-semibold tabular-nums font-mono ${
        accent
          ? 'text-indigo-600 dark:text-indigo-400'
          : 'text-zinc-900 dark:text-[#ddddf0]'
      }`}>
        {value}
        {unit && <span className="text-base font-normal text-zinc-400 dark:text-zinc-600 ml-1">{unit}</span>}
      </p>
      {sub && <p className="text-xs text-zinc-400 dark:text-zinc-600 mt-0.5">{sub}</p>}
    </div>
  )
}
