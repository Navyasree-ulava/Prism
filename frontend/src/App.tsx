import { BrowserRouter, Routes, Route, NavLink, useLocation } from 'react-router-dom'
import Overview from './pages/Overview'
import ModelPerformance from './pages/ModelPerformance'
import RoutingDistribution from './pages/RoutingDistribution'
import RequestInspector from './pages/RequestInspector'
import LandingPage from './pages/LandingPage'
import { useTheme } from './hooks/useTheme'

const NAV_ITEMS = [
  { to: '/', label: 'Home', end: true },
  { to: '/overview', label: 'Overview', end: false },
  { to: '/models', label: 'Models', end: false },
  { to: '/routing', label: 'Routing', end: false },
  { to: '/requests', label: 'Inspector', end: false },
]

function SunIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="5" />
      <line x1="12" y1="1" x2="12" y2="3" />
      <line x1="12" y1="21" x2="12" y2="23" />
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
      <line x1="1" y1="12" x2="3" y2="12" />
      <line x1="21" y1="12" x2="23" y2="12" />
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
    </svg>
  )
}

function MoonIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  )
}

function Layout() {
  const { dark, toggle } = useTheme()
  const location = useLocation()
  const isLanding = location.pathname === '/'

  if (isLanding) {
    return (
      <Routes>
        <Route path="/" element={<LandingPage />} />
      </Routes>
    )
  }

  return (
    <div className="min-h-screen bg-[#f4f4fb] dark:bg-transparent transition-colors duration-200">
      {/* ── Console Navigation ── */}
      <header className="
        sticky top-0 z-20
        bg-white/80 dark:bg-[#0a0a18]/80
        backdrop-blur-md
        border-b border-zinc-200 dark:border-[#1a1a32]
        transition-colors duration-200
      ">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center gap-6">

          {/* Wordmark */}
          <NavLink to="/" className="flex items-center gap-2.5 shrink-0 group">
            <div className="flex flex-col gap-[3px] dark:glow-logo transition-transform group-hover:scale-105" aria-hidden="true">
              <div className="h-[3px] w-5 rounded-full bg-indigo-500 dark:bg-indigo-400" />
              <div className="h-[3px] w-[14px] rounded-full bg-indigo-400 dark:bg-indigo-500/70" />
              <div className="h-[3px] w-2 rounded-full bg-indigo-300 dark:bg-indigo-600/50" />
            </div>
            <span className="text-sm font-semibold text-zinc-900 dark:text-white tracking-tight">
              Prism
            </span>
            <span className="
              text-[10px] font-mono px-1.5 py-0.5 rounded
              border border-zinc-200 text-zinc-500
              dark:border-indigo-500/30 dark:text-indigo-400 dark:bg-indigo-500/5
              ml-1
            ">
              gateway
            </span>
          </NavLink>

          {/* Nav links */}
          <nav className="flex items-center gap-0.5" aria-label="Main navigation">
            {NAV_ITEMS.map(({ to, label, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded-md text-sm transition-all duration-150 ${
                    isActive
                      ? 'bg-indigo-50 text-indigo-700 font-medium dark:bg-indigo-500/10 dark:text-indigo-400 dark:glow-indigo-sm'
                      : 'text-zinc-500 hover:text-zinc-800 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:text-zinc-100 dark:hover:bg-white/5'
                  }`
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>

          {/* Theme toggle */}
          <button
            onClick={toggle}
            aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
            className="
              ml-auto flex items-center justify-center
              w-8 h-8 rounded-lg
              text-zinc-500 hover:text-zinc-800
              hover:bg-zinc-100
              dark:text-zinc-400 dark:hover:text-zinc-100 dark:hover:bg-white/8
              border border-transparent
              dark:border-[#1e1e38] dark:hover:border-indigo-500/30
              transition-all duration-150
            "
          >
            {dark ? <SunIcon /> : <MoonIcon />}
          </button>
        </div>
      </header>

      {/* Page content */}
      <main className="max-w-6xl mx-auto px-6 py-8">
        <Routes>
          <Route path="/overview" element={<Overview />} />
          <Route path="/models" element={<ModelPerformance />} />
          <Route path="/routing" element={<RoutingDistribution />} />
          <Route path="/requests" element={<RequestInspector />} />
        </Routes>
      </main>
    </div>
  )
}

function App() {
  return (
    <BrowserRouter>
      <Layout />
    </BrowserRouter>
  )
}

export default App

