export type ApiTokenResponse = { access_token: string }
export type ApiUserOut = { id: string; email: string }

export type ApiGarmentOut = {
  id: string
  garment_type: string
  crop_path: string | null
  attributes: Record<string, unknown> | null
}

export type ApiCaptureOut = {
  id: string
  user_id: string
  created_at: string
  image_path: string | null
  status: 'queued' | 'processing' | 'done' | 'failed' | string
  error: string | null
  global_attributes: Record<string, unknown> | null
  garments: ApiGarmentOut[]
  matches: Array<Record<string, unknown>>
}

export type ApiUserProfileOut = {
  user_id: string
  user_embedding_meta: Record<string, unknown>
  radar_vector: Record<string, number>
  brand_stats: Record<string, number>
  color_stats: Record<string, number>
  category_bias: Record<string, number>
  updated_at: string | null
}

export type ApiRadarHistoryPoint = {
  id: string
  created_at: string
  radar_vector: Record<string, number>
}

export type ApiCatalogRecommendationOut = {
  rank: number
  title: string
  product_url: string
  source?: string | null
  price_text?: string | null
  price_value?: number | null
  query_used?: string | null
  recommendation_image_url?: string | null
  has_recommendation_image_bytes: boolean
}

export type ApiProductSearchOut = {
  product_id: string
  title: string
  brand: string | null
  category: string | null
  price: number | null
  currency: string | null
  image_url?: string | null
  source: string | null
  product_url: string | null
  similarity: number | null
  rank: number | null
}

export type ApiProductRecommendationOut = {
  product_id: string
  title: string
  brand: string | null
  category: string | null
  price: number | null
  currency: string | null
  image_url?: string | null
  product_url: string | null
  reason?: string | null
  score?: number | null
}

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000').replace(/\/+$/, '')
const DEV_EMAIL = process.env.NEXT_PUBLIC_DEV_AUTH_EMAIL || ''
const DEV_PASSWORD = process.env.NEXT_PUBLIC_DEV_AUTH_PASSWORD || ''

const TOKEN_STORAGE_KEY = 'aesthetica_access_token'

function isBrowser() {
  return typeof window !== 'undefined'
}

export function getStoredToken(): string | null {
  if (!isBrowser()) return null
  try {
    return window.localStorage.getItem(TOKEN_STORAGE_KEY)
  } catch {
    return null
  }
}

export function setStoredToken(token: string | null) {
  if (!isBrowser()) return
  try {
    if (!token) window.localStorage.removeItem(TOKEN_STORAGE_KEY)
    else window.localStorage.setItem(TOKEN_STORAGE_KEY, token)
  } catch {
    // ignore storage failures (private mode, etc.)
  }
}

async function apiFetch<T>(
  path: string,
  opts: {
    method?: string
    token?: string | null
    json?: unknown
    signal?: AbortSignal
  } = {},
): Promise<T> {
  const url = `${API_BASE_URL}${path.startsWith('/') ? '' : '/'}${path}`
  const res = await fetch(url, {
    method: opts.method ?? (opts.json ? 'POST' : 'GET'),
    headers: {
      ...(opts.json ? { 'Content-Type': 'application/json' } : {}),
      ...(opts.token ? { Authorization: `Bearer ${opts.token}` } : {}),
    },
    body: opts.json ? JSON.stringify(opts.json) : undefined,
    signal: opts.signal,
  })

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`API ${res.status} ${res.statusText}: ${text}`)
  }

  return (await res.json()) as T
}

export async function loginWithPassword(email: string, password: string, signal?: AbortSignal) {
  const tokenResp = await apiFetch<ApiTokenResponse>(
    '/v1/auth/login',
    { json: { email, password }, signal },
  )
  setStoredToken(tokenResp.access_token)
  return tokenResp.access_token
}

export function logout() {
  setStoredToken(null)
}

export async function ensureDevToken(signal?: AbortSignal): Promise<string | null> {
  const existing = getStoredToken()
  if (existing) return existing
  if (!DEV_EMAIL || !DEV_PASSWORD) return null

  return await loginWithPassword(DEV_EMAIL, DEV_PASSWORD, signal)
}

export function mediaUrl(path: string, token: string) {
  const u = new URL(`${API_BASE_URL}/v1/media`)
  u.searchParams.set('path', path)
  u.searchParams.set('token', token)
  return u.toString()
}

export const api = {
  baseUrl: API_BASE_URL,
  me: (token: string, signal?: AbortSignal) =>
    apiFetch<ApiUserOut>('/v1/auth/me', { token, signal }),
  userCaptures: (userId: string, token: string, limit = 20, signal?: AbortSignal) =>
    apiFetch<ApiCaptureOut[]>(`/v1/users/${encodeURIComponent(userId)}/captures?limit=${limit}`, {
      token,
      signal,
    }),
  userProfile: (userId: string, token: string, signal?: AbortSignal) =>
    apiFetch<ApiUserProfileOut>(`/v1/users/${encodeURIComponent(userId)}/profile`, { token, signal }),
  radarHistory: (userId: string, token: string, days = 30, signal?: AbortSignal) =>
    apiFetch<ApiRadarHistoryPoint[]>(
      `/v1/users/${encodeURIComponent(userId)}/radar/history?days=${days}`,
      { token, signal },
    ),
  catalogRecommendations: (token: string, limit = 24, signal?: AbortSignal) =>
    apiFetch<ApiCatalogRecommendationOut[]>(`/v1/catalog/recommendations?limit=${limit}`, { token, signal }),
  productSearchByCapture: (
    captureId: string,
    garmentType: string,
    token: string,
    topK = 6,
    includeWeb = true,
    signal?: AbortSignal,
  ) =>
    apiFetch<ApiProductSearchOut[]>(
      `/v1/products/search?capture_id=${encodeURIComponent(captureId)}&garment_type=${encodeURIComponent(garmentType)}&top_k=${topK}&include_web=${includeWeb ? 'true' : 'false'}`,
      { token, signal },
    ),
  recommendations: (token: string, limit = 24, signal?: AbortSignal) =>
    apiFetch<ApiProductRecommendationOut[]>(`/v1/products/recommendations?limit=${limit}`, {
      token,
      signal,
    }),
}

