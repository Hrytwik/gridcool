import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { DemandPoint } from '../lib/dashboardTypes'

function fmtTime(iso: string) {
  try {
    const d = new Date(iso)
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

export function DemandChart(props: {
  points: DemandPoint[]
  dispatchActive: boolean
}) {
  const data = props.points.map((p) => ({
    ...p,
    t: fmtTime(p.ts),
    hour: (() => {
      try {
        return new Date(p.ts).getHours()
      } catch {
        return 0
      }
    })(),
  }))

  // Highlight the evening peak window (6 PM - 8 PM) for the demo story.
  const peakStartIdx = data.findIndex((d) => d.hour === 18)
  const peakEndIdx = data.findIndex((d) => d.hour === 20)
  const peakStart = peakStartIdx >= 0 ? data[peakStartIdx]?.t : undefined
  const peakEnd = peakEndIdx >= 0 ? data[peakEndIdx]?.t : undefined

  return (
    <div className="h-[260px] w-full rounded-2xl border border-[var(--gc-panel-border)] bg-black/25 p-3">
      <div className="mb-2 flex items-center justify-between">
        <div className="text-xs uppercase tracking-[0.26em] text-[var(--gc-muted)]">
          Peak demand curve
        </div>
        <div className="font-mono text-xs text-[var(--gc-muted)]">
          {props.dispatchActive ? (
            <span className="text-[var(--gc-blue)]">Intervention active</span>
          ) : (
            'Monitoring'
          )}
        </div>
      </div>

      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="rgba(255,255,255,0.07)" strokeDasharray="3 6" />
          <XAxis
            dataKey="t"
            tick={{ fill: 'rgba(215,226,255,0.6)', fontSize: 11, fontFamily: 'var(--gc-mono)' }}
            axisLine={{ stroke: 'rgba(255,255,255,0.12)' }}
            tickLine={false}
            minTickGap={18}
          />
          <YAxis
            tick={{ fill: 'rgba(215,226,255,0.6)', fontSize: 11, fontFamily: 'var(--gc-mono)' }}
            axisLine={{ stroke: 'rgba(255,255,255,0.12)' }}
            tickLine={false}
            width={44}
            domain={['dataMin - 120', 'dataMax + 120']}
            tickFormatter={(v: number) => Math.round(v).toString()}
          />
          <Tooltip
            contentStyle={{
              background: 'rgba(10,15,30,0.92)',
              border: '1px solid rgba(64,87,140,0.45)',
              borderRadius: 12,
              color: 'rgba(215,226,255,0.9)',
              fontFamily: 'var(--gc-mono)',
              fontSize: 12,
            }}
            labelStyle={{ color: 'rgba(215,226,255,0.7)' }}
          />

          {peakStart && peakEnd ? (
            <ReferenceArea
              x1={peakStart}
              x2={peakEnd}
              fill={props.dispatchActive ? 'rgba(0,212,255,0.12)' : 'rgba(255,170,0,0.08)'}
              strokeOpacity={0}
            />
          ) : null}

          <Line
            type="monotone"
            dataKey="predicted_mw"
            stroke="rgba(0,212,255,0.95)"
            strokeWidth={2.2}
            dot={false}
            activeDot={{ r: 4 }}
          />
          <Line
            type="monotone"
            dataKey="actual_mw"
            stroke="rgba(215,226,255,0.55)"
            strokeWidth={1.6}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

