import { useEffect, useState, useCallback } from 'react'
import { fetchRoutingStats } from '../api/admin'
import type { RoutingStats } from '../types'
import StatCard from '../components/StatCard'
import LoadingSkeleton from '../components/LoadingSkeleton'
import ErrorBanner from '../components/ErrorBanner'
import EmptyState from '../components/EmptyState'

function fmtPct(n: number) { return `${(n * 100).toFixed(1)}%` }
function fmtCost(n: number) { return n === 0 ? '$0.000000' : `$${n.toFixed(6)}` }

export default function Overview() {
  const [stats, setStats] = useState<RoutingStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setError(null)
    try { setStats(await fetchRoutingStats()) }
    catch { setError('Failed to load routing stats. Is the backend running?') }
    finally { setLoading(false) }
  }, [])

  useEffect(() => {
    load()
    const id = setInterval(load, 30_000)
    return () => clearInterval(id)
  }, [load])

  return (
    <div className="max-w-5xl mx-auto">
      <div className="mb-7">
        <h1 className="text-lg font-semibold text-zinc-900 dark:text-white">Overview</h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-500">
          Global aggregate metrics. Auto-refreshes every 30s.
        </p>
      </div>

      {error && <div className="mb-5"><ErrorBanner message={error} onRetry={() => { setLoading(true); load() }} /></div>}

      {loading ? (
        <LoadingSkeleton type="card" rows={5} />
      ) : stats === null ? null : stats.total_requests === 0 ? (
        <EmptyState
          title="No requests yet"
          description="Send a request to POST /v1/chat/completions to see routing stats here."
        />
      ) : (
        <>
          {/* Stat cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
            <StatCard label="Total Requests" value={stats.total_requests.toLocaleString()} accent />
            <StatCard label="Success Rate" value={fmtPct(stats.success_rate)} sub={`Error ${fmtPct(stats.error_rate)}`} />
            <StatCard label="Avg Latency" value={stats.avg_latency_ms.toFixed(0)} unit="ms" />
            <StatCard label="Total Cost" value={fmtCost(stats.total_cost_usd)} />
            <StatCard label="Fallback Rate" value={fmtPct(stats.fallback_rate)} />
          </div>

          {/* Summary table */}
          <div className="mt-5 rounded-xl border border-zinc-200 dark:border-[#1e1e38] bg-white dark:bg-[#0d0d1c] overflow-hidden">
            <div className="px-5 py-3 border-b border-zinc-100 dark:border-[#1a1a30] bg-zinc-50 dark:bg-[#0a0a16]">
              <h2 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-600">
                Breakdown
              </h2>
            </div>
            <div className="divide-y divide-zinc-100 dark:divide-[#1a1a30]">
              {[
                { label: 'Successful requests', value: `${Math.round(stats.total_requests * stats.success_rate).toLocaleString()} of ${stats.total_requests.toLocaleString()}` },
                { label: 'Failed / error requests', value: Math.round(stats.total_requests * stats.error_rate).toLocaleString() },
                { label: 'Served by fallback model', value: Math.round(stats.total_requests * stats.fallback_rate).toLocaleString() },
                {
                  label: 'Average cost per request',
                  value: stats.total_requests > 0
                    ? `$${(stats.total_cost_usd / stats.total_requests).toFixed(8)}`
                    : '—',
                },
              ].map(({ label, value }) => (
                <div key={label} className="flex items-center justify-between px-5 py-2.5">
                  <span className="text-sm text-zinc-600 dark:text-zinc-400">{label}</span>
                  <span className="text-sm font-medium font-mono tabular-nums text-zinc-900 dark:text-[#ddddf0]">{value}</span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
