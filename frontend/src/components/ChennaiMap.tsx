import { divIcon, latLngBounds } from 'leaflet'
import { motion } from 'framer-motion'
import { useEffect, useMemo, useState } from 'react'
import { MapContainer, Marker, TileLayer, Tooltip as LeafletTooltip, ZoomControl } from 'react-leaflet'
import type { DashboardBuilding, Severity } from '../lib/dashboardTypes'

function markerHtml(sev: Severity, dispatchActive: boolean) {
  const base =
    sev === 'critical' ? 'gc-marker critical' : sev === 'warning' ? 'gc-marker warning' : 'gc-marker'
  const cls = dispatchActive ? `${base} dispatch` : base
  return `<div class="${cls}" />`
}

function iconFor(sev: Severity, dispatchActive: boolean) {
  return divIcon({
    className: '',
    html: markerHtml(sev, dispatchActive),
    iconSize: [14, 14],
    iconAnchor: [7, 7],
  })
}

export function ChennaiMap(props: {
  buildings: DashboardBuilding[]
  dispatchActive: boolean
  onSelectBuilding?: (buildingId: string) => void
}) {
  const bounds = useMemo(() => {
    const pts = props.buildings.map((b) => [b.lat, b.lng] as [number, number])
    if (!pts.length) return latLngBounds([[13.0827, 80.2707], [13.0827, 80.2707]])
    return latLngBounds(pts)
  }, [props.buildings])

  const [waveKey, setWaveKey] = useState(0)
  const [prevDispatch, setPrevDispatch] = useState(props.dispatchActive)
  useEffect(() => {
    if (!prevDispatch && props.dispatchActive) {
      setWaveKey((k) => k + 1)
    }
    setPrevDispatch(props.dispatchActive)
  }, [prevDispatch, props.dispatchActive])

  return (
    <div className="overflow-hidden rounded-2xl border border-[var(--gc-panel-border)] bg-black/25">
      <div className="flex items-center justify-between px-4 pt-4">
        <div className="text-xs uppercase tracking-[0.26em] text-[var(--gc-muted)]">
          Chennai — enrolled buildings
        </div>
        <div className="font-mono text-xs text-[var(--gc-muted)]">
          Nodes: {props.buildings.length}
        </div>
      </div>

      <div className="relative h-[420px] w-full p-3 pt-3">
        {/* Legend overlay */}
        <div className="pointer-events-none absolute left-6 top-16 z-[1000] rounded-xl border border-[var(--gc-panel-border)] bg-black/55 px-3 py-2 backdrop-blur sm:top-6">
          <div className="font-mono text-[10px] tracking-[0.28em] text-[var(--gc-muted)]">LEGEND</div>
          <div className="mt-2 grid gap-1 text-xs text-[rgba(215,226,255,0.85)]">
            <div className="flex items-center gap-2">
              <span className="gc-marker" style={{ display: 'inline-block' }} /> <span>Normal</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="gc-marker warning" style={{ display: 'inline-block' }} /> <span>Warning</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="gc-marker critical" style={{ display: 'inline-block' }} /> <span>Critical</span>
            </div>
          </div>
        </div>

        {/* Attribution (keep legal, but subtle) */}
        <div className="absolute bottom-6 right-6 z-[1000] rounded-lg border border-[var(--gc-panel-border)] bg-black/55 px-2 py-1 font-mono text-[10px] text-[var(--gc-muted)] backdrop-blur">
          © OpenStreetMap • © CARTO
        </div>

        {/* Dispatch wave (one-shot) */}
        <motion.div
          key={waveKey}
          className="pointer-events-none absolute left-1/2 top-1/2 z-[900] h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full"
          initial={{ scale: 0.2, opacity: 0 }}
          animate={
            props.dispatchActive
              ? { scale: [0.2, 18], opacity: [0, 0.28, 0] }
              : { scale: 0.2, opacity: 0 }
          }
          transition={{ duration: 1.6, ease: 'easeOut' }}
          style={{
            border: `1px solid ${props.dispatchActive ? 'rgba(0,212,255,0.55)' : 'transparent'}`,
            boxShadow: props.dispatchActive ? '0 0 80px rgba(0,212,255,0.25)' : 'none',
          }}
        />

        <MapContainer
          bounds={bounds}
          boundsOptions={{ padding: [32, 32] }}
          zoom={13}
          scrollWheelZoom={false}
          attributionControl={false}
          zoomControl={false}
          style={{ height: '100%', width: '100%', borderRadius: 16 }}
        >
          <ZoomControl position="topright" />
          <TileLayer
            // Free dark tiles (no key). Great for hackathon demo; swap later if needed.
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          />

          {props.buildings.map((b) => (
            <Marker
              key={b.building_id}
              position={[b.lat, b.lng]}
              icon={iconFor(b.severity, props.dispatchActive)}
              eventHandlers={{
                click: () => props.onSelectBuilding?.(b.building_id),
              }}
            >
              <LeafletTooltip direction="top" offset={[0, -6]} opacity={1}>
                <div className="font-mono text-xs">
                  <div className="font-sans text-sm">{b.name}</div>
                  <div style={{ opacity: 0.8 }}>{b.ac_count} AC • {b.enrolled_kw.toFixed(1)} kW</div>
                </div>
              </LeafletTooltip>
            </Marker>
          ))}
        </MapContainer>
      </div>
    </div>
  )
}

