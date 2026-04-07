import { AnimatePresence, motion } from 'framer-motion'
import type { DashboardBuilding, DashboardSnapshot } from '../lib/dashboardTypes'

function makeDevices(building: DashboardBuilding) {
  const count = Math.min(24, Math.max(1, building.ac_count))
  return Array.from({ length: count }).map((_, i) => ({
    device_id: `${building.building_id}_ac_${String(i + 1).padStart(3, '0')}`,
    name: `Panasonic AC ${String(i + 1).padStart(2, '0')}`,
    mode: building.last_action ? 'PRECOOL' : 'AUTO',
    setpoint_c: building.last_action ? 22 : 24,
    status: 'ONLINE' as const,
  }))
}

export function BuildingDrawer(props: {
  open: boolean
  building: DashboardBuilding | null
  snapshot: DashboardSnapshot | null
  onClose: () => void
}) {
  const b = props.building
  const dispatchUntil = props.snapshot?.demo.dispatch_until
  const devices = b ? makeDevices(b) : []
  const tf = b?.thermal_fingerprint ?? null

  const creditsShare = (() => {
    if (!b || !props.snapshot) return 0
    const total = props.snapshot.enrolled_kw_total || 1
    return (b.enrolled_kw / total) * props.snapshot.credits_inr
  })()

  return (
    <AnimatePresence>
      {props.open ? (
        <>
          <motion.button
            aria-label="Close"
            onClick={props.onClose}
            className="fixed inset-0 z-[2000] bg-black/55"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          />

          <motion.aside
            className="fixed right-0 top-0 z-[2100] h-full w-full max-w-[520px] border-l border-[var(--gc-panel-border)] bg-[rgba(10,15,30,0.92)] backdrop-blur-xl"
            initial={{ x: 40, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 40, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 140, damping: 20 }}
          >
            <div className="flex h-full flex-col">
              <div className="flex items-start justify-between gap-3 border-b border-[var(--gc-panel-border)] p-5">
                <div className="min-w-0">
                  <div className="font-mono text-[10px] tracking-[0.28em] text-[var(--gc-muted)] uppercase">
                    Building owner portal (demo)
                  </div>
                  <div className="mt-2 truncate text-xl font-semibold">{b?.name ?? '—'}</div>
                  <div className="mt-1 font-mono text-xs text-[var(--gc-muted)]">
                    {b ? `${b.ac_count} AC • ${b.enrolled_kw.toFixed(1)} kW • ${b.lat.toFixed(3)}, ${b.lng.toFixed(3)}` : ''}
                  </div>
                </div>

                <button
                  onClick={props.onClose}
                  className="rounded-xl border border-[var(--gc-panel-border)] bg-black/30 px-3 py-2 font-mono text-xs text-[var(--gc-muted)] hover:border-[rgba(0,212,255,0.45)]"
                >
                  CLOSE
                </button>
              </div>

              <div className="flex-1 overflow-auto p-5">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-2xl border border-[var(--gc-panel-border)] bg-black/25 p-4">
                    <div className="text-xs uppercase tracking-[0.26em] text-[var(--gc-muted)]">Status</div>
                    <div className="mt-2 font-mono text-sm">
                      {b?.last_action ? (
                        <span className="text-[var(--gc-blue)]">PRE-COOLING</span>
                      ) : (
                        <span className="text-[rgba(215,226,255,0.85)]">STANDBY</span>
                      )}
                    </div>
                    <div className="mt-2 font-mono text-xs text-[var(--gc-muted)]">
                      Next action: {b?.last_action ? `raise setpoint @ peak window` : 'monitoring'}
                    </div>
                  </div>

                  <div className="rounded-2xl border border-[var(--gc-panel-border)] bg-black/25 p-4">
                    <div className="text-xs uppercase tracking-[0.26em] text-[var(--gc-muted)]">Credits</div>
                    <div className="mt-2 text-2xl font-semibold">
                      ₹ {creditsShare.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                    </div>
                    <div className="mt-2 font-mono text-xs text-[var(--gc-muted)]">
                      Estimated share of session credits (demo).
                    </div>
                  </div>
                </div>

                <div className="mt-4 rounded-2xl border border-[var(--gc-panel-border)] bg-black/25 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-xs uppercase tracking-[0.26em] text-[var(--gc-muted)]">
                      MirAIe command acknowledgements
                    </div>
                    <div className="font-mono text-[10px] text-[var(--gc-muted)]">
                      {dispatchUntil ? `dispatch_until: ${new Date(dispatchUntil).toLocaleTimeString()}` : ''}
                    </div>
                  </div>
                  <div className="mt-3 font-mono text-xs text-[rgba(215,226,255,0.85)]">
                    {b?.last_ack ? (
                      <div className="rounded-xl border border-[rgba(0,212,255,0.25)] bg-black/20 px-3 py-2">
                        {b.last_ack}
                      </div>
                    ) : (
                      <div className="text-[var(--gc-muted)]">No ACK yet (waiting for MirAIe fleet)…</div>
                    )}
                  </div>
                </div>

                <div className="mt-4 rounded-2xl border border-[var(--gc-panel-border)] bg-black/25 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-xs uppercase tracking-[0.26em] text-[var(--gc-muted)]">
                      Thermal fingerprint (RC model)
                    </div>
                    <div className="font-mono text-[10px] text-[var(--gc-muted)]">
                      {tf?.calibration_status === 'calibrating'
                        ? `calibrating ${tf.calibration_progress_pct ?? 0}%`
                        : tf?.calibration_status === 'fingerprinted'
                          ? 'fingerprinted ✓'
                          : ''}
                    </div>
                  </div>

                  <div className="mt-3 grid gap-2 sm:grid-cols-2">
                    <div className="rounded-2xl border border-[var(--gc-panel-border)] bg-black/20 p-3">
                      <div className="font-mono text-[10px] tracking-[0.22em] text-[var(--gc-muted)] uppercase">Flexibility</div>
                      <div className="mt-2 text-2xl font-semibold">
                        {typeof tf?.flexibility_window_minutes === 'number'
                          ? `${Math.round(tf.flexibility_window_minutes)} min`
                          : '—'}
                      </div>
                      <div className="mt-1 font-mono text-xs text-[var(--gc-muted)]">
                        Comfort band: ±1.5°C (demo)
                      </div>
                    </div>

                    <div className="rounded-2xl border border-[var(--gc-panel-border)] bg-black/20 p-3">
                      <div className="font-mono text-[10px] tracking-[0.22em] text-[var(--gc-muted)] uppercase">Construction type</div>
                      <div className="mt-2 text-2xl font-semibold">
                        {tf?.construction_type ? tf.construction_type.replace('_', ' ') : '—'}
                      </div>
                      <div className="mt-1 font-mono text-xs text-[var(--gc-muted)]">
                        Thermal mass: {tf?.thermal_mass_class ?? '—'}
                      </div>
                    </div>
                  </div>

                  <div className="mt-3 rounded-2xl border border-[var(--gc-panel-border)] bg-black/20 p-3">
                    <div className="font-mono text-[10px] tracking-[0.22em] text-[var(--gc-muted)] uppercase">RC parameters</div>
                    <div className="mt-2 grid gap-2 sm:grid-cols-2 font-mono text-xs text-[rgba(215,226,255,0.85)]">
                      <div>R: {typeof tf?.rc_r === 'number' ? tf.rc_r.toFixed(3) : '—'}</div>
                      <div>C: {typeof tf?.rc_c === 'number' ? tf.rc_c.toFixed(3) : '—'}</div>
                    </div>
                    <div className="mt-2 font-mono text-[10px] text-[var(--gc-muted)]">
                      GridCool infers this from MirAIe telemetry (compressor cycles, time-to-target, rebound rate). No surveys.
                    </div>
                  </div>
                </div>

                <div className="mt-4 rounded-2xl border border-[var(--gc-panel-border)] bg-black/25 p-4">
                  <div className="text-xs uppercase tracking-[0.26em] text-[var(--gc-muted)]">Devices</div>
                  <div className="mt-3 space-y-2">
                    {devices.map((d) => (
                      <div
                        key={d.device_id}
                        className="flex items-center justify-between gap-3 rounded-2xl border border-[var(--gc-panel-border)] bg-black/20 px-3 py-3"
                      >
                        <div className="min-w-0">
                          <div className="truncate text-sm">{d.name}</div>
                          <div className="mt-1 font-mono text-xs text-[var(--gc-muted)]">
                            {d.device_id} • {d.status} • mode={d.mode}
                          </div>
                        </div>
                        <div className="shrink-0 text-right">
                          <div className="font-mono text-xs text-[rgba(215,226,255,0.88)]">
                            {d.setpoint_c}°C
                          </div>
                          <div className="mt-1 font-mono text-[10px] text-[var(--gc-muted)]">setpoint</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </motion.aside>
        </>
      ) : null}
    </AnimatePresence>
  )
}

