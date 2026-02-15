'use client'

import * as React from 'react'
import {
  ChevronLeft,
  ChevronRight,
  Clock3,
  Copy,
  LineChart,
  MapPin,
  Share2,
  Sparkles,
  Users,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type {
  ApiCatalogRecommendationOut,
  ApiCatalogRequestOut,
  ApiStyleRecommendationOut,
  ApiStyleScoreOut,
} from '@/lib/api'
import {
  computeFashionIdentityCached,
  paletteNameToHex,
} from '@/lib/fashion-identity/compute'
import type {
  DriftAnnotation,
  FashionIdentityResult,
  IdentitySeasonSegment,
  IdentityTimePoint,
  IdentityVector,
  NoteworthyStyle,
  TasteMatchPerson,
} from '@/lib/fashion-identity/types'
import { cn } from '@/lib/utils'

type FashionIdentityTabProps = {
  loading: boolean
  styleScores: ApiStyleScoreOut[]
  captures: ApiCatalogRequestOut[]
  catalogRecommendations: ApiCatalogRecommendationOut[]
  styleRecommendations: ApiStyleRecommendationOut[]
}

type Timeframe = '7d' | '30d' | '90d' | 'all'

const CITY_TO_COUNTRY: Record<string, string> = {
  Barcelona: 'Spain',
  Seoul: 'South Korea',
  Tokyo: 'Japan',
  Paris: 'France',
  'New York': 'United States',
  Copenhagen: 'Denmark',
}

function useCountUp(value: number, duration = 720) {
  const [display, setDisplay] = React.useState(0)

  React.useEffect(() => {
    let raf = 0
    const start = performance.now()
    const origin = display
    const delta = value - origin

    const step = (t: number) => {
      const progress = Math.min(1, (t - start) / duration)
      const eased = 1 - (1 - progress) ** 3
      setDisplay(origin + delta * eased)
      if (progress < 1) raf = window.requestAnimationFrame(step)
    }

    raf = window.requestAnimationFrame(step)
    return () => window.cancelAnimationFrame(raf)
    // animation intentionally only updates on target changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value])

  return display
}

function formatDateTime(iso: string) {
  const d = new Date(iso)
  if (!Number.isFinite(d.getTime())) return '--'
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZoneName: 'short',
  }).format(d)
}

function formatDate(iso: string) {
  const d = new Date(iso)
  if (!Number.isFinite(d.getTime())) return '--'
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(d)
}

function formatRange(startISO: string, endISO: string) {
  return `${formatDateTime(startISO)} - ${formatDateTime(endISO)}`
}

function SlideFrame({
  question,
  bridge,
  children,
}: {
  question: string
  bridge: string
  children: React.ReactNode
}) {
  return (
    <article className="flex min-h-[78vh] flex-col rounded-[2.2rem] border border-border/60 bg-background/58 p-5 shadow-[0_30px_110px_rgba(0,0,0,0.16)] backdrop-blur-xl md:min-h-[80vh] md:p-7 dark:shadow-[0_42px_125px_rgba(0,0,0,0.64)]">
      <div className="mb-5 space-y-2">
        <div className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground">Fashion Identity</div>
        <h2 className="text-3xl font-semibold tracking-tight md:text-5xl">{question}</h2>
        <p className="max-w-4xl text-sm leading-relaxed text-muted-foreground md:text-base">{bridge}</p>
      </div>
      <div className="min-h-0 flex-1 space-y-4">{children}</div>
    </article>
  )
}

function PremiumCard({
  title,
  subtitle,
  children,
  className,
}: {
  title: string
  subtitle?: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <Card
      className={cn(
        'flex h-full min-h-[280px] flex-col overflow-hidden border-border/60 bg-background/60 shadow-[0_22px_70px_rgba(0,0,0,0.12)] backdrop-blur-xl dark:shadow-[0_30px_92px_rgba(0,0,0,0.58)]',
        className,
      )}
    >
      <CardHeader className="pb-3">
        <CardTitle className="text-xl md:text-2xl">{title}</CardTitle>
        {subtitle ? <div className="text-sm text-muted-foreground">{subtitle}</div> : null}
      </CardHeader>
      <CardContent className="min-h-0 flex-1 pt-0">{children}</CardContent>
    </Card>
  )
}

function NarrativeBeat({
  question,
  line,
  className,
}: {
  question: string
  line: string
  className?: string
}) {
  return (
    <div className={cn('rounded-2xl border border-border/55 bg-muted/15 px-4 py-3 backdrop-blur', className)}>
      <div className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Narrative cue</div>
      <div className="mt-1 text-base font-medium tracking-tight">{question}</div>
      <div className="mt-1 text-sm text-muted-foreground">{line}</div>
    </div>
  )
}

function buildPath(points: Array<{ x: number; y: number }>): string {
  if (!points.length) return ''
  return points
    .map((p, idx) => `${idx === 0 ? 'M' : 'L'} ${p.x.toFixed(2)} ${p.y.toFixed(2)}`)
    .join(' ')
}

function lineColor(axis: 'minimal' | 'neutral' | 'structured' | 'classic') {
  if (axis === 'minimal') return 'hsl(var(--foreground))'
  if (axis === 'neutral') return 'rgba(68,68,68,0.78)'
  if (axis === 'structured') return 'rgba(100,100,100,0.72)'
  return 'rgba(138,138,138,0.66)'
}

function DriftChart({
  series,
  annotations,
}: {
  series: IdentityTimePoint[]
  annotations: DriftAnnotation[]
}) {
  const [drawn, setDrawn] = React.useState(false)

  React.useEffect(() => {
    const t = window.setTimeout(() => setDrawn(true), 70)
    return () => window.clearTimeout(t)
  }, [series])

  const width = 760
  const height = 290
  const padX = 34
  const padY = 24
  const innerW = width - padX * 2
  const innerH = height - padY * 2

  const toX = (idx: number) => {
    if (series.length <= 1) return padX + innerW / 2
    return padX + (idx / (series.length - 1)) * innerW
  }

  const toY = (value: number) => padY + ((100 - value) / 100) * innerH

  const axes: Array<{ key: 'minimal' | 'neutral' | 'structured' | 'classic'; label: string }> = [
    { key: 'minimal', label: 'Minimal vs Maximal' },
    { key: 'neutral', label: 'Neutral vs Color-forward' },
    { key: 'structured', label: 'Structured vs Relaxed' },
    { key: 'classic', label: 'Classic vs Trend-driven' },
  ]

  return (
    <div className="w-full">
      <svg viewBox={`0 0 ${width} ${height}`} className="h-[clamp(220px,33vw,300px)] w-full">
        {[0, 25, 50, 75, 100].map((tick) => (
          <g key={tick}>
            <line
              x1={padX}
              y1={toY(tick)}
              x2={width - padX}
              y2={toY(tick)}
              stroke="hsl(var(--border))"
              strokeOpacity={tick === 50 ? 0.55 : 0.24}
              strokeWidth={1}
            />
            <text x={8} y={toY(tick) + 4} fill="hsl(var(--muted-foreground))" fontSize="10">
              {tick}
            </text>
          </g>
        ))}

        {axes.map((axis) => {
          const points = series.map((row, idx) => ({ x: toX(idx), y: toY(row[axis.key]) }))
          const path = buildPath(points)
          return (
            <path
              key={axis.key}
              d={path}
              fill="none"
              stroke={lineColor(axis.key)}
              strokeWidth={axis.key === 'minimal' ? 2.3 : 1.9}
              strokeLinecap="round"
              strokeLinejoin="round"
              pathLength={1}
              strokeDasharray={1}
              strokeDashoffset={drawn ? 0 : 1}
              style={{ transition: 'stroke-dashoffset 1000ms cubic-bezier(0.2, 0.9, 0.2, 1)' }}
            />
          )
        })}

        {annotations.slice(0, 2).map((ann) => {
          const candidate = series.find((row) => ann.key.includes(row.key))
          if (!candidate) return null
          const x = toX(series.findIndex((row) => row.key === candidate.key))
          const y = toY(candidate[ann.axis])
          return <circle key={ann.key} cx={x} cy={y} r={4.2} fill="hsl(var(--foreground))" />
        })}

        {series.length > 1
          ? series
              .filter((_row, idx) => idx === 0 || idx === series.length - 1 || idx % Math.ceil(series.length / 5) === 0)
              .map((row, idx) => (
                <text
                  key={`${row.key}_${idx}`}
                  x={toX(series.findIndex((s) => s.key === row.key))}
                  y={height - 4}
                  textAnchor="middle"
                  fill="hsl(var(--muted-foreground))"
                  fontSize="10"
                >
                  {row.label}
                </text>
              ))
          : null}
      </svg>

      <div className="mt-2 grid gap-2 text-xs md:grid-cols-2">
        {axes.map((axis) => (
          <div key={axis.key} className="flex items-center gap-2 text-muted-foreground">
            <span className="inline-block h-2 w-6 rounded-full" style={{ background: lineColor(axis.key) }} />
            {axis.label}
          </div>
        ))}
      </div>
    </div>
  )
}

function CountrySimilarityBars({
  regions,
}: {
  regions: FashionIdentityResult['geography']['regions']
}) {
  const rows = React.useMemo(() => {
    // Aggregate by country so the UI matches the question wording.
    const byCountry = new Map<string, { country: string; similarity: number; samples: string[] }>()
    for (const region of regions) {
      const country = CITY_TO_COUNTRY[region.city] ?? region.city
      const label = `${region.city} ${region.year}`
      const existing = byCountry.get(country)
      if (!existing) {
        byCountry.set(country, { country, similarity: region.similarity, samples: [label] })
        continue
      }
      existing.similarity = Math.max(existing.similarity, region.similarity)
      if (existing.samples.length < 2) existing.samples.push(label)
    }
    return Array.from(byCountry.values()).sort((a, b) => b.similarity - a.similarity).slice(0, 6)
  }, [regions])

  const max = rows.reduce((acc, cur) => Math.max(acc, cur.similarity), 0) || 100

  return (
    <div className="space-y-3">
      {rows.map((row) => (
        <div key={row.country} className="rounded-xl border border-border/50 bg-background/55 p-3">
          <div className="mb-1 flex items-center justify-between text-xs">
            <div className="font-medium">{row.country}</div>
            <div>{row.similarity}%</div>
          </div>
          <div className="h-1.5 rounded-full bg-muted/60">
            <div
              className="h-1.5 rounded-full bg-foreground/80 transition-[width] duration-700"
              style={{ width: `${Math.round((row.similarity / max) * 100)}%` }}
            />
          </div>
          <div className="mt-2 text-xs text-muted-foreground">
            Signals: {row.samples.join(' · ')}
          </div>
        </div>
      ))}
    </div>
  )
}

function RadarChart({
  data,
  compare,
}: {
  data: Array<{ key: string; label: string; value: number }>
  compare?: Array<{ key: string; label: string; value: number }>
}) {
  const width = 460
  const height = 360
  const cx = width / 2
  const cy = height / 2
  const outer = 126
  const angle = (i: number, n: number) => -Math.PI / 2 + (Math.PI * 2 * i) / n

  const point = (i: number, n: number, r: number) => ({
    x: cx + Math.cos(angle(i, n)) * r,
    y: cy + Math.sin(angle(i, n)) * r,
  })

  const polygon = (items: Array<{ value: number }>) =>
    items
      .map((item, i) => {
        const p = point(i, items.length, (outer * item.value) / 100)
        return `${p.x.toFixed(2)},${p.y.toFixed(2)}`
      })
      .join(' ')

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-[clamp(260px,40vw,360px)] w-full">
      {[20, 40, 60, 80, 100].map((ring) => (
        <polygon
          key={ring}
          points={data
            .map((_row, i) => {
              const p = point(i, data.length, (outer * ring) / 100)
              return `${p.x},${p.y}`
            })
            .join(' ')}
          fill="none"
          stroke="hsl(var(--border))"
          strokeOpacity={ring === 100 ? 0.45 : 0.25}
          strokeWidth={1}
        />
      ))}

      {data.map((row, i) => {
        const p = point(i, data.length, outer)
        const label = point(i, data.length, outer + 20)
        return (
          <g key={row.key}>
            <line x1={cx} y1={cy} x2={p.x} y2={p.y} stroke="hsl(var(--border))" strokeOpacity={0.35} strokeWidth={1} />
            <text
              x={label.x}
              y={label.y}
              fill="hsl(var(--muted-foreground))"
              fontSize={11}
              textAnchor={label.x > cx + 4 ? 'start' : label.x < cx - 4 ? 'end' : 'middle'}
            >
              {row.label}
            </text>
          </g>
        )
      })}

      {compare ? (
        <polygon
          points={polygon(compare)}
          fill="hsl(var(--muted))"
          fillOpacity={0.18}
          stroke="hsl(var(--muted-foreground))"
          strokeOpacity={0.85}
          strokeWidth={1.4}
        />
      ) : null}

      <polygon
        points={polygon(data)}
        fill="hsl(var(--foreground))"
        fillOpacity={0.12}
        stroke="hsl(var(--foreground))"
        strokeWidth={2}
      />
    </svg>
  )
}

