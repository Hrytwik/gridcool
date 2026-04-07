import { useMemo } from 'react'
import type { DashboardSnapshot } from '../lib/dashboardTypes'
import { Panel } from '../components/Panel'

function downloadJson(filename: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function toCsvRow(values: Array<string | number | boolean | null | undefined>) {
  return values
    .map((v) => {
      const s = String(v ?? '')
      const needsQuotes = /[",\n]/.test(s)
      const escaped = s.replace(/"/g, '""')
      return needsQuotes ? `"${escaped}"` : escaped
    })
    .join(',')
}

function downloadCsv(filename: string, rows: string[][]) {
  const csv = rows.map((r) => toCsvRow(r)).join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export function AdminPanel(props: { snapshot: DashboardSnapshot | null }) {
  const report = useMemo(() => {
    const s = props.snapshot
    if (!s) return null

    const dispatchEvents = s.events.filter((e) => e.toLowerCase().includes('dispatch'))
    const ackEvents = s.events.filter((e) => e.toLowerCase().includes('miraie ack'))

    return {
      ts: s.ts,
      city: s.city,
      stress_score: s.stress_score,
      enrolled_kw_total: s.enrolled_kw_total,
      estimated_kw_reduction: s.estimated_kw_reduction,
      credits_inr: s.credits_inr,
      buildings: s.buildings.length,
      dispatch_active: s.demo.dispatch_active,
      dispatch_until: s.demo.dispatch_until,
      dispatch_events: dispatchEvents,
      ack_events: ackEvents,
    }
  }, [props.snapshot])

  const csvRows = useMemo(() => {
    const s = props.snapshot
    if (!s) return null

    // Summary row + per-building rows, DISCOM-friendly.
    const rows: string[][] = []
    rows.push([
      'ts',
      'city',
      'stress_score',
      'enrolled_kw_total',
      'estimated_kw_reduction',
      'credits_inr',
      'buildings',
      'dispatch_active',
      'dispatch_until',
    ])
    rows.push([
      s.ts,
      s.city,
      String(s.stress_score),
      String(s.enrolled_kw_total),
      String(s.estimated_kw_reduction),
      String(s.credits_inr),
      String(s.buildings.length),
      String(s.demo.dispatch_active),
      String(s.demo.dispatch_until ?? ''),
    ])

    rows.push([''])
    rows.push(['building_id', 'name', 'ac_count', 'enrolled_kw', 'severity', 'last_action', 'last_ack'])
    for (const b of s.buildings) {
      rows.push([
        b.building_id,
        b.name,
        String(b.ac_count),
        String(b.enrolled_kw),
        b.severity,
        b.last_action ?? '',
        b.last_ack ?? '',
      ])
    }

    return rows
  }, [props.snapshot])

  return (
    <div className="grid gap-4">
      <Panel title="DISCOM / ADMIN PANEL" right="Phase 1 (demo)">
        <div className="text-sm text-[rgba(215,226,255,0.88)]">
          Aggregate fleet view for DISCOM justification: capacity enrolled, reduction delivered, and credits paid.
        </div>
      </Panel>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-2xl border border-[var(--gc-panel-border)] bg-black/25 p-4">
          <div className="text-xs uppercase tracking-[0.26em] text-[var(--gc-muted)]">Enrolled capacity</div>
          <div className="mt-2 text-3xl font-semibold">
            {props.snapshot ? `${props.snapshot.enrolled_kw_total.toFixed(1)} kW` : '—'}
          </div>
          <div className="mt-2 font-mono text-xs text-[var(--gc-muted)]">
            Buildings: {props.snapshot?.buildings.length ?? '—'}
          </div>
        </div>

        <div className="rounded-2xl border border-[var(--gc-panel-border)] bg-black/25 p-4">
          <div className="text-xs uppercase tracking-[0.26em] text-[var(--gc-muted)]">Reduction delivered</div>
          <div className="mt-2 text-3xl font-semibold">
            {props.snapshot ? `${props.snapshot.estimated_kw_reduction.toFixed(1)} kW` : '—'}
          </div>
          <div className="mt-2 font-mono text-xs text-[var(--gc-muted)]">
            Dispatch: {props.snapshot?.demo.dispatch_active ? 'ACTIVE' : 'STANDBY'}
          </div>
        </div>

        <div className="rounded-2xl border border-[var(--gc-panel-border)] bg-black/25 p-4">
          <div className="text-xs uppercase tracking-[0.26em] text-[var(--gc-muted)]">Credits paid (₹)</div>
          <div className="mt-2 text-3xl font-semibold">
            {props.snapshot ? props.snapshot.credits_inr.toFixed(2) : '—'}
          </div>
          <div className="mt-2 font-mono text-xs text-[var(--gc-muted)]">
            Demo rate: kWh reduced × ₹8
          </div>
        </div>
      </div>

      <Panel
        title="EXPORTABLE REPORT"
        right={
          report ? (
            <div className="flex items-center gap-2">
              <button
                className="rounded-xl border border-[var(--gc-panel-border)] bg-black/25 px-3 py-2 font-mono text-[10px] tracking-[0.22em] uppercase text-[var(--gc-muted)] hover:border-[rgba(0,212,255,0.45)]"
                onClick={() => downloadJson(`gridcool_report_${new Date().toISOString()}.json`, report)}
              >
                DOWNLOAD JSON
              </button>
              <button
                className="rounded-xl border border-[var(--gc-panel-border)] bg-black/25 px-3 py-2 font-mono text-[10px] tracking-[0.22em] uppercase text-[var(--gc-muted)] hover:border-[rgba(0,212,255,0.45)]"
                onClick={() => {
                  if (!csvRows) return
                  downloadCsv(`gridcool_report_${new Date().toISOString()}.csv`, csvRows)
                }}
              >
                DOWNLOAD CSV
              </button>
            </div>
          ) : (
            'Waiting…'
          )
        }
      >
        <div className="font-mono text-xs text-[var(--gc-muted)]">
          {report ? (
            <pre className="overflow-auto rounded-2xl border border-[var(--gc-panel-border)] bg-black/25 p-4">
              {JSON.stringify(report, null, 2)}
            </pre>
          ) : (
            'No telemetry yet.'
          )}
        </div>
      </Panel>
    </div>
  )
}

