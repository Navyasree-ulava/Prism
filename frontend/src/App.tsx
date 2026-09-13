import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import Overview from './pages/Overview'
import ModelPerformance from './pages/ModelPerformance'
import RoutingDistribution from './pages/RoutingDistribution'
import RequestInspector from './pages/RequestInspector'

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50">
        <nav className="bg-white border-b border-gray-200 px-6 py-3 flex gap-6">
          <span className="font-bold text-lg text-indigo-600 mr-4">Prism</span>
          {[
            { to: '/', label: 'Overview' },
            { to: '/models', label: 'Model Performance' },
            { to: '/routing', label: 'Routing Distribution' },
            { to: '/requests', label: 'Request Inspector' },
          ].map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `text-sm font-medium ${isActive ? 'text-indigo-600' : 'text-gray-500 hover:text-gray-700'}`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>

        <main className="p-6">
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/models" element={<ModelPerformance />} />
            <Route path="/routing" element={<RoutingDistribution />} />
            <Route path="/requests" element={<RequestInspector />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
