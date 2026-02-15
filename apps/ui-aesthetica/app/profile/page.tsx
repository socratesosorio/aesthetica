'use client'

import * as React from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Search, Sparkles, TrendingUp } from 'lucide-react'

import { TasteRadar } from '@/components/aesthetica/taste-radar'
import { CvBodyBoxes, type RegionLabel } from '@/components/dashboard/cv-body-boxes'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Separator } from '@/components/ui/separator'
import { sampleTasteRadar } from '@/lib/aesthetica/sample-data'
import { cn } from '@/lib/utils'
import { api, ensureDevToken, getStoredToken, mediaUrl } from '@/lib/api'

const kpis = [
  { label: 'Captures (7d)', value: '18', meta: '+4 vs last week' },
  { label: 'Matches generated', value: '420', meta: 'top‑K per garment' },
  { label: 'Cheapest saved', value: '$69', meta: 'today' },
  { label: 'Saved to buy', value: '26', meta: 'across captures' },
  { label: 'Purchases (30d)', value: '6', meta: '$842 total' },
] as const

const recentPurchases = [
  { item: 'Wide-leg trouser', retailer: 'Arket', price: '$119', when: '2 days', capture: '#0184' },
  { item: 'Leather loafer', retailer: 'Vagabond', price: '$140', when: '8 days', capture: '#0184' },
  { item: 'Overshirt', retailer: 'COS', price: '$145', when: '3 weeks', capture: '#0183' },
] as const

const forYou = [
  { label: 'Relaxed neutral tailoring', meta: 'new arrivals' },
  { label: 'Minimal leather footwear', meta: 'under $200' },
  { label: 'Boxy overshirts', meta: 'premium picks' },
  { label: 'Wide silhouettes', meta: 'closest to your profile' },
] as const

const CV_REGIONS: RegionLabel[] = [
  { id: 'top', label: 'Top' },
  { id: 'bottom', label: 'Bottom' },
  { id: 'shoes', label: 'Shoes' },
] as const

type ProductTile = {
  id: string
  title: string
  brand?: string | null
  price?: number | null
  currency?: string | null
  imageUrl?: string | null
  url?: string | null
  badge?: string | null
}

type CheckedItem = ProductTile & {
  checkedAtISO: string
  source: 'recommended' | 'capture'
  tags: string[]
  description: string
}

type CaptureRow = {
  id: string
  createdAtLabel: string
  status: string
  imageUrl: string
  products: ProductTile[]
}

type OutfitKind = 'separates' | 'onepiece'

function detectOutfitKind(products: ProductTile[]): OutfitKind {
  const text = products.map((p) => `${p.title ?? ''} ${p.brand ?? ''} ${p.badge ?? ''}`).join(' ').toLowerCase()
  const onepieceKeys = ['dress', 'jumpsuit', 'romper', 'overall', 'onesie', 'bodysuit']
  return onepieceKeys.some((k) => text.includes(k)) ? 'onepiece' : 'separates'
}

function bestProductForRegion(
  region: 'top' | 'bottom' | 'shoes',
  products: ProductTile[],
  kind: OutfitKind,
) {
  const hay = (p: ProductTile) => `${p.title ?? ''} ${p.brand ?? ''} ${p.badge ?? ''}`.toLowerCase()
  const byRegion: Record<typeof region, string[]> =
    kind === 'onepiece'
      ? {
          shoes: ['shoe', 'loafer', 'sneaker', 'boot', 'heel', 'mule', 'sandal', 'clog'],
          bottom: ['dress', 'jumpsuit', 'romper', 'overall', 'skirt', 'gown', 'maxi', 'mini'],
          top: ['dress', 'jumpsuit', 'romper', 'overall', 'onesie', 'bodysuit', 'gown'],
        }
      : {
          shoes: ['shoe', 'loafer', 'sneaker', 'boot', 'heel', 'mule', 'sandal', 'clog'],
          bottom: ['pant', 'trouser', 'jean', 'denim', 'skirt', 'short', 'cargo'],
          top: ['jacket', 'coat', 'blazer', 'shirt', 'tee', 't-shirt', 'knit', 'sweater', 'hoodie', 'cardigan'],
        }

  const keys = byRegion[region]
  const match = products.find((p) => keys.some((k) => hay(p).includes(k)))
  if (match) return match

  // Fallbacks: keep it deterministic.
  if (region === 'top') return products[0]
  if (region === 'bottom') return products[1] ?? products[0]
  return products[2] ?? products[0]
}

