import React, { useEffect, useRef, useState } from 'react'

export const LightingBeam: React.FC<{ className?: string }> = ({ className = '' }) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const [mousePos, setMousePos] = useState({ x: 50, y: 0 })

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return
      const rect = containerRef.current.getBoundingClientRect()
      const rawX = ((e.clientX - rect.left) / rect.width) * 100
      const clampedX = Math.max(25, Math.min(75, rawX))
      setMousePos({ x: clampedX, y: e.clientY - rect.top })
    }

    window.addEventListener('mousemove', handleMouseMove)
    return () => window.removeEventListener('mousemove', handleMouseMove)
  }, [])

  return (
    <div
      ref={containerRef}
      className={`absolute inset-0 overflow-hidden pointer-events-none select-none z-0 ${className}`}
      aria-hidden="true"
    >
      {/* ── Wide Horizon Ambient Light Glow ── */}
      <div
        className="absolute -top-24 left-1/2 -translate-x-1/2 w-[90vw] max-w-[1400px] h-64 rounded-[100%] blur-3xl opacity-60"
        style={{
          background: 'radial-gradient(ellipse at 50% 30%, rgba(255,255,255,0.3) 0%, rgba(180,215,255,0.18) 35%, rgba(99,130,241,0.06) 65%, transparent 80%)',
          transform: `translateX(calc(-50% + ${(mousePos.x - 50) * 0.3}px))`,
          transition: 'transform 0.6s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      />

      {/* ── Wide Top Horizon Light Edge ── */}
      <div
        className="absolute top-0 left-1/2 -translate-x-1/2 w-[70vw] max-w-[900px] h-[3px] bg-gradient-to-r from-transparent via-white/80 to-transparent opacity-80 blur-[1px]"
        style={{
          transform: `translateX(calc(-50% + ${(mousePos.x - 50) * 0.25}px))`,
          transition: 'transform 0.6s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      />

      {/* ── Wide Primary Spotlight Beam (Spans broadly across entire hero) ── */}
      <div
        className="absolute top-0 left-1/2 -translate-x-1/2 w-[140vw] max-w-[1800px] h-[850px] opacity-70 mix-blend-screen"
        style={{
          // Conic spread broadened from narrow 25deg to a wide 80deg fan
          background: `conic-gradient(from 140deg at 50% 0%, transparent 0deg, rgba(200, 225, 255, 0.03) 15deg, rgba(255, 255, 255, 0.14) 28deg, rgba(220, 235, 255, 0.26) 36deg, rgba(255, 255, 255, 0.35) 40deg, rgba(220, 235, 255, 0.26) 44deg, rgba(255, 255, 255, 0.14) 52deg, rgba(200, 225, 255, 0.03) 65deg, transparent 80deg)`,
          maskImage: 'radial-gradient(ellipse 80% 90% at 50% 0%, black 25%, rgba(0,0,0,0.5) 60%, transparent 88%)',
          WebkitMaskImage: 'radial-gradient(ellipse 80% 90% at 50% 0%, black 25%, rgba(0,0,0,0.5) 60%, transparent 88%)',
          transform: `translateX(calc(-50% + ${(mousePos.x - 50) * 0.5}px))`,
          transition: 'transform 0.5s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      />

      {/* ── Wide Moving Volumetric God Rays (Left Drift) ── */}
      <div
        className="absolute top-0 left-1/2 -translate-x-1/2 w-[130vw] max-w-[1600px] h-[880px] opacity-55 mix-blend-screen animate-beam-drift-left"
        style={{
          background: `conic-gradient(from 135deg at 50% 0%, transparent 0deg, rgba(255,255,255,0.02) 12deg, rgba(190, 220, 255, 0.14) 24deg, transparent 32deg, rgba(255, 255, 255, 0.22) 42deg, transparent 50deg, rgba(200, 225, 255, 0.12) 62deg, transparent 85deg)`,
          maskImage: 'linear-gradient(to bottom, black 15%, rgba(0,0,0,0.5) 55%, transparent 92%)',
          WebkitMaskImage: 'linear-gradient(to bottom, black 15%, rgba(0,0,0,0.5) 55%, transparent 92%)',
        }}
      />

      {/* ── Wide Moving Volumetric God Rays (Right Drift) ── */}
      <div
        className="absolute top-0 left-1/2 -translate-x-1/2 w-[125vw] max-w-[1550px] h-[850px] opacity-45 mix-blend-screen animate-beam-drift-right"
        style={{
          background: `conic-gradient(from 145deg at 50% 0%, transparent 0deg, rgba(255,255,255,0.16) 18deg, transparent 28deg, rgba(210, 230, 255, 0.24) 40deg, transparent 48deg, rgba(255, 255, 255, 0.12) 58deg, transparent 78deg)`,
          maskImage: 'linear-gradient(to bottom, black 20%, rgba(0,0,0,0.4) 65%, transparent 95%)',
          WebkitMaskImage: 'linear-gradient(to bottom, black 20%, rgba(0,0,0,0.4) 65%, transparent 95%)',
        }}
      />

      {/* ── Broad Radial Atmospheric Fill Over Hero ── */}
      <div
        className="absolute top-0 left-1/2 -translate-x-1/2 w-[80vw] max-w-[1100px] h-[600px] opacity-35 mix-blend-screen"
        style={{
          background: 'radial-gradient(ellipse 65% 55% at 50% 0%, rgba(255,255,255,0.4) 0%, rgba(180,215,255,0.18) 35%, transparent 75%)',
        }}
      />

      {/* ── Subtle Atmospheric Dust Motes / Particles ── */}
      <div className="absolute top-10 left-1/2 -translate-x-1/2 w-[700px] h-[450px] opacity-30">
        <div className="absolute top-12 left-1/4 w-1 h-1 bg-white rounded-full animate-float-slow blur-[0.5px]" />
        <div className="absolute top-24 left-1/2 w-1.5 h-1.5 bg-sky-200 rounded-full animate-float-medium blur-[0.5px]" />
        <div className="absolute top-36 left-3/4 w-1 h-1 bg-white rounded-full animate-float-fast blur-[0.5px]" />
        <div className="absolute top-48 left-1/3 w-1.5 h-1.5 bg-blue-100 rounded-full animate-float-slow blur-[0.5px]" />
        <div className="absolute top-64 left-2/3 w-1 h-1 bg-white rounded-full animate-float-medium blur-[0.5px]" />
      </div>
    </div>
  )
}
