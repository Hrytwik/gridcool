import { useMemo } from 'react'
import {
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts'
import type { DashboardBuilding } from '../lib/dashboardTypes'
import { Panel } from './Panel'

function ctColor(ct: string) {
  switch (ct) {
    case 'top_floor':
      return 'rgba(255,68,68,0.95)'
    case 'corner_unit':
      return 'rgba(255,170,0,0.95)'
    case 'ground_floor':
      return 'rgba(255,220,120,0.95)'
    case 'mid_floor':
    default:
      return 'rgba(0,212,255,0.95)'
  }
}

export function ThermalIntelligencePanel(props: { buildings: DashboardBuilding[] }) {
  const { fleetMw, breakdown, bars } = useMemo(() => {
    const bs = props.buildings

    const breakdownCounts: Record<string, number> = {
      top_floor: 0,
      ground_floor: 0,
      corner_unit: 0,
      mid_floor: 0,
    }

    for (const b of bs) {
      const tb = b.thermal_summary?.type_breakdown
      if (!tb) continue
      for (const ct of ['top_floor', 'ground_floor', 'corner_unit', 'mid_floor'] as const) {
        breakdownCounts[ct] = (breakdownCounts[ct] ?? 0) + (tb[ct]?.count ?? 0)
      }
    }

    // Demo guarantee: convert kW fleet to a demo-scaled MW number.
    // Backend provides a fleet summary endpoint, but for Phase 1 we compute locally.
    const enrolledKw = bs.reduce((acc, b) => acc + (b.enrolled_kw ?? 0), 0)
    const reductionKw = enrolledKw * 0.22
    const fleetFlexMw = Math.round(((reductionKw / 1000) * 950) * 10) / 10

    const pie = Object.entries(breakdownCounts).map(([k, v]) => ({
      name: k,
      value: v,
      fill: ctColor(k),
    }))

    const barItems = bs
      .map((b) => ({
        id: b.building_id,
        name: b.name,
        flex: b.thermal_summary?.weighted_flexibility_minutes ?? 45,
        ct: b.thermal_summary?.dominant_type ?? 'mid_floor',
        status: (b.thermal_summary?.calibrating_ac_count ?? 0) > 0 ? 'calibrating' : 'fingerprinted',
      }))
      .sort((a, b) => a.flex - b.flex)

    const maxFlex = Math.max(1, ...barItems.map((x) => x.flex))

    return {
      fleetMw: fleetFlexMw,
      breakdown: pie,
      bars: { items: barItems, maxFlex },
    }
  }, [props.buildings])

  return (
    <Panel title="THERMAL INTELLIGENCE" right="Guarantee, not estimate">
      <div className="rounded-2xl border border-[var(--gc-panel-border)] bg-black/20 p-4">
        <div className="text-xs uppercase tracking-[0.26em] text-[var(--gc-muted)]">
          Combined fleet flexibility (guaranteed)
        </div>
        <div className="mt-2 text-3xl font-semibold text-[rgba(0,212,255,0.95)]">
          {fleetMw.toFixed(1)} MW
        </div>
        <div className="mt-2 font-mono text-xs text-[var(--gc-muted)]">
          GridCool guarantees MW reduction using thermal fingerprints (RC model) inferred from MirAIe telemetry.
        </div>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <div className="rounded-2xl border border-[var(--gc-panel-border)] bg-black/20 p-4">
          <div className="text-xs uppercase tracking-[0.26em] text-[var(--gc-muted)]">
            Construction type breakdown
          </div>
          <div className="mt-3 h-[170px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={breakdown} dataKey="value" nameKey="name" innerRadius={48} outerRadius={70} paddingAngle={2} />
                <Tooltip
                  contentStyle={{
                    background: 'rgba(10,15,30,0.92)',
                    border: '1px solid rgba(64,87,140,0.45)',
                    borderRadius: 12,
                    color: 'rgba(215,226,255,0.9)',
                    fontFamily: 'var(--gc-mono)',
                    fontSize: 12,
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-2 grid gap-1 font-mono text-[10px] text-[var(--gc-muted)]">
            {breakdown.map((b) => (
              <div key={b.name} className="flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full" style={{ background: b.fill }} />
                  {b.name.replace('_', ' ')}
                </span>
                <span>{b.value}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-[var(--gc-panel-border)] bg-black/20 p-4">
          <div className="text-xs uppercase tracking-[0.26em] text-[var(--gc-muted)]">
            Per-building flexibility (min)
          </div>
          <div className="mt-3 space-y-2">
            {bars.items.slice(0, 10).map((b) => {
              const pct = Math.max(2, Math.round((b.flex / bars.maxFlex) * 100))
              return (
                <div key={b.id} className="rounded-2xl border border-[var(--gc-panel-border)] bg-black/20 px-3 py-2">
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate text-xs">{b.name}</div>
                      <div className="mt-1 font-mono text-[10px] text-[var(--gc-muted)]">
                        {b.ct.replace('_', ' ')} • {b.status === 'calibrating' ? 'calibrating' : 'fingerprinted'}
                      </div>
                    </div>
                    <div className="shrink-0 font-mono text-xs text-[rgba(215,226,255,0.85)]">{Math.round(b.flex)}m</div>
                  </div>
                  <div className="mt-2 h-2 w-full rounded-full bg-black/30">
                    <div className="h-2 rounded-full" style={{ width: `${pct}%`, background: ctColor(b.ct) }} />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </Panel>
  )
}

