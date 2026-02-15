/* eslint-disable @typescript-eslint/no-explicit-any */
'use client'

import * as React from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ChartContainer } from '@/components/ui/chart'
import { cn } from '@/lib/utils'
import { TasteRadar } from '@/components/aesthetica/taste-radar'

export type TasteAnalyticsCapture = {
  id: string
  createdAtLabel: string
  createdAtISO?: string
  status: string
  imageUrl: string
}

export type TasteAnalyticsRec = {
  title: string
  brand?: string | null
  badge?: string | null
  note?: string | null
}

export type TasteAnalyticsStyleScore = {
  created_at: string
  minimal?: number | null
  structured?: number | null
  neutral?: number | null
  classic?: number | null
  casual?: number | null
  description?: string | null
}

type Vec5 = [number, number, number, number, number] // minimal, structured, neutral, classic, casual

function clamp01(x: number) {
  return Math.max(0, Math.min(1, x))
}

function v(n: unknown, fallback = 50) {
  const x = typeof n === 'number' && Number.isFinite(n) ? n : fallback
  return Math.max(0, Math.min(100, x))
}

function toVec5(s: TasteAnalyticsStyleScore | null | undefined): Vec5 {
  return [v(s?.minimal), v(s?.structured), v(s?.neutral), v(s?.classic), v(s?.casual)]
}

function dot(a: number[], b: number[]) {
  let out = 0
  for (let i = 0; i < Math.min(a.length, b.length); i++) out += a[i]! * b[i]!
  return out
}

function norm(a: number[]) {
  return Math.sqrt(dot(a, a))
}

function cosine(a: number[], b: number[]) {
  const na = norm(a)
  const nb = norm(b)
  if (!na || !nb) return 0
  return dot(a, b) / (na * nb)
}

function fmtPct(x: number) {
  const n = Math.round(x)
  return `${Math.max(0, Math.min(100, n))}%`
}

function monthKey(iso: string) {
  const d = new Date(iso)
  if (!Number.isFinite(d.getTime())) return 'unknown'
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

function prettyMonth(iso: string) {
  const d = new Date(iso)
  if (!Number.isFinite(d.getTime())) return '—'
  return d.toLocaleString(undefined, { month: 'short', year: '2-digit' })
}

function stablePick<T>(seed: string, arr: T[]) {
  let h = 0
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) | 0
  return arr[Math.abs(h) % Math.max(1, arr.length)]!
}

function adjectives(vec: Vec5) {
  const [minimal, structured, neutral, classic, casual] = vec
  const a = minimal >= 55 ? 'Minimal' : 'Expressive'
  const b = structured >= 55 ? 'Structured' : 'Relaxed'
  const c = neutral >= 55 ? 'Neutral' : 'Color-forward'
  const d = classic >= 55 ? 'Classic' : 'Experimental'
  const e = casual >= 55 ? 'Casual' : 'Polished'
  return { a, b, c, d, e }
}

function eraLabel(vec: Vec5) {
  const { a, b, c, d, e } = adjectives(vec)
  // A few narrative buckets (hard-coded), selected deterministically.
  const candidates = [
    `${a} ${b} ${c}`,
    `${c} ${b} ${d}`,
    `${a} ${e} ${d}`,
    `${a} ${b} “Soft Power”`,
    `${c} “Quiet Statement”`,
    `${d} “New Proportions”`,
  ]
  return stablePick(`${a}_${b}_${c}_${d}_${e}`, candidates)
}

function percentileFromScore(x: number) {
  // No population baseline yet; map 0..100 to a "pseudo percentile" with a gentle S-curve.
  const t = (x - 50) / 18
  const sig = 1 / (1 + Math.exp(-t))
  return Math.round(sig * 100)
}

const COLOR_WORDS = [
  'black',
  'white',
  'cream',
  'ivory',
  'beige',
  'tan',
  'brown',
  'camel',
  'navy',
  'blue',
  'charcoal',
  'gray',
  'grey',
  'green',
  'olive',
  'khaki',
  'red',
  'burgundy',
  'pink',
  'purple',
  'lavender',
  'yellow',
  'gold',
  'orange',
  'silver',
]

