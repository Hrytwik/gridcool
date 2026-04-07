import { motion } from 'framer-motion'
import type { Severity } from '../lib/dashboardTypes'

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n))
}

function severityMeta(sev: Severity) {
  if (sev === 'critical') return { label: 'CRITICAL', color: 'var(--gc-red)', glow: 'shadow-glowRed' }
  if (sev === 'warning') return { label: 'WARNING', color: 'var(--gc-amber)', glow: 'shadow-glowAmber' }
  return { label: 'NORMAL', color: 'var(--gc-blue)', glow: 'shadow-glow' }
}

export function StressGauge(props: { score: number; severity: Severity }) {
  const meta = severityMeta(props.severity)

  // Map 0..100 to a true top-semicircle sweep (-180..0 degrees).
  // 0 => far left, 100 => far right.
  const angle = -180 + (clamp(props.score, 0, 100) / 100) * 180

  return (
    <div className="grid gap-3 md:grid-cols-[1fr_auto] md:items-center">
      <div>
        <div className="flex items-end gap-3">
          <div className="text-5xl font-semibold tracking-tight">{props.score}</div>
          <div className="pb-2 font-mono text-xs tracking-[0.28em]" style={{ color: meta.color }}>
            {meta.label}
          </div>
        </div>
        <div className="mt-1 text-sm text-[var(--gc-muted)]">
          Demand-response readiness across enrolled MirAIe AC capacity.
        </div>
      </div>

      <div
        className={[
          'relative h-[140px] w-[240px] overflow-hidden rounded-2xl border border-[var(--gc-panel-border)] bg-black/25',
          meta.glow,
        ].join(' ')}
      >
        <div className="absolute left-1/2 top-[18px] h-[110px] w-[220px] -translate-x-1/2 rounded-[999px] border border-white/10 bg-gradient-to-b from-white/5 to-transparent" />

        {/* ticks */}
        <div className="absolute inset-0">
          {Array.from({ length: 11 }).map((_, i) => {
            const a = (-180 + (180 / 10) * i) * (Math.PI / 180)
            const cx = 120
            const cy = 118
            const r1 = 78
            const r2 = i % 5 === 0 ? 60 : 68
            const x1 = cx + r1 * Math.cos(a)
            const y1 = cy + r1 * Math.sin(a)
            const x2 = cx + r2 * Math.cos(a)
            const y2 = cy + r2 * Math.sin(a)
            return (
              <svg key={i} className="absolute inset-0" viewBox="0 0 240 140">
                <line
                  x1={x1}
                  y1={y1}
                  x2={x2}
                  y2={y2}
                  stroke="rgba(255,255,255,0.18)"
                  strokeWidth={i % 5 === 0 ? 2 : 1}
                />
              </svg>
            )
          })}
        </div>

        {/* needle (pivot aligned to tick center at y=118) */}
        <div className="absolute left-1/2 top-[118px] h-0 w-0">
          <motion.div
            animate={{ rotate: angle }}
            transition={{ type: 'spring', stiffness: 90, damping: 14 }}
            className="origin-left"
          >
            <div
              className="h-[3px] w-[82px] rounded-full"
              style={{ background: meta.color, boxShadow: `0 0 18px ${meta.color}` }}
            />
          </motion.div>
          <div className="absolute -left-[8px] -top-[8px] h-4 w-4 rounded-full border border-white/20 bg-black/60" />
          <div className="absolute -left-[5px] -top-[5px] h-[10px] w-[10px] rounded-full" style={{ background: meta.color, boxShadow: `0 0 18px ${meta.color}` }} />
        </div>

        {/* thresholds */}
        <div className="absolute bottom-3 left-3 right-3 flex items-center justify-between font-mono text-[10px] text-[var(--gc-muted)]">
          <div>0</div>
          <div className="text-[var(--gc-amber)]">65</div>
          <div className="text-[var(--gc-red)]">80</div>
          <div>100</div>
        </div>
      </div>
    </div>
  )
}