function canvasSafeSrc(src: string) {
  if (!src) return src
  if (src.startsWith('/')) return src
  return `/api/image-proxy?url=${encodeURIComponent(src)}`
}

function money(price: number | null | undefined, currency: string | null | undefined) {
  if (!price) return ''
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency || 'USD',
      maximumFractionDigits: 0,
    }).format(price)
  } catch {
    return `$${Math.round(price)}`
  }
}

const CHECKED_STORAGE_KEY = 'aesthetica_last_checked_v1'

function loadChecked(): CheckedItem[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(CHECKED_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed as CheckedItem[]
  } catch {
    return []
  }
}

function saveChecked(items: CheckedItem[]) {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(CHECKED_STORAGE_KEY, JSON.stringify(items.slice(0, 50)))
  } catch {
    // ignore storage failures
  }
}

function radarStyleTags(radar: typeof sampleTasteRadar): string[] {
  const byId = Object.fromEntries(radar.map((p) => [p.id, p.value])) as Record<string, number>
  const tags: string[] = []
  tags.push((byId.minimal_maximal ?? 50) < 45 ? 'Minimal' : 'Maximal')
  tags.push((byId.structured_relaxed ?? 50) < 45 ? 'Structured' : 'Relaxed')
  tags.push((byId.neutral_color ?? 50) > 55 ? 'Color-forward' : 'Neutral')
  tags.push((byId.classic_experimental ?? 50) > 55 ? 'Experimental' : 'Classic')
  tags.push((byId.casual_formal ?? 50) > 55 ? 'Formal' : 'Casual')
  return tags
}

function priceTags(price?: number | null): string[] {
  if (!price) return []
  if (price < 50) return ['Under $50']
  if (price < 100) return ['Under $100']
  if (price < 200) return ['$100–$199']
  return ['$200+']
}

function categoryTag(brand?: string | null, badge?: string | null): string[] {
  const tags: string[] = []
  if (brand) tags.push(brand)
  if (badge && badge.length < 40) tags.push(badge)
  return tags
}

function useInViewOnce<T extends HTMLElement>(threshold = 0.12) {
  const ref = React.useRef<T | null>(null)
  const [inView, setInView] = React.useState(false)

  React.useEffect(() => {
    if (!ref.current || inView) return
    const el = ref.current
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          setInView(true)
          obs.disconnect()
        }
      },
      { threshold },
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [inView, threshold])

  return { ref, inView }
}

function ProductCard({
  p,
  onChecked,
  source,
}: {
  p: ProductTile
  source: 'recommended' | 'capture'
  onChecked: (p: ProductTile, source: 'recommended' | 'capture') => void
}) {
  return (
    <a
      href={p.url || '#'}
      onClick={() => onChecked(p, source)}
      className={cn(
        'group relative flex flex-col overflow-hidden rounded-xl border border-border/60 bg-background',
        'transition-[transform,box-shadow,border-color,background-color] duration-300 will-change-transform',
        'hover:-translate-y-1 hover:shadow-xl hover:border-foreground/15 hover:bg-muted/30',
      )}
    >
      <div className="relative aspect-[4/5] w-full overflow-hidden bg-muted">
        <img
          src={p.imageUrl || '/images/outfit-1.png'}
          alt={p.title}
          className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.06]"
          loading="lazy"
        />
        <div className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100">
          <div className="absolute inset-0 bg-gradient-to-t from-black/20 via-transparent to-transparent" />
        </div>
        {p.badge ? (
          <div className="absolute left-2 top-2">
            <Badge variant="secondary" className="bg-white/85 text-black">
              {p.badge}
            </Badge>
          </div>
        ) : null}
      </div>
      <div className="flex flex-1 flex-col gap-1 px-3 py-3">
        <div className="line-clamp-2 text-sm font-medium">{p.title}</div>
        <div className="text-muted-foreground text-xs">{p.brand || '—'}</div>
        <div className="mt-1 text-sm font-semibold">{money(p.price, p.currency)}</div>
      </div>
    </a>
  )
}

