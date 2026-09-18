import { useEffect, useState, useCallback } from 'react'
import { fetchModelsPerformance } from '../api/admin'
import type { ModelPerformance } from '../types'
import LoadingSkeleton from '../components/LoadingSkeleton'
import ErrorBanner from '../components/ErrorBanner'
import EmptyState from '../components/EmptyState'

function fmtPct(n: number) { return `${(n * 100).toFixed(1)}%` }

function formatProvider(provider: string) {
  if (!provider) return 'Unknown'
  const p = provider.toLowerCase()
  if (p === 'openai') return 'OpenAI'
  if (p === 'anthropic') return 'Anthropic'
  if (p === 'groq') return 'Groq'
  return provider.charAt(0).toUpperCase() + provider.slice(1)
}

function providerStyleKey(provider: string) {
  if (!provider) return '?'
  const p = provider.toLowerCase()
  if (p === 'openai') return 'OpenAI'
  if (p === 'anthropic') return 'Anthropic'
  if (p === 'groq') return 'Groq'
  return '?'
}

const PROVIDER_LIGHT: Record<string, string> = {
  OpenAI: 'bg-green-50 text-green-700 ring-1 ring-green-600/20',
  Anthropic: 'bg-orange-50 text-orange-700 ring-1 ring-orange-600/20',
  Groq: 'bg-indigo-50 text-indigo-700 ring-1 ring-indigo-600/20',
  '?': 'bg-zinc-100 text-zinc-600 ring-1 ring-zinc-500/20',
}
const PROVIDER_DARK: Record<string, string> = {
  OpenAI: 'dark:bg-green-500/10 dark:text-green-400 dark:ring-1 dark:ring-green-500/25',
  Anthropic: 'dark:bg-orange-500/10 dark:text-orange-400 dark:ring-1 dark:ring-orange-500/25',
  Groq: 'dark:bg-indigo-500/10 dark:text-indigo-400 dark:ring-1 dark:ring-indigo-500/25',
  '?': 'dark:bg-zinc-500/10 dark:text-zinc-400 dark:ring-1 dark:ring-zinc-500/25',
}

export default function ModelPerformance() {
  const [models, setModels] = useState<ModelPerformance[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setError(null)
    try { setModels(await fetchModelsPerformance()) }
    catch { setError('Failed to load model performance data.') }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  return (
    <div className="max-w-5xl mx-auto">
      <div className="mb-7">
        <h1 className="text-lg font-semibold text-zinc-900 dark:text-white">Model Performance</h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-500">
          Per-model breakdown of request volume, success rate, latency, and cost.
        </p>
      </div>

      {error && <div className="mb-5"><ErrorBanner message={error} onRetry={() => { setLoading(true); load() }} /></div>}

      <div className="rounded-xl border border-zinc-200 dark:border-[#1e1e38] bg-white dark:bg-[#0d0d1c] overflow-hidden">
        {/* Header row */}
        <div className="grid grid-cols-[1fr_auto_auto_auto_auto] gap-x-6 px-5 py-3 border-b border-zinc-200 dark:border-[#1a1a30] bg-zinc-50 dark:bg-[#0a0a16]">
          {['Model', 'Requests', 'Success', 'Avg Latency', 'Total Cost'].map((h) => (
            <span key={h} className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-600">{h}</span>
          ))}
        </div>

        {loading ? (
          <LoadingSkeleton type="table" rows={5} />
        ) : models.length === 0 ? (
          <EmptyState title="No model data yet" description="Models appear after serving at least one request." />
        ) : (
          <div className="divide-y divide-zinc-100 dark:divide-[#1a1a30]">
            {models.map((m) => {
              const pKey = providerStyleKey(m.provider)
              const provLabel = formatProvider(m.provider)
              return (
                <div
                  key={m.model_id}
                  className="grid grid-cols-[1fr_auto_auto_auto_auto] gap-x-6 px-5 py-3 items-center
                    hover:bg-zinc-50 dark:hover:bg-white/[0.02] transition-colors"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <span className={`shrink-0 inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium
                      ${PROVIDER_LIGHT[pKey] || PROVIDER_LIGHT['?']} ${PROVIDER_DARK[pKey] || PROVIDER_DARK['?']}`}>
                      {provLabel}
                    </span>
                    <span className="text-sm font-mono text-zinc-800 dark:text-zinc-200 truncate" title={m.model_id}>
                      {m.model_id}
                    </span>
                  </div>
                  <span className="text-sm font-mono tabular-nums text-right text-zinc-700 dark:text-zinc-300">
                    {m.total_requests.toLocaleString()}
                  </span>
                  <span className={`text-sm font-mono tabular-nums text-right font-medium ${
                    m.success_rate >= 0.95 ? 'text-emerald-600 dark:text-emerald-400'
                    : m.success_rate >= 0.80 ? 'text-amber-600 dark:text-amber-400'
                    : 'text-red-600 dark:text-red-400'
                  }`}>{fmtPct(m.success_rate)}</span>
                  <span className="text-sm font-mono tabular-nums text-right text-zinc-600 dark:text-zinc-400">
                    {m.avg_latency_ms.toFixed(0)}<span className="text-xs ml-0.5 text-zinc-400 dark:text-zinc-600">ms</span>
                  </span>
                  <span className="text-sm font-mono tabular-nums text-right text-zinc-600 dark:text-zinc-400">
                    ${m.total_cost_usd.toFixed(6)}
                  </span>
                </div>
              )
            })}
          </div>
        )}

        {!loading && models.length > 0 && (
          <div className="px-5 py-2 border-t border-zinc-100 dark:border-[#1a1a30] bg-zinc-50 dark:bg-[#0a0a16]">
            <p className="text-xs text-zinc-400 dark:text-zinc-600">
              {models.length} model{models.length !== 1 ? 's' : ''} · by request volume
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
