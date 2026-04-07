import { AnimatePresence, motion } from 'framer-motion'

type Status = 'connecting' | 'open' | 'closed' | 'error'

export function ConnectionBanner(props: { status: Status; error?: string | null }) {
  const show = props.status !== 'open'
  const tone =
    props.status === 'error'
      ? { border: 'rgba(255,68,68,0.45)', text: 'rgba(255,68,68,0.95)', bg: 'rgba(255,68,68,0.08)' }
      : props.status === 'closed'
        ? { border: 'rgba(255,170,0,0.40)', text: 'rgba(255,170,0,0.95)', bg: 'rgba(255,170,0,0.08)' }
        : { border: 'rgba(0,212,255,0.40)', text: 'rgba(0,212,255,0.95)', bg: 'rgba(0,212,255,0.08)' }

  const label =
    props.status === 'connecting'
      ? 'CONNECTING…'
      : props.status === 'closed'
        ? 'DISCONNECTED — RECONNECTING'
        : props.status === 'error'
          ? 'CONNECTION ERROR — RETRYING'
          : ''

  return (
    <AnimatePresence>
      {show ? (
        <motion.div
          className="fixed left-1/2 top-4 z-[3000] w-[min(920px,92vw)] -translate-x-1/2"
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: 0.22 }}
        >
          <div
            className="rounded-2xl border px-4 py-3 backdrop-blur-xl"
            style={{ borderColor: tone.border, background: tone.bg }}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="font-mono text-[10px] tracking-[0.28em] uppercase" style={{ color: tone.text }}>
                  {label}
                </div>
                {props.error ? (
                  <div className="mt-1 font-mono text-xs text-[rgba(215,226,255,0.75)]">{props.error}</div>
                ) : (
                  <div className="mt-1 font-mono text-xs text-[rgba(215,226,255,0.75)]">
                    Telemetry stream will resume automatically.
                  </div>
                )}
              </div>

              <div className="mt-1 inline-flex items-center gap-2 font-mono text-xs text-[rgba(215,226,255,0.70)]">
                <span className="relative inline-flex h-2 w-2">
                  <span
                    className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-60"
                    style={{ background: tone.text }}
                  />
                  <span className="relative inline-flex h-2 w-2 rounded-full" style={{ background: tone.text }} />
                </span>
                <span>LIVE LINK</span>
              </div>
            </div>
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  )
}

