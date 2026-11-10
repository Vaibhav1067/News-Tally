import type {
  AnalyzeResponse, Facets, FactCheck, FactCheckPage, HistoryItem, IndiaMapData, ModelsInfo, Statistics,
} from '../types/api'

const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? ''

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    })
  } catch {
    throw new ApiError(0, 'Cannot reach the News Tally API. Is the backend running on port 8000?')
  }
  if (!res.ok) {
    let msg = `Request failed (${res.status})`
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') msg = body.detail
      if (Array.isArray(body.errors) && body.errors.length) msg = body.errors.map((e: { message: string }) => e.message).join('; ')
    } catch { /* non-JSON error */ }
    throw new ApiError(res.status, msg)
  }
  return res.json() as Promise<T>
}

export interface AnalyzeInput { text?: string; url?: string; language?: string; save_to_history?: boolean }

export const api = {
  analyze: (body: AnalyzeInput) => request<AnalyzeResponse>('/api/analyze', { method: 'POST', body: JSON.stringify(body) }),
  statistics: () => request<Statistics>('/api/statistics'),
  indiaMap: () => request<IndiaMapData>('/api/map'),
  factChecks: (params: Record<string, string | number | undefined>) => {
    const q = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== '') q.set(k, String(v)) })
    return request<FactCheckPage>(`/api/fact-checks?${q}`)
  },
  factCheck: (id: string) => request<FactCheck>(`/api/fact-checks/${encodeURIComponent(id)}`),
  facets: () => request<Facets>('/api/fact-checks/facets'),
  models: () => request<ModelsInfo>('/api/models'),
  history: () => request<HistoryItem[]>('/api/history'),
  health: () => request<{ status: string; fact_checks_loaded: number; components: Record<string, any> }>('/api/health'),
  feedback: (analysis_id: string, feedback_type: string, comments?: string) =>
    request<{ id: number }>('/api/feedback', { method: 'POST', body: JSON.stringify({ analysis_id, feedback_type, comments }) }),
}
