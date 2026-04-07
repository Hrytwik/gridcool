export type Severity = 'ok' | 'warning' | 'critical'

export type DashboardBuilding = {
  building_id: string
  name: string
  lat: number
  lng: number
  ac_count: number
  enrolled_kw: number
  severity: Severity
  last_action: string | null
  last_ack?: string | null
}

export type DemandPoint = {
  ts: string
  predicted_mw: number
  actual_mw: number
}

export type DashboardSnapshot = {
  ts: string
  city: string
  stress_score: number
  severity: Severity
  temperature_c: number
  heat_index_c: number
  credits_inr: number
  enrolled_kw_total: number
  estimated_kw_reduction: number
  buildings: DashboardBuilding[]
  demand_curve: DemandPoint[]
  events: string[]
  demo: {
    demo_mode: boolean
    dispatch_active: boolean
    dispatch_until: string | null
  }
}

