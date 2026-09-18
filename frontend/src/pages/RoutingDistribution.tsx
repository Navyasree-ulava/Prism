import { useEffect, useState, useCallback } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell, Legend,
} from 'recharts'
import { fetchModelsPerformance, fetchRoutingStats } from '../api/admin'
import type { ModelPerformance, RoutingStats } from '../types'
import LoadingSkeleton from '../components/LoadingSkeleton'
import ErrorBanner from '../components/ErrorBanner'
import EmptyState from '../components/EmptyState'

// Vivid palette that pops on both light and dark
const BAR_COLORS = ['#6366f1', '#10b981', '#0ea5e9', '#f59e0b', '#ef4444', '#a855f7']
const GRID_COLOR_LIGHT = '#f4f4f5'
const GRID_COLOR_DARK = '#1a1a30'

function useDark() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains('dark'))
  useEffect(() => {
    const obs = new MutationObserver(() =>
      setDark(document.documentElement.classList.contains('dark'))
    )
    obs.observe(document.documentElement, { attributeFilter: ['class'] })
    return () => obs.disconnect()
  }, [])
  return dark
}

function BarTip({ active, payload }: { active?: boolean; payload?: { payload: ModelPerformance }[] }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="rounded-lg border border-zinc-200 dark:border-[#2a2a48] bg-white dark:bg-[#111128] shadow-lg px-3 py-2.5 text-xs font-mono">
      <p className="font-semibold text-zinc-800 dark:text-zinc-200 mb-1">{d.model_id}</p>
      <p className="text-zinc-600 dark:text-zinc-400">{d.total_requests} requests</p>
      <p className="text-emerald-600 dark:text-emerald-400">{(d.success_rate * 100).toFixed(1)}% success</p>
      <p className="text-zinc-500 dark:text-zinc-500">avg {d.avg_latency_ms.toFixed(0)}ms</p>
    </div>
  )
}

export default function RoutingDistribution() {
  const [models, setModels] = useState<ModelPerformance[]>([])
  const [stats, setStats] = useState<RoutingStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const dark = useDark()

  const load = useCallback(async () => {
    setError(null)
    try {
      const [m, s] = await Promise.all([fetchModelsPerformance(), fetchRoutingStats()])
      setModels(m); setStats(s)
    } catch { setError('Failed to load distribution data.') }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const isEmpty = !loading && (!stats || stats.total_requests === 0)
  const barData = models.map((m) => ({ ...m, label: m.model_id.length > 16 ? m.model_id.slice(0, 14) + '…' : m.model_id }))
  const pieData = stats && stats.total_requests > 0
    ? [
        { name: 'Success', value: Math.round(stats.total_requests * stats.success_rate) },
        { name: 'Error', value: Math.round(stats.total_requests * stats.error_rate) },
      ].filter((d) => d.value > 0)
    : []

  const gridColor = dark ? GRID_COLOR_DARK : GRID_COLOR_LIGHT
  const axisColor = dark ? '#55556a' : '#71717a'
  const tooltipStyle = {
    backgroundColor: dark ? '#111128' : '#ffffff',
    border: `1px solid ${dark ? '#2a2a48' : '#e4e4e7'}`,
    borderRadius: '8px',
    fontSize: 11,
    fontFamily: 'IBM Plex Mono, monospace',
  }

  const card = 'rounded-xl border border-zinc-200 dark:border-[#1e1e38] bg-white dark:bg-[#0d0d1c]'

  return (
    <div className="max-w-5xl mx-auto">
      <div className="mb-7">
        <h1 className="text-lg font-semibold text-zinc-900 dark:text-white">Routing Distribution</h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-500">
          Model selection frequency and outcome breakdown.
        </p>
      </div>

      {error && <div className="mb-5"><ErrorBanner message={error} onRetry={() => { setLoading(true); load() }} /></div>}

      {loading ? (
        <div className="space-y-4">
          <LoadingSkeleton type="card" rows={2} />
          <div className={`${card} h-72 animate-pulse`} />
        </div>
      ) : isEmpty ? (
        <EmptyState title="No routing data yet" description="Charts appear after requests are routed through the gateway." />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Bar chart (2/3) */}
          <div className={`lg:col-span-2 ${card} p-5`}>
            <h2 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-600 mb-5">
              Requests per Model
            </h2>
            {models.length === 0 ? <EmptyState title="No model data" /> : (
              <ResponsiveContainer width="100%" height={270}>
                <BarChart data={barData} margin={{ top: 4, right: 8, bottom: 44, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
                  <XAxis
                    dataKey="label"
                    tick={{ fontSize: 10, fill: axisColor, fontFamily: 'IBM Plex Mono, monospace' }}
                    angle={-35} textAnchor="end" interval={0}
                    tickLine={false} axisLine={{ stroke: gridColor }}
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: axisColor, fontFamily: 'IBM Plex Mono, monospace' }}
                    tickLine={false} axisLine={false} allowDecimals={false}
                  />
                  <Tooltip content={<BarTip />} cursor={{ fill: dark ? 'rgba(99,102,241,0.06)' : '#f4f4f5' }} />
                  <Bar dataKey="total_requests" radius={[4, 4, 0, 0]} maxBarSize={52}>
                    {barData.map((_, i) => <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* Right column */}
          <div className="flex flex-col gap-4">
            {/* Pie */}
            <div className={`${card} p-5`}>
              <h2 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-600 mb-4">
                Outcome Split
              </h2>
              {pieData.length === 0 ? <EmptyState title="No outcome data" /> : (
                <ResponsiveContainer width="100%" height={160}>
                  <PieChart>
                    <Pie data={pieData} cx="50%" cy="50%" innerRadius={44} outerRadius={64} paddingAngle={2} dataKey="value">
                      {pieData.map((e) => (
                        <Cell key={e.name} fill={e.name === 'Success' ? '#10b981' : '#ef4444'} />
                      ))}
                    </Pie>
                    <Legend iconType="circle" iconSize={7} formatter={(v) => (
                      <span style={{ fontSize: 11, color: dark ? '#8888aa' : '#71717a' }}>{v}</span>
                    )} />
                    <Tooltip
                      formatter={(v: number) => [v, 'requests']}
                      contentStyle={tooltipStyle}
                    />
                  </PieChart>
                </ResponsiveContainer>
              )}
            </div>

            {/* Fallback callout */}
            {stats && (
              <div className={`${card} p-5 flex flex-col gap-1.5`}>
                <h2 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-600">
                  Fallback Rate
                </h2>
                <p className="text-3xl font-semibold font-mono tabular-nums text-zinc-900 dark:text-[#ddddf0]">
                  {(stats.fallback_rate * 100).toFixed(1)}
                  <span className="text-base font-normal text-zinc-400 dark:text-zinc-600 ml-1">%</span>
                </p>
                <p className="text-xs text-zinc-400 dark:text-zinc-600">
                  {Math.round(stats.total_requests * stats.fallback_rate)} of {stats.total_requests} used fallback
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
