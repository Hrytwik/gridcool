import { useMemo, useState } from 'react'
import { useDashboardSocket } from './lib/useDashboardSocket'
import { Panel } from './components/Panel'
import { StressGauge } from './components/StressGauge'
import { CreditCounter } from './components/CreditCounter'
import { DemandChart } from './components/DemandChart'
import { ChennaiMap } from './components/ChennaiMap'
import { EventTicker } from './components/EventTicker'
import { OperatorConsole } from './components/OperatorConsole'
import { BuildingDrawer } from './components/BuildingDrawer'

function App() {
  const { status, snapshot, lastError, wsUrl } = useDashboardSocket()
  const severity = snapshot?.severity ?? 'ok'
  const accent = severity === 'critical' ? 'red' : severity === 'warning' ? 'amber' : 'blue'
  const dispatchActive = snapshot?.demo.dispatch_active ?? false
  const [selectedBuildingId, setSelectedBuildingId] = useState<string | null>(null)

  const selectedBuilding = useMemo(() => {
    if (!snapshot || !selectedBuildingId) return null
    return snapshot.buildings.find((b) => b.building_id === selectedBuildingId) ?? null
  }, [snapshot, selectedBuildingId])

  return (
    <div className="min-h-screen">
      <header className="px-5 py-5">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="font-mono text-xs tracking-[0.28em] uppercase text-[var(--gc-muted)]">
              GridCool / Equinox 2026 / Smart Infrastructure
            </div>
            <div className="mt-1 text-3xl font-semibold tracking-tight">
              Mission Control — Chennai Demand Response Fleet
            </div>
            <div className="mt-2 text-sm text-[var(--gc-muted)]">
              Panasonic MirAIe-native AC orchestration • Virtual Power Plant dispatch • ₹ credits
            </div>
          </div>

          <div className="rounded-2xl border border-[var(--gc-panel-border)] bg-black/25 px-4 py-3 font-mono text-xs text-[var(--gc-muted)]">
            <div className="flex items-center justify-between gap-3">
              <span>WS</span>
              <span
                className={
                  status === 'open'
                    ? 'text-[var(--gc-blue)]'
                    : status === 'error'
                      ? 'text-[var(--gc-red)]'
                      : ''
                }
              >
                {status.toUpperCase()}
              </span>
            </div>
            <div className="mt-1 truncate max-w-[52vw] opacity-80">{wsUrl}</div>
            {lastError ? <div className="mt-1 text-[var(--gc-red)]">{lastError}</div> : null}
          </div>
        </div>
      </header>

      <main className="px-5 pb-10">
        <div className="grid gap-4 lg:grid-cols-12">
          <div className="lg:col-span-7 grid gap-4">
            <EventTicker events={snapshot?.events ?? []} dispatchActive={dispatchActive} />

            <Panel
              title="GRID STRESS DIAL"
              right={
                snapshot ? (
                  <>
                    {snapshot.city} • {new Date(snapshot.ts).toLocaleTimeString()}
                  </>
                ) : (
                  'Connecting…'
                )
              }
            >
              {snapshot ? (
                <StressGauge score={snapshot.stress_score} severity={snapshot.severity} />
              ) : (
                <div className="text-sm text-[var(--gc-muted)]">Waiting for telemetry…</div>
              )}

              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                <div className="rounded-2xl border border-[var(--gc-panel-border)] bg-black/25 p-3">
                  <div className="text-xs uppercase tracking-[0.26em] text-[var(--gc-muted)]">
                    Temperature
                  </div>
                  <div className="mt-2 text-2xl font-semibold">
                    {snapshot ? `${snapshot.temperature_c.toFixed(1)}°C` : '—'}
                  </div>
                  <div className="mt-1 font-mono text-xs text-[var(--gc-muted)]">
                    Heat index: {snapshot ? `${snapshot.heat_index_c.toFixed(1)}°C` : '—'}
                  </div>
                </div>
                <div className="rounded-2xl border border-[var(--gc-panel-border)] bg-black/25 p-3">
                  <div className="text-xs uppercase tracking-[0.26em] text-[var(--gc-muted)]">
                    Enrolled capacity
                  </div>
                  <div className="mt-2 text-2xl font-semibold">
                    {snapshot ? `${snapshot.enrolled_kw_total.toFixed(1)} kW` : '—'}
                  </div>
                  <div className="mt-1 font-mono text-xs text-[var(--gc-muted)]">
                    Buildings: {snapshot ? snapshot.buildings.length : '—'}
                  </div>
                </div>
                <div className="rounded-2xl border border-[var(--gc-panel-border)] bg-black/25 p-3">
                  <div className="text-xs uppercase tracking-[0.26em] text-[var(--gc-muted)]">
                    Est. reduction
                  </div>
                  <div className="mt-2 text-2xl font-semibold">
                    {snapshot ? `${snapshot.estimated_kw_reduction.toFixed(1)} kW` : '—'}
                  </div>
                  <div className="mt-1 font-mono text-xs text-[var(--gc-muted)]">
                    Dispatch: {snapshot?.demo.dispatch_active ? 'ACTIVE' : 'STANDBY'}
                  </div>
                </div>
              </div>

              {snapshot ? (
                <div className="mt-4">
                  <DemandChart
                    points={snapshot.demand_curve}
                    dispatchActive={snapshot.demo.dispatch_active}
                  />
                </div>
              ) : null}
            </Panel>
          </div>

          <div className="lg:col-span-5 grid gap-4">
            {snapshot ? (
              <ChennaiMap
                buildings={snapshot.buildings}
                dispatchActive={dispatchActive}
                onSelectBuilding={(id) => setSelectedBuildingId(id)}
              />
            ) : (
              <div className="rounded-2xl border border-[var(--gc-panel-border)] bg-black/25 p-4 text-[var(--gc-muted)]">
                Loading map…
              </div>
            )}

            <CreditCounter value={snapshot?.credits_inr ?? 0} accent={accent} />

            <OperatorConsole dispatchActive={dispatchActive} />

            <Panel
              title="ENROLLED BUILDINGS"
              right={
                snapshot?.demo.dispatch_active ? (
                  <span className="text-[var(--gc-blue)]">DISPATCH ON</span>
                ) : (
                  'DISPATCH OFF'
                )
              }
            >
              <div className="space-y-2">
                {snapshot?.buildings?.length ? (
                  snapshot.buildings.map((b) => (
                    <div
                      key={b.building_id}
                      className="group flex items-center justify-between gap-3 rounded-2xl border border-[var(--gc-panel-border)] bg-black/20 px-3 py-3 transition hover:bg-black/30"
                    >
                      <div className="min-w-0">
                        <div className="truncate text-sm">{b.name}</div>
                        <div className="mt-1 font-mono text-xs text-[var(--gc-muted)]">
                          {b.ac_count} AC • {b.enrolled_kw.toFixed(1)} kW • {b.lat.toFixed(3)},{' '}
                          {b.lng.toFixed(3)}
                        </div>
                      </div>
                      <div className="shrink-0 text-right">
                        <div
                          className={[
                            'rounded-full border px-2 py-1 font-mono text-[10px] tracking-[0.22em]',
                            b.severity === 'critical'
                              ? 'border-[rgba(255,68,68,0.45)] text-[var(--gc-red)]'
                              : b.severity === 'warning'
                                ? 'border-[rgba(255,170,0,0.45)] text-[var(--gc-amber)]'
                                : 'border-[rgba(0,212,255,0.45)] text-[var(--gc-blue)]',
                          ].join(' ')}
                        >
                          {b.severity.toUpperCase()}
                        </div>
                        {b.last_action ? (
                          <div className="mt-2 font-mono text-[10px] text-[var(--gc-muted)]">
                            {b.last_action}
                          </div>
                        ) : (
                          <div className="mt-2 font-mono text-[10px] text-[var(--gc-muted)] opacity-70">
                            STANDBY
                          </div>
                        )}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-sm text-[var(--gc-muted)]">Waiting for telemetry…</div>
                )}
              </div>
            </Panel>
          </div>
        </div>
      </main>

      <BuildingDrawer
        open={!!selectedBuildingId}
        building={selectedBuilding}
        snapshot={snapshot}
        onClose={() => setSelectedBuildingId(null)}
      />
    </div>
  )
}

export default App
