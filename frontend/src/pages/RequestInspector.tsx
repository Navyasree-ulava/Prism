import { useEffect, useState, useCallback } from 'react'
import { fetchDecisions, fetchDecisionDetail } from '../api/admin'
import type { DecisionSummary, DecisionDetail, Candidate } from '../types'
import StatusBadge from '../components/StatusBadge'
import LoadingSkeleton from '../components/LoadingSkeleton'
import ErrorBanner from '../components/ErrorBanner'
import EmptyState from '../components/EmptyState'

function fmtTime(iso: string | null) {
  if (!iso) return '—'
  try { return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) }
  catch { return iso }
}
function fmtDate(iso: string | null) {
  if (!iso) return '—'
  try { return new Date(iso).toLocaleDateString([], { month: 'short', day: 'numeric' }) }
  catch { return iso }
}
function truncateId(id: string) { return id.slice(0, 8) + '…' }
function complexityColor(c: string) {
  if (c === 'high') return 'text-red-600 dark:text-red-400'
  if (c === 'medium') return 'text-amber-600 dark:text-amber-400'
  return 'text-emerald-600 dark:text-emerald-400'
}

// ── Detail panel ────────────────────────────────────────────────────────────

function DetailPanel({ detail, loading, error }: {
  detail: DecisionDetail | null
  loading: boolean
  error: string | null
}) {
  if (loading) return <LoadingSkeleton type="detail" />
  if (error) return <div className="p-5"><ErrorBanner message={error} /></div>
  if (!detail) {
    return (
      <EmptyState
        title="Select a request to inspect"
        description="Click any row on the left to see the full routing decision trail."
      />
    )
  }

  const { prompt_meta: pm, routing_decision: rd, model_run: mr } = detail
  const candidates: Candidate[] = [...(rd.candidates ?? [])].sort((a, b) => b.score - a.score)
  const maxScore = candidates[0]?.score ?? 1

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      {/* Header strip */}
      <div className="px-5 py-4 border-b border-zinc-100 dark:border-[#1a1a30] bg-zinc-50 dark:bg-[#0a0a16] shrink-0">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-mono text-zinc-400 dark:text-zinc-600 select-all">{detail.request_id}</p>
            <p className="text-xs text-zinc-400 dark:text-zinc-600 mt-0.5">
              {fmtDate(detail.created_at)} · {fmtTime(detail.created_at)}
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-mono uppercase tracking-wide
              bg-zinc-100 text-zinc-600 dark:bg-white/5 dark:text-zinc-400">
              {detail.strategy}
            </span>
            <StatusBadge status={mr.status ?? 'unknown'} fallback={mr.fallback_used} />
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto divide-y divide-zinc-100 dark:divide-[#1a1a30]">

        {/* Analyzer output */}
        {pm && (
          <section className="px-5 py-4">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-600 mb-3">
              Analyzer Output
            </h3>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
              {[
                { label: 'Task type', value: pm.task_type, mono: true },
                { label: 'Complexity', value: pm.complexity, cls: complexityColor(pm.complexity), mono: true },
                { label: 'Context req.', value: pm.context_requirement, mono: true },
                { label: 'Est. tokens', value: pm.estimated_input_tokens.toLocaleString(), mono: true },
                { label: 'Confidence', value: `${(pm.confidence * 100).toFixed(0)}%`, mono: true },
              ].map(({ label, value, cls, mono }) => (
                <div key={label}>
                  <dt className="text-xs text-zinc-400 dark:text-zinc-600">{label}</dt>
                  <dd className={`text-sm mt-0.5 ${mono ? 'font-mono' : ''} ${cls ?? 'text-zinc-800 dark:text-zinc-200'}`}>
                    {value}
                  </dd>
                </div>
              ))}
              <div className="col-span-2">
                <dt className="text-xs text-zinc-400 dark:text-zinc-600 mb-1">Capabilities</dt>
                <dd className="flex flex-wrap gap-1">
                  {pm.required_capabilities.map((cap) => (
                    <span key={cap} className="
                      inline-flex items-center rounded px-1.5 py-0.5 text-xs font-mono
                      bg-indigo-50 text-indigo-700 ring-1 ring-indigo-600/20
                      dark:bg-indigo-500/10 dark:text-indigo-400 dark:ring-indigo-500/25
                    ">
                      {cap}
                    </span>
                  ))}
                  {pm.required_capabilities.length === 0 && (
                    <span className="text-xs text-zinc-400 dark:text-zinc-600">none</span>
                  )}
                </dd>
              </div>
            </dl>
          </section>
        )}

        {/* Candidate scores */}
        {candidates.length > 0 && (
          <section className="px-5 py-4">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-600 mb-3">
              Candidate Scores
            </h3>
            <div className="flex flex-col gap-2">
              {candidates.map((c, i) => {
                const isSelected = c.model_id === rd.selected_model
                const pct = maxScore > 0 ? (c.score / maxScore) * 100 : 0
                return (
                  <div key={c.model_id} className={`
                    rounded-lg border px-3 py-2.5 transition-all
                    ${isSelected
                      ? 'border-indigo-200 bg-indigo-50 dark:border-indigo-500/30 dark:bg-indigo-500/5 dark:glow-indigo'
                      : 'border-zinc-100 bg-white dark:border-[#1e1e38] dark:bg-[#0d0d1c]'
                    }
                  `}>
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2 min-w-0">
                        {isSelected ? (
                          <span className="shrink-0 inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium
                            bg-indigo-600 text-white dark:bg-indigo-500 dark:glow-indigo-sm font-mono uppercase">
                            SELECTED
                          </span>
                        ) : (
                          <span className="shrink-0 text-xs text-zinc-400 dark:text-zinc-600 font-mono w-5 text-right">
                            #{i + 1}
                          </span>
                        )}
                        <span className="text-xs font-mono text-zinc-700 dark:text-zinc-300 truncate" title={c.model_id}>
                          {c.model_id}
                        </span>
                      </div>
                      <span className="shrink-0 text-xs font-mono tabular-nums font-semibold ml-2 text-zinc-700 dark:text-zinc-300">
                        {c.score.toFixed(4)}
                      </span>
                    </div>
                    {/* Score bar */}
                    <div className="h-1 w-full rounded-full bg-zinc-100 dark:bg-[#1a1a30] overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${
                          isSelected ? 'bg-indigo-500 dark:bg-indigo-400' : 'bg-zinc-300 dark:bg-[#2a2a48]'
                        }`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
            {rd.reason && (
              <p className="mt-3 text-xs text-zinc-500 dark:text-zinc-600 italic leading-relaxed">
                &ldquo;{rd.reason}&rdquo;
              </p>
            )}
          </section>
        )}

        {/* Model run */}
        <section className="px-5 py-4">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-600 mb-3">
            Model Run
          </h3>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
            {[
              { label: 'Model used', value: mr.model_id ?? '—' },
              { label: 'Latency', value: mr.latency_ms != null ? `${mr.latency_ms}ms` : '—' },
              { label: 'Cost', value: mr.cost_usd != null ? `$${mr.cost_usd.toFixed(6)}` : '—' },
              { label: 'Tokens in', value: mr.tokens_in?.toLocaleString() ?? '—' },
              { label: 'Tokens out', value: mr.tokens_out?.toLocaleString() ?? '—' },
            ].map(({ label, value }) => (
              <div key={label}>
                <dt className="text-xs text-zinc-400 dark:text-zinc-600">{label}</dt>
                <dd className="text-sm font-mono tabular-nums text-zinc-800 dark:text-zinc-200 mt-0.5">{value}</dd>
              </div>
            ))}
            <div>
              <dt className="text-xs text-zinc-400 dark:text-zinc-600 mb-1">Status</dt>
              <dd><StatusBadge status={mr.status ?? 'unknown'} fallback={mr.fallback_used} /></dd>
            </div>
          </dl>
        </section>
      </div>
    </div>
  )
}

// ── Main page ────────────────────────────────────────────────────────────────

export default function RequestInspector() {
  const [decisions, setDecisions] = useState<DecisionSummary[]>([])
  const [listLoading, setListLoading] = useState(true)
  const [listError, setListError] = useState<string | null>(null)

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<DecisionDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState<string | null>(null)

  const loadList = useCallback(async () => {
    setListError(null)
    try { setDecisions(await fetchDecisions(50)) }
    catch { setListError('Failed to load request list.') }
    finally { setListLoading(false) }
  }, [])

  const loadDetail = useCallback(async (id: string) => {
    setDetailLoading(true); setDetailError(null); setDetail(null)
    try { setDetail(await fetchDecisionDetail(id)) }
    catch { setDetailError(`Failed to load details for ${truncateId(id)}.`) }
    finally { setDetailLoading(false) }
  }, [])

  useEffect(() => { loadList() }, [loadList])

  function selectRow(id: string) { setSelectedId(id); loadDetail(id) }

  const card = 'rounded-xl border border-zinc-200 dark:border-[#1e1e38] bg-white dark:bg-[#0d0d1c]'

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-5">
        <h1 className="text-lg font-semibold text-zinc-900 dark:text-white">Request Inspector</h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-500">
          Click a request to inspect the full routing decision trail.
        </p>
      </div>

      {listError && <div className="mb-4"><ErrorBanner message={listError} onRetry={() => { setListLoading(true); loadList() }} /></div>}

      <div className="flex gap-4 min-h-[600px]">
        {/* List panel */}
        <div className={`w-full max-w-[340px] shrink-0 ${card} flex flex-col overflow-hidden`}>
          <div className="px-4 py-2.5 border-b border-zinc-200 dark:border-[#1a1a30] bg-zinc-50 dark:bg-[#0a0a16] shrink-0">
            <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-600">
              Recent Requests
            </p>
          </div>
          <div className="flex-1 overflow-y-auto divide-y divide-zinc-100 dark:divide-[#1a1a30]">
            {listLoading ? (
              <LoadingSkeleton type="table" rows={8} />
            ) : decisions.length === 0 ? (
              <EmptyState title="No requests yet" description="Send requests through the gateway to inspect them." />
            ) : (
              decisions.map((d) => {
                const active = d.request_id === selectedId
                return (
                  <button
                    key={d.request_id}
                    onClick={() => selectRow(d.request_id)}
                    className={`
                      w-full text-left px-4 py-3 flex flex-col gap-1 transition-all duration-150
                      ${active
                        ? 'bg-zinc-50 border-l-2 border-indigo-500 pl-3.5 dark:bg-[#15152a] dark:border-indigo-500 dark:shadow-[inset_0_1px_0_0_rgba(255,255,255,0.05)]'
                        : 'hover:bg-zinc-50 dark:hover:bg-[#121224]'
                      }
                    `}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className={`text-xs font-mono ${active ? 'text-indigo-600 dark:text-indigo-400' : 'text-zinc-500 dark:text-zinc-500'}`}>
                        {truncateId(d.request_id)}
                      </span>
                      <StatusBadge status={d.status} fallback={d.fallback_used} />
                    </div>
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-mono text-zinc-700 dark:text-zinc-300 truncate" title={d.selected_model}>
                        {d.selected_model}
                      </span>
                      <span className="shrink-0 text-xs font-mono tabular-nums text-zinc-500 dark:text-zinc-500">
                        ${d.cost_usd.toFixed(6)}
                      </span>
                    </div>
                    <p className="text-xs text-zinc-400 dark:text-zinc-600">
                      {fmtDate(d.created_at)} · {fmtTime(d.created_at)} · {d.latency_ms}ms
                    </p>
                  </button>
                )
              })
            )}
          </div>
          {!listLoading && decisions.length > 0 && (
            <div className="px-4 py-2 border-t border-zinc-100 dark:border-[#1a1a30] bg-zinc-50 dark:bg-[#0a0a16] shrink-0">
              <p className="text-xs text-zinc-400 dark:text-zinc-600">
                {decisions.length} request{decisions.length !== 1 ? 's' : ''}
              </p>
            </div>
          )}
        </div>

        {/* Detail panel */}
        <div className={`flex-1 ${card} overflow-hidden`}>
          <DetailPanel detail={detail} loading={detailLoading} error={detailError} />
        </div>
      </div>
    </div>
  )
}
