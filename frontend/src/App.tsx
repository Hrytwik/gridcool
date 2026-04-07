import { useEffect, useMemo, useState } from 'react'
import { useDashboardSocket } from './lib/useDashboardSocket'
import { Panel } from './components/Panel'
import { StressGauge } from './components/StressGauge'
import { CreditCounter } from './components/CreditCounter'
import { DemandChart } from './components/DemandChart'
import { ChennaiMap } from './components/ChennaiMap'
import { EventTicker } from './components/EventTicker'
import { OperatorConsole } from './components/OperatorConsole'
import { BuildingDrawer } from './components/BuildingDrawer'
import { OwnerPortal } from './views/OwnerPortal'
import { AdminPanel } from './views/AdminPanel'
import { ConnectionBanner } from './components/ConnectionBanner'
import { Skeleton } from './components/Skeleton'
import { ThermalIntelligencePanel } from './components/ThermalIntelligencePanel'

function App() {
  const { status, snapshot, lastError, wsUrl } = useDashboardSocket()
  const severity = snapshot?.severity ?? 'ok'
  const accent = severity === 'critical' ? 'red' : severity === 'warning' ? 'amber' : 'blue'
  const dispatchActive = snapshot?.demo.dispatch_active ?? false
  const [selectedBuildingId, setSelectedBuildingId] = useState<string | null>(null)
  const [view, setView] = useState<'dashboard' | 'owner' | 'admin'>('dashboard')

  const selectedBuilding = useMemo(() => {
    if (!snapshot || !selectedBuildingId) return null
    return snapshot.buildings.find((b) => b.building_id === selectedBuildingId) ?? null
  }, [snapshot, selectedBuildingId])

  useEffect(() => {
    const fromHash = () => {
      const h = window.location.hash.replace('#', '')
      if (h === 'owner' || h === 'admin' || h === 'dashboard') setView(h)
    }
    fromHash()
    window.addEventListener('hashchange', fromHash)
    return () => window.removeEventListener('hashchange', fromHash)
  }, [])

  const navBtn = (id: 'dashboard' | 'owner' | 'admin', label: string) => (
    <button
      onClick={() => {
        setView(id)
        window.location.hash = id
      }}
      className={[
        'rounded-xl border px-3 py-2 font-mono text-[10px] tracking-[0.28em] uppercase transition',
        view === id
          ? 'border-[rgba(0,212,255,0.45)] bg-[rgba(0,212,255,0.08)] text-[rgba(0,212,255,0.95)] shadow-glow'
          : 'border-[var(--gc-panel-border)] bg-black/20 text-[var(--gc-muted)] hover:border-[rgba(0,212,255,0.35)]',
      ].join(' ')}
    >
      {label}
    </button>
  )

  return (
    <div className="min-h-screen">
      <ConnectionBanner status={status} error={lastError} />
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

            <div className="mt-4 flex flex-wrap items-center gap-2">
              {navBtn('dashboard', 'DASHBOARD')}
              {navBtn('owner', 'OWNER PORTAL')}
              {navBtn('admin', 'DISCOM / ADMIN')}
            </div>
          </div>

          <div className="w-full sm:w-auto rounded-2xl border border-[var(--gc-panel-border)] bg-black/25 px-4 py-3 font-mono text-xs text-[var(--gc-muted)]">
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
        {view === 'dashboard' ? (
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
                  <div className="grid gap-3 md:grid-cols-[1fr_auto] md:items-center">
                    <div className="space-y-3">
                      <Skeleton className="h-10 w-44" />
                      <Skeleton className="h-4 w-72" />
                    </div>
                    <Skeleton className="h-[140px] w-[240px]" />
                  </div>
                )}

                <div className="mt-4 grid gap-3 sm:grid-cols-3">
                  <div className="rounded-2xl border border-[var(--gc-panel-border)] bg-black/25 p-3">
                    <div className="text-xs uppercase tracking-[0.26em] text-[var(--gc-muted)]">
                      Temperature
                    </div>
                    <div className="mt-2 text-2xl font-semibold">
                      {snapshot ? `${snapshot.temperature_c.toFixed(1)}°C` : <Skeleton className="h-8 w-28" />}
                    </div>
                    <div className="mt-1 font-mono text-xs text-[var(--gc-muted)]">
                      Heat index:{' '}
                      {snapshot ? `${snapshot.heat_index_c.toFixed(1)}°C` : <span className="inline-block align-middle"><Skeleton className="h-4 w-20" /></span>}
                    </div>
                  </div>
                  <div className="rounded-2xl border border-[var(--gc-panel-border)] bg-black/25 p-3">
                    <div className="text-xs uppercase tracking-[0.26em] text-[var(--gc-muted)]">
                      Enrolled capacity
                    </div>
                    <div className="mt-2 text-2xl font-semibold">
                      {snapshot ? `${snapshot.enrolled_kw_total.toFixed(1)} kW` : <Skeleton className="h-8 w-36" />}
                    </div>
                    <div className="mt-1 font-mono text-xs text-[var(--gc-muted)]">
                      Buildings: {snapshot ? snapshot.buildings.length : <span className="inline-block align-middle"><Skeleton className="h-4 w-10" /></span>}
                    </div>
                  </div>
                  <div className="rounded-2xl border border-[var(--gc-panel-border)] bg-black/25 p-3">
                    <div className="text-xs uppercase tracking-[0.26em] text-[var(--gc-muted)]">
                      Est. reduction
                    </div>
                    <div className="mt-2 text-2xl font-semibold">
                      {snapshot ? `${snapshot.estimated_kw_reduction.toFixed(1)} kW` : <Skeleton className="h-8 w-32" />}
                    </div>
                    <div className="mt-1 font-mono text-xs text-[var(--gc-muted)]">
                      Dispatch:{' '}
                      {snapshot ? (snapshot.demo.dispatch_active ? 'ACTIVE' : 'STANDBY') : <span className="inline-block align-middle"><Skeleton className="h-4 w-20" /></span>}
                    </div>
                  </div>
                </div>

                {snapshot ? (
                  <div className="mt-4">
                    <DemandChart points={snapshot.demand_curve} dispatchActive={snapshot.demo.dispatch_active} />
                  </div>
                ) : (
                  <div className="mt-4">
                    <Skeleton className="h-[260px] w-full" />
                  </div>
                )}
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
                <Skeleton className="h-[470px] w-full" />
              )}

              {snapshot ? <CreditCounter value={snapshot.credits_inr} accent={accent} /> : <Skeleton className="h-[140px] w-full" />}
              {snapshot ? <ThermalIntelligencePanel buildings={snapshot.buildings} /> : <Skeleton className="h-[420px] w-full" />}
              <OperatorConsole dispatchActive={dispatchActive} />
            </div>
          </div>
        ) : null}

        {view === 'owner' ? <OwnerPortal snapshot={snapshot} /> : null}
        {view === 'admin' ? <AdminPanel snapshot={snapshot} /> : null}
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