const MATERIAL_WORDS = [
  'denim',
  'leather',
  'suede',
  'wool',
  'cashmere',
  'linen',
  'cotton',
  'silk',
  'satin',
  'velvet',
  'nylon',
  'mesh',
  'tweed',
]

const ITEM_WORDS = [
  'blazer',
  'coat',
  'jacket',
  'trench',
  'hoodie',
  'sweater',
  'knit',
  'shirt',
  'tee',
  't-shirt',
  'trouser',
  'pant',
  'jean',
  'denim',
  'skirt',
  'dress',
  'loafer',
  'boot',
  'sneaker',
  'heel',
  'bag',
]

function tokenize(recs: TasteAnalyticsRec[]) {
  const text = recs
    .map((r) => `${r.title ?? ''} ${r.brand ?? ''} ${r.badge ?? ''} ${r.note ?? ''}`)
    .join(' ')
    .toLowerCase()
  const tokens = text.split(/[^a-z0-9]+/g).filter(Boolean)
  return tokens
}

function topKeywords(tokens: string[], candidates: string[], k = 3) {
  const counts = new Map<string, number>()
  for (const t of tokens) {
    if (!candidates.includes(t)) continue
    counts.set(t, (counts.get(t) ?? 0) + 1)
  }
  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, k)
    .map(([w]) => w)
}

type Archetype = { label: string; meta: string; vec: Vec5 }

const GEO_ARCHETYPES: Archetype[] = [
  { label: '🇪🇸 Barcelona', meta: '2020 · Mediterranean Minimal Revival', vec: [78, 55, 72, 58, 52] },
  { label: '🇫🇷 Paris', meta: '2018 · Soft tailoring + tonal layering', vec: [70, 68, 78, 72, 40] },
  { label: '🇯🇵 Tokyo', meta: '2016 · Sharp minimal + experimental edge', vec: [62, 58, 66, 38, 55] },
  { label: '🇰🇷 Seoul', meta: '2023 · Clean street + silhouette play', vec: [55, 42, 52, 45, 72] },
  { label: '🇺🇸 NYC', meta: '2019 · Urban uniform + monochrome staples', vec: [72, 50, 70, 52, 64] },
]

const CELEB_ARCHETYPES: Archetype[] = [
  { label: 'Zendaya (press-tour tailoring era)', meta: 'Silhouette + polish', vec: [55, 74, 60, 62, 38] },
  { label: 'Timothée Chalamet (lean experimental)', meta: 'Novelty + proportion', vec: [48, 52, 55, 34, 58] },
  { label: 'Rosé (tonal minimal)', meta: 'Tonal + refined', vec: [76, 50, 74, 60, 50] },
  { label: 'Hailey Bieber (clean street)', meta: 'Relaxed + staples', vec: [60, 42, 58, 52, 72] },
]

function bestArchetypes(vec: Vec5, list: Archetype[], topN = 2) {
  return [...list]
    .map((a) => ({ ...a, score: cosine(vec, a.vec) }))
    .sort((x, y) => y.score - x.score)
    .slice(0, topN)
}

function slope(xs: number[], ys: number[]) {
  // simple least squares slope
  const n = Math.min(xs.length, ys.length)
  if (n < 2) return 0
  const mx = xs.slice(0, n).reduce((a, b) => a + b, 0) / n
  const my = ys.slice(0, n).reduce((a, b) => a + b, 0) / n
  let num = 0
  let den = 0
  for (let i = 0; i < n; i++) {
    const dx = xs[i]! - mx
    num += dx * (ys[i]! - my)
    den += dx * dx
  }
  return den ? num / den : 0
}

function forecast(vec: Vec5, history: TasteAnalyticsStyleScore[]) {
  // Forecast 6 weeks (~42 days) forward using recent slope.
  const last = history.slice(0, 12).reverse() // chronological
  const xs = last.map((p) => new Date(p.created_at).getTime()).filter((t) => Number.isFinite(t))
  const take = <K extends keyof TasteAnalyticsStyleScore>(k: K) =>
    last.map((p) => v((p as any)[k] as any)).slice(0, xs.length)

  const x0 = xs[0] ?? Date.now()
  const xNorm = xs.map((t) => (t - x0) / (24 * 3600 * 1000))
  const f = (arr: number[], cur: number) => cur + slope(xNorm, arr) * 42

  const m = f(take('minimal'), vec[0])
  const s = f(take('structured'), vec[1])
  const n = f(take('neutral'), vec[2])
  const c = f(take('classic'), vec[3])
  const ca = f(take('casual'), vec[4])
  return [m, s, n, c, ca].map((x) => Math.max(0, Math.min(100, x))) as Vec5
}

