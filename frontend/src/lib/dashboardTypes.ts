export type Severity = 'ok' | 'warning' | 'critical'

export type ThermalFingerprint = {
  flexibility_window_minutes: number
  construction_type: 'top_floor' | 'ground_floor' | 'corner_unit' | 'mid_floor'
  thermal_mass_class: 'low' | 'medium' | 'high'
  calibration_status: 'calibrating' | 'fingerprinted'
  calibration_progress_pct: number
  rc_r?: number
  rc_c?: number
}

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
  thermal_fingerprint?: ThermalFingerprint | null
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

