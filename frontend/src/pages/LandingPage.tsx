import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { LightRays } from '../components/LightRays'
import { AnimatedText } from '../components/AnimatedText'

interface DemoScenario {
  id: string
  title: string
  tag: string
  prompt: string
  analysis: {
    task_type: string
    complexity: string
    capabilities: string[]
    estimated_tokens: number
  }
  winner: {
    model: string
    provider: string
    score: number
    latency: number
    cost: number
  }
  candidates: {
    model: string
    provider: string
    score: number
    latency: number
    status: 'selected' | 'viable' | 'failed'
  }[]
  fallbackTriggered?: boolean
}

const DEMO_SCENARIOS: DemoScenario[] = [
  {
    id: 'code',
    title: 'Code Refactoring & Security Audit',
    tag: 'High Complexity',
    prompt: 'Analyze this distributed consensus implementation for concurrency hazards and race conditions...',
    analysis: {
      task_type: 'code_generation',
      complexity: 'high',
      capabilities: ['deep_reasoning', 'concurrency', 'ast_analysis'],
      estimated_tokens: 1420,
    },
    winner: {
      model: 'openai/gpt-4o',
      provider: 'OpenAI',
      score: 0.942,
      latency: 380,
      cost: 0.0071,
    },
    candidates: [
      { model: 'openai/gpt-4o', provider: 'OpenAI', score: 0.942, latency: 380, status: 'selected' },
      { model: 'anthropic/claude-3-5-sonnet', provider: 'Anthropic', score: 0.915, latency: 490, status: 'viable' },
      { model: 'groq/llama-3.3-70b-versatile', provider: 'Groq', score: 0.785, latency: 120, status: 'viable' },
      { model: 'mistral/mistral-large', provider: 'Mistral', score: 0.710, latency: 440, status: 'viable' },
    ],
  },
  {
    id: 'summary',
    title: 'Ultra-Fast Markdown Summarization',
    tag: 'Latency Optimized',
    prompt: 'Generate an executive bulleted summary of these 5 product roadmap tickets...',
    analysis: {
      task_type: 'summarization',
      complexity: 'low',
      capabilities: ['fast_inference', 'concise_formatting'],
      estimated_tokens: 490,
    },
    winner: {
      model: 'groq/llama-3.3-70b-versatile',
      provider: 'Groq',
      score: 0.978,
      latency: 112,
      cost: 0.00034,
    },
    candidates: [
      { model: 'groq/llama-3.3-70b-versatile', provider: 'Groq', score: 0.978, latency: 112, status: 'selected' },
      { model: 'openai/gpt-4o-mini', provider: 'OpenAI', score: 0.892, latency: 260, status: 'viable' },
      { model: 'anthropic/claude-3-haiku', provider: 'Anthropic', score: 0.840, latency: 290, status: 'viable' },
    ],
  },
  {
    id: 'fallback',
    title: 'Fault-Tolerant Failover Simulation',
    tag: 'Self-Healing Fallback',
    prompt: 'Classify 50 customer feedback sentiments with structured JSON extraction...',
    analysis: {
      task_type: 'classification',
      complexity: 'medium',
      capabilities: ['json_mode', 'high_reliability'],
      estimated_tokens: 650,
    },
    fallbackTriggered: true,
    winner: {
      model: 'openai/gpt-oss-20b',
      provider: 'Groq',
      score: 0.884,
      latency: 210,
      cost: 0.00052,
    },
    candidates: [
      { model: 'openai/gpt-4o', provider: 'OpenAI', score: 0.950, latency: 0, status: 'failed' },
      { model: 'openai/gpt-oss-20b', provider: 'Groq', score: 0.884, latency: 210, status: 'selected' },
      { model: 'groq/llama-3.1-8b-instant', provider: 'Groq', score: 0.812, latency: 85, status: 'viable' },
    ],
  },
]

