import { useMemo, useState } from 'react'
import type { DashboardSnapshot } from '../lib/dashboardTypes'
import { Panel } from '../components/Panel'
import { BuildingDrawer } from '../components/BuildingDrawer'

export function OwnerPortal(props: { snapshot: DashboardSnapshot | null }) {
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const selected = useMemo(() => {
    if (!props.snapshot || !selectedId) return null
    return props.snapshot.buildings.find((b) => b.building_id === selectedId) ?? null
  }, [props.snapshot, selectedId])

  const options = props.snapshot?.buildings ?? []

  return (
    <div className="grid gap-4">
      <Panel title="BUILDING OWNER PORTAL" right="Phase 1 (demo)">
        <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
          <div>
            <div className="text-sm text-[rgba(215,226,255,0.88)]">
              Select your building to view devices, scheduled actions, credits, and last MirAIe ACK.
            </div>
            <div className="mt-2 font-mono text-xs text-[var(--gc-muted)]">
              In production this is scoped by account + MirAIe OAuth token.
            </div>
          </div>

          <div className="flex gap-2">
            <select
              className="w-full min-w-[260px] rounded-xl border border-[var(--gc-panel-border)] bg-black/25 px-3 py-2 text-sm text-[rgba(215,226,255,0.9)] outline-none focus:border-[rgba(0,212,255,0.55)]"
              value={selectedId ?? ''}
              onChange={(e) => setSelectedId(e.target.value || null)}
            >
              <option value="">Choose building…</option>
              {options.map((b) => (
                <option key={b.building_id} value={b.building_id}>
                  {b.name}
                </option>
              ))}
            </select>
            <button
              className="rounded-xl border border-[var(--gc-panel-border)] bg-black/25 px-3 py-2 font-mono text-xs text-[var(--gc-muted)] hover:border-[rgba(0,212,255,0.45)]"
              onClick={() => setSelectedId(null)}
            >
              CLEAR
            </button>
          </div>
        </div>
      </Panel>

      <div className="rounded-2xl border border-[var(--gc-panel-border)] bg-black/20 p-4 text-[var(--gc-muted)]">
        Tip: you can also click buildings on the map in the main dashboard.
      </div>

      <BuildingDrawer
        open={!!selectedId}
        building={selected}
        snapshot={props.snapshot}
        onClose={() => setSelectedId(null)}
      />
    </div>
  )
}