function ProfileTopbar({
  query,
  setQuery,
}: {
  query: string
  setQuery: (v: string) => void
}) {
  return (
    <div className="sticky top-0 z-40 border-b border-border bg-background/70 backdrop-blur-md">
      <div className="mx-auto flex h-14 w-full max-w-[1600px] items-center gap-3 px-4 md:px-8">
        <Link href="/" aria-label="Aesthetica" className="flex items-center gap-3">
          <img
            src="/logo.png"
            alt="Aesthetica"
            width={28}
            height={28}
            className="h-7 w-7 rounded-md object-cover"
          />
          <span className="text-muted-foreground text-xs">Profile</span>
        </Link>

        <div className="mx-auto hidden w-full max-w-xl items-center gap-2 md:flex">
          <div className="relative w-full">
            <Search className="text-muted-foreground absolute left-3 top-1/2 size-4 -translate-y-1/2" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search your recommended items"
              className="h-10 pl-9"
            />
          </div>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <Button asChild size="sm" variant="outline" className="h-9">
            <Link href="/">Back to landing</Link>
          </Button>
          <Button asChild size="sm" variant="outline" className="h-9">
            <Link href="/database">Database</Link>
          </Button>
          <Button asChild size="sm" variant="outline" className="h-9">
            <Link href="/logout">Log out</Link>
          </Button>
        </div>
      </div>
    </div>
  )
}

