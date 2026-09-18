// Admin API response types for Phase 7 dashboard

export interface RoutingStats {
  total_requests: number
  success_rate: number
  error_rate: number
  avg_latency_ms: number
  total_cost_usd: number
  fallback_rate: number
}

export interface ModelPerformance {
  model_id: string
  provider: string
  total_requests: number
  success_rate: number
  avg_latency_ms: number
  total_cost_usd: number
}

export interface DecisionSummary {
  request_id: string
  created_at: string | null
  selected_model: string
  status: string
  cost_usd: number
  latency_ms: number
  fallback_used: boolean
}

export interface Candidate {
  model_id: string
  score: number
}

export interface PromptMeta {
  task_type: string
  complexity: string
  required_capabilities: string[]
  context_requirement: string
  estimated_input_tokens: number
  confidence: number
}

export interface RoutingDecisionDetail {
  selected_model: string | null
  reason: string | null
  confidence: number | null
  candidates: Candidate[]
}

export interface ModelRunDetail {
  model_id: string | null
  latency_ms: number | null
  tokens_in: number | null
  tokens_out: number | null
  cost_usd: number | null
  status: string | null
  fallback_used: boolean
}

export interface DecisionDetail {
  request_id: string
  created_at: string | null
  strategy: string
  prompt_meta: PromptMeta | null
  routing_decision: RoutingDecisionDetail
  model_run: ModelRunDetail
}
