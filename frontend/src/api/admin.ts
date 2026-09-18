import { apiClient } from './client'
import type {
  RoutingStats,
  ModelPerformance,
  DecisionSummary,
  DecisionDetail,
} from '../types'

export async function fetchRoutingStats(): Promise<RoutingStats> {
  const res = await apiClient.get<RoutingStats>('/admin/routing-stats')
  return res.data
}

export async function fetchModelsPerformance(): Promise<ModelPerformance[]> {
  const res = await apiClient.get<ModelPerformance[]>('/admin/models-performance')
  return res.data
}

export async function fetchDecisions(limit = 50): Promise<DecisionSummary[]> {
  const res = await apiClient.get<DecisionSummary[]>('/admin/decisions', {
    params: { limit },
  })
  return res.data
}

export async function fetchDecisionDetail(requestId: string): Promise<DecisionDetail> {
  const res = await apiClient.get<DecisionDetail>(`/admin/decisions/${requestId}`)
  return res.data
}
