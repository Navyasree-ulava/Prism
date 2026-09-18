import { useState, useEffect } from 'react'

export function useTheme() {
  const [dark, setDark] = useState(() => {
    const stored = localStorage.getItem('prism-theme')
    if (stored) return stored === 'dark'
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  })

  useEffect(() => {
    const root = document.documentElement
    if (dark) {
      root.classList.add('dark')
      localStorage.setItem('prism-theme', 'dark')
    } else {
      root.classList.remove('dark')
      localStorage.setItem('prism-theme', 'light')
    }
  }, [dark])

  return { dark, toggle: () => setDark((d) => !d) }
}