function SeasonsTimeline({
  segments,
}: {
  segments: IdentitySeasonSegment[]
}) {
  const color = (label: IdentitySeasonSegment['label']) => {
    if (label === 'Comfort season') return 'bg-neutral-200 dark:bg-neutral-700'
    if (label === 'Formal ambition season') return 'bg-neutral-400 dark:bg-neutral-500'
    if (label === 'Experimental season') return 'bg-neutral-600 dark:bg-neutral-300'
    return 'bg-neutral-300 dark:bg-neutral-600'
  }

  return (
    <div className="space-y-3">
      <div className="flex h-10 overflow-hidden rounded-xl border border-border/50 bg-muted/10">
        {segments.map((segment) => (
          <div
            key={segment.key}
            className={cn('flex items-center justify-center px-2 text-[10px] font-medium text-foreground/90', color(segment.label))}
            style={{ flexGrow: Math.max(1, Math.round(segment.share * 100)), flexBasis: 0 }}
            title={`${segment.label} - ${segment.weeks} week${segment.weeks > 1 ? 's' : ''}`}
          >
            <span className="truncate">{segment.label.replace(' season', '')}</span>
          </div>
        ))}
      </div>
      <div className="grid gap-2 md:grid-cols-2">
        {segments.map((segment) => (
          <div key={`${segment.key}_label`} className="rounded-xl border border-border/50 bg-muted/10 px-3 py-2 text-xs">
            <div className="font-medium">{segment.label}</div>
            <div className="mt-1 text-muted-foreground">
              {segment.weeks} week{segment.weeks > 1 ? 's' : ''} - {Math.round(segment.share * 100)}%
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function NoteworthyList({
  items,
}: {
  items: NoteworthyStyle[]
}) {
  return (
    <div className="max-h-[min(56vh,430px)] space-y-2 overflow-y-auto pr-1">
      {items.slice(0, 4).map((item) => (
        <div key={item.key} className="rounded-2xl border border-border/60 bg-muted/10 p-3">
          <div className="min-w-0 text-sm font-medium">{item.title}</div>
          <div className="mt-1 text-xs text-muted-foreground">{item.prompt}</div>
          <div className="mt-2 text-xs text-muted-foreground">{item.rationale}</div>
          <div className="mt-2 flex items-center gap-2 text-[11px] text-muted-foreground">
            <span className="rounded-full border border-border/60 bg-background/50 px-1.5 py-0.5 uppercase">
              {item.source}
            </span>
            <span>{formatDateTime(item.createdAtISO)}</span>
          </div>
        </div>
      ))}
    </div>
  )
}

function IdentitySkeleton() {
  return (
    <div className="mt-6 grid gap-4 xl:grid-cols-12">
      <Card className="xl:col-span-12">
        <CardContent className="p-6">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="mt-4 h-28 w-full" />
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            <Skeleton className="h-20" />
            <Skeleton className="h-20" />
            <Skeleton className="h-20" />
          </div>
        </CardContent>
      </Card>
      {Array.from({ length: 6 }).map((_, idx) => (
        <Card key={idx} className="xl:col-span-6">
          <CardContent className="p-6">
            <Skeleton className="h-6 w-48" />
            <Skeleton className="mt-4 h-44 w-full" />
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

function mapRadarFields(vector: IdentityVector) {
  return [
    { key: 'minimal', label: 'Minimal', value: vector.minimal },
    { key: 'structured', label: 'Structured', value: vector.structured },
    { key: 'neutral', label: 'Neutral', value: vector.neutral },
    { key: 'classic', label: 'Classic', value: vector.classic },
    { key: 'casual', label: 'Casual', value: vector.casual },
    { key: 'experimental', label: 'Experimental', value: vector.experimental },
    { key: 'tailored', label: 'Tailored', value: vector.tailored },
    { key: 'street', label: 'Street', value: vector.street },
  ].map((x) => ({ ...x, value: Math.round(x.value) }))
}

function useFilteredSeries(
  series: IdentityTimePoint[],
  annotations: DriftAnnotation[],
  lastSignalISO: string,
  timeframe: Timeframe,
) {
  return React.useMemo(() => {
    if (timeframe === 'all') return { series, annotations }
    const days = timeframe === '7d' ? 7 : timeframe === '30d' ? 30 : 90
    const end = +new Date(lastSignalISO)
    const filteredSeries = series.filter((row) => end - +new Date(row.dateISO) <= days * 24 * 3600 * 1000)
    const fallbackSeries = filteredSeries.length >= 2 ? filteredSeries : series.slice(-Math.min(8, series.length))
    const keySet = new Set(fallbackSeries.map((row) => row.key))
    const filteredAnnotations = annotations.filter((ann) =>
      Array.from(keySet).some((key) => ann.key.includes(key)),
    )
    return { series: fallbackSeries, annotations: filteredAnnotations }
  }, [annotations, lastSignalISO, series, timeframe])
}

function CompareModal({
  open,
  onOpenChange,
  user,
  friend,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  user: IdentityVector
  friend: TasteMatchPerson
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl rounded-3xl border-border/60 bg-background/95">
        <DialogHeader>
          <DialogTitle className="text-2xl">Taste comparison</DialogTitle>
          <DialogDescription>
            Side-by-side radar and deltas for your profile versus {friend.handle}.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-2xl border border-border/60 bg-muted/5 p-3">
            <div className="mb-2 text-sm font-medium">You</div>
            <RadarChart data={mapRadarFields(user)} />
          </div>
          <div className="rounded-2xl border border-border/60 bg-muted/5 p-3">
            <div className="mb-2 text-sm font-medium">{friend.handle}</div>
            <RadarChart data={mapRadarFields(friend.vector)} />
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

export function FashionIdentityTab({
  loading,
  styleScores,
  captures,
  catalogRecommendations,
  styleRecommendations,
}: FashionIdentityTabProps) {
  const data = React.useMemo(
    () =>
      computeFashionIdentityCached({
        styleScores,
        captures,
        catalogRecommendations,
        styleRecommendations,
      }),
    [captures, catalogRecommendations, styleRecommendations, styleScores],
  )

  const [timeframe, setTimeframe] = React.useState<Timeframe>('30d')
  const [copied, setCopied] = React.useState(false)
  const [shareCardMode, setShareCardMode] = React.useState(false)
  const [selectedTwinKey, setSelectedTwinKey] = React.useState(data.celebrityTwin.selected.key)
  const [compareOpen, setCompareOpen] = React.useState(false)
  const [activeSlide, setActiveSlide] = React.useState(0)

  const railRef = React.useRef<HTMLDivElement | null>(null)
  const slideRefs = React.useRef<Array<HTMLDivElement | null>>([])

  React.useEffect(() => {
    setSelectedTwinKey(data.celebrityTwin.selected.key)
  }, [data.celebrityTwin.selected.key])

  React.useEffect(() => {
    if (!railRef.current) return
    const observer = new IntersectionObserver(
      (entries) => {
        const top = [...entries]
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0]
        if (!top) return
        const idx = Number((top.target as HTMLElement).dataset.slideIndex ?? -1)
        if (Number.isFinite(idx) && idx >= 0) setActiveSlide(idx)
      },
      { root: railRef.current, threshold: [0.55, 0.7, 0.9] },
    )

    for (const node of slideRefs.current) {
      if (node) observer.observe(node)
    }

    return () => observer.disconnect()
  }, [])

  const selectedTwin =
    data.celebrityTwin.top3.find((twin) => twin.key === selectedTwinKey) ?? data.celebrityTwin.selected

  const topScore = useCountUp(data.wrapped.topAesthetic.score)
  const fashionAge = useCountUp(data.wrapped.fashionAge.value)
  const matchScore = useCountUp(data.tasteMatch.topMatch.overlap)

  const filtered = useFilteredSeries(
    data.drift.series,
    data.drift.annotations,
    data.lastSignalISO,
    timeframe,
  )

  const copySummary = React.useCallback(async () => {
    const summary = `${data.wrapped.summaryText}\nPeriod: ${formatRange(data.wrapped.periodStartISO, data.wrapped.periodEndISO)}\nLast signal: ${formatDateTime(data.lastSignalISO)}`
    try {
      await window.navigator.clipboard.writeText(summary)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1200)
    } catch {
      setCopied(false)
    }
  }, [data.lastSignalISO, data.wrapped.periodEndISO, data.wrapped.periodStartISO, data.wrapped.summaryText])

  const slideCount = 7

  const scrollToSlide = React.useCallback((nextIndex: number) => {
    const clamped = Math.max(0, Math.min(slideCount - 1, nextIndex))
    const target = slideRefs.current[clamped]
    if (!target) return
    target.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' })
  }, [slideCount])

  const onWheelHorizontal = React.useCallback((event: React.WheelEvent<HTMLDivElement>) => {
    if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return
    event.currentTarget.scrollLeft += event.deltaY
    event.preventDefault()
  }, [])

  if (loading) return <IdentitySkeleton />

  return (
    <div className="mt-6 space-y-5 rounded-3xl border border-border/40 bg-gradient-to-br from-indigo-500/5 via-background to-rose-500/5 p-4 md:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">Fashion Identity</h2>
          <div className="mt-1 text-sm text-muted-foreground">
            Swipe or scroll horizontally through your wrapped story.
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 w-8 rounded-full p-0"
            onClick={() => scrollToSlide(activeSlide - 1)}
            disabled={activeSlide <= 0}
          >
            <ChevronLeft className="size-4" />
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 w-8 rounded-full p-0"
            onClick={() => scrollToSlide(activeSlide + 1)}
            disabled={activeSlide >= slideCount - 1}
          >
            <ChevronRight className="size-4" />
          </Button>
        </div>
      </div>

      <div className="flex items-center gap-1.5 px-1">
        {Array.from({ length: slideCount }).map((_, idx) => (
          <button
            key={idx}
            type="button"
            onClick={() => scrollToSlide(idx)}
            className={cn(
              'h-1.5 rounded-full transition-all duration-300',
              idx === activeSlide ? 'w-8 bg-foreground/80' : 'w-3 bg-muted-foreground/35',
            )}
            aria-label={`Go to slide ${idx + 1}`}
          />
        ))}
      </div>

      <div
        ref={railRef}
        className="flex items-stretch gap-5 overflow-x-auto overflow-y-hidden px-1 pb-3 scroll-smooth snap-x snap-proximity [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        onWheel={onWheelHorizontal}
      >
        <div className="w-1 shrink-0 md:w-4" />

        <div
          ref={(node) => {
            slideRefs.current[0] = node
          }}
          data-slide-index={0}
          className={cn(
            'w-[min(92vw,1160px)] shrink-0 snap-center transition-transform duration-500',
            activeSlide === 0 ? 'scale-100' : 'scale-[0.985]',
          )}
        >
          <SlideFrame
            question="What does your style say this month?"
            bridge={`You are currently tracking ${data.wrapped.topAesthetic.label}. Last signal landed at ${formatDateTime(data.lastSignalISO)}.`}
          >
            <div className="grid gap-4 xl:grid-cols-12 xl:items-stretch">
              <PremiumCard
                className="xl:col-span-7"
                title="Your Style Wrapped"
                subtitle={`Current period: ${formatRange(data.wrapped.periodStartISO, data.wrapped.periodEndISO)}`}
              >
                <div className="space-y-3">
                  <div className="text-3xl font-semibold tracking-tight md:text-4xl">
                    {data.wrapped.topAesthetic.label} ({Math.round(topScore)}%)
                  </div>
                  <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <Clock3 className="size-3" />
                    Last signal {formatDateTime(data.lastSignalISO)}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    Fashion age {fashionAge.toFixed(1)}. {data.wrapped.fashionAge.rationale}
                  </div>
                  <div className="grid gap-1.5 text-sm">
                    <div>
                      <span className="text-muted-foreground">Fashion geography:</span> {data.wrapped.fashionGeography.topMatch} / drift {data.wrapped.fashionGeography.driftMatch}
                    </div>
                    <div>
                      <span className="text-muted-foreground">Silhouette bias:</span> relaxed {data.wrapped.silhouetteBias.relaxed}% / structured {data.wrapped.silhouetteBias.structured}% / maximal {data.wrapped.silhouetteBias.maximal}%
                    </div>
                    <div>
                      <span className="text-muted-foreground">Most captured item:</span> {data.wrapped.mostCapturedItem.item} ({data.wrapped.mostCapturedItem.count})
                    </div>
                    <div>
                      <span className="text-muted-foreground">Unexpected phase:</span> {data.wrapped.unexpectedPhase}
                    </div>
                  </div>
                </div>
              </PremiumCard>

              <PremiumCard className="xl:col-span-5" title="Palette + Share" subtitle="Ready for wrapped-style sharing">
                <div className="space-y-3">
                  <div className="flex flex-wrap gap-2">
                    {data.wrapped.palette.slice(0, 4).map((name) => (
                      <div key={name} className="inline-flex items-center gap-2 rounded-full border border-border/50 bg-background/60 px-3 py-1 text-xs">
                        <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: paletteNameToHex(name) }} />
                        <span className="capitalize">{name}</span>
                      </div>
                    ))}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button type="button" variant="outline" size="sm" className="h-8 rounded-full px-3" onClick={copySummary}>
                      <Copy className="mr-2 size-4" />
                      {copied ? 'Copied' : 'Copy summary'}
                    </Button>
                    <Button
                      type="button"
                      variant={shareCardMode ? 'default' : 'outline'}
                      size="sm"
                      className="h-8 rounded-full px-3"
                      onClick={() => setShareCardMode((cur) => !cur)}
                    >
                      <Share2 className="mr-2 size-4" />
                      Share card
                    </Button>
                  </div>
                  {shareCardMode ? (
                    <div className="rounded-2xl border border-border/50 bg-background/70 p-4">
                      <div className="text-xs uppercase tracking-[0.12em] text-muted-foreground">Exportable share card</div>
                      <div className="mt-2 text-xl font-semibold">Aesthetica Fashion Identity</div>
                      <div className="mt-2 text-sm">{data.wrapped.topAesthetic.label}</div>
                      <div className="text-sm text-muted-foreground">Era: {data.era.current}</div>
                      <div className="text-sm text-muted-foreground">Future: {data.futureSelf.era}</div>
                      <div className="mt-2 text-xs text-muted-foreground">{formatDate(data.lastSignalISO)}</div>
                    </div>
                  ) : null}
                </div>
              </PremiumCard>

              <NarrativeBeat
                className="xl:col-span-12"
                question="Is your current chapter about control or experimentation?"
                line={`Right now your strongest axis is ${data.wrapped.topAesthetic.label}, with ${data.wrapped.silhouetteBias.structured}% structured influence shaping the month.`}
              />
            </div>
          </SlideFrame>
        </div>

        <div
          ref={(node) => {
            slideRefs.current[1] = node
          }}
          data-slide-index={1}
          className={cn(
            'w-[min(92vw,1160px)] shrink-0 snap-center transition-transform duration-500',
            activeSlide === 1 ? 'scale-100' : 'scale-[0.985]',
          )}
        >
          <SlideFrame
            question="What country do you dress most similarly to?"
            bridge={`${data.geography.headline} ${data.geography.driftLine}`}
          >
            <div className="grid gap-4 xl:grid-cols-12 xl:items-stretch">
              <PremiumCard className="xl:col-span-8" title="Country Similarity" subtitle="Where your current taste vector clusters most strongly">
                <CountrySimilarityBars regions={data.geography.regions} />
              </PremiumCard>
              <PremiumCard className="xl:col-span-4" title="Noteworthy Captures" subtitle="Prompt-linked outfit signals from catalog requests">
                <NoteworthyList items={data.noteworthy.items} />
              </PremiumCard>

              <NarrativeBeat
                className="xl:col-span-12"
                question="Which requests actually changed your direction?"
                line="These highlighted captures are ranked by prompt strength, recency, and confidence from your Supabase catalog request stream."
              />
            </div>
          </SlideFrame>
        </div>

        <div
          ref={(node) => {
            slideRefs.current[2] = node
          }}
          data-slide-index={2}
          className={cn(
            'w-[min(92vw,1160px)] shrink-0 snap-center transition-transform duration-500',
            activeSlide === 2 ? 'scale-100' : 'scale-[0.985]',
          )}
        >
          <SlideFrame
            question="When did your style pivot?"
            bridge={filtered.annotations[0]?.message ?? 'No large pivot was detected in the selected range.'}
          >
            <div className="grid gap-4 xl:grid-cols-12 xl:items-stretch">
              <PremiumCard className="xl:col-span-8" title="Style Drift" subtitle="Minimal vs Maximal, Neutral vs Color-forward, Structured vs Relaxed, Classic vs Trend-driven">
                <div className="mb-3 flex items-center gap-2">
                  <Tabs value={timeframe} onValueChange={(next) => setTimeframe(next as Timeframe)}>
                    <TabsList className="h-8 rounded-full border border-border/50 bg-background/70">
                      <TabsTrigger value="7d" className="h-7 rounded-full px-3 text-xs">
                        7d
                      </TabsTrigger>
                      <TabsTrigger value="30d" className="h-7 rounded-full px-3 text-xs">
                        30d
                      </TabsTrigger>
                      <TabsTrigger value="90d" className="h-7 rounded-full px-3 text-xs">
                        90d
                      </TabsTrigger>
                      <TabsTrigger value="all" className="h-7 rounded-full px-3 text-xs">
                        All
                      </TabsTrigger>
                    </TabsList>
                  </Tabs>
                </div>
                <DriftChart series={filtered.series} annotations={filtered.annotations} />
              </PremiumCard>

              <PremiumCard className="xl:col-span-4" title="Micro-trends" subtitle="Material, item, and color-temperature signals">
                <div className="space-y-2">
                  {data.microTrends.insights.map((line, idx) => (
                    <div key={`${line}_${idx}`} className="rounded-xl border border-border/50 bg-muted/10 px-3 py-2 text-sm text-muted-foreground">
                      {line}
                    </div>
                  ))}
                </div>
              </PremiumCard>

              <NarrativeBeat
                className="xl:col-span-12"
                question="Was this shift gradual or sudden?"
                line={filtered.annotations[0]?.message ?? 'The selected period shows a smooth transition without a sharp spike.'}
              />
            </div>
          </SlideFrame>
        </div>

        <div
          ref={(node) => {
            slideRefs.current[3] = node
          }}
          data-slide-index={3}
          className={cn(
            'w-[min(92vw,1160px)] shrink-0 snap-center transition-transform duration-500',
            activeSlide === 3 ? 'scale-100' : 'scale-[0.985]',
          )}
        >
          <SlideFrame
            question="Who dresses closest to your taste profile?"
            bridge={`You and ${data.tasteMatch.topMatch.handle} currently overlap by ${Math.round(matchScore)}%. ${data.tasteMatch.divergenceLine}`}
          >
            <div className="grid gap-4 xl:grid-cols-12 xl:items-stretch">
              <PremiumCard className="xl:col-span-4" title="Celebrity Twin" subtitle={`Your style twin: ${selectedTwin.name}`}>
                <div className="rounded-2xl border border-border/60 bg-muted/10 p-4">
                  <div className="text-2xl font-semibold">{selectedTwin.similarity}% match</div>
                  <div className="mt-1 text-sm text-muted-foreground">
                    Match in silhouette bias and tonal palette - {selectedTwin.era}.
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {data.celebrityTwin.top3.map((twin) => (
                    <button
                      key={twin.key}
                      type="button"
                      onClick={() => setSelectedTwinKey(twin.key)}
                      className={cn(
                        'rounded-full border px-3 py-1 text-xs transition-colors',
                        twin.key === selectedTwin.key
                          ? 'border-foreground/30 bg-foreground/10'
                          : 'border-border/60 bg-background/55 hover:bg-muted/20',
                      )}
                    >
                      {twin.name}
                    </button>
                  ))}
                </div>
              </PremiumCard>

              <PremiumCard
                className="xl:col-span-8"
                title="Taste Match"
                subtitle={`You and ${data.tasteMatch.topMatch.handle} have ${Math.round(matchScore)}% overlap.`}
              >
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="rounded-2xl border border-border/50 bg-muted/10 p-4">
                    <div className="mb-2 inline-flex items-center gap-1 rounded-full border border-border/50 bg-background/60 px-2 py-1 text-[11px] text-muted-foreground">
                      <Users className="size-3" />
                      Social layer
                    </div>
                    <div className="text-sm font-medium">{data.tasteMatch.topMatch.handle}</div>
                    <div className="mt-2 text-3xl font-semibold">{Math.round(matchScore)}%</div>
                    <div className="mt-1 text-sm text-muted-foreground">{data.tasteMatch.divergenceLine}</div>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="mt-4 h-8 rounded-full px-3"
                      onClick={() => setCompareOpen(true)}
                    >
                      Compare
                    </Button>
                  </div>

                  <div className="space-y-2">
                    {data.tasteMatch.deltas.map((row) => (
                      <div key={row.key} className="rounded-xl border border-border/50 bg-background/55 p-3">
                        <div className="mb-1 flex items-center justify-between text-xs">
                          <span className="text-muted-foreground">{row.label}</span>
                          <span>{row.overlap}%</span>
                        </div>
                        <div className="h-1.5 rounded-full bg-muted/60">
                          <div
                            className="h-1.5 rounded-full bg-foreground/80 transition-[width] duration-700"
                            style={{ width: `${row.overlap}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </PremiumCard>

              <NarrativeBeat
                className="xl:col-span-12"
                question="Do you mirror icons or peers more closely?"
                line={`Your top peer overlap is ${Math.round(matchScore)}%, while your closest celebrity centroid is ${selectedTwin.name} at ${selectedTwin.similarity}%.`}
              />
            </div>
          </SlideFrame>
        </div>

        <div
          ref={(node) => {
            slideRefs.current[4] = node
          }}
          data-slide-index={4}
          className={cn(
            'w-[min(92vw,1160px)] shrink-0 snap-center transition-transform duration-500',
            activeSlide === 4 ? 'scale-100' : 'scale-[0.985]',
          )}
        >
          <SlideFrame
            question="What defines your style DNA right now?"
            bridge={`Your profile is ${data.dna.stabilityPercent}% stable year-over-year.`}
          >
            <div className="grid gap-4 xl:grid-cols-12 xl:items-stretch">
              <PremiumCard className="xl:col-span-8" title="Style DNA Breakdown" subtitle="Eight-axis radar profile">
                <RadarChart data={data.dna.radar} />
                <div className="mt-2 text-sm text-muted-foreground">
                  {data.dna.mutationPhase
                    ? 'You are currently in a style mutation phase.'
                    : 'You are currently in a style consolidation phase.'}
                </div>
              </PremiumCard>

              <PremiumCard className="xl:col-span-4" title="Era" subtitle="Current classification and near-term drift">
                <div className="space-y-3">
                  <div className="rounded-2xl border border-border/50 bg-muted/10 p-4">
                    <div className="text-xs uppercase tracking-[0.12em] text-muted-foreground">Current era</div>
                    <div className="mt-2 text-xl font-semibold">{data.era.current}</div>
                  </div>
                  <div className="rounded-2xl border border-border/50 bg-muted/10 p-4">
                    <div className="text-xs uppercase tracking-[0.12em] text-muted-foreground">Trending toward</div>
                    <div className="mt-2 text-xl font-semibold">{data.era.trendingToward}</div>
                  </div>
                </div>
              </PremiumCard>

              <NarrativeBeat
                className="xl:col-span-12"
                question="How stable is your style identity over time?"
                line={`Your DNA stability sits at ${data.dna.stabilityPercent}%, and the current pattern is classified as ${data.era.current}.`}
              />
            </div>
          </SlideFrame>
        </div>

        <div
          ref={(node) => {
            slideRefs.current[5] = node
          }}
          data-slide-index={5}
          className={cn(
            'w-[min(92vw,1160px)] shrink-0 snap-center transition-transform duration-500',
            activeSlide === 5 ? 'scale-100' : 'scale-[0.985]',
          )}
        >
          <SlideFrame
            question="Where is your style heading next?"
            bridge={data.forecast.primary}
          >
            <div className="grid gap-4 xl:grid-cols-12 xl:items-stretch">
              <PremiumCard className="xl:col-span-4" title="Forecast" subtitle="Predictive trend modeling">
                <div className="mb-3 inline-flex items-center gap-1 rounded-full border border-border/50 bg-background/60 px-2 py-1 text-[11px] text-muted-foreground">
                  <LineChart className="size-3" />
                  6-week model
                </div>
                <div className="rounded-2xl border border-border/50 bg-muted/10 p-4 text-sm">{data.forecast.primary}</div>
                <div className="mt-3 space-y-2">
                  {data.forecast.signals.map((signal) => (
                    <div key={signal} className="rounded-xl border border-border/50 bg-background/55 px-3 py-2 text-xs text-muted-foreground">
                      {signal}
                    </div>
                  ))}
                </div>
              </PremiumCard>

              <PremiumCard
                className="xl:col-span-4"
                title="Future Self"
                subtitle={`If your trajectory continues, your ${data.futureSelf.year} aesthetic will resemble`}
              >
                <div className="space-y-3">
                  <div className="rounded-2xl border border-border/50 bg-muted/10 p-4">
                    <div className="text-xs uppercase tracking-[0.12em] text-muted-foreground">Future era label</div>
                    <div className="mt-2 text-xl font-semibold">{data.futureSelf.era}</div>
                  </div>
                  <div className="rounded-2xl border border-border/50 bg-muted/10 p-4">
                    <div className="text-xs uppercase tracking-[0.12em] text-muted-foreground">Future twin</div>
                    <div className="mt-2 text-lg font-semibold">{data.futureSelf.twinName}</div>
                  </div>
                  <div className="text-sm text-muted-foreground">{data.futureSelf.rationale}</div>
                </div>
              </PremiumCard>

              <PremiumCard className="xl:col-span-4" title="Seasons" subtitle="Weekly phase detection">
                <SeasonsTimeline segments={data.seasons.segments} />
              </PremiumCard>

              <NarrativeBeat
                className="xl:col-span-12"
                question="What does your next chapter look like?"
                line={`${data.forecast.primary} The strongest long-horizon anchor is ${data.futureSelf.era}.`}
              />
            </div>
          </SlideFrame>
        </div>

        <div
          ref={(node) => {
            slideRefs.current[6] = node
          }}
          data-slide-index={6}
          className={cn(
            'w-[min(92vw,1160px)] shrink-0 snap-center transition-transform duration-500',
            activeSlide === 6 ? 'scale-100' : 'scale-[0.985]',
          )}
        >
          <SlideFrame
            question="How rare is your profile among peers?"
            bridge={`Compare your percentile ranking, then read your monthly narrative summary.`}
          >
            <div className="grid gap-4 xl:grid-cols-12 xl:items-stretch">
              <PremiumCard className="xl:col-span-5" title="Percentiles" subtitle="Fashion rank percentiles">
                <div className="space-y-3">
                  {data.percentiles.lines.map((line) => (
                    <div key={line.key} className="rounded-xl border border-border/50 bg-muted/10 p-3">
                      <div className="mb-1 flex items-center justify-between text-xs">
                        <span className="text-muted-foreground">{line.label}</span>
                        <span className="font-medium">{line.value}%</span>
                      </div>
                      <div className="h-1.5 rounded-full bg-background/70">
                        <div className="h-1.5 rounded-full bg-foreground/80 transition-[width] duration-700" style={{ width: `${line.value}%` }} />
                      </div>
                      <div className="mt-2 text-xs text-muted-foreground">{line.text}</div>
                    </div>
                  ))}
                </div>
              </PremiumCard>

              <PremiumCard className="xl:col-span-7" title="Monthly Essay" subtitle="Agent-generated style recap">
                <div className="mb-3 inline-flex items-center gap-1 rounded-full border border-border/50 bg-background/60 px-2 py-1 text-[11px] text-muted-foreground">
                  <Sparkles className="size-3" />
                  Monthly narrative
                </div>
                <div className="rounded-2xl border border-border/50 bg-muted/10 p-4 text-sm leading-relaxed text-muted-foreground">
                  {data.monthlyEssay.paragraph}
                </div>
                <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
                  <MapPin className="size-3" />
                  Last updated {formatDateTime(data.lastSignalISO)}
                </div>
              </PremiumCard>

              <NarrativeBeat
                className="xl:col-span-12"
                question="What should you test next month?"
                line="Use percentile deltas to choose one axis to push and one axis to hold, then monitor the next 30-day drift line."
              />
            </div>
          </SlideFrame>
        </div>

        <div className="w-2 shrink-0 md:w-4" />
      </div>

      <Separator />

      <div className="rounded-2xl border border-border/50 bg-muted/10 p-3 text-xs text-muted-foreground">
        Sources: style scores, capture timestamps and metadata, style recommendations, catalog recommendations. When source coverage is sparse, values are inferred through deterministic heuristics.
      </div>

      <CompareModal
        open={compareOpen}
        onOpenChange={setCompareOpen}
        user={data.vector}
        friend={data.tasteMatch.topMatch}
      />
    </div>
  )
}
