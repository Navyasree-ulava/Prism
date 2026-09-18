interface ErrorBannerProps {
  message: string
  onRetry?: () => void
}

export default function ErrorBanner({ message, onRetry }: ErrorBannerProps) {
  return (
    <div className="
      rounded-lg border px-4 py-3 flex items-start gap-3
      border-red-200 bg-red-50 text-red-700
      dark:border-red-500/20 dark:bg-red-500/8 dark:text-red-400
    ">
      <span className="mt-0.5 shrink-0 opacity-80" aria-hidden="true">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <circle cx="7" cy="7" r="6.5" stroke="currentColor" />
          <path d="M7 4v3.5M7 9.5v.5" stroke="currentColor" strokeLinecap="round" />
        </svg>
      </span>
      <p className="flex-1 min-w-0 text-sm">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="shrink-0 text-xs font-medium underline hover:no-underline"
        >
          Retry
        </button>
      )}
    </div>
  )
}
