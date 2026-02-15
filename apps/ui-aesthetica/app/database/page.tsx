'use client'

import * as React from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { Database, ExternalLink, RefreshCcw } from 'lucide-react'

import {
  api,
  ensureDevToken,
  getStoredToken,
  mediaUrl,
  type ApiCaptureOut,
  type ApiRadarHistoryPoint,
  type ApiUserOut,
  type ApiUserProfileOut,
} from '@/lib/api'
import { cn } from '@/lib/utils'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

function fmtDate(iso: string | null | undefined) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

function safeStringify(value: unknown) {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function DatabaseTopbar({ onRefresh }: { onRefresh: () => void }) {
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
          <span className="text-muted-foreground text-xs">Database</span>
        </Link>

        <div className="ml-auto flex items-center gap-2">
          <Button asChild size="sm" variant="outline" className="h-9">
            <Link href="/profile">Profile</Link>
          </Button>
          <Button size="sm" variant="outline" className="h-9" onClick={onRefresh}>
            <RefreshCcw className="mr-2 size-4" />
            Refresh
          </Button>
          <Button asChild size="sm" variant="outline" className="h-9">
            <Link href="/logout">Log out</Link>
          </Button>
        </div>
      </div>
    </div>
  )
}

export default function DatabasePage() {
  return (
    <React.Suspense fallback={<main className="min-h-screen" />}>
      <DatabasePageInner />
    </React.Suspense>
  )
}

function DatabasePageInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const captureParam = searchParams.get('capture')

  const [token, setToken] = React.useState<string | null>(null)
  const [me, setMe] = React.useState<ApiUserOut | null>(null)
  const [profile, setProfile] = React.useState<ApiUserProfileOut | null>(null)
  const [history, setHistory] = React.useState<ApiRadarHistoryPoint[]>([])
  const [captures, setCaptures] = React.useState<ApiCaptureOut[]>([])

  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [reloadKey, setReloadKey] = React.useState(0)
  const [openCaptureId, setOpenCaptureId] = React.useState<string | null>(null)

  React.useEffect(() => {
    const ctrl = new AbortController()

    async function load() {
      setLoading(true)
      setError(null)

      try {
        const t =
          getStoredToken() ||
          (process.env.NEXT_PUBLIC_AUTO_DEV_LOGIN === 'true'
            ? await ensureDevToken(ctrl.signal)
            : null)

        if (!t) {
          const next = captureParam ? `/database?capture=${encodeURIComponent(captureParam)}` : '/database'
          router.replace(`/login?next=${encodeURIComponent(next)}`)
          return
        }

        setToken(t)
        const user = await api.me(t, ctrl.signal)
        setMe(user)

        const [p, h, c] = await Promise.all([
          api.userProfile(user.id, t, ctrl.signal),
          api.radarHistory(user.id, t, 90, ctrl.signal).catch(() => []),
          api.userCaptures(user.id, t, 50, ctrl.signal).catch(() => []),
        ])

        let capturesForView = c
        if (captureParam && !capturesForView.some((row) => row.id === captureParam)) {
          const exact = await api.capture(captureParam, t, ctrl.signal).catch(() => null)
          if (exact) capturesForView = [exact, ...capturesForView]
        }

        setProfile(p)
        setHistory(h)
        setCaptures(capturesForView)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load database view.')
      } finally {
        setLoading(false)
      }
    }

    load()
    return () => ctrl.abort()
  }, [router, reloadKey, captureParam])

  React.useEffect(() => {
    if (!captures.length) {
      setOpenCaptureId(null)
      return
    }
    setOpenCaptureId((cur) => {
      if (captureParam && captures.some((c) => c.id === captureParam)) return captureParam
      return cur && captures.some((c) => c.id === cur) ? cur : null
    })
  }, [captures, captureParam])

  const totals = React.useMemo(() => {
    let garments = 0
    let matches = 0
    for (const cap of captures) {
      garments += cap.garments?.length ?? 0
      matches += cap.matches?.length ?? 0
    }
    const lastCapture = captures[0]?.created_at
    const lastRadar = history.at(-1)?.created_at
    return { garments, matches, lastCapture, lastRadar }
  }, [captures, history])

  const latestRadar = history.at(-1)?.radar_vector ?? profile?.radar_vector ?? {}

  return (
    <main className="min-h-screen bg-background">
      <DatabaseTopbar onRefresh={() => setReloadKey((n) => n + 1)} />

      <div className="mx-auto w-full max-w-[1600px] px-4 py-10 md:px-8">
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary" className="gap-2">
              <Database className="size-3.5" />
              User-scoped DB view
            </Badge>
            <Badge variant="secondary">API-backed</Badge>
            <Badge variant="secondary">Supabase-ready</Badge>
          </div>
          <h1 className="text-4xl font-semibold tracking-tight md:text-6xl">Database</h1>
          <p className="text-muted-foreground max-w-3xl text-sm leading-relaxed md:text-base">
            Live readout of the records powering your Profile: captures, garments, matches, and your taste profile.
          </p>
        </div>

        <div className="mt-8">
          {loading ? (
            <Card className="overflow-hidden">
              <CardContent className="py-10 text-sm text-muted-foreground">
                Loading database view…
              </CardContent>
            </Card>
          ) : error ? (
            <Card className="overflow-hidden border-destructive/40">
              <CardContent className="py-10 text-sm">
                <div className="font-medium">Couldn’t load database view</div>
                <div className="mt-2 text-muted-foreground">{error}</div>
                <div className="mt-4 flex flex-wrap gap-2">
                  <Button variant="outline" onClick={() => setReloadKey((n) => n + 1)}>
                    Try again
                  </Button>
                  <Button asChild variant="outline">
                    <Link href="/profile">Back to Profile</Link>
                  </Button>
                </div>
              </CardContent>
            </Card>
          ) : (
            <>
              <Card className="overflow-hidden">
                <CardHeader className="pb-3">
                  <CardTitle className="text-2xl md:text-3xl">Session</CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                  <div className="grid gap-3 md:grid-cols-3">
                    <div className="rounded-2xl border border-border/60 p-4">
                      <div className="text-xs text-muted-foreground">User</div>
                      <div className="mt-1 text-sm font-medium">{me?.email ?? '—'}</div>
                      <div className="mt-1 font-mono text-[11px] text-muted-foreground break-all">
                        {me?.id ?? '—'}
                      </div>
                    </div>
                    <div className="rounded-2xl border border-border/60 p-4">
                      <div className="text-xs text-muted-foreground">API base</div>
                      <div className="mt-1 text-sm font-medium break-all">{api.baseUrl}</div>
                      <div className="mt-2 text-xs text-muted-foreground">Token in storage: {token ? 'yes' : 'no'}</div>
                    </div>
                    <div className="rounded-2xl border border-border/60 p-4">
                      <div className="text-xs text-muted-foreground">Last activity</div>
                      <div className="mt-1 text-sm">
                        <div className="flex items-center justify-between gap-3">
                          <span className="text-muted-foreground">Last capture</span>
                          <span className="font-medium">{fmtDate(totals.lastCapture)}</span>
                        </div>
                        <div className="mt-2 flex items-center justify-between gap-3">
                          <span className="text-muted-foreground">Last radar point</span>
                          <span className="font-medium">{fmtDate(totals.lastRadar)}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <div className="mt-6 grid gap-3 md:grid-cols-3">
                <Card className="overflow-hidden">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-muted-foreground">Captures</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-3xl font-semibold tracking-tight md:text-4xl">
                      {captures.length}
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">Most recent 50</div>
                  </CardContent>
                </Card>
                <Card className="overflow-hidden">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-muted-foreground">Garments</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-3xl font-semibold tracking-tight md:text-4xl">
                      {totals.garments}
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">Across loaded captures</div>
                  </CardContent>
                </Card>
                <Card className="overflow-hidden">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-muted-foreground">Matches</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-3xl font-semibold tracking-tight md:text-4xl">
                      {totals.matches}
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">Across loaded captures</div>
                  </CardContent>
                </Card>
              </div>

              <div className="mt-6 grid gap-6 xl:grid-cols-2">
                <Card className="min-w-0 overflow-hidden">
                  <CardHeader>
                    <CardTitle className="text-2xl md:text-3xl">User profile</CardTitle>
                  </CardHeader>
                  <CardContent className="pt-0">
                    <div className="grid gap-3 md:grid-cols-2">
                      <div className="rounded-2xl border border-border/60 p-4">
                        <div className="text-xs text-muted-foreground">Updated</div>
                        <div className="mt-1 text-sm font-medium">{fmtDate(profile?.updated_at)}</div>
                        <div className="mt-3 text-xs text-muted-foreground">Embedding meta</div>
                        <pre className="mt-1 max-h-[180px] overflow-auto rounded-xl bg-muted/30 p-3 text-[11px] leading-relaxed">
                          {safeStringify(profile?.user_embedding_meta ?? {})}
                        </pre>
                      </div>
                      <div className="rounded-2xl border border-border/60 p-4">
                        <div className="text-xs text-muted-foreground">Radar vector (latest)</div>
                        <pre className="mt-2 max-h-[260px] overflow-auto rounded-xl bg-muted/30 p-3 text-[11px] leading-relaxed">
                          {safeStringify(latestRadar)}
                        </pre>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Card className="min-w-0 overflow-hidden">
                  <CardHeader>
                    <CardTitle className="text-2xl md:text-3xl">Radar history (90d)</CardTitle>
                  </CardHeader>
                  <CardContent className="pt-0">
                    {history.length ? (
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>When</TableHead>
                            <TableHead>Point ID</TableHead>
                            <TableHead>Keys</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {history
                            .slice()
                            .reverse()
                            .slice(0, 10)
                            .map((h) => (
                              <TableRow key={h.id}>
                                <TableCell className="text-muted-foreground">{fmtDate(h.created_at)}</TableCell>
                                <TableCell className="font-mono text-[11px] text-muted-foreground">{h.id}</TableCell>
                                <TableCell className="text-muted-foreground">
                                  {Object.keys(h.radar_vector ?? {}).length}
                                </TableCell>
                              </TableRow>
                            ))}
                        </TableBody>
                      </Table>
                    ) : (
                      <div className="rounded-2xl border border-border/60 p-4 text-sm text-muted-foreground">
                        No radar history yet. Upload a capture to generate taste updates.
                      </div>
                    )}
                    <Separator className="my-4" />
                    <div className="text-xs text-muted-foreground">
                      Tip: the “history” table is backed by `user_radar_history`.
                    </div>
                  </CardContent>
                </Card>
              </div>

              <Card className="mt-6 overflow-hidden">
                <CardHeader>
                  <CardTitle className="text-2xl md:text-3xl">Captures</CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                  {captures.length ? (
                    <Accordion
                      type="single"
                      collapsible
                      value={openCaptureId ?? undefined}
                      onValueChange={(v) => setOpenCaptureId(v || null)}
                      className="w-full"
                    >
                      {captures.map((cap) => {
                        const garmentCount = cap.garments?.length ?? 0
                        const matchCount = cap.matches?.length ?? 0
                        const imgSrc =
                          token && cap.image_path ? mediaUrl(cap.image_path, token) : '/images/outfit-1.png'

                        return (
                          <AccordionItem key={cap.id} value={cap.id}>
                            <AccordionTrigger>
                              <div className="flex w-full flex-col gap-2 md:flex-row md:items-start md:justify-between">
                                <div className="min-w-0">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <Badge variant="outline">{cap.status}</Badge>
                                    <span className="text-sm font-medium">{fmtDate(cap.created_at)}</span>
                                  </div>
                                  <div className="mt-1 font-mono text-[11px] text-muted-foreground break-all">
                                    {cap.id}
                                  </div>
                                </div>
                                <div className="flex shrink-0 flex-wrap items-center gap-2 text-xs text-muted-foreground">
                                  <span>{garmentCount} garments</span>
                                  <span>·</span>
                                  <span>{matchCount} matches</span>
                                </div>
                              </div>
                            </AccordionTrigger>

                            <AccordionContent className="pt-2">
                              <div className="grid gap-4 2xl:grid-cols-[0.9fr_1.1fr]">
                                <div className="rounded-2xl border border-border/60 bg-muted/20 p-4">
                                  <div className="relative overflow-hidden rounded-2xl border border-border bg-muted">
                                    <img src={imgSrc} alt={cap.id} className="h-full w-full object-cover" />
                                  </div>
                                  {cap.error ? (
                                    <div className="mt-3 rounded-xl border border-destructive/40 bg-destructive/5 p-3 text-xs">
                                      <div className="font-medium">Capture error</div>
                                      <div className="mt-1 text-muted-foreground">{cap.error}</div>
                                    </div>
                                  ) : null}
                                </div>

                                <div className="min-w-0 space-y-4">
                                  <div className="rounded-2xl border border-border/60 p-4">
                                    <div className="text-sm font-medium">Garments</div>
                                    {cap.garments?.length ? (
                                      <div className="mt-3 space-y-3">
                                        {cap.garments.map((g) => {
                                          const crop =
                                            token && g.crop_path ? mediaUrl(g.crop_path, token) : undefined
                                          return (
                                            <div
                                              key={g.id}
                                              className="flex flex-col gap-3 rounded-2xl border border-border/60 p-3 md:flex-row"
                                            >
                                              <div className="relative aspect-[4/5] w-full overflow-hidden rounded-xl bg-muted md:w-[120px]">
                                                {crop ? (
                                                  <img src={crop} alt={g.garment_type} className="h-full w-full object-cover" />
                                                ) : (
                                                  <div className="h-full w-full" />
                                                )}
                                              </div>
                                              <div className="min-w-0 flex-1">
                                                <div className="flex flex-wrap items-center gap-2">
                                                  <Badge variant="secondary">{g.garment_type}</Badge>
                                                  <span className="font-mono text-[11px] text-muted-foreground break-all">
                                                    {g.id}
                                                  </span>
                                                </div>
                                                <pre className="mt-2 max-h-[220px] overflow-auto rounded-xl bg-muted/30 p-3 text-[11px] leading-relaxed">
                                                  {safeStringify(g.attributes ?? {})}
                                                </pre>
                                              </div>
                                            </div>
                                          )
                                        })}
                                      </div>
                                    ) : (
                                      <div className="mt-2 text-xs text-muted-foreground">No garments recorded.</div>
                                    )}
                                  </div>

                                  <div className="rounded-2xl border border-border/60 p-4">
                                    <div className="flex items-center justify-between gap-3">
                                      <div className="text-sm font-medium">Matches</div>
                                      <div className="text-xs text-muted-foreground">
                                        Backed by `matches` + `products`
                                      </div>
                                    </div>

                                    {cap.matches?.length ? (
                                      <div className="mt-3">
                                        <Table>
                                          <TableHeader>
                                            <TableRow>
                                              <TableHead>Group</TableHead>
                                              <TableHead>Product</TableHead>
                                              <TableHead>Rank</TableHead>
                                              <TableHead>Similarity</TableHead>
                                            </TableRow>
                                          </TableHeader>
                                          <TableBody>
                                            {cap.matches.slice(0, 30).map((m, idx) => {
                                              const mm = m as Record<string, unknown>
                                              const group = String(mm.match_group ?? '—')
                                              const productId = String(mm.product_id ?? '—')
                                              const rank = mm.rank != null ? String(mm.rank) : '—'
                                              const sim =
                                                typeof mm.similarity === 'number'
                                                  ? mm.similarity.toFixed(3)
                                                  : mm.similarity != null
                                                    ? String(mm.similarity)
                                                    : '—'
                                              const href =
                                                typeof mm.product_url === 'string' && mm.product_url
                                                  ? mm.product_url
                                                  : null

                                              return (
                                                <TableRow key={`${cap.id}_${group}_${productId}_${idx}`}>
                                                  <TableCell className="text-muted-foreground">{group}</TableCell>
                                                  <TableCell className="font-mono text-[11px] text-muted-foreground">
                                                    <div className="flex items-center gap-2">
                                                      <span className="truncate">{productId}</span>
                                                      {href ? (
                                                        <a
                                                          href={href}
                                                          target="_blank"
                                                          rel="noreferrer"
                                                          className={cn(
                                                            'ml-auto inline-flex items-center gap-1 rounded-full border border-border px-2 py-1 text-[11px] text-foreground',
                                                            'transition-colors hover:bg-muted',
                                                          )}
                                                        >
                                                          Open
                                                          <ExternalLink className="size-3" />
                                                        </a>
                                                      ) : null}
                                                    </div>
                                                  </TableCell>
                                                  <TableCell className="text-muted-foreground">{rank}</TableCell>
                                                  <TableCell className="text-muted-foreground">{sim}</TableCell>
                                                </TableRow>
                                              )
                                            })}
                                          </TableBody>
                                        </Table>
                                      </div>
                                    ) : (
                                      <div className="mt-2 text-xs text-muted-foreground">No matches recorded.</div>
                                    )}
                                  </div>
                                </div>
                              </div>
                            </AccordionContent>
                          </AccordionItem>
                        )
                      })}
                    </Accordion>
                  ) : (
                    <div className="rounded-2xl border border-border/60 p-6 text-sm text-muted-foreground">
                      No captures found yet. Upload a capture to `POST /v1/captures` and refresh this page.
                    </div>
                  )}
                </CardContent>
              </Card>
            </>
          )}
        </div>
      </div>
    </main>
  )
}