export default function ProfilePage() {
  const router = useRouter()
  const [query, setQuery] = React.useState('')
  const [recent, setRecent] = React.useState<CaptureRow[]>([])
  const [recommended, setRecommended] = React.useState<ProductTile[]>([])
  const [tasteRadar, setTasteRadar] = React.useState(sampleTasteRadar)
  const [checked, setChecked] = React.useState<CheckedItem[]>([])
  const [loading, setLoading] = React.useState(true)
  const [selectedCaptureId, setSelectedCaptureId] = React.useState<string | null>(null)
  const [cvMode, setCvMode] = React.useState<'captures' | 'sample'>('captures')

  const heroView = useInViewOnce<HTMLDivElement>(0.08)
  const recentView = useInViewOnce<HTMLDivElement>(0.1)
  const lastCapturedView = useInViewOnce<HTMLDivElement>(0.1)
  const recsView = useInViewOnce<HTMLDivElement>(0.1)
  const kpisView = useInViewOnce<HTMLDivElement>(0.12)
  const belowView = useInViewOnce<HTMLDivElement>(0.12)
  const lastCheckedView = useInViewOnce<HTMLDivElement>(0.12)
  const radarView = useInViewOnce<HTMLDivElement>(0.12)
  const purchasesView = useInViewOnce<HTMLDivElement>(0.12)
  const savedView = useInViewOnce<HTMLDivElement>(0.12)

  React.useEffect(() => {
    setChecked(loadChecked())
  }, [])

  React.useEffect(() => {
    if (!recent.length) {
      setSelectedCaptureId(null)
      return
    }
    setSelectedCaptureId((cur) => (cur && recent.some((r) => r.id === cur) ? cur : recent[0]!.id))
  }, [recent])

  const onChecked = React.useCallback(
    (p: ProductTile, source: 'recommended' | 'capture') => {
      const now = new Date().toISOString()
      const style = radarStyleTags(tasteRadar)
      const tags = Array.from(
        new Set([
          source === 'capture' ? 'From capture' : 'Recommended',
          ...categoryTag(p.brand, p.badge),
          ...priceTags(p.price),
          style[0],
          style[2],
        ].filter(Boolean)),
      )

      const descriptionParts = [
        source === 'capture' ? 'Matched from a recent capture' : 'Recommended from your taste radar',
        style.slice(0, 3).join(' · '),
      ]

      const item: CheckedItem = {
        ...p,
        checkedAtISO: now,
        source,
        tags: tags.slice(0, 6),
        description: descriptionParts.filter(Boolean).join(' · '),
      }

      setChecked((prev) => {
        const deduped = [item, ...prev.filter((x) => x.id !== p.id)]
        saveChecked(deduped)
        return deduped
      })
    },
    [tasteRadar],
  )

  React.useEffect(() => {
    const ctrl = new AbortController()
    async function load() {
      const autoDev = process.env.NEXT_PUBLIC_AUTO_DEV_LOGIN === 'true'
      const token = getStoredToken() || (autoDev ? await ensureDevToken(ctrl.signal) : null)
      if (!token) {
        router.replace(`/login?next=${encodeURIComponent('/profile')}`)
        return
      }

      const me = await api.me(token, ctrl.signal)
      const [caps, recs, profile] = await Promise.all([
        api.userCaptures(me.id, token, 10, ctrl.signal),
        api.catalogRecommendations(token, 24, ctrl.signal).catch(() => []),
        api.userProfile(me.id, token, ctrl.signal),
      ])

      const profileRadar = profile?.radar_vector ?? {}
      const neutral = profileRadar.neutral_color_forward ?? profileRadar.neutral_color
      setTasteRadar([
        {
          id: 'minimal_maximal',
          axis: 'Minimal',
          leftLabel: 'Minimal',
          rightLabel: 'Maximal',
          value: profileRadar.minimal_maximal ?? sampleTasteRadar[0]?.value ?? 50,
        },
        {
          id: 'structured_relaxed',
          axis: 'Structured',
          leftLabel: 'Structured',
          rightLabel: 'Relaxed',
          value: profileRadar.structured_relaxed ?? sampleTasteRadar[1]?.value ?? 50,
        },
        {
          id: 'neutral_color',
          axis: 'Neutral',
          leftLabel: 'Neutral',
          rightLabel: 'Color-forward',
          value: neutral ?? sampleTasteRadar[2]?.value ?? 50,
        },
        {
          id: 'classic_experimental',
          axis: 'Classic',
          leftLabel: 'Classic',
          rightLabel: 'Experimental',
          value: profileRadar.classic_experimental ?? sampleTasteRadar[3]?.value ?? 50,
        },
        {
          id: 'casual_formal',
          axis: 'Casual',
          leftLabel: 'Casual',
          rightLabel: 'Formal',
          value: profileRadar.casual_formal ?? sampleTasteRadar[4]?.value ?? 50,
        },
      ])

      // Recent captures + correlated products
      const capRows: CaptureRow[] = await Promise.all(
        (caps ?? []).slice(0, 6).map(async (cap) => {
          const created = new Date(cap.created_at)
          const createdAtLabel = created.toLocaleString(undefined, {
            month: 'short',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
          })

          const capImage = cap.image_path ? mediaUrl(cap.image_path, token) : '/images/outfit-1.png'

          const garmentTypes = Array.from(
            new Set((cap.garments ?? []).map((g) => (g.garment_type || 'top').toLowerCase())),
          )
          const types = garmentTypes.length ? garmentTypes.slice(0, 3) : ['top']

          const results = await Promise.all(
            types.map((t) => api.productSearchByCapture(cap.id, t, token, 6, true, ctrl.signal).catch(() => [])),
          )
          const flattened = results.flat().slice(0, 8)
          const products: ProductTile[] = flattened.map((p, idx) => ({
            id: `${cap.id}_${p.product_id}_${idx}`,
            title: p.title,
            brand: p.brand,
            price: p.price,
            currency: p.currency,
            imageUrl: p.image_url || null,
            url: p.product_url,
            badge: p.source === 'catalog' ? 'Local' : p.source ? 'Web' : null,
          }))

          return {
            id: cap.id,
            createdAtLabel,
            status: cap.status,
            imageUrl: capImage,
            products,
          }
        }),
      )

      setRecent(capRows)
      setRecommended(
        (recs ?? []).map((r) => ({
          id: `${r.rank}_${r.product_url}`,
          title: r.title,
          brand: r.source || 'Catalog',
          price: r.price_value ?? null,
          currency: 'USD',
          imageUrl: r.recommendation_image_url || null,
          url: r.product_url,
          badge: r.price_text || r.source || 'Catalog',
        })),
      )
      setLoading(false)
    }

    load().catch(() => setLoading(false))
    return () => ctrl.abort()
  }, [router])

  const filteredRecommended = React.useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return recommended
    return recommended.filter((p) => `${p.title} ${p.brand ?? ''}`.toLowerCase().includes(q))
  }, [query, recommended])

  const lastChecked = React.useMemo(() => checked.slice(0, 7), [checked])
  const selectedCapture = React.useMemo(
    () => (selectedCaptureId ? recent.find((r) => r.id === selectedCaptureId) : undefined) ?? recent[0],
    [recent, selectedCaptureId],
  )
  const selectedIndex = React.useMemo(
    () => (selectedCapture ? Math.max(0, recent.findIndex((r) => r.id === selectedCapture.id)) : -1),
    [recent, selectedCapture],
  )
  const selectedProducts = selectedCapture?.products ?? []
  const outfitKind = detectOutfitKind(selectedProducts)
  const topProduct = bestProductForRegion('top', selectedProducts, outfitKind)
  const bottomProduct = bestProductForRegion('bottom', selectedProducts, outfitKind)
  const shoesProduct = bestProductForRegion('shoes', selectedProducts, outfitKind)
  const regionHints = React.useMemo(
    () => ({
      top: topProduct
        ? {
            title: topProduct.title,
            brand: topProduct.brand,
            priceLabel: money(topProduct.price, topProduct.currency),
            href: topProduct.url,
          }
        : undefined,
      bottom: bottomProduct
        ? {
            title: bottomProduct.title,
            brand: bottomProduct.brand,
            priceLabel: money(bottomProduct.price, bottomProduct.currency),
            href: bottomProduct.url,
          }
        : undefined,
      shoes: shoesProduct
        ? {
            title: shoesProduct.title,
            brand: shoesProduct.brand,
            priceLabel: money(shoesProduct.price, shoesProduct.currency),
            href: shoesProduct.url,
          }
        : undefined,
    }),
    [topProduct, bottomProduct, shoesProduct],
  )
  const orderedLabels =
    outfitKind === 'onepiece'
      ? (['One-piece', 'Hem / legs', 'Shoes'] as const)
      : (['Top', 'Bottom', 'Shoes'] as const)
  const cvSrcRaw =
    cvMode === 'captures' && selectedCapture?.imageUrl ? selectedCapture.imageUrl : '/images/outfit-6.png'
  const cvSrc = canvasSafeSrc(cvSrcRaw)

  return (
    <main className="min-h-screen bg-background">
      <ProfileTopbar query={query} setQuery={setQuery} />

      <div className="mx-auto w-full max-w-[1600px] px-4 py-10 md:px-8">
        <div
          ref={heroView.ref}
          className={cn(
            'flex flex-col gap-3',
            heroView.inView ? 'animate-reveal-up' : 'opacity-0 motion-reduce:opacity-100',
          )}
        >
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary" className="gap-1">
              <TrendingUp className="size-3" />
              Home feed
            </Badge>
            <Badge variant="secondary" className="gap-1">
              <Sparkles className="size-3" />
              Personalized
            </Badge>
            <Badge variant="secondary">Captures → matches</Badge>
          </div>
          <h1 className="text-4xl font-semibold tracking-tight md:text-6xl">Your Profile</h1>
          <p className="text-muted-foreground max-w-3xl text-sm leading-relaxed md:text-base">
            Browse recent captures and shop items recommended from your evolving taste radar—laid out like a marketplace home page.
          </p>
        </div>

        {/* Top row: Last captured (CV body boxes) */}
        <Card
          ref={lastCapturedView.ref as any}
          className={cn(
            'mt-8 overflow-hidden transition-[transform,box-shadow,opacity] duration-500 will-change-transform',
            lastCapturedView.inView ? 'animate-reveal-up animation-delay-150' : 'opacity-0 motion-reduce:opacity-100',
            loading && 'opacity-90',
          )}
        >
          <CardHeader className="pb-3">
            <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
              <div className="min-w-0">
                <CardTitle className="text-2xl md:text-3xl">Last captured</CardTitle>
                <div className="text-muted-foreground mt-1 text-xs">
                  {selectedCapture
                    ? `Showing ${selectedCapture.createdAtLabel} · ${selectedCapture.id}`
                    : 'No captures yet — using a sample image'}
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="secondary">{outfitKind === 'onepiece' ? 'Detected: one-piece' : 'Detected: separates'}</Badge>
                <div className="flex items-center gap-1 rounded-full border border-border bg-background p-1">
                  <Button
                    type="button"
                    size="sm"
                    variant={cvMode === 'captures' ? 'default' : 'ghost'}
                    className="h-8 rounded-full px-3"
                    onClick={() => setCvMode('captures')}
                    disabled={!selectedCapture?.imageUrl}
                    title={!selectedCapture?.imageUrl ? 'Add a capture to enable' : undefined}
                  >
                    Captures
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant={cvMode === 'sample' ? 'default' : 'ghost'}
                    className="h-8 rounded-full px-3"
                    onClick={() => setCvMode('sample')}
                  >
                    Sample
                  </Button>
                </div>

                {recent.length ? (
                  <div className="flex items-center gap-1.5">
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="h-8 rounded-full px-3"
                      onClick={() => setSelectedCaptureId(recent[Math.max(0, selectedIndex - 1)]!.id)}
                      disabled={selectedIndex <= 0}
                    >
                      Prev
                    </Button>
                    <div className="flex max-w-[52vw] items-center gap-1 overflow-x-auto rounded-full border border-border bg-background p-1">
                      {recent.slice(0, 8).map((cap) => {
                        const active = cap.id === selectedCapture?.id
                        return (
                          <Button
                            key={cap.id}
                            type="button"
                            size="sm"
                            variant={active ? 'default' : 'ghost'}
                            className={cn('h-8 rounded-full px-3', !active && 'text-muted-foreground')}
                            onClick={() => setSelectedCaptureId(cap.id)}
                            title={cap.id}
                          >
                            {cap.createdAtLabel}
                          </Button>
                        )
                      })}
                    </div>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="h-8 rounded-full px-3"
                      onClick={() =>
                        setSelectedCaptureId(recent[Math.min(recent.length - 1, selectedIndex + 1)]!.id)
                      }
                      disabled={selectedIndex < 0 || selectedIndex >= recent.length - 1}
                    >
                      Next
                    </Button>
                  </div>
                ) : null}
              </div>
            </div>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
              <div className="min-w-0">
                {lastCapturedView.inView ? (
                  <CvBodyBoxes
                    src={cvSrc}
                    regions={CV_REGIONS}
                    regionHints={regionHints}
                    orderedLabels={orderedLabels}
                  />
                ) : (
                  <div className="h-[520px] w-full rounded-2xl border border-border bg-muted" />
                )}
                <div className="text-muted-foreground mt-3 text-xs">
                  Hover a region (Top / Bottom / Shoes) to see the best correlated product link.
                </div>
              </div>

              <div className="flex min-w-0 flex-col gap-3">
                <div className="rounded-2xl border border-border/60 bg-muted/20 p-4">
                  <div className="text-sm font-medium">Best correlated matches</div>
                  <div className="text-muted-foreground mt-1 text-sm leading-relaxed">
                    These are the top picks per region (heuristic based on product titles). Hover the boxes for quick
                    links.
                  </div>
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  {[{ k: 'top' as const, label: 'Top', p: topProduct }, { k: 'bottom' as const, label: 'Bottom', p: bottomProduct }, { k: 'shoes' as const, label: 'Shoes', p: shoesProduct }].map(
                    (row) => (
                      <div
                        key={row.k}
                        className="rounded-2xl border border-border/60 p-4 transition-[transform,box-shadow,border-color,background-color] duration-300 hover:-translate-y-0.5 hover:shadow-lg hover:border-foreground/15 hover:bg-muted/20"
                      >
                        <div className="flex items-center justify-between gap-3">
                          <div className="text-sm font-medium">{row.label}</div>
                          <Badge variant="secondary">Best match</Badge>
                        </div>
                        <div className="mt-2 text-sm font-medium line-clamp-2">{row.p?.title ?? '—'}</div>
                        <div className="text-muted-foreground mt-1 text-xs">
                          {[row.p?.brand ?? null, money(row.p?.price, row.p?.currency) || null]
                            .filter(Boolean)
                            .join(' · ') || 'No correlated product available'}
                        </div>
                        {row.p?.url ? (
                          <a
                            href={row.p.url}
                            target="_blank"
                            rel="noreferrer"
                            className="mt-3 inline-flex items-center rounded-full border border-border bg-background px-3 py-1 text-xs font-medium transition-colors hover:bg-muted/50"
                          >
                            Open product
                          </a>
                        ) : null}
                      </div>
                    ),
                  )}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Separator className="my-8" />

        {/* Row 1: Recent captures + correlated products */}
        <Card
          ref={recentView.ref as any}
          className={cn(
            'mt-8 overflow-hidden transition-[transform,box-shadow,opacity] duration-500 will-change-transform',
            recentView.inView ? 'animate-spotlight' : 'opacity-0 motion-reduce:opacity-100',
            loading && 'opacity-80',
          )}
        >
          <CardHeader className="pb-3">
            <CardTitle className="text-2xl md:text-3xl">Recent captures</CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            {recent.length ? (
              <div className="grid gap-4">
                {recent.map((cap) => (
                  <div
                    key={cap.id}
                    className={cn(
                      'rounded-2xl border border-border/60 p-4',
                      'transition-[transform,box-shadow,border-color,background-color] duration-300 will-change-transform',
                      'hover:-translate-y-0.5 hover:shadow-lg hover:border-foreground/15 hover:bg-muted/20',
                    )}
                  >
                    <div className="flex flex-col gap-4 xl:flex-row">
                      <div className="flex min-w-0 items-center gap-4 xl:w-[420px]">
                        <div className="relative h-24 w-24 overflow-hidden rounded-2xl bg-muted">
                          <img
                            src={cap.imageUrl}
                            alt={cap.id}
                            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.02]"
                          />
                        </div>
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge variant="outline">{cap.status}</Badge>
                            <div className="text-sm font-medium">
                              {cap.createdAtLabel}
                            </div>
                          </div>
                          <div className="text-muted-foreground mt-1 text-xs font-mono">
                            {cap.id}
                          </div>
                        </div>
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="text-muted-foreground mb-3 text-xs">
                          Correlated products (best matches)
                        </div>
                        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                          {cap.products.slice(0, 4).map((p) => (
                            <ProductCard key={p.id} p={p} source="capture" onChecked={onChecked} />
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-muted-foreground text-sm">
                No captures yet. Upload one and come back—this section will populate automatically.
              </div>
            )}
          </CardContent>
        </Card>

        <Separator className="my-8" />

        {/* Row 2: Recommended shopping items */}
        <Card
          ref={recsView.ref as any}
          className={cn(
            'overflow-hidden transition-[transform,box-shadow,opacity] duration-500 will-change-transform',
            recsView.inView ? 'animate-reveal-up animation-delay-200' : 'opacity-0 motion-reduce:opacity-100',
            loading && 'opacity-80',
          )}
        >
          <CardHeader className="pb-3">
            <CardTitle className="text-2xl md:text-3xl">Recommended for you</CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="mb-4 flex flex-wrap items-center gap-2">
              <Badge variant="secondary">Trending + taste</Badge>
              <Badge variant="secondary">Fast picks</Badge>
              <Badge variant="secondary">Marketplace-style grid</Badge>
            </div>
            <div className="grid gap-3 grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 2xl:grid-cols-6">
              {filteredRecommended.slice(0, 18).map((p) => (
                <ProductCard key={p.id} p={p} source="recommended" onChecked={onChecked} />
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Bring back original dashboard sections below */}
        <div
          ref={belowView.ref}
          className={cn(
            belowView.inView ? 'animate-reveal-up animation-delay-200' : 'opacity-0 motion-reduce:opacity-100',
          )}
        >
          <Separator className="my-10" />
        </div>

        {/* KPI tiles */}
        <div ref={kpisView.ref} className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          {kpis.map((kpi, idx) => (
            <Card
              key={kpi.label}
              className={cn(
                'group overflow-hidden transition-[transform,box-shadow,opacity] duration-300 will-change-transform',
                'hover:-translate-y-0.5 hover:shadow-lg hover:border-foreground/15',
                kpisView.inView ? 'animate-scale-in' : 'opacity-0 motion-reduce:opacity-100',
                idx === 0 ? 'animation-delay-100' : '',
                idx === 1 ? 'animation-delay-200' : '',
                idx === 2 ? 'animation-delay-300' : '',
                idx === 3 ? 'animation-delay-400' : '',
                idx === 4 ? 'animation-delay-500' : '',
              )}
            >
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  {kpi.label}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-semibold tracking-tight md:text-4xl">
                  {kpi.value}
                </div>
                <div className="text-muted-foreground mt-1 text-xs">{kpi.meta}</div>
              </CardContent>
            </Card>
          ))}
        </div>

        <div className="mt-8 grid gap-6 xl:grid-cols-[1.25fr_0.75fr]">
          {/* Last checked items/styles */}
          <Card
            ref={lastCheckedView.ref as any}
            className={cn(
              'min-w-0 overflow-hidden transition-opacity duration-500',
              lastCheckedView.inView ? 'animate-reveal-left' : 'opacity-0 motion-reduce:opacity-100',
            )}
          >
            <CardHeader>
              <CardTitle className="text-2xl md:text-3xl">Last checked</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              {lastChecked.map((row) => (
                <div
                  key={`${row.id}_${row.checkedAtISO}`}
                  className="flex items-start justify-between gap-4 rounded-2xl border border-border/60 px-4 py-3"
                >
                  <div className="flex min-w-0 items-start gap-3">
                    <div className="relative h-14 w-14 shrink-0 overflow-hidden rounded-xl bg-muted">
                      <img
                        src={row.imageUrl || '/images/outfit-1.png'}
                        alt={row.title}
                        className="h-full w-full object-cover"
                        loading="lazy"
                      />
                    </div>
                    <div className="min-w-0">
                      <div className="truncate text-base font-medium">{row.title}</div>
                      <div className="text-muted-foreground mt-1 text-xs">
                        {row.brand || '—'} · {money(row.price, row.currency)}
                      </div>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {row.tags.map((t) => (
                          <Badge key={`${row.id}_${t}`} variant="secondary">
                            {t}
                          </Badge>
                        ))}
                      </div>
                      <div className="text-muted-foreground mt-2 text-xs">
                        {row.description}
                      </div>
                    </div>
                  </div>
                  <div className="shrink-0">
                    <Button size="sm" variant="outline" className="h-8" asChild>
                      <a href={row.url || '#'}>View</a>
                    </Button>
                  </div>
                </div>
              ))}
              {!lastChecked.length ? (
                <div className="text-muted-foreground text-sm">
                  Click products above to build your “last checked” list.
                </div>
              ) : null}
            </CardContent>
          </Card>

          {/* Taste Radar (restored) */}
          <Card
            ref={radarView.ref as any}
            className={cn(
              'min-w-0 overflow-hidden transition-opacity duration-500',
              radarView.inView ? 'animate-reveal-right' : 'opacity-0 motion-reduce:opacity-100',
            )}
          >
            <CardHeader>
              <CardTitle className="text-2xl md:text-3xl">Taste Radar</CardTitle>
            </CardHeader>
            <CardContent className="min-w-0">
              <TasteRadar data={tasteRadar} className="aspect-auto h-[520px] w-full" />
              <Separator className="my-4" />
              <div className="flex flex-wrap gap-2">
                {forYou.map((x) => (
                  <Badge key={x.label} variant="outline" className="px-3 py-1 text-sm">
                    {x.label} · {x.meta}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="mt-6 grid gap-4 xl:grid-cols-3">
          {/* Recent purchases (restored mocked section) */}
          <Card
            ref={purchasesView.ref as any}
            className={cn(
              'overflow-hidden transition-opacity duration-500',
              purchasesView.inView ? 'animate-reveal-up animation-delay-200' : 'opacity-0 motion-reduce:opacity-100',
            )}
          >
            <CardHeader>
              <CardTitle className="text-2xl md:text-3xl">Recent purchases</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              {recentPurchases.map((p) => (
                <div
                  key={`${p.item}_${p.when}`}
                  className="flex items-center justify-between gap-3 rounded-lg border border-border/60 px-4 py-3"
                >
                  <div className="min-w-0">
                    <div className="truncate text-base font-medium">{p.item}</div>
                    <div className="text-muted-foreground mt-1 text-xs">
                      {p.retailer} · {p.when} ago · {p.capture}
                    </div>
                  </div>
                  <div className="text-muted-foreground text-sm">{p.price}</div>
                </div>
              ))}
              <Separator className="my-2" />
              <div className="text-muted-foreground text-xs">
                Purchases are mocked for now; integrations can power this later.
              </div>
            </CardContent>
          </Card>

          {/* Saved items (restored) */}
          <Card
            ref={savedView.ref as any}
            className={cn(
              'overflow-hidden xl:col-span-2 transition-opacity duration-500',
              savedView.inView ? 'animate-reveal-up animation-delay-300' : 'opacity-0 motion-reduce:opacity-100',
            )}
          >
            <CardHeader>
              <CardTitle className="text-2xl md:text-3xl">Saved items</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {checked.slice(0, 6).map((row) => (
                  <div
                    key={`${row.id}_${row.checkedAtISO}_saved`}
                    className="flex items-center justify-between gap-3 rounded-lg border border-border/60 px-4 py-3 transition-colors hover:bg-muted/50"
                  >
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium">{row.title}</div>
                      <div className="text-muted-foreground mt-1 text-xs">
                        {row.brand || '—'}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="text-sm font-semibold">
                        {money(row.price, row.currency)}
                      </div>
                      <Button size="sm" variant="outline" className="h-8" asChild>
                        <a href={row.url || '#'}>Buy</a>
                      </Button>
                    </div>
                  </div>
                ))}
              {!checked.length ? (
                <div className="text-muted-foreground text-sm">
                  Save items by generating matches from a capture.
                </div>
              ) : null}
            </CardContent>
          </Card>
        </div>
      </div>
    </main>
  )
}

