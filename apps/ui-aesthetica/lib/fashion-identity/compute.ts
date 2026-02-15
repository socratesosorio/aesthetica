import type {
  ApiCatalogRecommendationOut,
  ApiCatalogRequestOut,
  ApiStyleRecommendationOut,
  ApiStyleScoreOut,
} from '@/lib/api'

import type {
  DriftAnnotation,
  FashionIdentityResult,
  IdentityDemoFlags,
  IdentityRegionMatch,
  IdentitySeasonSegment,
  IdentityTimePoint,
  IdentityVector,
  TasteMatchPerson,
} from './types'

export type FashionIdentityInput = {
  styleScores: ApiStyleScoreOut[]
  captures: ApiCatalogRequestOut[]
  catalogRecommendations: ApiCatalogRecommendationOut[]
  styleRecommendations: ApiStyleRecommendationOut[]
  now?: Date
}

type BasePoint = {
  createdAtISO: string
  minimal: number
  structured: number
  neutral: number
  classic: number
  casual: number
}

type GeoCentroid = {
  key: string
  city: string
  year: number
  lat: number
  lng: number
  vector: IdentityVector
}

type CelebrityCentroid = {
  key: string
  name: string
  era: string
  palette: string[]
  vector: IdentityVector
}

type MockTasteUser = {
  key: string
  handle: string
  vector: IdentityVector
  tonalConsistency: number
}

const COLOR_HEX: Record<string, string> = {
  black: '#121212',
  charcoal: '#2E3138',
  slate: '#4A5568',
  gray: '#7A7F89',
  navy: '#1E2B45',
  blue: '#2E4D7D',
  olive: '#4A5B3D',
  green: '#3E5D4A',
  brown: '#6B4B3A',
  camel: '#A7814D',
  tan: '#B4946C',
  beige: '#D8C9AE',
  cream: '#EFE8DA',
  ivory: '#F3EFE6',
  white: '#F7F7F5',
  burgundy: '#6A2138',
  red: '#A93A3A',
  orange: '#C87439',
  yellow: '#CCAE52',
  pink: '#C78CA7',
  purple: '#6F5A8D',
  silver: '#A6ADB7',
  gold: '#B59043',
}

const COLOR_WORDS = Object.keys(COLOR_HEX)
const WARM_COLORS = new Set(['red', 'orange', 'yellow', 'gold', 'tan', 'camel', 'brown', 'burgundy', 'pink'])
const COOL_COLORS = new Set(['blue', 'navy', 'green', 'olive', 'purple', 'slate', 'gray', 'charcoal', 'black', 'silver'])

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
  'shirt',
  'tee',
  't-shirt',
  'trouser',
  'pant',
  'jean',
  'skirt',
  'dress',
  'loafer',
  'boot',
  'sneaker',
  'heel',
  'bag',
  'hoodie',
  'sweater',
  'knit',
]

const DEMO_BASE_SERIES: BasePoint[] = [
  { createdAtISO: '2025-11-07T12:00:00.000Z', minimal: 61, structured: 58, neutral: 65, classic: 57, casual: 48 },
  { createdAtISO: '2025-11-14T12:00:00.000Z', minimal: 63, structured: 60, neutral: 67, classic: 59, casual: 47 },
  { createdAtISO: '2025-11-21T12:00:00.000Z', minimal: 59, structured: 64, neutral: 63, classic: 61, casual: 45 },
  { createdAtISO: '2025-11-28T12:00:00.000Z', minimal: 66, structured: 68, neutral: 69, classic: 64, casual: 42 },
  { createdAtISO: '2025-12-05T12:00:00.000Z', minimal: 70, structured: 71, neutral: 73, classic: 66, casual: 40 },
  { createdAtISO: '2025-12-12T12:00:00.000Z', minimal: 68, structured: 72, neutral: 70, classic: 67, casual: 41 },
]

function clamp(x: number, min = 0, max = 100) {
  return Math.max(min, Math.min(max, x))
}

function safeDate(iso: string | null | undefined, fallback: Date) {
  const d = iso ? new Date(iso) : fallback
  return Number.isFinite(d.getTime()) ? d : fallback
}

