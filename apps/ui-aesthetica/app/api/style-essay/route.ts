import { NextRequest } from 'next/server'

export const runtime = 'nodejs'

type Payload = {
  topAesthetic?: string
  era?: string
  phase?: string
  palette?: string[]
  microTrends?: string[]
  vec?: number[]
  nextVec?: number[]
}

export async function POST(req: NextRequest) {
  const key = process.env.OPENAI_API_KEY
  const body = (await req.json().catch(() => ({}))) as Payload

  // Safe fallback: don’t fail the page if AI isn’t configured.
  if (!key) {
    return Response.json({
      essay: null,
      reason: 'OPENAI_API_KEY not set',
    })
  }

  const palette = Array.isArray(body.palette) ? body.palette.slice(0, 4) : []
  const micro = Array.isArray(body.microTrends) ? body.microTrends.slice(0, 4) : []

  const prompt = `Write a short, poetic monthly style recap (120-170 words).
Tone: confident, insightful, not cringe, "Spotify Wrapped" energy.
Avoid bullet points; use 2 short paragraphs.
Include: top aesthetic, era, phase, palette, 1-2 micro-trends, and a gentle forecast.

Top aesthetic: ${body.topAesthetic ?? '—'}
Era: ${body.era ?? '—'}
Phase: ${body.phase ?? '—'}
Palette: ${palette.join(', ') || '—'}
Micro-trends: ${micro.join(' | ') || '—'}
`

  try {
    const res = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${key}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: process.env.OPENAI_MODEL || 'gpt-4o-mini',
        messages: [
          { role: 'system', content: 'You are a fashion identity analyst and writer.' },
          { role: 'user', content: prompt },
        ],
        temperature: 0.8,
        max_tokens: 240,
      }),
    })

    if (!res.ok) {
      const text = await res.text().catch(() => '')
      return Response.json({ essay: null, reason: `OpenAI ${res.status}: ${text}` }, { status: 200 })
    }

    const json = (await res.json().catch(() => null)) as any
    const essay =
      (typeof json?.choices?.[0]?.message?.content === 'string' && json.choices[0].message.content.trim()) || null

    return Response.json({ essay }, { status: 200 })
  } catch (e) {
    return Response.json({ essay: null, reason: e instanceof Error ? e.message : 'OpenAI request failed' }, { status: 200 })
  }
}

