import { NextRequest } from 'next/server'

function getApiOrigin() {
  const base = (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000').replace(/\/+$/, '')
  try {
    return new URL(base).origin
  } catch {
    return 'http://localhost:8000'
  }
}

function isAllowedOrigin(u: URL, apiOrigin: string) {
  if (u.origin === apiOrigin) return true
  // Allow Supabase Storage public URLs (used for catalog_requests.image_path).
  if (u.hostname.endsWith('.supabase.co') || u.hostname.endsWith('.supabase.in')) return true
  return false
}

export const runtime = 'nodejs'

export async function GET(req: NextRequest) {
  const raw = req.nextUrl.searchParams.get('url')
  if (!raw) return new Response('Missing url', { status: 400 })

  let u: URL
  try {
    u = new URL(raw)
  } catch {
    return new Response('Invalid url', { status: 400 })
  }

  if (u.protocol !== 'http:' && u.protocol !== 'https:') {
    return new Response('Unsupported protocol', { status: 400 })
  }

  const apiOrigin = getApiOrigin()
  if (!isAllowedOrigin(u, apiOrigin)) {
    return new Response('Forbidden', { status: 403 })
  }

  const ctrl = new AbortController()
  const timeout = setTimeout(() => ctrl.abort(), 12_000)
  let upstream: Response
  try {
    upstream = await fetch(u.toString(), {
      method: 'GET',
      redirect: 'follow',
      signal: ctrl.signal,
      headers: {
        // Some CDNs/images behave differently without a UA.
        'user-agent': 'Mozilla/5.0 (Aesthetica Image Proxy)',
        accept: 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
      },
    })
  } catch (err) {
    clearTimeout(timeout)
    const msg = err && typeof err === 'object' && 'name' in err && (err as any).name === 'AbortError' ? 'Timeout' : 'Fetch failed'
    return new Response(`Upstream error: ${msg}`, { status: 502 })
  } finally {
    clearTimeout(timeout)
  }

  if (!upstream.body) return new Response('Upstream missing body', { status: 502 })

  const headers = new Headers()
  const contentType = upstream.headers.get('content-type') || 'application/octet-stream'
  headers.set('content-type', contentType)
  headers.set('cache-control', upstream.ok ? 'public, max-age=300' : 'no-store')

  // Pass-through upstream status (helps debug 401/403 vs true 502s).
  return new Response(upstream.body, { status: upstream.status, headers })
}