function phaseLabel(cur: Vec5, prev: Vec5) {
  const deltas = [
    { k: 'Minimal', d: cur[0] - prev[0] },
    { k: 'Structured', d: cur[1] - prev[1] },
    { k: 'Neutral', d: cur[2] - prev[2] },
    { k: 'Classic', d: cur[3] - prev[3] },
    { k: 'Casual', d: cur[4] - prev[4] },
  ].sort((a, b) => Math.abs(b.d) - Math.abs(a.d))
  const top = deltas[0]
  if (!top || Math.abs(top.d) < 10) return 'Identity consolidation season'
  const dir = top.d > 0 ? 'toward' : 'away from'
  return `Style mutation phase (${dir} ${top.k.toLowerCase()})`
}

export function TasteAnalytics({
  styleScores,
  captures,
  recommended,
  styleRecommended,
  className,
}: {
  styleScores: TasteAnalyticsStyleScore[]
  captures: TasteAnalyticsCapture[]
  recommended: TasteAnalyticsRec[]
  styleRecommended: TasteAnalyticsRec[]
  className?: string
}) {
  const latest = styleScores?.[0]
  const vec = React.useMemo(() => toVec5(latest), [latest])
  const vecPrev = React.useMemo(() => toVec5(styleScores?.[1]), [styleScores])

  const { a, b, c } = React.useMemo(() => adjectives(vec), [vec])
  const topAesthetic = `${a} ${b} ${c}`
  const topAestheticPct = Math.round((vec[0] + vec[1] + vec[2]) / 3)

  const tokens = React.useMemo(
    () => tokenize([...(recommended ?? []), ...(styleRecommended ?? [])]),
    [recommended, styleRecommended],
  )
  const palette = React.useMemo(() => {
    const tops = topKeywords(tokens, COLOR_WORDS, 3)
    return tops.length ? tops : ['navy', 'charcoal', 'cream']
  }, [tokens])

  const topItem = React.useMemo(() => {
    const tops = topKeywords(tokens, ITEM_WORDS, 1)
    return tops[0] ?? 'outerwear'
  }, [tokens])

  const microTrends = React.useMemo(() => {
    const mats = topKeywords(tokens, MATERIAL_WORDS, 2)
    const colors = topKeywords(tokens, COLOR_WORDS, 2)
    const items = topKeywords(tokens, ITEM_WORDS, 2)

    const out: string[] = []
    if (mats[0]) out.push(`You’re in a ${mats[0]} phase (high frequency in rec keywords).`)
    if (items[0] && items[1]) out.push(`Item drift: more ${items[0]} and ${items[1]} lately.`)
    if (colors[0]) out.push(`Palette pull: ${colors.join(' / ')} showing up repeatedly.`)
    return out.slice(0, 3)
  }, [tokens])

  const geo = React.useMemo(() => bestArchetypes(vec, GEO_ARCHETYPES, 2), [vec])
  const celeb = React.useMemo(() => bestArchetypes(vec, CELEB_ARCHETYPES, 1)[0], [vec])

  const silhouette = React.useMemo(() => {
    const relaxed = 100 - vec[1]
    const structured = vec[1]
    const maximal = 100 - vec[0]
    const sum = relaxed + structured + maximal
    return {
      relaxed: Math.round((relaxed / sum) * 100),
      structured: Math.round((structured / sum) * 100),
      maximal: Math.round((maximal / sum) * 100),
    }
  }, [vec])

  const fashionAge = React.useMemo(() => {
    const age =
      18 +
      (vec[3] / 100) * 8 + // classic
      (vec[1] / 100) * 6 - // structured
      ((100 - vec[2]) / 100) * 2 - // color-forward reduces "age"
      ((100 - vec[0]) / 100) * 2 // maximal reduces "age"
    return Math.round(age * 10) / 10
  }, [vec])

  const era = React.useMemo(() => eraLabel(vec), [vec])
  const phase = React.useMemo(() => phaseLabel(vec, vecPrev), [vec, vecPrev])

  const driftData = React.useMemo(() => {
    const rows = (styleScores ?? [])
      .slice(0, 24)
      .reverse()
      .map((s) => ({
        t: prettyMonth(s.created_at),
        minimal: v(s.minimal),
        structured: v(s.structured),
        neutral: v(s.neutral),
        classic: v(s.classic),
        casual: v(s.casual),
      }))
    return rows
  }, [styleScores])

  const nextVec = React.useMemo(() => forecast(vec, styleScores ?? []), [vec, styleScores])
  const futureSelf = React.useMemo(() => {
    const { a, b, c } = adjectives(nextVec)
    return `${a} ${b} ${c}`
  }, [nextVec])

  const dnaRadar = React.useMemo(() => {
    const experimental = 100 - vec[3]
    const tailored = Math.round((vec[1] * 0.6 + vec[3] * 0.4) * 10) / 10
    const street = Math.round((vec[4] * 0.6 + (100 - vec[3]) * 0.4) * 10) / 10
    return [
      { id: 'minimal_maximal', axis: 'Minimal', leftLabel: 'Maximal', rightLabel: 'Minimal', value: vec[0] },
      { id: 'structured_relaxed', axis: 'Structured', leftLabel: 'Relaxed', rightLabel: 'Structured', value: vec[1] },
      { id: 'neutral_color', axis: 'Neutral', leftLabel: 'Color-forward', rightLabel: 'Neutral', value: vec[2] },
      { id: 'classic_experimental', axis: 'Classic', leftLabel: 'Experimental', rightLabel: 'Classic', value: vec[3] },
      { id: 'casual_formal', axis: 'Casual', leftLabel: 'Formal', rightLabel: 'Casual', value: vec[4] },
      { id: 'experimental', axis: 'Experimental', leftLabel: 'Classic', rightLabel: 'Experimental', value: experimental },
      { id: 'tailored', axis: 'Tailored', leftLabel: 'Loose', rightLabel: 'Tailored', value: tailored },
      { id: 'street', axis: 'Street', leftLabel: 'Refined', rightLabel: 'Street', value: street },
    ]
  }, [vec])

  const [essay, setEssay] = React.useState<string | null>(null)
  const [essayLoading, setEssayLoading] = React.useState(false)

  const loadEssay = React.useCallback(async () => {
    if (essayLoading || essay) return
    setEssayLoading(true)
    try {
      const res = await fetch('/api/style-essay', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topAesthetic,
          era,
          phase,
          palette,
          microTrends,
          vec,
          nextVec,
        }),
      })
      const json = (await res.json().catch(() => null)) as any
      const text = typeof json?.essay === 'string' ? json.essay : null
      setEssay(
        text ||
          `This month, your wardrobe leaned into restraint: ${palette.join(', ')} — with a steady pull toward ${topAesthetic.toLowerCase()}. You’re in an ${phase.toLowerCase()} right now, and the signal suggests your next shift may drift toward ${futureSelf.toLowerCase()}.`,
      )
    } catch {
      setEssay(
        `This month, your wardrobe leaned into restraint: ${palette.join(', ')} — with a steady pull toward ${topAesthetic.toLowerCase()}. You’re in an ${phase.toLowerCase()} right now, and the signal suggests your next shift may drift toward ${futureSelf.toLowerCase()}.`,
      )
    } finally {
      setEssayLoading(false)
    }
  }, [essay, essayLoading, era, futureSelf, microTrends, nextVec, palette, phase, topAesthetic, vec])

  const wrappedCards = (
    <div className="grid gap-4 lg:grid-cols-3">
      <div
        className={cn(
          'relative overflow-hidden rounded-3xl border border-border/50 bg-background/50 p-6 backdrop-blur-xl',
          'shadow-[0_32px_90px_rgba(0,0,0,0.16)] dark:shadow-[0_44px_120px_rgba(0,0,0,0.65)]',
        )}
      >
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(800px_circle_at_10%_0%,rgba(0,0,0,0.06),transparent_60%),radial-gradient(700px_circle_at_90%_20%,rgba(0,0,0,0.05),transparent_55%)] dark:bg-[radial-gradient(800px_circle_at_10%_0%,rgba(255,255,255,0.08),transparent_60%),radial-gradient(700px_circle_at_90%_20%,rgba(255,255,255,0.06),transparent_55%)]" />
        <div className="relative flex items-start justify-between gap-4">
          <div>
            <div className="text-muted-foreground text-xs">Your top aesthetic</div>
            <div className="mt-2 text-2xl font-semibold tracking-tight">{topAesthetic}</div>
            <div className="mt-2 flex items-center gap-2">
              <Badge variant="secondary">{fmtPct(topAestheticPct)}</Badge>
              <Badge variant="outline">Taste Analytics · Beta</Badge>
            </div>
          </div>
          <div className="rounded-2xl border border-border/40 bg-muted/20 px-4 py-3 text-right">
            <div className="text-muted-foreground text-[11px]">Era</div>
            <div className="mt-1 text-sm font-medium">{era}</div>
          </div>
        </div>
        <div className="relative mt-5 grid gap-2 text-sm text-muted-foreground">
          <div>
            <span className="text-foreground font-medium">Phase:</span> {phase}
          </div>
          <div>
            <span className="text-foreground font-medium">Future self projection:</span> {futureSelf}
          </div>
        </div>
      </div>

      <div className="grid gap-4">
        <div className="rounded-3xl border border-border/50 bg-background/50 p-6 backdrop-blur-xl">
          <div className="text-muted-foreground text-xs">Fashion age</div>
          <div className="mt-2 text-3xl font-semibold tracking-tight">{fashionAge}</div>
          <div className="text-muted-foreground mt-1 text-sm">years old</div>
          <div className="mt-3 text-xs text-muted-foreground">
            Young silhouette bias, low logo-dependency, high tonal consistency (beta inference).
          </div>
        </div>
        <div className="rounded-3xl border border-border/50 bg-background/50 p-6 backdrop-blur-xl">
          <div className="text-muted-foreground text-xs">Top captured palette</div>
          <div className="mt-2 flex flex-wrap gap-2">
            {palette.map((x) => (
              <Badge key={x} variant="secondary" className="capitalize">
                {x}
              </Badge>
            ))}
          </div>
          <div className="text-muted-foreground mt-3 text-xs">Derived from recommendation keywords + recent signals.</div>
        </div>
      </div>

      <div className="rounded-3xl border border-border/50 bg-background/50 p-6 backdrop-blur-xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-muted-foreground text-xs">Style geography</div>
            <div className="mt-2 text-xl font-semibold">Your closest regions</div>
          </div>
          <Badge variant="outline">Heatmap (beta)</Badge>
        </div>

        <div className="mt-4 grid gap-3">
          {geo.map((g) => (
            <div key={g.label} className="rounded-2xl border border-border/50 bg-muted/10 p-4">
              <div className="flex items-center justify-between gap-3">
                <div className="text-sm font-medium">{g.label}</div>
                <Badge variant="secondary">{fmtPct(Math.round(g.score * 100))}</Badge>
              </div>
              <div className="text-muted-foreground mt-1 text-xs">{g.meta}</div>
            </div>
          ))}
        </div>

        <Separator className="my-4" />

        <div className="grid gap-2">
          <div className="text-muted-foreground text-xs">Celebrity twin</div>
          <div className="rounded-2xl border border-border/50 bg-muted/10 p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="text-sm font-medium">{celeb?.label ?? '—'}</div>
              <Badge variant="secondary">{fmtPct(Math.round((celeb?.score ?? 0) * 100))}</Badge>
            </div>
            <div className="text-muted-foreground mt-1 text-xs">{celeb?.meta ?? ''}</div>
          </div>
        </div>
      </div>
    </div>
  )

  const insightsCards = (
    <div className="grid gap-4 lg:grid-cols-3">
      <div className="rounded-3xl border border-border/50 bg-background/50 p-6 backdrop-blur-xl">
        <div className="text-muted-foreground text-xs">Silhouette bias</div>
        <div className="mt-4 grid gap-2">
          {[
            { k: 'Relaxed', v: silhouette.relaxed },
            { k: 'Structured', v: silhouette.structured },
            { k: 'Maximal', v: silhouette.maximal },
          ].map((row) => (
            <div key={row.k} className="flex items-center justify-between gap-3 rounded-xl border border-border/40 bg-muted/10 px-3 py-2">
              <div className="text-sm font-medium">{row.k}</div>
              <div className="font-mono text-sm">{fmtPct(row.v)}</div>
            </div>
          ))}
        </div>
        <div className="text-muted-foreground mt-3 text-xs">Derived from structured + minimal signals.</div>
      </div>

      <div className="rounded-3xl border border-border/50 bg-background/50 p-6 backdrop-blur-xl">
        <div className="text-muted-foreground text-xs">Micro-trend detection</div>
        <div className="mt-3 grid gap-2">
          {microTrends.map((t, i) => (
            <div key={`${t}_${i}`} className="rounded-2xl border border-border/40 bg-muted/10 p-3 text-sm text-muted-foreground">
              <span className="text-foreground font-medium">Signal:</span> {t}
            </div>
          ))}
          {!microTrends.length ? (
            <div className="text-muted-foreground text-sm">Not enough keyword signal yet.</div>
          ) : null}
        </div>
      </div>

      <div className="rounded-3xl border border-border/50 bg-background/50 p-6 backdrop-blur-xl">
        <div className="text-muted-foreground text-xs">Percentiles (beta)</div>
        <div className="mt-3 grid gap-2">
          {[
            { k: 'Minimal', v: vec[0] },
            { k: 'Structured', v: vec[1] },
            { k: 'Neutral', v: vec[2] },
            { k: 'Classic', v: vec[3] },
          ].map((row) => (
            <div key={row.k} className="flex items-center justify-between gap-3 rounded-xl border border-border/40 bg-muted/10 px-3 py-2">
              <div className="text-sm font-medium">{row.k}</div>
              <div className="text-muted-foreground text-sm">
                top <span className="font-mono text-foreground">{fmtPct(100 - percentileFromScore(row.v))}</span>
              </div>
            </div>
          ))}
        </div>
        <div className="text-muted-foreground mt-3 text-xs">Until we have population baselines, this is a calibrated estimate.</div>
      </div>

      <div className="rounded-3xl border border-border/50 bg-background/50 p-6 backdrop-blur-xl lg:col-span-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-muted-foreground text-xs">Taste match score (social layer)</div>
            <div className="mt-2 text-xl font-semibold">People with similar taste</div>
          </div>
          <Badge variant="outline">Coming soon</Badge>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          {[
            { h: '@alex', vec: [62, 45, 72, 54, 64] as Vec5 },
            { h: '@mila', vec: [74, 62, 68, 70, 42] as Vec5 },
            { h: '@jules', vec: [50, 40, 50, 38, 78] as Vec5 },
          ].map((p) => {
            const s = Math.round(cosine(vec, p.vec) * 100)
            return (
              <div key={p.h} className="rounded-2xl border border-border/50 bg-muted/10 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm font-medium">{p.h}</div>
                  <Badge variant="secondary">{fmtPct(s)}</Badge>
                </div>
                <div className="text-muted-foreground mt-1 text-xs">
                  Overlap strongest on {stablePick(p.h, ['palette', 'silhouette', 'minimalism', 'polish'])}.
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )

  const drift = (
    <div className="grid gap-4 lg:grid-cols-3">
      <div className="rounded-3xl border border-border/50 bg-background/50 p-6 backdrop-blur-xl lg:col-span-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-muted-foreground text-xs">Style drift timeline</div>
            <div className="mt-2 text-xl font-semibold">Your aesthetic over time</div>
          </div>
          <Badge variant="secondary">{styleScores?.length ? `${styleScores.length} pts` : 'sample'}</Badge>
        </div>

        <div className="mt-4">
          <ChartContainer
            config={{
              minimal: { label: 'Minimal', color: 'hsl(var(--foreground))' },
              structured: { label: 'Structured', color: 'rgba(0,0,0,0.55)' },
              neutral: { label: 'Neutral', color: 'rgba(0,0,0,0.35)' },
              classic: { label: 'Classic', color: 'rgba(0,0,0,0.25)' },
            }}
            className="aspect-auto h-[320px] w-full"
          >
            <LineChart data={driftData}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="t" tickLine={false} axisLine={false} interval="preserveStartEnd" />
              <YAxis domain={[0, 100]} tickLine={false} axisLine={false} width={28} />
              <Tooltip
                cursor={{ stroke: 'hsl(var(--border))', strokeWidth: 1 }}
                contentStyle={{
                  background: 'hsl(var(--background))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: 12,
                }}
              />
              <Line type="monotone" dataKey="minimal" stroke="var(--color-minimal)" strokeWidth={2.5} dot={false} />
              <Line
                type="monotone"
                dataKey="structured"
                stroke="var(--color-structured)"
                strokeWidth={2.2}
                dot={false}
              />
              <Line type="monotone" dataKey="neutral" stroke="var(--color-neutral)" strokeWidth={2.0} dot={false} />
              <Line type="monotone" dataKey="classic" stroke="var(--color-classic)" strokeWidth={1.8} dot={false} />
            </LineChart>
          </ChartContainer>
        </div>

        <div className="mt-4 grid gap-2 text-sm text-muted-foreground">
          <div>
            <span className="text-foreground font-medium">Predictive trend model:</span> next 6 weeks trending toward{' '}
            <span className="text-foreground font-medium">{adjectives(nextVec).b.toLowerCase()}</span> +{' '}
            <span className="text-foreground font-medium">{adjectives(nextVec).c.toLowerCase()}</span>.
          </div>
        </div>
      </div>

      <div className="rounded-3xl border border-border/50 bg-background/50 p-6 backdrop-blur-xl">
        <div className="text-muted-foreground text-xs">Unexpected phase</div>
        <div className="mt-2 text-xl font-semibold">Notable swing</div>
        <div className="mt-3 rounded-2xl border border-border/40 bg-muted/10 p-4 text-sm text-muted-foreground">
          {Math.abs(vec[2] - vecPrev[2]) >= 12
            ? `A noticeable shift in palette: you moved ${vec[2] > vecPrev[2] ? 'more neutral' : 'more color-forward'} recently.`
            : `No major swing detected — your signal is stable (which is a flex).`}
        </div>

        <Separator className="my-4" />

        <div className="text-muted-foreground text-xs">Most captured item type</div>
        <div className="mt-2 text-lg font-semibold capitalize">{topItem}</div>
        <div className="text-muted-foreground mt-1 text-xs">
          Inferred from recommendation keywords and recent signals (beta).
        </div>

        <Separator className="my-4" />

        <div className="text-muted-foreground text-xs">Captures</div>
        <div className="mt-3 grid gap-2">
          {captures?.slice(0, 4).map((c) => (
            <div key={c.id} className="flex items-center justify-between gap-3 rounded-xl border border-border/40 bg-muted/10 px-3 py-2">
              <div className="truncate text-sm font-medium">{c.createdAtLabel}</div>
              <Badge variant="outline">{c.status}</Badge>
            </div>
          ))}
          {!captures?.length ? <div className="text-muted-foreground text-sm">No captures yet.</div> : null}
        </div>
      </div>
    </div>
  )

  const dna = (
    <div className="grid gap-4 lg:grid-cols-3">
      <div className="rounded-3xl border border-border/50 bg-background/50 p-6 backdrop-blur-xl lg:col-span-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-muted-foreground text-xs">Style DNA</div>
            <div className="mt-2 text-xl font-semibold">Your identity vector</div>
          </div>
          <Badge variant="secondary">{styleScores?.length ? 'style_scores' : 'sample'}</Badge>
        </div>
        <div className="mt-4">
          <TasteRadar data={dnaRadar as any} className="aspect-auto h-[420px] w-full" />
        </div>
      </div>

      <div className="rounded-3xl border border-border/50 bg-background/50 p-6 backdrop-blur-xl">
        <div className="text-muted-foreground text-xs">Future self (projection)</div>
        <div className="mt-2 text-2xl font-semibold tracking-tight">{futureSelf}</div>
        <div className="text-muted-foreground mt-2 text-sm leading-relaxed">
          If your trajectory continues, your next era reads as{' '}
          <span className="text-foreground font-medium">{futureSelf}</span>.
        </div>

        <Separator className="my-4" />

        <div className="text-muted-foreground text-xs">Trend deltas</div>
        <div className="mt-3 grid gap-2">
          {[
            { k: 'Minimal', d: vec[0] - vecPrev[0] },
            { k: 'Structured', d: vec[1] - vecPrev[1] },
            { k: 'Neutral', d: vec[2] - vecPrev[2] },
            { k: 'Classic', d: vec[3] - vecPrev[3] },
          ].map((row) => (
            <div key={row.k} className="flex items-center justify-between gap-3 rounded-xl border border-border/40 bg-muted/10 px-3 py-2">
              <div className="text-sm font-medium">{row.k}</div>
              <div className={cn('font-mono text-sm', row.d >= 0 ? 'text-foreground' : 'text-muted-foreground')}>
                {row.d >= 0 ? '+' : ''}
                {Math.round(row.d)}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )

  const essayTab = (
    <div className="grid gap-4 lg:grid-cols-3">
      <div className="rounded-3xl border border-border/50 bg-background/50 p-6 backdrop-blur-xl lg:col-span-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-muted-foreground text-xs">Agent-generated style essay</div>
            <div className="mt-2 text-xl font-semibold">Your month in words</div>
          </div>
          <Badge variant="outline">Beta</Badge>
        </div>

        <div className="mt-4 rounded-2xl border border-border/50 bg-muted/10 p-5 text-sm leading-relaxed text-muted-foreground">
          {essayLoading ? 'Writing…' : essay || 'Tap “Generate essay” to create your monthly recap.'}
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <Button type="button" variant="outline" className="h-9 rounded-full px-4" onClick={loadEssay} disabled={essayLoading}>
            {essay ? 'Regenerate (beta)' : 'Generate essay'}
          </Button>
          <div className="text-muted-foreground text-xs">
            Uses server-side AI only if configured; otherwise falls back to a template.
          </div>
        </div>
      </div>

      <div className="rounded-3xl border border-border/50 bg-background/50 p-6 backdrop-blur-xl">
        <div className="text-muted-foreground text-xs">Wrapped share preview</div>
        <div className="mt-2 text-xl font-semibold">Aesthetica Wrapped</div>
        <div className="mt-4 rounded-2xl border border-border/50 bg-background/40 p-4">
          <div className="text-xs text-muted-foreground">Top aesthetic</div>
          <div className="mt-1 text-base font-semibold">{topAesthetic}</div>
          <div className="mt-3 text-xs text-muted-foreground">Era</div>
          <div className="mt-1 text-sm font-medium">{era}</div>
          <div className="mt-3 text-xs text-muted-foreground">Palette</div>
          <div className="mt-2 flex flex-wrap gap-2">
            {palette.slice(0, 3).map((p) => (
              <Badge key={p} variant="secondary" className="capitalize">
                {p}
              </Badge>
            ))}
          </div>
        </div>
        <div className="text-muted-foreground mt-3 text-xs">Share/export hooks can be added later.</div>
      </div>
    </div>
  )

  return (
    <Card className={cn('overflow-hidden', className)}>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <CardTitle className="text-2xl md:text-3xl">Taste Analytics</CardTitle>
            <div className="text-muted-foreground mt-1 text-sm">
              Aesthetica Wrapped–style identity analytics. Some metrics are inferred from available signals (beta).
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="secondary">Beta</Badge>
            <Badge variant="outline">{styleScores?.length ? 'style_scores' : 'sample'}</Badge>
          </div>
        </div>
      </CardHeader>

      <CardContent className="pt-0">
        <Tabs defaultValue="wrapped" className="w-full">
          <TabsList className="mb-4">
            <TabsTrigger value="wrapped">Wrapped</TabsTrigger>
            <TabsTrigger value="drift">Drift</TabsTrigger>
            <TabsTrigger value="dna">DNA</TabsTrigger>
            <TabsTrigger value="insights">Insights</TabsTrigger>
            <TabsTrigger value="essay">Essay</TabsTrigger>
          </TabsList>

          <TabsContent value="wrapped">{wrappedCards}</TabsContent>
          <TabsContent value="drift">{drift}</TabsContent>
          <TabsContent value="dna">{dna}</TabsContent>
          <TabsContent value="insights">{insightsCards}</TabsContent>
          <TabsContent value="essay">{essayTab}</TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}

