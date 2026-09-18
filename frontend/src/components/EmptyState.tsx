interface EmptyStateProps {
  title: string
  description?: string
}

export default function EmptyState({ title, description }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="flex flex-col gap-1.5 mb-5" aria-hidden="true">
        <div className="h-0.5 w-10 rounded-full mx-auto bg-zinc-300 dark:bg-[#2a2a48]" />
        <div className="h-0.5 w-7 rounded-full mx-auto bg-zinc-200 dark:bg-[#1e1e38]" />
        <div className="h-0.5 w-4 rounded-full mx-auto bg-zinc-100 dark:bg-[#14142a]" />
      </div>
      <p className="text-sm font-medium text-zinc-600 dark:text-zinc-400">{title}</p>
      {description && (
        <p className="mt-1 text-xs text-zinc-400 dark:text-zinc-600 max-w-xs">{description}</p>
      )}
    </div>
  )
}
