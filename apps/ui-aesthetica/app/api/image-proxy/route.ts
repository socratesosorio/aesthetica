import { NextRequest } from 'next/server'

function getApiOrigin() {
  const base = (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000').replace(/\/+$/, '')
  try {
    return new URL(base).origin
  } catch {
    return 'http://localhost:8000'
  }
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
  if (u.origin !== apiOrigin) {
    return new Response('Forbidden', { status: 403 })
  }

  const upstream = await fetch(u.toString(), { method: 'GET' })
  if (!upstream.ok || !upstream.body) {
    const text = await upstream.text().catch(() => '')
    return new Response(`Upstream ${upstream.status}: ${text}`, { status: 502 })
  }

  const headers = new Headers()
  const contentType = upstream.headers.get('content-type') || 'application/octet-stream'
  headers.set('content-type', contentType)
  headers.set('cache-control', 'private, max-age=60')

  return new Response(upstream.body, { status: 200, headers })
}