function dayKey(d: Date) {
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}-${String(d.getUTCDate()).padStart(2, '0')}`
}

function weekKey(d: Date) {
  const normalized = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()))
  const day = normalized.getUTCDay()
  const distanceToMonday = (day + 6) % 7
  normalized.setUTCDate(normalized.getUTCDate() - distanceToMonday)
  return dayKey(normalized)
}

function labelFromISO(iso: string) {
  const d = new Date(iso)
  if (!Number.isFinite(d.getTime())) return '--'
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function axisLabelFromISO(iso: string) {
  const d = new Date(iso)
  if (!Number.isFinite(d.getTime())) return '--'
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function toTitleWord(input: string) {
  if (!input) return input
  return input[0].toUpperCase() + input.slice(1).toLowerCase()
}

function compactPrompt(input: string, max = 88) {
  const clean = input.replace(/\s+/g, ' ').trim()
  if (clean.length <= max) return clean
  return `${clean.slice(0, Math.max(0, max - 1)).trim()}...`
}

function parseScorePoint(point: ApiStyleScoreOut): BasePoint {
  const fallbackDate = new Date()
  return {
    createdAtISO: safeDate(point.created_at, fallbackDate).toISOString(),
    minimal: clamp(typeof point.minimal === 'number' ? point.minimal : 50),
    structured: clamp(typeof point.structured === 'number' ? point.structured : 50),
    neutral: clamp(typeof point.neutral === 'number' ? point.neutral : 50),
    classic: clamp(typeof point.classic === 'number' ? point.classic : 50),
    casual: clamp(typeof point.casual === 'number' ? point.casual : 50),
  }
}

function avg(values: number[]) {
  if (!values.length) return 0
  return values.reduce((acc, cur) => acc + cur, 0) / values.length
}

function variance(values: number[]) {
  if (values.length <= 1) return 0
  const m = avg(values)
  return avg(values.map((x) => (x - m) ** 2))
}

function stddev(values: number[]) {
  return Math.sqrt(variance(values))
}

function cosineSimilarity(a: number[], b: number[]) {
  const len = Math.min(a.length, b.length)
  if (!len) return 0
  let dot = 0
  let na = 0
  let nb = 0
  for (let i = 0; i < len; i++) {
    const av = a[i] ?? 0
    const bv = b[i] ?? 0
    dot += av * bv
    na += av * av
    nb += bv * bv
  }
  if (!na || !nb) return 0
  return dot / (Math.sqrt(na) * Math.sqrt(nb))
}

function vectorToArray(v: IdentityVector) {
  return [
    v.minimal,
    v.structured,
    v.neutral,
    v.classic,
    v.casual,
    v.experimental,
    v.tailored,
    v.street,
    v.colorForward,
    v.trendDriven,
    v.relaxed,
    v.maximal,
  ]
}

function textTokens(input: string) {
  return input
    .toLowerCase()
    .split(/[^a-z0-9]+/g)
    .filter(Boolean)
}

function countKeywords(tokens: string[], keywords: string[]) {
  const set = new Set(keywords)
  const counts = new Map<string, number>()
  for (const token of tokens) {
    if (!set.has(token)) continue
    counts.set(token, (counts.get(token) ?? 0) + 1)
  }
  return counts
}

function topEntries(counts: Map<string, number>, k: number) {
  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, k)
}

function blend(a: number, b: number, c = 50, wa = 0.5, wb = 0.35, wc = 0.15) {
  return clamp(a * wa + b * wb + c * wc)
}

function toIdentityVector(base: BasePoint, volatility = 0) {
  const relaxed = clamp(100 - base.structured)
  const maximal = clamp(100 - base.minimal)
  const colorForward = clamp(100 - base.neutral)
  const trendDriven = clamp(100 - base.classic)
  const experimental = blend(colorForward, maximal, volatility, 0.46, 0.34, 0.2)
  const tailored = blend(base.structured, base.classic, base.neutral, 0.58, 0.3, 0.12)
  const street = blend(base.casual, trendDriven, maximal, 0.44, 0.31, 0.25)
  return {
    minimal: clamp(base.minimal),
    structured: clamp(base.structured),
    neutral: clamp(base.neutral),
    classic: clamp(base.classic),
    casual: clamp(base.casual),
    experimental,
    tailored,
    street,
    colorForward,
    trendDriven,
    relaxed,
    maximal,
  }
}

function averageBase(points: BasePoint[]) {
  if (!points.length) {
    return { minimal: 50, structured: 50, neutral: 50, classic: 50, casual: 50 }
  }
  return {
    minimal: avg(points.map((p) => p.minimal)),
    structured: avg(points.map((p) => p.structured)),
    neutral: avg(points.map((p) => p.neutral)),
    classic: avg(points.map((p) => p.classic)),
    casual: avg(points.map((p) => p.casual)),
  }
}

function inferVolatility(points: BasePoint[]) {
  if (!points.length) return 0
  const axisStd = [
    stddev(points.map((p) => p.minimal)),
    stddev(points.map((p) => p.structured)),
    stddev(points.map((p) => p.neutral)),
    stddev(points.map((p) => p.classic)),
    stddev(points.map((p) => p.casual)),
  ]
  return clamp(avg(axisStd) * 3.2)
}

function groupByPeriod(points: BasePoint[], unit: 'day' | 'week') {
  const grouped = new Map<string, BasePoint[]>()
  for (const point of points) {
    const d = safeDate(point.createdAtISO, new Date())
    const key = unit === 'day' ? dayKey(d) : weekKey(d)
    const row = grouped.get(key)
    if (row) row.push(point)
    else grouped.set(key, [point])
  }
  return Array.from(grouped.entries())
    .sort((a, b) => +new Date(a[0]) - +new Date(b[0]))
    .map(([key, rows]) => {
      const base = averageBase(rows)
      return {
        key,
        createdAtISO: safeDate(rows[rows.length - 1]?.createdAtISO, new Date()).toISOString(),
        minimal: base.minimal,
        structured: base.structured,
        neutral: base.neutral,
        classic: base.classic,
        casual: base.casual,
      }
    })
}

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t
}

function densifyBasePoints(points: BasePoint[]) {
  // Style scores can be legitimately sparse (weekly/monthly). For the drift chart we
  // densify to daily points via interpolation so the plot doesn't look empty.
  const sorted = [...points].sort((a, b) => +new Date(a.createdAtISO) - +new Date(b.createdAtISO))
  if (sorted.length < 2) return sorted

  const dayMs = 24 * 3600 * 1000
  const gaps = sorted
    .slice(1)
    .map((p, idx) => Math.max(0, (+new Date(p.createdAtISO) - +new Date(sorted[idx]!.createdAtISO)) / dayMs))
    .filter((x) => Number.isFinite(x) && x > 0)
  const avgGap = gaps.length ? avg(gaps) : 0

  // Only densify when data is sparse enough that charts look empty.
  if (sorted.length >= 18 || avgGap <= 1.2) return sorted

  const out: BasePoint[] = []
  for (let i = 0; i < sorted.length - 1; i++) {
    const a = sorted[i]!
    const b = sorted[i + 1]!
    out.push(a)

    const d0 = safeDate(a.createdAtISO, new Date())
    const d1 = safeDate(b.createdAtISO, new Date(+d0 + dayMs))
    const days = Math.round((+d1 - +d0) / dayMs)
    if (!Number.isFinite(days) || days <= 1) continue

    const steps = Math.min(days - 1, 45) // hard cap between any two points
    for (let step = 1; step <= steps; step++) {
      const t = step / days
      out.push({
        createdAtISO: new Date(+d0 + step * dayMs).toISOString(),
        minimal: lerp(a.minimal, b.minimal, t),
        structured: lerp(a.structured, b.structured, t),
        neutral: lerp(a.neutral, b.neutral, t),
        classic: lerp(a.classic, b.classic, t),
        casual: lerp(a.casual, b.casual, t),
      })
      if (out.length >= 140) break
    }
    if (out.length >= 140) break
  }

  if (out.length < 140) out.push(sorted[sorted.length - 1]!)
  return out
}

function buildTimeSeries(points: BasePoint[]): IdentityTimePoint[] {
  const grouped = groupByPeriod(densifyBasePoints(points), 'day')
  return grouped.map((point, index) => ({
    key: point.key,
    dateISO: point.createdAtISO,
    label: axisLabelFromISO(point.createdAtISO),
    index,
    minimal: Math.round(point.minimal),
    maximal: Math.round(100 - point.minimal),
    neutral: Math.round(point.neutral),
    colorForward: Math.round(100 - point.neutral),
    structured: Math.round(point.structured),
    relaxed: Math.round(100 - point.structured),
    classic: Math.round(point.classic),
    trendDriven: Math.round(100 - point.classic),
  }))
}

function computeSlopePerWeek(points: BasePoint[], axis: keyof Omit<BasePoint, 'createdAtISO'>) {
  if (points.length <= 1) return 0
  const sorted = [...points].sort((a, b) => +new Date(a.createdAtISO) - +new Date(b.createdAtISO))
  const x0 = +new Date(sorted[0]!.createdAtISO)
  const xs = sorted.map((p) => (+new Date(p.createdAtISO) - x0) / (24 * 3600 * 1000))
  const ys = sorted.map((p) => p[axis])
  const mx = avg(xs)
  const my = avg(ys)
  let num = 0
  let den = 0
  for (let i = 0; i < xs.length; i++) {
    const dx = (xs[i] ?? 0) - mx
    num += dx * ((ys[i] ?? 0) - my)
    den += dx * dx
  }
  if (!den) return 0
  return (num / den) * 7
}

function predictFromSlopes(current: IdentityVector, slopesPerWeek: FashionIdentityResult['forecast']['slopesPerWeek'], weeks: number) {
  const minimal = clamp(current.minimal + slopesPerWeek.minimal * weeks)
  const structured = clamp(current.structured + slopesPerWeek.structured * weeks)
  const neutral = clamp(current.neutral + slopesPerWeek.neutral * weeks)
  const classic = clamp(current.classic + slopesPerWeek.classic * weeks)
  const casual = clamp(current.casual + slopesPerWeek.casual * weeks)
  const base: BasePoint = {
    createdAtISO: new Date().toISOString(),
    minimal,
    structured,
    neutral,
    classic,
    casual,
  }
  const volatility = clamp(current.experimental + slopesPerWeek.tailored * 4)
  return toIdentityVector(base, volatility)
}

function describeEra(vector: IdentityVector) {
  if (vector.minimal >= 62 && vector.structured >= 60 && vector.neutral >= 60) return 'Soft Power Minimalism'
  if (vector.structured >= 62 && vector.classic >= 60 && vector.neutral >= 55 && vector.trendDriven >= 44) {
    return 'Late 90s Corporate Core'
  }
  if (vector.colorForward >= 60 && vector.maximal >= 60 && vector.trendDriven >= 58) return 'Pop Maximalism'
  if (vector.street >= 61 && vector.casual >= 62) return 'Relaxed Street Utility'
  if (vector.minimal >= 65 && vector.classic >= 62 && vector.neutral >= 68) return 'Quiet Luxury Core'
  if (vector.experimental >= 62 && vector.tailored >= 57) return 'Experimental Studio Tailoring'
  return 'Modern Transitional Uniform'
}

function seasonLabel(vector: IdentityVector): IdentitySeasonSegment['label'] {
  if (vector.casual >= 62 && vector.structured <= 46 && vector.trendDriven <= 48) return 'Comfort season'
  if (vector.structured >= 62 && vector.classic >= 56 && vector.tailored >= 58) return 'Formal ambition season'
  if (vector.experimental >= 58 || vector.colorForward >= 58 || vector.maximal >= 58) return 'Experimental season'
  return 'Identity consolidation season'
}

function extractCapturePrompt(capture: ApiCatalogRequestOut) {
  const directCandidates = [
    capture.prompt,
    capture.prompt_text,
    capture.query_used,
    capture.request_text,
    capture.notes,
  ]
  for (const candidate of directCandidates) {
    if (typeof candidate === 'string' && candidate.trim()) return candidate.trim()
  }

  const loose = capture as ApiCatalogRequestOut & Record<string, unknown>
  const looseCandidates = [
    loose.query,
    loose.prompt_used,
    loose.search_prompt,
    loose.caption,
    loose.description,
    loose.request_prompt,
  ]
  for (const candidate of looseCandidates) {
    if (typeof candidate === 'string' && candidate.trim()) return candidate.trim()
  }

  const metadata = capture.metadata
  if (metadata && typeof metadata === 'object') {
    const meta = metadata as Record<string, unknown>
    const metaCandidates = [meta.prompt, meta.query, meta.caption, meta.description, meta.request]
    for (const candidate of metaCandidates) {
      if (typeof candidate === 'string' && candidate.trim()) return candidate.trim()
    }
  }

  return ''
}

function textFromSources(input: FashionIdentityInput) {
  const segments: string[] = []
  for (const rec of input.catalogRecommendations) {
    segments.push(rec.title ?? '')
    segments.push(rec.source ?? '')
    segments.push(rec.query_used ?? '')
    segments.push(rec.price_text ?? '')
  }
  for (const rec of input.styleRecommendations) {
    segments.push(rec.title ?? '')
    segments.push(rec.source ?? '')
    segments.push(rec.query_used ?? '')
    segments.push(rec.rationale ?? '')
  }
  for (const capture of input.captures) {
    segments.push(capture.garment_name ?? '')
    segments.push(capture.brand_hint ?? '')
    segments.push(extractCapturePrompt(capture))
  }
  return segments.join(' ')
}

function topDescriptor(value: number, highLabel: string, lowLabel: string) {
  return value >= 50 ? highLabel : lowLabel
}

function normalizedBias(relaxed: number, structured: number, maximal: number) {
  const sum = Math.max(1, relaxed + structured + maximal)
  return {
    relaxed: Math.round((relaxed / sum) * 100),
    structured: Math.round((structured / sum) * 100),
    maximal: Math.round((maximal / sum) * 100),
  }
}

function formatSigned(n: number) {
  const rounded = Math.round(n * 10) / 10
  if (rounded > 0) return `+${rounded}`
  return `${rounded}`
}

function percentile(value: number, population: number[]) {
  if (!population.length) return 50
  let below = 0
  let equal = 0
  for (const p of population) {
    if (p < value) below += 1
    else if (p === value) equal += 1
  }
  return Math.round(((below + equal * 0.5) / population.length) * 100)
}

function stableTopK(counts: Map<string, number>, k: number, fallback: Array<[string, number]>) {
  const entries = topEntries(counts, k)
  if (entries.length >= k) return entries
  return [...entries, ...fallback.filter(([word]) => !entries.some(([x]) => x === word)).slice(0, k - entries.length)]
}

function withinDays(iso: string, base: Date, days: number) {
  const d = safeDate(iso, base)
  return +d >= +base - days * 24 * 3600 * 1000
}

function strongestDeltaAxis(deltas: Array<{ key: keyof IdentityVector; label: string; value: number }>) {
  if (!deltas.length) return null
  return [...deltas].sort((a, b) => Math.abs(b.value) - Math.abs(a.value))[0] ?? null
}

function buildDemoFlags(): IdentityDemoFlags {
  return {
    wrapped: false,
    geography: false,
    drift: false,
    celebrity: false,
    dna: false,
    microTrends: false,
    noteworthy: false,
    tasteMatch: true,
    era: false,
    forecast: false,
    essay: false,
    seasons: false,
    percentiles: true,
    futureSelf: false,
  }
}

function signature(input: FashionIdentityInput) {
  const styleSig = input.styleScores
    .slice(0, 80)
    .map((s) => `${s.id}:${s.created_at}:${s.minimal ?? ''}:${s.structured ?? ''}:${s.neutral ?? ''}:${s.classic ?? ''}:${s.casual ?? ''}`)
    .join('|')
  const capSig = input.captures
    .slice(0, 80)
    .map((c) => `${c.id}:${c.created_at}:${c.garment_name ?? ''}:${c.brand_hint ?? ''}:${extractCapturePrompt(c)}`)
    .join('|')
  const recSig = input.catalogRecommendations
    .slice(0, 60)
    .map((r) => `${r.rank}:${r.title}:${r.query_used ?? ''}`)
    .join('|')
  const styleRecSig = input.styleRecommendations
    .slice(0, 60)
    .map((r) => `${r.rank}:${r.title}:${r.query_used ?? ''}:${r.rationale ?? ''}`)
    .join('|')
  return `${styleSig}::${capSig}::${recSig}::${styleRecSig}`
}

const cache = new Map<string, FashionIdentityResult>()
const cacheOrder: string[] = []
const CACHE_LIMIT = 16

function putCache(key: string, value: FashionIdentityResult) {
  cache.set(key, value)
  cacheOrder.push(key)
  if (cacheOrder.length <= CACHE_LIMIT) return
  const oldest = cacheOrder.shift()
  if (oldest) cache.delete(oldest)
}

function buildGeoCentroids(volatility = 45): GeoCentroid[] {
  const mk = (
    key: string,
    city: string,
    year: number,
    lat: number,
    lng: number,
    base: BasePoint,
  ): GeoCentroid => ({
    key,
    city,
    year,
    lat,
    lng,
    vector: toIdentityVector(base, volatility),
  })
  return [
    mk('barcelona_2020', 'Barcelona', 2020, 41.3851, 2.1734, { createdAtISO: '', minimal: 72, structured: 58, neutral: 70, classic: 56, casual: 50 }),
    mk('seoul_2023', 'Seoul', 2023, 37.5665, 126.978, { createdAtISO: '', minimal: 54, structured: 48, neutral: 52, classic: 45, casual: 70 }),
    mk('tokyo_2018', 'Tokyo', 2018, 35.6762, 139.6503, { createdAtISO: '', minimal: 64, structured: 61, neutral: 66, classic: 50, casual: 48 }),
    mk('paris_2019', 'Paris', 2019, 48.8566, 2.3522, { createdAtISO: '', minimal: 69, structured: 69, neutral: 76, classic: 73, casual: 36 }),
    mk('newyork_2017', 'New York', 2017, 40.7128, -74.006, { createdAtISO: '', minimal: 61, structured: 56, neutral: 64, classic: 51, casual: 64 }),
    mk('copenhagen_2021', 'Copenhagen', 2021, 55.6761, 12.5683, { createdAtISO: '', minimal: 68, structured: 54, neutral: 62, classic: 57, casual: 58 }),
  ]
}

function buildCelebrityCentroids(volatility = 42): CelebrityCentroid[] {
  const mk = (
    key: string,
    name: string,
    era: string,
    palette: string[],
    base: BasePoint,
  ): CelebrityCentroid => ({
    key,
    name,
    era,
    palette,
    vector: toIdentityVector(base, volatility),
  })
  return [
    mk('nicole_wallace', 'Nicole Wallace', 'Modern tailored neutrals', ['charcoal', 'navy', 'ivory'], {
      createdAtISO: '',
      minimal: 74,
      structured: 76,
      neutral: 78,
      classic: 70,
      casual: 34,
    }),
    mk('zendaya', 'Zendaya', 'Press-tour tailoring', ['black', 'ivory', 'burgundy'], {
      createdAtISO: '',
      minimal: 58,
      structured: 80,
      neutral: 59,
      classic: 62,
      casual: 36,
    }),
    mk('hailey_bieber', 'Hailey Bieber', 'Clean street base', ['beige', 'black', 'gray'], {
      createdAtISO: '',
      minimal: 65,
      structured: 42,
      neutral: 66,
      classic: 54,
      casual: 74,
    }),
    mk('tilda_swinton', 'Tilda Swinton', 'Architectural minimalism', ['black', 'slate', 'cream'], {
      createdAtISO: '',
      minimal: 79,
      structured: 71,
      neutral: 73,
      classic: 47,
      casual: 42,
    }),
    mk('rihanna', 'Rihanna', 'Luxury maximal drift', ['red', 'black', 'gold'], {
      createdAtISO: '',
      minimal: 31,
      structured: 48,
      neutral: 37,
      classic: 30,
      casual: 63,
    }),
  ]
}

function buildMockTasteUsers(volatility = 40): MockTasteUser[] {
  const mk = (
    key: string,
    handle: string,
    tonalConsistency: number,
    base: BasePoint,
  ): MockTasteUser => ({
    key,
    handle,
    tonalConsistency,
    vector: toIdentityVector(base, volatility),
  })
  return [
    mk('alex', '@Alex', 82, { createdAtISO: '', minimal: 67, structured: 62, neutral: 69, classic: 58, casual: 47 }),
    mk('socrates', '@ Socrates', 76, { createdAtISO: '', minimal: 52, structured: 48, neutral: 56, classic: 44, casual: 70 }),
    mk('mila', '@Mila', 89, { createdAtISO: '', minimal: 75, structured: 68, neutral: 80, classic: 72, casual: 33 }),
    mk('jules', '@Jules', 61, { createdAtISO: '', minimal: 42, structured: 40, neutral: 45, classic: 36, casual: 76 }),
    mk('noah', '@Noah', 78, { createdAtISO: '', minimal: 58, structured: 57, neutral: 63, classic: 52, casual: 60 }),
  ]
}

export function computeFashionIdentity(input: FashionIdentityInput): FashionIdentityResult {
  const now = input.now ?? new Date()
  const demoFlags = buildDemoFlags()

  const rawStylePoints = input.styleScores
    .map(parseScorePoint)
    .sort((a, b) => +new Date(a.createdAtISO) - +new Date(b.createdAtISO))
  const stylePoints = rawStylePoints.length >= 3 ? rawStylePoints : [...DEMO_BASE_SERIES]
  const usingStyleDemo = rawStylePoints.length < 3
  if (usingStyleDemo) {
    demoFlags.wrapped = true
    demoFlags.geography = true
    demoFlags.drift = true
    demoFlags.celebrity = true
    demoFlags.dna = true
    demoFlags.era = true
    demoFlags.forecast = true
    demoFlags.noteworthy = true
    demoFlags.seasons = true
    demoFlags.futureSelf = true
  }

  const volatility = inferVolatility(stylePoints)
  const latestBase = stylePoints[stylePoints.length - 1] ?? DEMO_BASE_SERIES[DEMO_BASE_SERIES.length - 1]!
  const currentVector = toIdentityVector(latestBase, volatility)
  const latestStyleSignalDate = safeDate(latestBase.createdAtISO, now)

  const latestCaptureSignalDate = input.captures.length
    ? input.captures
        .map((c) => safeDate(c.created_at, now))
        .sort((a, b) => +b - +a)[0] ?? now
    : safeDate(latestBase.createdAtISO, now)
  const lastSignalDate = +latestCaptureSignalDate > +latestStyleSignalDate ? latestCaptureSignalDate : latestStyleSignalDate
  const periodStart = new Date(+lastSignalDate - 30 * 24 * 3600 * 1000)
  const previousPeriodStart = new Date(+periodStart - 30 * 24 * 3600 * 1000)

  const currentPeriodPoints = stylePoints.filter((p) => +new Date(p.createdAtISO) >= +periodStart)
  const previousPeriodPoints = stylePoints.filter(
    (p) => +new Date(p.createdAtISO) >= +previousPeriodStart && +new Date(p.createdAtISO) < +periodStart,
  )
  const currentPeriodBase = averageBase(currentPeriodPoints.length ? currentPeriodPoints : stylePoints.slice(-5))
  const previousPeriodBase = averageBase(previousPeriodPoints.length ? previousPeriodPoints : stylePoints.slice(-10, -5))
  const currentPeriodVector = toIdentityVector(
    { createdAtISO: latestBase.createdAtISO, ...currentPeriodBase },
    inferVolatility(currentPeriodPoints),
  )
  const previousPeriodVector = toIdentityVector(
    { createdAtISO: latestBase.createdAtISO, ...previousPeriodBase },
    inferVolatility(previousPeriodPoints.length ? previousPeriodPoints : stylePoints),
  )

  const timeSeries = buildTimeSeries(stylePoints)

  const annotations: DriftAnnotation[] = []
  if (timeSeries.length >= 3) {
    const axes: Array<{ key: 'minimal' | 'neutral' | 'structured' | 'classic'; label: string }> = [
      { key: 'minimal', label: 'minimal' },
      { key: 'neutral', label: 'neutral' },
      { key: 'structured', label: 'structured' },
      { key: 'classic', label: 'classic' },
    ]
    for (const axis of axes) {
      let bestIdx = 1
      let bestDelta = 0
      for (let i = 1; i < timeSeries.length; i++) {
        const delta = (timeSeries[i]?.[axis.key] ?? 0) - (timeSeries[i - 1]?.[axis.key] ?? 0)
        if (Math.abs(delta) > Math.abs(bestDelta)) {
          bestDelta = delta
          bestIdx = i
        }
      }
      if (Math.abs(bestDelta) >= 7) {
        const row = timeSeries[bestIdx]!
        annotations.push({
          key: `${axis.key}_${row.key}`,
          dateISO: row.dateISO,
          label: row.label,
          axis: axis.key,
          delta: bestDelta,
          message: `${row.label} ${axis.label} spike (${bestDelta > 0 ? '+' : ''}${Math.round(bestDelta)}).`,
        })
      }
    }
  }
  if (!annotations.length) {
    const latest = timeSeries[timeSeries.length - 1]
    if (latest) {
      annotations.push({
        key: `steady_${latest.key}`,
        dateISO: latest.dateISO,
        label: latest.label,
        axis: 'structured',
        delta: 0,
        message: 'No large spike detected. Your silhouette signal is steady.',
      })
    }
  }

  const sourceText = textFromSources(input)
  const tokens = textTokens(sourceText)
  const colorCounts = countKeywords(tokens, COLOR_WORDS)
  const materialCounts = countKeywords(tokens, MATERIAL_WORDS)
  const itemCounts = countKeywords(tokens, ITEM_WORDS)

  const paletteTop = stableTopK(
    colorCounts,
    4,
    [
      ['charcoal', 4],
      ['navy', 3],
      ['cream', 2],
      ['beige', 2],
    ],
  )
  const palette = paletteTop.slice(0, 4).map(([name]) => name)
  if (!colorCounts.size) demoFlags.wrapped = true

  const topItemEntry = stableTopK(itemCounts, 1, [['blazer', 3]])[0] ?? ['blazer', 3]
  const mostCapturedItem = { item: topItemEntry[0], count: topItemEntry[1] }
  if (!itemCounts.size && !input.captures.some((c) => c.garment_name)) demoFlags.wrapped = true

  const captureCurrent = input.captures.filter((c) => withinDays(c.created_at, lastSignalDate, 30))
  if (captureCurrent.length < 2) demoFlags.wrapped = true

  const topAesthetic = {
    label: [
      topDescriptor(currentPeriodVector.minimal, 'Minimal', 'Maximal'),
      topDescriptor(currentPeriodVector.structured, 'Structured', 'Relaxed'),
      topDescriptor(currentPeriodVector.neutral, 'Neutral', 'Color-forward'),
    ].join(' '),
    score: Math.round(
      avg([
        currentPeriodVector.minimal >= 50 ? currentPeriodVector.minimal : 100 - currentPeriodVector.minimal,
        currentPeriodVector.structured >= 50 ? currentPeriodVector.structured : 100 - currentPeriodVector.structured,
        currentPeriodVector.neutral >= 50 ? currentPeriodVector.neutral : 100 - currentPeriodVector.neutral,
      ]),
    ),
  }

  const fashionAgeValue = clamp(
    19 +
      currentPeriodVector.classic * 0.11 +
      currentPeriodVector.structured * 0.06 +
      currentPeriodVector.neutral * 0.05 -
      currentPeriodVector.maximal * 0.03 -
      currentPeriodVector.colorForward * 0.02,
    18,
    44,
  )
  const fashionAge = {
    value: Math.round(fashionAgeValue * 10) / 10,
    rationale:
      currentPeriodVector.classic >= 58
        ? 'Timeless proportions and tonal discipline are pulling your score upward.'
        : 'Experimental and relaxed swings are keeping your score youthful.',
  }

  const geoCentroids = buildGeoCentroids(volatility)
  const geoMatches = geoCentroids
    .map((c): IdentityRegionMatch => ({
      key: c.key,
      city: c.city,
      year: c.year,
      label: `${c.city} ${c.year}`,
      similarity: clamp(Math.round(cosineSimilarity(vectorToArray(currentPeriodVector), vectorToArray(c.vector)) * 100), 0, 100),
      lat: c.lat,
      lng: c.lng,
    }))
    .sort((a, b) => b.similarity - a.similarity)

  const geoPrev = geoCentroids
    .map((c) => ({
      key: c.key,
      city: c.city,
      year: c.year,
      similarity: cosineSimilarity(vectorToArray(previousPeriodVector), vectorToArray(c.vector)),
    }))
    .sort((a, b) => b.similarity - a.similarity)

  const geoTop = geoMatches[0] ?? {
    key: 'barcelona_2020',
    city: 'Barcelona',
    year: 2020,
    label: 'Barcelona 2020',
    similarity: 74,
    lat: 41.3851,
    lng: 2.1734,
  }
  const geoDrift = geoMatches[1] ?? geoTop
  const prevTop = geoPrev[0] ?? geoDrift
  const driftMessage =
    prevTop.key !== geoTop.key
      ? `Your style drifted toward ${geoTop.city} ${geoTop.year} this month.`
      : `Your style drifted toward ${geoDrift.city} ${geoDrift.year} this month.`

  const silhouetteBias = normalizedBias(currentPeriodVector.relaxed, currentPeriodVector.structured, currentPeriodVector.maximal)

  const unexpectedPhase = annotations[0]?.message ?? 'No unexpected phase spike this period.'

  const wrappedSummaryLines = [
    `Your Style Wrapped (${labelFromISO(periodStart.toISOString())} - ${labelFromISO(lastSignalDate.toISOString())})`,
    `Top aesthetic: ${topAesthetic.label} (${topAesthetic.score}%)`,
    `Fashion age: ${fashionAge.value}`,
    `Fashion geography: ${geoTop.city} ${geoTop.year}; drift: ${geoDrift.city} ${geoDrift.year}`,
    `Silhouette bias: relaxed ${silhouetteBias.relaxed}% / structured ${silhouetteBias.structured}% / maximal ${silhouetteBias.maximal}%`,
    `Top palette: ${palette.slice(0, 4).join(', ')}`,
    `Most captured item: ${mostCapturedItem.item} (${mostCapturedItem.count})`,
    `Unexpected phase: ${unexpectedPhase}`,
  ]

  const celebrityCentroids = buildCelebrityCentroids(volatility)
  const celebTop = celebrityCentroids
    .map((c) => ({
      key: c.key,
      name: c.name,
      era: c.era,
      palette: c.palette,
      similarity: clamp(Math.round(cosineSimilarity(vectorToArray(currentPeriodVector), vectorToArray(c.vector)) * 100), 0, 100),
    }))
    .sort((a, b) => b.similarity - a.similarity)
    .slice(0, 3)
  const selectedCeleb = celebTop[0] ?? {
    key: 'nicole_wallace',
    name: 'Nicole Wallace',
    era: 'Modern tailored neutrals',
    palette: ['charcoal', 'navy', 'ivory'],
    similarity: 92,
  }
  if (!rawStylePoints.length) demoFlags.celebrity = true

  const dnaRadar = [
    { key: 'minimal', label: 'Minimal', value: Math.round(currentPeriodVector.minimal) },
    { key: 'structured', label: 'Structured', value: Math.round(currentPeriodVector.structured) },
    { key: 'neutral', label: 'Neutral', value: Math.round(currentPeriodVector.neutral) },
    { key: 'classic', label: 'Classic', value: Math.round(currentPeriodVector.classic) },
    { key: 'casual', label: 'Casual', value: Math.round(currentPeriodVector.casual) },
    { key: 'experimental', label: 'Experimental', value: Math.round(currentPeriodVector.experimental) },
    { key: 'tailored', label: 'Tailored', value: Math.round(currentPeriodVector.tailored) },
    { key: 'street', label: 'Street', value: Math.round(currentPeriodVector.street) },
  ]

  const longRunStd = avg([
    stddev(stylePoints.map((p) => p.minimal)),
    stddev(stylePoints.map((p) => p.structured)),
    stddev(stylePoints.map((p) => p.neutral)),
    stddev(stylePoints.map((p) => p.classic)),
  ])
  const shortRunStd = avg([
    stddev(stylePoints.slice(-5).map((p) => p.minimal)),
    stddev(stylePoints.slice(-5).map((p) => p.structured)),
    stddev(stylePoints.slice(-5).map((p) => p.neutral)),
    stddev(stylePoints.slice(-5).map((p) => p.classic)),
  ])
  const stabilityPercent = clamp(Math.round((1 - longRunStd / 24) * 100), 20, 98)
  const mutationPhase = shortRunStd > Math.max(6.8, longRunStd * 0.86)

  const microInsights: string[] = []
  const topMaterials = topEntries(materialCounts, 2)
  if (topMaterials[0]) {
    microInsights.push(`You captured ${topMaterials[0][1]} ${topMaterials[0][0]} pieces in the last cycle.`)
  }
  if (topMaterials[1]) {
    microInsights.push(`You are entering a ${topMaterials[1][0]} phase.`)
  }

  const currentText = textTokens(
    [
      ...input.catalogRecommendations
        .map((r) => `${r.title} ${r.query_used ?? ''}`),
      ...input.styleRecommendations.map((r) => `${r.title} ${r.rationale ?? ''}`),
      ...captureCurrent.map((c) => `${c.garment_name ?? ''} ${c.brand_hint ?? ''} ${extractCapturePrompt(c)}`),
    ].join(' '),
  )
  const prevCaptures = input.captures.filter(
    (c) => +safeDate(c.created_at, now) < +periodStart && +safeDate(c.created_at, now) >= +previousPeriodStart,
  )
  const previousText = textTokens(
    [
      ...prevCaptures.map((c) => `${c.garment_name ?? ''} ${c.brand_hint ?? ''} ${extractCapturePrompt(c)}`),
      ...input.catalogRecommendations.slice(12).map((r) => `${r.title} ${r.query_used ?? ''}`),
    ].join(' '),
  )

  const warmCurrent = currentText.reduce((acc, t) => acc + (WARM_COLORS.has(t) ? 1 : 0), 0)
  const coolCurrent = currentText.reduce((acc, t) => acc + (COOL_COLORS.has(t) ? 1 : 0), 0)
  const warmPrev = previousText.reduce((acc, t) => acc + (WARM_COLORS.has(t) ? 1 : 0), 0)
  const coolPrev = previousText.reduce((acc, t) => acc + (COOL_COLORS.has(t) ? 1 : 0), 0)
  const currentWarmRatio = warmCurrent + coolCurrent ? warmCurrent / (warmCurrent + coolCurrent) : 0.5
  const previousWarmRatio = warmPrev + coolPrev ? warmPrev / (warmPrev + coolPrev) : 0.5
  const temperatureShift = Math.round((currentWarmRatio - previousWarmRatio) * 100)
  microInsights.push(`Your color temperature shifted ${Math.abs(temperatureShift)}% ${temperatureShift >= 0 ? 'warmer' : 'cooler'} this month.`)

  const topItemList = topEntries(itemCounts, 2)
  if (topItemList[0]) microInsights.push(`Most captured silhouette driver: ${topItemList[0][0]} (${topItemList[0][1]} mentions).`)

  if (microInsights.length < 3) {
    demoFlags.microTrends = true
    microInsights.push('Structured outerwear continued to outperform in your capture cadence.')
    microInsights.push('Tonal consistency remained high across recent recommendations.')
  }

  const captureHighlights = [...input.captures]
    .sort((a, b) => +safeDate(b.created_at, now) - +safeDate(a.created_at, now))
    .slice(0, 18)
    .map((capture) => {
      const createdAt = safeDate(capture.created_at, now)
      const garment = capture.garment_name?.trim() || ''
      const brand = capture.brand_hint?.trim() || ''
      const capturePrompt = extractCapturePrompt(capture)
      const promptSeed = [capturePrompt, brand, garment].filter(Boolean).join(' ').trim()
      const prompt = promptSeed || 'Captured outfit signal'
      const promptTokens = textTokens(prompt)
      const hasTailoring = promptTokens.some((token) => ['blazer', 'trouser', 'shirt', 'coat', 'jacket'].includes(token))
      const hasSoft = promptTokens.some((token) => ['knit', 'sweater', 'hoodie', 'tee'].includes(token))
      const hasStatement = promptTokens.some((token) => ['leather', 'velvet', 'satin', 'mesh', 'denim'].includes(token))
      const rationale = capturePrompt
        ? hasTailoring
          ? 'Catalog request prompt shows strong structured-tailoring intent.'
          : hasStatement
            ? 'Catalog request prompt is material-forward and experimentally biased.'
            : hasSoft
              ? 'Catalog request prompt leans relaxed and casual.'
              : 'Catalog request prompt aligns with your current aesthetic baseline.'
        : hasTailoring
          ? 'Strong structured-tailoring prompt signal.'
          : hasStatement
            ? 'Material-forward prompt signal with experimental potential.'
            : hasSoft
              ? 'Relaxed and casual prompt bias.'
              : 'Prompt aligns with your current aesthetic baseline.'
      const promptLead = textTokens(capturePrompt)
        .slice(0, 4)
        .map((token) => toTitleWord(token))
        .join(' ')
      const title = garment
        ? `${toTitleWord(garment)}${brand ? ` / ${brand}` : ''}`
        : brand
          ? `${brand} style capture`
          : promptLead
            ? `${promptLead} prompt`
            : 'Outfit capture'
      const recencyBoost = Math.max(0, 14 - Math.round((+lastSignalDate - +createdAt) / (24 * 3600 * 1000)))
      const confidence = typeof capture.confidence === 'number' ? capture.confidence : 0.5
      const score = recencyBoost + confidence * 7 + (promptSeed ? 3 : 0) + (capturePrompt ? 4 : 0)
      return {
        key: `capture_${capture.id}`,
        createdAtISO: createdAt.toISOString(),
        title,
        prompt: compactPrompt(prompt),
        rationale,
        source: 'capture' as const,
        captureId: capture.id,
        score,
      }
    })

  const recommendationPrompts = [
    ...input.catalogRecommendations.map((row) => row.query_used).filter((x): x is string => typeof x === 'string' && x.trim().length > 6),
    ...input.styleRecommendations.map((row) => row.query_used).filter((x): x is string => typeof x === 'string' && x.trim().length > 6),
    ...input.captures.map((row) => extractCapturePrompt(row)).filter((x) => x.trim().length > 6),
  ]
  const promptCount = new Map<string, number>()
  for (const prompt of recommendationPrompts) {
    const key = prompt.trim()
    promptCount.set(key, (promptCount.get(key) ?? 0) + 1)
  }
  const recommendationHighlights = Array.from(promptCount.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([prompt, count], idx) => {
      const promptTokens = textTokens(prompt)
      const leading = promptTokens.slice(0, 5).map((token) => toTitleWord(token)).join(' ')
      const mentionsColor = promptTokens.some((token) => COLOR_WORDS.includes(token))
      const mentionsTexture = promptTokens.some((token) => MATERIAL_WORDS.includes(token))
      const rationale = mentionsTexture
        ? `Prompt repeated across ${count} recommendation pulls with a clear material motif.`
        : mentionsColor
          ? `Prompt repeated across ${count} recommendation pulls with palette emphasis.`
          : `Prompt repeated across ${count} recommendation pulls and tracks current style drift.`
      return {
        key: `prompt_${idx}_${prompt.slice(0, 16)}`,
        createdAtISO: lastSignalDate.toISOString(),
        title: leading || 'Recommendation prompt',
        prompt: compactPrompt(prompt),
        rationale,
        source: 'recommendation' as const,
        score: 2 + count * 2.4,
      }
    })

  const noteworthyRaw = [...captureHighlights, ...recommendationHighlights]
    .sort((a, b) => b.score - a.score)
    .slice(0, 6)
    .map(({ score, ...item }) => item)

  const noteworthyItems = noteworthyRaw.length
    ? noteworthyRaw
    : [
        {
          key: 'demo_noteworthy_1',
          createdAtISO: lastSignalDate.toISOString(),
          title: 'Structured navy blazer',
          prompt: 'Navy structured blazer clean trousers minimal accessories',
          rationale: 'Prompt emphasis indicates a strong tailored direction.',
          source: 'capture' as const,
        },
        {
          key: 'demo_noteworthy_2',
          createdAtISO: lastSignalDate.toISOString(),
          title: 'Monochrome knit layering',
          prompt: 'Charcoal knit layering tonal palette soft drape',
          rationale: 'Prompt repetition signals consistency in tonal layering.',
          source: 'recommendation' as const,
        },
      ]
  if (!noteworthyRaw.length || input.captures.length < 2) demoFlags.noteworthy = true

  const mockUsers = buildMockTasteUsers(volatility)
  const userArr = vectorToArray(currentPeriodVector)
  const matches: TasteMatchPerson[] = mockUsers
    .map((user) => ({
      key: user.key,
      handle: user.handle,
      overlap: clamp(Math.round(cosineSimilarity(userArr, vectorToArray(user.vector)) * 100), 0, 100),
      vector: user.vector,
    }))
    .sort((a, b) => b.overlap - a.overlap)

  const topMatch = matches[0] ?? {
    key: 'alex',
    handle: '@Alex',
    overlap: 81,
    vector: currentPeriodVector,
  }
  const compareDims: Array<{ key: keyof IdentityVector; label: string }> = [
    { key: 'minimal', label: 'Minimalism' },
    { key: 'structured', label: 'Structure' },
    { key: 'neutral', label: 'Palette' },
    { key: 'classic', label: 'Classics' },
    { key: 'casual', label: 'Casualness' },
  ]
  const deltas = compareDims.map((dim) => {
    const userValue = currentPeriodVector[dim.key]
    const friendValue = topMatch.vector[dim.key]
    return {
      key: dim.key,
      label: dim.label,
      overlap: clamp(Math.round(100 - Math.abs(userValue - friendValue))),
      delta: Math.round(userValue - friendValue),
    }
  })
  const strongestDivergence = strongestDeltaAxis(
    deltas.map((d) => ({ key: d.key as keyof IdentityVector, label: d.label, value: d.delta })),
  )
  const divergenceLine = strongestDivergence
    ? `Your styles diverge on ${strongestDivergence.label.toLowerCase()} but match on palette.`
    : 'Your styles remain closely aligned across core dimensions.'

  const trendWindow = stylePoints.slice(-14)
  const slopeMinimal = computeSlopePerWeek(trendWindow, 'minimal')
  const slopeStructured = computeSlopePerWeek(trendWindow, 'structured')
  const slopeNeutral = computeSlopePerWeek(trendWindow, 'neutral')
  const slopeClassic = computeSlopePerWeek(trendWindow, 'classic')
  const slopeCasual = computeSlopePerWeek(trendWindow, 'casual')
  const slopeTailored = slopeStructured * 0.58 + slopeClassic * 0.32 + slopeNeutral * 0.1
  const slopesPerWeek = {
    minimal: slopeMinimal,
    structured: slopeStructured,
    neutral: slopeNeutral,
    classic: slopeClassic,
    casual: slopeCasual,
    tailored: slopeTailored,
  }

  const projected6w = predictFromSlopes(currentPeriodVector, slopesPerWeek, 6)
  const projected52w = predictFromSlopes(currentPeriodVector, slopesPerWeek, 52)

  let primaryForecast = 'You are likely to keep your current style balance over the next 6 weeks.'
  if (slopeTailored >= 0.18 || slopeStructured >= 0.18) {
    primaryForecast = 'You are likely to shift toward structured tailoring in 6 weeks.'
  } else if (slopeMinimal >= 0.16 && slopeNeutral >= 0.14) {
    primaryForecast = 'You are likely to move deeper into tonal minimalism in 6 weeks.'
  } else if (slopeCasual >= 0.18 && slopeClassic <= -0.14) {
    primaryForecast = 'You are likely to drift toward relaxed street layering in 6 weeks.'
  }

  const currentEra = describeEra(currentPeriodVector)
  const trendingEra = describeEra(projected6w)
  const futureEra = describeEra(projected52w)

  const weeklyPoints = groupByPeriod(stylePoints, 'week').map((point) =>
    toIdentityVector(point, inferVolatility(stylePoints.slice(-8))),
  )
  const seasonRuns: IdentitySeasonSegment[] = []
  if (weeklyPoints.length) {
    const weekRows = groupByPeriod(stylePoints, 'week')
    for (let i = 0; i < weekRows.length; i++) {
      const row = weekRows[i]!
      const vector = toIdentityVector(row, inferVolatility(weekRows))
      const label = seasonLabel(vector)
      if (!seasonRuns.length || seasonRuns[seasonRuns.length - 1]?.label !== label) {
        seasonRuns.push({
          key: `${label}_${row.key}_${i}`,
          label,
          startISO: row.createdAtISO,
          endISO: row.createdAtISO,
          weeks: 1,
          share: 0,
        })
      } else {
        const last = seasonRuns[seasonRuns.length - 1]!
        last.endISO = row.createdAtISO
        last.weeks += 1
      }
    }
  }
  if (!seasonRuns.length) {
    demoFlags.seasons = true
    seasonRuns.push({
      key: 'season_demo_consolidation',
      label: 'Identity consolidation season',
      startISO: now.toISOString(),
      endISO: now.toISOString(),
      weeks: 1,
      share: 1,
    })
  }
  const totalSeasonWeeks = seasonRuns.reduce((acc, cur) => acc + cur.weeks, 0)
  for (const segment of seasonRuns) {
    segment.share = totalSeasonWeeks ? segment.weeks / totalSeasonWeeks : 0
  }

  const userTonalConsistency = clamp(Math.round(100 - stddev(stylePoints.map((p) => p.neutral)) * 2.8), 12, 98)
  const percentilePopulationMinimal = mockUsers.map((u) => Math.round(u.vector.minimal))
  const percentilePopulationTonal = mockUsers.map((u) => u.tonalConsistency)
  const percentilePopulationStructure = mockUsers.map((u) => Math.round(u.vector.structured))
  const percentilePopulationClassic = mockUsers.map((u) => Math.round(u.vector.classic))
  const minimalPct = percentile(Math.round(currentPeriodVector.minimal), percentilePopulationMinimal)
  const tonalPct = percentile(userTonalConsistency, percentilePopulationTonal)
  const structuredPct = percentile(Math.round(currentPeriodVector.structured), percentilePopulationStructure)
  const classicPct = percentile(Math.round(currentPeriodVector.classic), percentilePopulationClassic)

  const percentileLines = [
    {
      key: 'minimal',
      label: 'Minimal preference',
      value: minimalPct,
      text: `You are more minimal than ${minimalPct}% of users.`,
    },
    {
      key: 'tonal',
      label: 'Tonal consistency',
      value: tonalPct,
      text: `You are in the top ${Math.max(1, 100 - tonalPct)}% for tonal consistency.`,
    },
    {
      key: 'structured',
      label: 'Structured silhouettes',
      value: structuredPct,
      text: `You are more structured than ${structuredPct}% of users.`,
    },
    {
      key: 'classic',
      label: 'Classic bias',
      value: classicPct,
      text: `You are more classic than ${classicPct}% of users.`,
    },
  ]

  const strongestProjection = strongestDeltaAxis([
    { key: 'structured', label: 'structure', value: slopesPerWeek.structured },
    { key: 'tailored', label: 'tailoring', value: slopesPerWeek.tailored },
    { key: 'classic', label: 'classic framing', value: slopesPerWeek.classic },
    { key: 'minimal', label: 'minimalism', value: slopesPerWeek.minimal },
    { key: 'neutral', label: 'palette neutrality', value: slopesPerWeek.neutral },
  ])

  const futureCeleb = celebrityCentroids
    .map((c) => ({
      name: c.name,
      score: cosineSimilarity(vectorToArray(projected52w), vectorToArray(c.vector)),
    }))
    .sort((a, b) => b.score - a.score)[0] ?? { name: 'Nicole Wallace', score: 0.9 }

  const essayPalette = palette
    .slice(0, 3)
    .map((p) => p.toLowerCase())
    .join(', ')
  const phaseLine = mutationPhase ? 'You are currently in a style mutation phase.' : 'You are currently in a style consolidation phase.'
  const essayParagraph = `This month, your wardrobe leaned into ${topAesthetic.label.toLowerCase()} energy: ${essayPalette}. Structured choices and tonal restraint carried the strongest signal while micro-shifts hinted at ${trendingEra.toLowerCase()}. ${phaseLine} If your current trajectory continues, you are likely to land in ${futureEra.toLowerCase()} next year.`

  const result: FashionIdentityResult = {
    generatedAtISO: now.toISOString(),
    lastSignalISO: lastSignalDate.toISOString(),
    sourceCounts: {
      styleScores: input.styleScores.length,
      captures: input.captures.length,
      catalogRecommendations: input.catalogRecommendations.length,
      styleRecommendations: input.styleRecommendations.length,
    },
    hasAnyDemo: Object.values(demoFlags).some(Boolean),
    demoFlags,
    vector: currentPeriodVector,
    wrapped: {
      periodStartISO: periodStart.toISOString(),
      periodEndISO: lastSignalDate.toISOString(),
      periodLabel: `${labelFromISO(periodStart.toISOString())} - ${labelFromISO(lastSignalDate.toISOString())}`,
      topAesthetic,
      fashionAge,
      fashionGeography: {
        topMatch: `${geoTop.city} ${geoTop.year}`,
        driftMatch: `${geoDrift.city} ${geoDrift.year}`,
      },
      silhouetteBias,
      palette,
      mostCapturedItem,
      unexpectedPhase,
      summaryText: wrappedSummaryLines.join('\n'),
    },
    geography: {
      regions: geoMatches.slice(0, 6),
      headline: `Your taste best matches ${geoTop.city} in ${geoTop.year}.`,
      driftLine: driftMessage,
    },
    drift: {
      series: timeSeries,
      annotations: annotations.slice(0, 4),
    },
    celebrityTwin: {
      selected: selectedCeleb,
      top3: celebTop.length ? celebTop : [selectedCeleb],
    },
    dna: {
      radar: dnaRadar,
      stabilityPercent,
      mutationPhase,
    },
    microTrends: {
      insights: microInsights.slice(0, 6),
    },
    noteworthy: {
      items: noteworthyItems,
    },
    tasteMatch: {
      topMatch,
      others: matches.slice(1, 5),
      divergenceLine,
      deltas,
    },
    era: {
      current: currentEra,
      trendingToward: trendingEra,
    },
    forecast: {
      primary: primaryForecast,
      signals: [
        `structured slope ${formatSigned(slopesPerWeek.structured)}/week`,
        `tailored slope ${formatSigned(slopesPerWeek.tailored)}/week`,
        `classic slope ${formatSigned(slopesPerWeek.classic)}/week`,
      ],
      projectedVector6w: projected6w,
      projectedVector52w: projected52w,
      slopesPerWeek,
    },
    monthlyEssay: {
      paragraph: essayParagraph,
    },
    seasons: {
      segments: seasonRuns,
    },
    percentiles: {
      lines: percentileLines,
    },
    futureSelf: {
      year: Math.max(2027, now.getFullYear() + 1),
      era: futureEra,
      twinName: futureCeleb.name,
      rationale: strongestProjection
        ? `The strongest projected shift is ${strongestProjection.label}, which aligns with ${futureEra.toLowerCase()}.`
        : `Your long-horizon vector remains aligned with ${futureEra.toLowerCase()}.`,
    },
  }

  return result
}

export function computeFashionIdentityCached(input: FashionIdentityInput): FashionIdentityResult {
  const key = signature(input)
  const existing = cache.get(key)
  if (existing) return existing
  const next = computeFashionIdentity(input)
  putCache(key, next)
  return next
}

export function paletteNameToHex(name: string) {
  return COLOR_HEX[name.toLowerCase()] ?? '#8B8E96'
}
