import React, { useEffect, useRef, useState } from 'react'

interface ElongatedTextProps {
  text: string
  subtitle?: string
  className?: string
  baseScaleY?: number
  hoverScaleY?: number
}

export const ElongatedText: React.FC<ElongatedTextProps> = ({
  text,
  subtitle,
  className = '',
  baseScaleY = 1.0,
  hoverScaleY = 1.36,
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const [isHovered, setIsHovered] = useState(false)
  const [mouseNormX, setMouseNormX] = useState<number | null>(null)
  const [scrollStretch, setScrollStretch] = useState(0)

  // Silky scroll velocity response
  useEffect(() => {
    let lastScrollY = window.scrollY
    let rafId: number

    const handleScroll = () => {
      const currentScrollY = window.scrollY
      const delta = Math.abs(currentScrollY - lastScrollY)
      lastScrollY = currentScrollY

      // Very subtle, smooth scroll stretch
      const stretch = Math.min(0.08, delta * 0.003)
      setScrollStretch(stretch)

      cancelAnimationFrame(rafId)
      rafId = requestAnimationFrame(() => {
        setScrollStretch((prev) => Math.max(0, prev * 0.9))
      })
    }

    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => {
      window.removeEventListener('scroll', handleScroll)
      cancelAnimationFrame(rafId)
    }
  }, [])

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current) return
    const rect = containerRef.current.getBoundingClientRect()
    const normX = (e.clientX - rect.left) / rect.width
    setMouseNormX(Math.max(0, Math.min(1, normX)))
  }

  const handleMouseEnter = () => {
    setIsHovered(true)
  }

  const handleMouseLeave = () => {
    setIsHovered(false)
    setMouseNormX(null)
  }

  const characters = text.split('')

  return (
    <div
      ref={containerRef}
      onMouseEnter={handleMouseEnter}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      className={`group cursor-pointer select-none flex flex-col items-center justify-center ${className}`}
    >
      {/* ── Main Elongating Letters (Exact Shadebyte Proportions) ── */}
      <div className="flex items-end justify-center overflow-visible py-1">
        {characters.map((char, index) => {
          if (char === ' ') {
            return (
              <span key={index} className="inline-block w-4 sm:w-6 md:w-8">
                &nbsp;
              </span>
            )
          }

          // Gentle, slow wave across letters
          let dynamicScale = isHovered ? hoverScaleY : baseScaleY

          if (isHovered && mouseNormX !== null) {
            const charNormX = index / (characters.length - 1 || 1)
            const distance = Math.abs(charNormX - mouseNormX)
            // Soft curve with max 0.08 variance for seamless unity
            const peakInfluence = Math.exp(-Math.pow(distance / 0.35, 2))
            dynamicScale = baseScaleY + (hoverScaleY - baseScaleY) * (0.9 + peakInfluence * 0.15)
          }

          const totalScaleY = dynamicScale + scrollStretch

          return (
            <span
              key={index}
              className="inline-block text-white will-change-transform"
              style={{
                fontFamily: "'Antonio', 'Bebas Neue', sans-serif",
                fontWeight: 500,
                letterSpacing: '0.015em',
                transform: `scaleY(${totalScaleY})`,
                transformOrigin: 'bottom center',
                // Slow, luxurious, buttery smooth transition - zero jarring jumps
                transition: isHovered
                  ? 'transform 0.75s cubic-bezier(0.16, 1, 0.3, 1)'
                  : 'transform 0.85s cubic-bezier(0.2, 1, 0.35, 1)',
              }}
            >
              {char}
            </span>
          )
        })}
      </div>

      {/* ── Subtitle Underneath (Exact Shadebyte Layout & Typography) ── */}
      {subtitle && (
        <p className="text-[11px] sm:text-xs tracking-[0.18em] text-zinc-400 uppercase text-center max-w-2xl mt-5 px-4 font-normal leading-relaxed transition-colors duration-300 group-hover:text-zinc-300">
          {subtitle}
        </p>
      )}
    </div>
  )
}
export default ElongatedText
