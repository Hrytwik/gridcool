type Json = Record<string, unknown>

function backendHttp() {
  return (import.meta.env.VITE_BACKEND_HTTP as string | undefined) ?? 'http://localhost:8000'
}

async function post<T extends Json>(path: string, body: Json): Promise<T> {
  const res = await fetch(`${backendHttp()}${path}`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `Request failed (${res.status})`)
  }
  return (await res.json()) as T
}

export async function demoForceStress(score = 82, minutes = 10) {
  return await post('/demo/force-stress', { score, minutes })
}

export async function demoTriggerDispatch(minutes = 90) {
  return await post('/demo/trigger-dispatch', { minutes })
}

export async function demoEnrollBuilding(input: {
  name: string
  lat: number
  lng: number
  ac_count: number
}) {
  return await post('/demo/enroll-building', input)
}

