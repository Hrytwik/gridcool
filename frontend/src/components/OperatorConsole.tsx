import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { demoEnrollBuilding, demoForceStress, demoTriggerDispatch } from '../lib/api'

export function OperatorConsole(props: {
  dispatchActive: boolean
  ml?: { source: string; artifact_status: string } | null
}) {
  const [busy, setBusy] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [ok, setOk] = useState<string | null>(null)

  const [enrollOpen, setEnrollOpen] = useState(false)
  const [step, setStep] = useState<1 | 2 | 3 | 4>(1)

  const [name, setName] = useState('New Building — Judge Demo')
  const [lat, setLat] = useState('13.050')
  const [lng, setLng] = useState('80.250')
  const [miraieLinked, setMiraieLinked] = useState(false)
  const [acCount, setAcCount] = useState('12')

  const canEnroll = useMemo(() => {
    const la = Number(lat)
    const ln = Number(lng)
    const ac = Number(acCount)
    return (
      name.trim().length >= 3 &&
      Number.isFinite(la) &&
      Number.isFinite(ln) &&
      miraieLinked &&
      ac >= 1
    )
  }, [name, lat, lng, acCount, miraieLinked])

  const canNextStep2 = useMemo(() => name.trim().length >= 3, [name])
  const canNextStep3 = useMemo(() => Number.isFinite(Number(lat)) && Number.isFinite(Number(lng)), [lat, lng])
  const canNextStep4 = useMemo(() => miraieLinked, [miraieLinked])

  async function run(actionId: string, fn: () => Promise<unknown>) {
    setBusy(actionId)
    setErr(null)
    setOk(null)
    try {
      await fn()
      setOk('Command acknowledged')
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Command failed')
    } finally {
      setBusy(null)
      window.setTimeout(() => setOk(null), 1500)
    }
  }

  const buttonBase =
    'rounded-xl border border-[var(--gc-panel-border)] bg-black/25 px-3 py-2 text-xs font-mono tracking-[0.22em] uppercase transition'

  return (
    <div className="relative overflow-hidden rounded-2xl border border-[var(--gc-panel-border)] bg-black/25 p-4">
      <div className="absolute inset-0 opacity-40">
        <div className="absolute inset-0 bg-gradient-to-r from-[rgba(0,212,255,0.10)] via-transparent to-[rgba(255,170,0,0.08)]" />
      </div>

      <div className="relative">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-xs uppercase tracking-[0.26em] text-[var(--gc-muted)]">Operator console</div>
            <div className="mt-1 text-sm text-[rgba(215,226,255,0.88)]">
              Presentation-safe triggers + instant enrollment.
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-end gap-2">
            {props.ml ? (
              <div
                className="rounded-full border border-[rgba(140,160,200,0.35)] bg-black/20 px-3 py-1 font-mono text-[10px] tracking-[0.22em] text-[var(--gc-muted)]"
                title="Forecast driver from websocket snapshot"
              >
                FCST: {props.ml.source === 'ml' ? 'ML' : 'SIM'} · {props.ml.artifact_status}
              </div>
            ) : null}
            {props.dispatchActive ? (
              <div className="rounded-full border border-[rgba(0,212,255,0.35)] bg-black/20 px-3 py-1 font-mono text-[10px] tracking-[0.28em] text-[rgba(0,212,255,0.9)]">
                DISPATCH LIVE
              </div>
            ) : (
              <div className="rounded-full border border-[rgba(64,87,140,0.35)] bg-black/20 px-3 py-1 font-mono text-[10px] tracking-[0.28em] text-[var(--gc-muted)]">
                STANDBY
              </div>
            )}
          </div>
        </div>

        <div className="mt-4 grid gap-2 sm:grid-cols-2">
          <button
            className={[
              buttonBase,
              'hover:border-[rgba(0,212,255,0.45)] hover:shadow-glow',
              busy === 'stress' ? 'opacity-60' : '',
            ].join(' ')}
            disabled={!!busy}
            onClick={() => run('stress', () => demoForceStress(86, 12))}
          >
            Force stress spike
          </button>
          <button
            className={[
              buttonBase,
              'hover:border-[rgba(0,212,255,0.45)] hover:shadow-glow',
              busy === 'dispatch' ? 'opacity-60' : '',
            ].join(' ')}
            disabled={!!busy}
            onClick={() => run('dispatch', () => demoTriggerDispatch(90))}
          >
            Trigger dispatch
          </button>
        </div>

        <div className="mt-4 rounded-2xl border border-[var(--gc-panel-border)] bg-black/20 p-3">
          <div className="flex items-center justify-between gap-3">
            <div className="font-mono text-[10px] tracking-[0.28em] text-[var(--gc-muted)] uppercase">
              Building enrollment
            </div>
            <div className="font-mono text-[10px] text-[var(--gc-muted)]">DEMO_MODE</div>
          </div>

          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <div className="font-mono text-xs text-[var(--gc-muted)]">
              Wizard: name → location → MirAIe link → devices
            </div>
            <button
              className={[buttonBase, 'hover:border-[rgba(0,212,255,0.45)] hover:shadow-glow'].join(' ')}
              onClick={() => {
                setEnrollOpen(true)
                setStep(1)
                setErr(null)
                setOk(null)
              }}
            >
              Open enrollment
            </button>
          </div>
        </div>

        <div className="mt-3 min-h-[18px] font-mono text-xs">
          {err ? <span className="text-[var(--gc-red)]">{err}</span> : null}
          {ok ? (
            <motion.span
              initial={{ opacity: 0, y: 2 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-[var(--gc-blue)]"
            >
              {ok}
            </motion.span>
          ) : null}
        </div>
      </div>

      {/* Enrollment wizard modal */}
      {enrollOpen ? (
        <div className="fixed inset-0 z-[2200]">
          <button
            aria-label="Close"
            className="absolute inset-0 bg-black/60"
            onClick={() => setEnrollOpen(false)}
          />
          <div className="absolute left-1/2 top-1/2 w-[min(720px,92vw)] -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-[var(--gc-panel-border)] bg-[rgba(10,15,30,0.94)] p-5 shadow-[0_20px_80px_rgba(0,0,0,0.75)] backdrop-blur-xl">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="font-mono text-[10px] tracking-[0.28em] text-[var(--gc-muted)] uppercase">
                  Enrollment wizard
                </div>
                <div className="mt-2 text-xl font-semibold">Enroll a building into GridCool</div>
                <div className="mt-1 text-sm text-[var(--gc-muted)]">
                  Demo flow mirrors Panasonic MirAIe onboarding.
                </div>
              </div>
              <button
                className="rounded-xl border border-[var(--gc-panel-border)] bg-black/25 px-3 py-2 font-mono text-xs text-[var(--gc-muted)] hover:border-[rgba(0,212,255,0.45)]"
                onClick={() => setEnrollOpen(false)}
              >
                CLOSE
              </button>
            </div>

            <div className="mt-4 flex items-center gap-2 font-mono text-[10px] tracking-[0.26em] text-[var(--gc-muted)]">
              <span className={step === 1 ? 'text-[var(--gc-blue)]' : ''}>01 NAME</span>
              <span>—</span>
              <span className={step === 2 ? 'text-[var(--gc-blue)]' : ''}>02 LOCATION</span>
              <span>—</span>
              <span className={step === 3 ? 'text-[var(--gc-blue)]' : ''}>03 MIRAIe LINK</span>
              <span>—</span>
              <span className={step === 4 ? 'text-[var(--gc-blue)]' : ''}>04 DEVICES</span>
            </div>

            <div className="mt-4 rounded-2xl border border-[var(--gc-panel-border)] bg-black/25 p-4">
              {step === 1 ? (
                <div className="grid gap-3">
                  <div className="text-sm text-[rgba(215,226,255,0.88)]">
                    Building name (owner-facing).
                  </div>
                  <input
                    className="w-full rounded-xl border border-[var(--gc-panel-border)] bg-black/25 px-3 py-3 text-sm text-[rgba(215,226,255,0.9)] outline-none focus:border-[rgba(0,212,255,0.55)]"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g., Marina Bay Towers — Mylapore"
                  />
                </div>
              ) : null}

              {step === 2 ? (
                <div className="grid gap-3">
                  <div className="text-sm text-[rgba(215,226,255,0.88)]">
                    Location (Chennai). Use approximate coordinates for the demo.
                  </div>
                  <div className="grid gap-2 sm:grid-cols-2">
                    <input
                      className="rounded-xl border border-[var(--gc-panel-border)] bg-black/25 px-3 py-3 text-sm text-[rgba(215,226,255,0.9)] outline-none focus:border-[rgba(0,212,255,0.55)]"
                      value={lat}
                      onChange={(e) => setLat(e.target.value)}
                      placeholder="lat"
                    />
                    <input
                      className="rounded-xl border border-[var(--gc-panel-border)] bg-black/25 px-3 py-3 text-sm text-[rgba(215,226,255,0.9)] outline-none focus:border-[rgba(0,212,255,0.55)]"
                      value={lng}
                      onChange={(e) => setLng(e.target.value)}
                      placeholder="lng"
                    />
                  </div>
                  <div className="font-mono text-xs text-[var(--gc-muted)]">
                    Tip: try ~13.05 / 80.25 to land near central Chennai.
                  </div>
                </div>
              ) : null}

              {step === 3 ? (
                <div className="grid gap-3">
                  <div className="text-sm text-[rgba(215,226,255,0.88)]">
                    Link Panasonic MirAIe account (mock).
                  </div>
                  <div className="rounded-2xl border border-[var(--gc-panel-border)] bg-black/20 p-4">
                    <div className="font-mono text-xs text-[var(--gc-muted)]">
                      OAuth would happen here in production. For demo, we simulate token grant.
                    </div>
                    <div className="mt-3 flex items-center gap-3">
                      <button
                        className={[
                          buttonBase,
                          miraieLinked ? 'opacity-60' : 'hover:border-[rgba(0,212,255,0.45)] hover:shadow-glow',
                        ].join(' ')}
                        disabled={miraieLinked}
                        onClick={() => setMiraieLinked(true)}
                      >
                        {miraieLinked ? 'Account linked' : 'Link MirAIe account'}
                      </button>
                      {miraieLinked ? (
                        <span className="font-mono text-xs text-[rgba(0,212,255,0.9)]">TOKEN_GRANTED</span>
                      ) : null}
                    </div>
                  </div>
                </div>
              ) : null}

              {step === 4 ? (
                <div className="grid gap-3">
                  <div className="text-sm text-[rgba(215,226,255,0.88)]">
                    Devices discovered (mock MirAIe device list).
                  </div>
                  <div className="flex items-center justify-between gap-3 rounded-2xl border border-[var(--gc-panel-border)] bg-black/20 p-4">
                    <div>
                      <div className="font-mono text-xs text-[var(--gc-muted)]">AC devices</div>
                      <div className="mt-1 text-2xl font-semibold">{Number(acCount) || 0}</div>
                    </div>
                    <input
                      className="w-[260px]"
                      type="range"
                      min={1}
                      max={60}
                      value={acCount}
                      onChange={(e) => setAcCount(e.target.value)}
                    />
                  </div>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {Array.from({ length: Math.min(6, Math.max(1, Number(acCount) || 1)) }).map((_, i) => (
                      <div
                        key={i}
                        className="rounded-2xl border border-[var(--gc-panel-border)] bg-black/20 px-3 py-3"
                      >
                        <div className="text-sm">Panasonic AC {String(i + 1).padStart(2, '0')}</div>
                        <div className="mt-1 font-mono text-xs text-[var(--gc-muted)]">
                          status=ONLINE • mode=AUTO • setpoint=24°C
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>

            <div className="mt-4 flex items-center justify-between gap-3">
              <button
                className={[buttonBase, step === 1 ? 'opacity-50' : 'hover:border-[rgba(64,87,140,0.55)]'].join(' ')}
                disabled={step === 1}
                onClick={() => setStep((s) => (s === 1 ? 1 : ((s - 1) as 1 | 2 | 3 | 4)))}
              >
                Back
              </button>

              <div className="flex items-center gap-2">
                {step < 4 ? (
                  <button
                    className={[
                      buttonBase,
                      'hover:border-[rgba(0,212,255,0.45)] hover:shadow-glow',
                      (step === 1 && !canNextStep2) ||
                      (step === 2 && !canNextStep3) ||
                      (step === 3 && !canNextStep4)
                        ? 'opacity-50'
                        : '',
                    ].join(' ')}
                    disabled={
                      (step === 1 && !canNextStep2) ||
                      (step === 2 && !canNextStep3) ||
                      (step === 3 && !canNextStep4)
                    }
                    onClick={() => setStep((s) => ((s + 1) as 1 | 2 | 3 | 4))}
                  >
                    Next
                  </button>
                ) : (
                  <button
                    className={[
                      buttonBase,
                      canEnroll ? 'hover:border-[rgba(0,212,255,0.45)] hover:shadow-glow' : 'opacity-50',
                      busy === 'enroll' ? 'opacity-60' : '',
                    ].join(' ')}
                    disabled={!canEnroll || !!busy}
                    onClick={() =>
                      run('enroll', async () => {
                        await demoEnrollBuilding({
                          name: name.trim(),
                          lat: Number(lat),
                          lng: Number(lng),
                          ac_count: Number(acCount),
                        })
                        setEnrollOpen(false)
                      })
                    }
                  >
                    Enroll building
                  </button>
                )}
              </div>
            </div>

            <div className="mt-3 min-h-[18px] font-mono text-xs">
              {err ? <span className="text-[var(--gc-red)]">{err}</span> : null}
              {ok ? (
                <motion.span initial={{ opacity: 0, y: 2 }} animate={{ opacity: 1, y: 0 }} className="text-[var(--gc-blue)]">
                  {ok}
                </motion.span>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}

