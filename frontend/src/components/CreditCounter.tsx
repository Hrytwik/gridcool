import { motion, useMotionValue, useSpring } from 'framer-motion'
import { useEffect, useState } from 'react'
import { Odometer } from './Odometer'

export function CreditCounter(props: { value: number; accent: 'blue' | 'amber' | 'red' }) {
  const mv = useMotionValue(0)
  const spring = useSpring(mv, { stiffness: 120, damping: 22, mass: 0.7 })
  const [displayValue, setDisplayValue] = useState(() => props.value)
  const [maxSeen, setMaxSeen] = useState(() => props.value)

  useEffect(() => {
    // Avoid visible “backwards” jumps on reconnect by clamping to the max seen.
    const clamped = Math.max(maxSeen, props.value)
    setMaxSeen(clamped)
    mv.set(clamped)
  }, [props.value, mv, maxSeen])

  useEffect(() => {
    const unsub = spring.on('change', (v) => {
      setDisplayValue(Math.max(0, v))
    })
    return () => unsub()
  }, [spring])

  const accent =
    props.accent === 'red'
      ? 'var(--gc-red)'
      : props.accent === 'amber'
        ? 'var(--gc-amber)'
        : 'var(--gc-blue)'

  return (
    <div className="relative overflow-hidden rounded-2xl border border-[var(--gc-panel-border)] bg-black/25 p-4">
      <div className="absolute inset-0 opacity-40">
        <div
          className="absolute -left-24 -top-24 h-60 w-60 rounded-full blur-2xl"
          style={{ background: `radial-gradient(circle, ${accent}33, transparent 60%)` }}
        />
        <div
          className="absolute -right-20 -bottom-24 h-60 w-60 rounded-full blur-2xl"
          style={{ background: `radial-gradient(circle, ${accent}26, transparent 60%)` }}
        />
      </div>

      <div className="relative">
        <div className="text-xs uppercase tracking-[0.26em] text-[var(--gc-muted)]">Credits earned</div>
        <div className="mt-2 flex items-end gap-3">
          <div className="text-3xl font-semibold tracking-tight" style={{ color: accent }}>
            ₹
          </div>
          <motion.div
            key={props.accent}
            initial={{ filter: 'brightness(1)' }}
            animate={{ filter: ['brightness(1)', 'brightness(1.15)', 'brightness(1)'] }}
            transition={{ duration: 1.1, ease: 'easeInOut', repeat: Infinity }}
            className="tracking-tight"
            style={{ textShadow: `0 0 22px ${accent}55` }}
          >
            <Odometer value={displayValue} glow={`${accent}66`} />
          </motion.div>
        </div>
        <div className="mt-2 font-mono text-xs text-[var(--gc-muted)]">
          Payout basis: estimated kWh reduced × ₹ rate (demo mode).
        </div>
      </div>
    </div>
  )
}

