import { motion } from 'framer-motion'

function chipKind(e: string) {
  const s = e.toLowerCase()
  if (s.includes('dispatch triggered') || s.includes('dispatch')) return 'dispatch'
  if (s.includes('miraie')) return 'ack'
  if (s.includes('stress')) return 'stress'
  return 'info'
}

function Chip(props: { text: string }) {
  const kind = chipKind(props.text)
  const cls =
    kind === 'dispatch'
      ? 'border-[rgba(0,212,255,0.40)] text-[rgba(0,212,255,0.95)]'
      : kind === 'ack'
        ? 'border-[rgba(215,226,255,0.22)] text-[rgba(215,226,255,0.88)]'
        : kind === 'stress'
          ? 'border-[rgba(255,170,0,0.35)] text-[rgba(255,170,0,0.92)]'
          : 'border-[rgba(64,87,140,0.35)] text-[rgba(215,226,255,0.85)]'

  const prefix =
    kind === 'dispatch'
      ? '[DISPATCH]'
      : kind === 'ack'
        ? '[MIRAIe ACK]'
        : kind === 'stress'
          ? '[GRID]'
          : '[INFO]'

  return (
    <span className={['inline-flex items-center gap-2 rounded-full border bg-black/20 px-3 py-1', cls].join(' ')}>
      <span className="font-mono text-[10px] tracking-[0.22em] opacity-80">{prefix}</span>
      <span className="font-mono text-xs">{props.text}</span>
    </span>
  )
}

export function EventTicker(props: { events: string[]; dispatchActive?: boolean }) {
  const items = props.events.length ? props.events : ['Waiting for telemetry…']

  return (
    <div className="relative overflow-hidden rounded-2xl border border-[var(--gc-panel-border)] bg-black/25">
      <div className="absolute inset-0 opacity-40">
        <div className="absolute inset-0 bg-gradient-to-r from-[rgba(0,212,255,0.12)] via-transparent to-[rgba(255,170,0,0.10)]" />
      </div>

      <div className="relative flex items-center gap-3 px-4 py-3">
        <div className="flex shrink-0 items-center gap-2">
          <div className="rounded-lg border border-[var(--gc-panel-border)] bg-black/30 px-2 py-1 font-mono text-[10px] tracking-[0.28em] text-[var(--gc-muted)]">
            LIVE FEED
          </div>
          {props.dispatchActive ? (
            <span className="relative inline-flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[rgba(0,212,255,0.75)] opacity-60" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-[rgba(0,212,255,0.95)]" />
            </span>
          ) : null}
        </div>

        <div className="relative min-w-0 flex-1 overflow-hidden">
          <div className="pointer-events-none absolute inset-y-0 left-0 w-12 bg-gradient-to-r from-black/40 to-transparent" />
          <div className="pointer-events-none absolute inset-y-0 right-0 w-12 bg-gradient-to-l from-black/40 to-transparent" />
          <motion.div
            className="flex items-center gap-3 whitespace-nowrap"
            animate={{ x: ['0%', '-50%'] }}
            transition={{ duration: 22, ease: 'linear', repeat: Infinity }}
          >
            {[...items, ...items].map((e, idx) => (
              <Chip key={`${idx}-${e}`} text={e} />
            ))}
          </motion.div>
        </div>
      </div>
    </div>
  )
}