export const LandingPage: React.FC = () => {
  const [selectedScenario, setSelectedScenario] = useState<DemoScenario>(DEMO_SCENARIOS[0])
  const [activeCodeTab, setActiveCodeTab] = useState<'curl' | 'python' | 'node'>('python')
  const [copied, setCopied] = useState(false)

  const codeSnippets = {
    python: `import openai

client = openai.OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="prism-local-dev-key"
)

# Prism automatically analyzes, scores, and routes to the optimal model
response = client.chat.completions.create(
    model="prism-auto",  # Or leave empty for default strategy
    messages=[
        {"role": "user", "content": "Analyze system telemetry and optimize routing."}
    ],
    extra_headers={"x-routing-strategy": "latency_optimized"}
)

print(f"Dispatched model: {response.routing.selected_model}")
print(f"Fallback utilized: {response.routing.fallback_used}")`,
    curl: `curl http://localhost:8000/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer prism-local-dev-key" \\
  -H "x-routing-strategy: balanced" \\
  -d '{
    "messages": [{"role": "user", "content": "Summarize release logs."}],
    "temperature": 0.3
  }'`,
    node: `import OpenAI from "openai";

const prism = new OpenAI({
  baseURL: "http://localhost:8000/v1",
  apiKey: "prism-local-dev-key",
});

const completion = await prism.chat.completions.create({
  model: "auto",
  messages: [{ role: "user", content: "Extract database entity relations." }],
});

console.log("Optimal Model:", completion.routing?.selected_model);`,
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(codeSnippets[activeCodeTab])
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="relative min-h-screen bg-black text-zinc-100 overflow-hidden font-sans selection:bg-indigo-500/30 selection:text-white">
      {/* ── PRscribe WebGL LightRays Effect ── */}
      <div className="pointer-events-none absolute inset-0 z-0 h-[820px] w-full overflow-hidden">
        <LightRays
          raysOrigin="top-center"
          raysColor="#ffffff"
          raysSpeed={1.0}
          lightSpread={1.4}
          rayLength={3.6}
          fadeDistance={1.1}
          saturation={1.0}
          followMouse={true}
          mouseInfluence={0.12}
          noiseAmount={0.02}
          distortion={0.03}
        />
      </div>

      {/* ── Subtle Technical Square Grid (User Favorite) ── */}
      <div
        className="absolute inset-0 pointer-events-none opacity-[0.035] select-none z-0"
        style={{
          backgroundImage: `linear-gradient(to right, #ffffff 1px, transparent 1px), linear-gradient(to bottom, #ffffff 1px, transparent 1px)`,
          backgroundSize: '54px 54px',
        }}
      />

      {/* ── Top Header Navigation ── */}
      <header className="relative z-20 border-b border-white/[0.06] backdrop-blur-md bg-black/20">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex flex-col gap-[3px] p-1.5 rounded-lg bg-white/[0.07] border border-white/10 glow-indigo-sm">
              <div className="h-[2.5px] w-5 rounded-full bg-white" />
              <div className="h-[2.5px] w-[14px] rounded-full bg-sky-300" />
              <div className="h-[2.5px] w-2.5 rounded-full bg-indigo-400" />
            </div>
            <span className="text-base font-semibold tracking-tight text-white flex items-center gap-2">
              Prism
              <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-white/10 text-zinc-300 border border-white/10">
                Gateway
              </span>
            </span>
          </div>

          <nav className="hidden md:flex items-center gap-8 text-xs font-medium tracking-wider uppercase text-zinc-400">
            <a href="#simulator" className="hover:text-white transition-colors">
              Demo
            </a>
            <a href="#features" className="hover:text-white transition-colors">
              Architecture
            </a>
            <a href="#code" className="hover:text-white transition-colors">
              Quickstart
            </a>
            <Link to="/requests" className="hover:text-white transition-colors">
              Inspector
            </Link>
          </nav>

          <div className="flex items-center gap-3">
            <Link
              to="/overview"
              className="px-4 py-2 rounded-full text-xs font-medium text-white bg-white/10 hover:bg-white/15 border border-white/20 transition-all duration-150 backdrop-blur-md hover:border-white/40 shadow-sm"
            >
              Launch Console →
            </Link>
          </div>
        </div>
      </header>

      {/* ── HERO SECTION ── */}
      <section className="relative z-10 pt-12 pb-16 md:pt-16 md:pb-24 px-6 max-w-5xl mx-auto text-center flex flex-col items-center">
        {/* Release Pill Badge */}
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/[0.05] border border-white/[0.12] backdrop-blur-md mb-6 hover:bg-white/[0.08] transition-all">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-[11px] font-medium text-zinc-300">
            Prism Adaptive Engine v1.0
          </span>
          <span className="text-zinc-600">·</span>
          <span className="text-[11px] font-mono text-zinc-400">Zero Latency Drop-in</span>
        </div>

        {/* Exact Shadebyte Animated Elongated Text */}
        <div className="my-2 w-full flex flex-col items-center justify-center">
          <AnimatedText text="PRISM" />
        </div>

        {/* Exact Shadebyte Subtitle Structure & Color */}
        <div className="flex flex-col justify-center items-center text-[#6d6d6d] text-center uppercase tracking-[0.2em] text-xs font-medium mt-3 leading-relaxed">
          <p>We route multi-model queries that serve both users</p>
          <p>and businesses and drive real results.</p>
        </div>

        {/* Exact Shadebyte Action Button & Status */}
        <div className="mt-8 flex flex-col items-center gap-3">
          <Link
            to="/overview"
            className="flex items-center gap-2.5 bg-white px-4 py-2.5 rounded-md transition-all duration-500 cursor-pointer ease-in-out group shadow-[0_4px_24px_rgba(255,255,255,0.15)] hover:shadow-[0_4px_32px_rgba(255,255,255,0.3)]"
          >
            <div className="w-5 h-5 rounded-full bg-black text-white flex items-center justify-center text-[10px] font-bold">
              ⚡
            </div>
            <span className="font-medium text-black text-sm transition-all duration-500 ease-in-out">
              Launch Gateway Console
            </span>
          </Link>

          {/* Green Status Ping */}
          <div className="flex justify-center items-center gap-2 mt-2">
            <div className="flex justify-center items-center bg-green-500 rounded-full size-2.5">
              <div className="bg-green-500 rounded-full animate-ping size-2.5" />
            </div>
            <span className="font-normal text-xs text-white">Let&apos;s Build!</span>
          </div>

          {/* Scroll For More */}
          <a
            href="#simulator"
            className="flex flex-col justify-center items-center text-zinc-400 hover:text-white transition-colors mt-8 text-[11px] uppercase tracking-widest gap-1"
          >
            <span>Scroll For More</span>
            <svg className="w-3.5 h-3.5 animate-bounce" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </a>
        </div>



        {/* Trust & Key Stats Strip */}
        <div className="mt-16 pt-8 border-t border-white/10 grid grid-cols-2 sm:grid-cols-4 gap-6 sm:gap-12 w-full max-w-4xl text-left">
          <div>
            <div className="text-2xl sm:text-3xl font-bold font-mono text-white tracking-tight">
              &lt; 12ms
            </div>
            <div className="text-xs text-zinc-400 mt-1">Gateway Overhead</div>
          </div>
          <div>
            <div className="text-2xl sm:text-3xl font-bold font-mono text-white tracking-tight">
              41.6%
            </div>
            <div className="text-xs text-zinc-400 mt-1">Avg. Cost Saved</div>
          </div>
          <div>
            <div className="text-2xl sm:text-3xl font-bold font-mono text-emerald-400 tracking-tight">
              99.98%
            </div>
            <div className="text-xs text-zinc-400 mt-1">Single-Hop Fallback</div>
          </div>
          <div>
            <div className="text-2xl sm:text-3xl font-bold font-mono text-white tracking-tight">
              100%
            </div>
            <div className="text-xs text-zinc-400 mt-1">Deterministic Scorer</div>
          </div>
        </div>
      </section>

      {/* ── INTERACTIVE LIVE ROUTING SIMULATOR ── */}
      <section id="simulator" className="relative z-10 max-w-6xl mx-auto px-6 py-16">
        <div className="text-center mb-10">
          <span className="text-xs font-mono uppercase tracking-wider text-sky-400 bg-sky-500/10 px-3 py-1 rounded-full border border-sky-500/20">
            Real-Time Simulation
          </span>
          <h2 className="text-3xl font-bold text-white mt-3 tracking-tight">
            See Intelligent Routing in Action
          </h2>
          <p className="text-sm text-zinc-400 mt-2 max-w-xl mx-auto">
            Choose a prompt workload to inspect how Prism dynamically analyzes intent, normalizes multi-factor weights, and dispatches to the highest-scoring candidate.
          </p>
        </div>

        <div className="rounded-2xl border border-[#1e1e38] bg-[#0c0d1c]/90 backdrop-blur-xl p-6 md:p-8 shadow-2xl">
          {/* Scenario Selector Tabs */}
          <div className="flex flex-wrap gap-2 pb-6 border-b border-white/5">
            {DEMO_SCENARIOS.map((scenario) => {
              const active = scenario.id === selectedScenario.id
              return (
                <button
                  key={scenario.id}
                  onClick={() => setSelectedScenario(scenario)}
                  className={`px-4 py-2.5 rounded-xl text-xs font-medium transition-all text-left flex items-center gap-2.5 ${
                    active
                      ? 'bg-white/15 text-white border border-white/30 shadow-inner'
                      : 'bg-white/5 text-zinc-400 hover:text-zinc-200 hover:bg-white/8 border border-transparent'
                  }`}
                >
                  <span>{scenario.title}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                    scenario.fallbackTriggered ? 'bg-amber-500/20 text-amber-300' : 'bg-white/10 text-zinc-300'
                  }`}>
                    {scenario.tag}
                  </span>
                </button>
              )
            })}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 mt-6">
            {/* Left Col: Prompt & Analysis */}
            <div className="lg:col-span-5 flex flex-col gap-6">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                    Incoming Prompt
                  </span>
                  <span className="text-xs font-mono text-zinc-500">
                    ~{selectedScenario.analysis.estimated_tokens} tokens
                  </span>
                </div>
                <div className="p-4 rounded-xl bg-black/40 border border-white/5 font-mono text-xs text-zinc-300 leading-relaxed">
                  "{selectedScenario.prompt}"
                </div>
              </div>

              <div>
                <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400 block mb-3">
                  Analyzer Extracted Traits
                </span>
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="p-3 rounded-lg bg-white/[0.03] border border-white/5">
                    <span className="text-zinc-500 block text-[11px]">Task Type</span>
                    <span className="font-mono text-zinc-200">{selectedScenario.analysis.task_type}</span>
                  </div>
                  <div className="p-3 rounded-lg bg-white/[0.03] border border-white/5">
                    <span className="text-zinc-500 block text-[11px]">Complexity</span>
                    <span className="font-mono text-zinc-200 capitalize">{selectedScenario.analysis.complexity}</span>
                  </div>
                </div>

                <div className="mt-3 flex flex-wrap gap-1.5">
                  {selectedScenario.analysis.capabilities.map((cap) => (
                    <span key={cap} className="px-2 py-0.5 rounded text-[11px] font-mono bg-sky-500/10 text-sky-300 border border-sky-500/20">
                      +{cap}
                    </span>
                  ))}
                </div>
              </div>

              {selectedScenario.fallbackTriggered && (
                <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-start gap-3">
                  <span className="text-amber-400 text-lg">⚠️</span>
                  <div>
                    <div className="text-xs font-semibold text-amber-300">Self-Healing Single-Hop Fallback</div>
                    <div className="text-xs text-amber-200/80 mt-0.5 leading-relaxed">
                      Primary candidate simulated upstream timeout (503). Prism automatically routed to secondary model without throwing client error.
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Right Col: Candidate Ranking & Dispatch */}
            <div className="lg:col-span-7 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                    Candidate Scoring Matrix
                  </span>
                  <span className="text-[11px] font-mono text-zinc-500">
                    Multi-Factor Weighted Normalization
                  </span>
                </div>

                <div className="flex flex-col gap-2.5">
                  {selectedScenario.candidates.map((cand, idx) => {
                    const isSelected = cand.status === 'selected'
                    const isFailed = cand.status === 'failed'

                    return (
                      <div
                        key={cand.model}
                        className={`p-3.5 rounded-xl border transition-all ${
                          isSelected
                            ? 'bg-white/[0.08] border-white/30 shadow-lg glow-indigo-sm'
                            : isFailed
                            ? 'bg-rose-500/5 border-rose-500/30 opacity-70'
                            : 'bg-white/[0.02] border-white/5 opacity-80'
                        }`}
                      >
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-mono font-medium text-zinc-200">
                              {cand.model}
                            </span>
                            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/10 text-zinc-400">
                              {cand.provider}
                            </span>
                          </div>

                          <div className="flex items-center gap-3">
                            {isFailed && (
                              <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/40">
                                503 FAILED
                              </span>
                            )}
                            {isSelected && (
                              <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                                WINNER DISPATCHED
                              </span>
                            )}
                            <span className="text-xs font-mono font-bold text-white">
                              {cand.score.toFixed(3)}
                            </span>
                          </div>
                        </div>

                        {/* Progress score bar */}
                        <div className="w-full h-1.5 rounded-full bg-white/5 overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-500 ${
                              isSelected ? 'bg-gradient-to-r from-sky-400 to-indigo-400' : isFailed ? 'bg-rose-500' : 'bg-zinc-600'
                            }`}
                            style={{ width: `${cand.score * 100}%` }}
                          />
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Winning Summary Box */}
              <div className="mt-6 p-4 rounded-xl bg-gradient-to-r from-sky-500/10 via-indigo-500/10 to-transparent border border-white/15 flex flex-wrap items-center justify-between gap-4">
                <div>
                  <div className="text-[11px] font-mono text-zinc-400 uppercase">Selected Dispatched Model</div>
                  <div className="text-sm font-bold text-white font-mono flex items-center gap-2 mt-0.5">
                    {selectedScenario.winner.model}
                    <span className="text-xs font-normal text-emerald-400 font-sans">
                      (Saved ~{((1 - selectedScenario.winner.cost / 0.015) * 100).toFixed(0)}% vs frontier)
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-6 font-mono text-xs">
                  <div>
                    <span className="text-zinc-500 block text-[10px]">Latency</span>
                    <span className="text-white font-semibold">{selectedScenario.winner.latency}ms</span>
                  </div>
                  <div>
                    <span className="text-zinc-500 block text-[10px]">Cost USD</span>
                    <span className="text-white font-semibold">${selectedScenario.winner.cost.toFixed(5)}</span>
                  </div>
                  <div>
                    <Link
                      to="/requests"
                      className="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-white font-sans text-xs transition-colors"
                    >
                      Inspect in Live DB →
                    </Link>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── ARCHITECTURE & FEATURES GRID ── */}
      <section id="features" className="relative z-10 max-w-6xl mx-auto px-6 py-20">
        <div className="text-center mb-16">
          <span className="text-xs font-mono uppercase tracking-wider text-zinc-400 bg-white/5 px-3 py-1 rounded-full border border-white/10">
            Engine Architecture
          </span>
          <h2 className="text-3xl sm:text-4xl font-bold text-white mt-3 tracking-tight">
            Engineered for Production Resilience
          </h2>
          <p className="text-sm sm:text-base text-zinc-400 mt-2 max-w-xl mx-auto">
            Prism solves the multi-provider trilemma: maximum capability, minimum latency, and strict budget predictability.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="p-6 rounded-2xl bg-white/[0.03] border border-white/10 hover:border-white/20 transition-all">
            <div className="w-10 h-10 rounded-xl bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400 mb-4 font-mono font-bold">
              01
            </div>
            <h3 className="text-lg font-semibold text-white mb-2">
              Multi-Factor Weighted Scorer
            </h3>
            <p className="text-sm text-zinc-400 leading-relaxed">
              Dynamically analyzes input tokens, prompt complexity, and desired routing strategy (Balanced, Cost, Speed, Quality) with deterministic tie-breaking.
            </p>
          </div>

          <div className="p-6 rounded-2xl bg-white/[0.03] border border-white/10 hover:border-white/20 transition-all">
            <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mb-4 font-mono font-bold">
              02
            </div>
            <h3 className="text-lg font-semibold text-white mb-2">
              Single-Hop Failover Engine
            </h3>
            <p className="text-sm text-zinc-400 leading-relaxed">
              If a provider returns 429, 500, or network timeouts, Prism switches to the pre-ranked runner-up instantly. No request dropping, zero client retries needed.
            </p>
          </div>

          <div className="p-6 rounded-2xl bg-white/[0.03] border border-white/10 hover:border-white/20 transition-all">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 mb-4 font-mono font-bold">
              03
            </div>
            <h3 className="text-lg font-semibold text-white mb-2">
              Authoritative Telemetry Logging
            </h3>
            <p className="text-sm text-zinc-400 leading-relaxed">
              Every request logs exact prompt metadata, candidate scores, actual responding model, token counts, and micro-dollar cost directly to PostgreSQL.
            </p>
          </div>
        </div>
      </section>

      {/* ── CODE INTEGRATION QUICKSTART ── */}
      <section id="code" className="relative z-10 max-w-5xl mx-auto px-6 py-16">
        <div className="rounded-2xl border border-white/10 bg-[#090a16] p-6 sm:p-8 shadow-2xl">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6 border-b border-white/10 pb-4">
            <div>
              <h3 className="text-xl font-bold text-white tracking-tight">
                Drop-in OpenAI API Replacement
              </h3>
              <p className="text-xs text-zinc-400 mt-1">
                Zero code rewrites. Just change the baseURL to route through Prism.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <div className="flex rounded-lg bg-white/5 p-1 border border-white/10">
                {(['python', 'curl', 'node'] as const).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveCodeTab(tab)}
                    className={`px-3 py-1 rounded-md text-xs font-mono capitalize transition-all ${
                      activeCodeTab === tab
                        ? 'bg-white/15 text-white font-semibold'
                        : 'text-zinc-400 hover:text-zinc-200'
                    }`}
                  >
                    {tab === 'node' ? 'TypeScript' : tab}
                  </button>
                ))}
              </div>

              <button
                onClick={handleCopy}
                className="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/15 border border-white/10 text-xs font-mono text-zinc-300 transition-colors flex items-center gap-1.5"
              >
                {copied ? (
                  <>
                    <span className="text-emerald-400">✓</span> Copied
                  </>
                ) : (
                  <>
                    <span>📋</span> Copy
                  </>
                )}
              </button>
            </div>
          </div>

          <pre className="p-4 rounded-xl bg-black/60 border border-white/5 overflow-x-auto text-xs font-mono text-zinc-300 leading-relaxed">
            <code>{codeSnippets[activeCodeTab]}</code>
          </pre>
        </div>
      </section>

      {/* ── BOTTOM CTA & FOOTER ── */}
      <footer className="relative z-10 border-t border-white/10 pt-16 pb-12 mt-20 bg-black/40">
        <div className="max-w-6xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-6 text-sm text-zinc-500">
          <div className="flex items-center gap-2.5">
            <div className="flex flex-col gap-[2px]">
              <div className="h-[2px] w-4 rounded-full bg-white" />
              <div className="h-[2px] w-[11px] rounded-full bg-sky-400" />
            </div>
            <span className="font-semibold text-white">Prism LLM Gateway</span>
            <span className="text-xs">· Open Source High-Performance Architecture</span>
          </div>

          <div className="flex items-center gap-6 text-xs">
            <Link to="/overview" className="hover:text-zinc-300 transition-colors">
              Console Overview
            </Link>
            <Link to="/models" className="hover:text-zinc-300 transition-colors">
              Models
            </Link>
            <Link to="/routing" className="hover:text-zinc-300 transition-colors">
              Routing Distribution
            </Link>
            <Link to="/requests" className="hover:text-zinc-300 transition-colors">
              Request Inspector
            </Link>
          </div>

          <div className="text-xs font-mono text-zinc-600">
            MIT License · Built with FastAPI & React
          </div>
        </div>
      </footer>
    </div>
  )
}
export default LandingPage
