'use client'

import * as React from 'react'

type RegionId = 'top' | 'bottom' | 'shoes'

export type RegionLabel = {
  id: RegionId
  label: string
}

export type RegionProductHint = {
  title: string
  brand?: string | null
  priceLabel?: string | null
  href?: string | null
}

export type RegionHints = Partial<Record<RegionId, RegionProductHint>>

type Box = {
  id: RegionId
  x: number
  y: number
  w: number
  h: number
}

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n))
}

async function loadImage(src: string) {
  const img = new Image()
  img.crossOrigin = 'anonymous'
  img.referrerPolicy = 'no-referrer'
  img.src = src
  // `decode()` isn't supported everywhere and can reject for non-fatal reasons.
  // Fall back to `onload` so we still run CV.
  if (typeof img.decode === 'function') {
    try {
      await img.decode()
      return img
    } catch {
      // fall through to onload/onerror
    }
  }
  await new Promise<void>((resolve, reject) => {
    const onLoad = () => {
      cleanup()
      resolve()
    }
    const onError = () => {
      cleanup()
      reject(new Error('Failed to load image.'))
    }
    const cleanup = () => {
      img.removeEventListener('load', onLoad)
      img.removeEventListener('error', onError)
    }
    img.addEventListener('load', onLoad)
    img.addEventListener('error', onError)
  })
  return img
}

function containRect(imgW: number, imgH: number, w: number, h: number) {
  const s = Math.min(w / imgW, h / imgH)
  const dw = imgW * s
  const dh = imgH * s
  const dx = (w - dw) / 2
  const dy = (h - dh) / 2
  return { dx, dy, dw, dh, scale: s }
}

function bboxFromMask(
  mask: Uint8Array,
  mw: number,
  mh: number,
  y0: number,
  y1: number,
) {
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity

  const yy0 = clamp(Math.floor(y0), 0, mh - 1)
  const yy1 = clamp(Math.ceil(y1), 0, mh)

  for (let y = yy0; y < yy1; y++) {
    for (let x = 0; x < mw; x++) {
      const v = mask[y * mw + x]
      if (v > 0) {
        if (x < minX) minX = x
        if (y < minY) minY = y
        if (x > maxX) maxX = x
        if (y > maxY) maxY = y
      }
    }
  }

  if (!Number.isFinite(minX)) {
    // No pixels in this band; return an empty box.
    return null
  }

  return { minX, minY, maxX, maxY }
}

function expandBox(
  box: { minX: number; minY: number; maxX: number; maxY: number },
  mw: number,
  mh: number,
  padX: number,
  padY: number,
) {
  return {
    minX: clamp(box.minX - padX, 0, mw - 1),
    minY: clamp(box.minY - padY, 0, mh - 1),
    maxX: clamp(box.maxX + padX, 0, mw - 1),
    maxY: clamp(box.maxY + padY, 0, mh - 1),
  }
}

export function CvBodyBoxes({
  src,
  regions,
  regionHints,
  orderedLabels,
  className,
}: {
  src: string
  regions: RegionLabel[]
  regionHints?: RegionHints
  orderedLabels?: readonly [string, string, string]
  className?: string
}) {
  const canvasRef = React.useRef<HTMLCanvasElement | null>(null)
  const [hovered, setHovered] = React.useState<RegionId | null>(null)
  const [state, setState] = React.useState<
    | { status: 'idle' | 'loading' | 'processing' }
    | { status: 'ready'; boxes: Box[]; draw: { dx: number; dy: number; dw: number; dh: number } }
    | { status: 'error'; message: string }
  >({ status: 'idle' })

  React.useEffect(() => {
    let cancelled = false

    async function run() {
      try {
        setState({ status: 'loading' })

        const [bodyPix, tf, img] = await Promise.all([
          import('@tensorflow-models/body-pix'),
          import('@tensorflow/tfjs'),
          loadImage(src),
        ])

        if (cancelled) return

        // Turbopack + some deps can surface CJS/ESM interop differences.
        // Normalize so both `mod.load` and `mod.default.load` work.
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const bodyPixAny = (bodyPix as any)?.default ?? bodyPix
        // Ensure a backend is set (webgl when available).
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const tfAny = (tf as any)?.default ?? (tf as any)
        if (tfAny?.getBackend?.() !== 'webgl') {
          try {
            await tfAny.setBackend?.('webgl')
            await tfAny.ready?.()
          } catch {
            // fall back silently
          }
        }

        const net = await bodyPixAny.load({
          architecture: 'MobileNetV1',
          outputStride: 16,
          multiplier: 0.75,
          quantBytes: 2,
        })

        if (cancelled) return
        setState({ status: 'processing' })

        // Run at lower internal resolution for speed.
        const inputSize = 257
        const off = document.createElement('canvas')
        off.width = inputSize
        off.height = inputSize
        const offCtx = off.getContext('2d')
        if (!offCtx) throw new Error('Canvas not supported.')
        offCtx.clearRect(0, 0, inputSize, inputSize)
        offCtx.drawImage(img, 0, 0, inputSize, inputSize)

        const segmentation = await net.segmentPerson(off, {
          internalResolution: 'low',
          segmentationThreshold: 0.7,
          maxDetections: 1,
          scoreThreshold: 0.2,
        })

        if (cancelled) return

        const mw = segmentation.width
        const mh = segmentation.height
        const mask = segmentation.data as Uint8Array

        // Person bbox.
        const allRaw = bboxFromMask(mask, mw, mh, 0, mh) ?? {
          minX: mw * 0.25,
          maxX: mw * 0.75,
          minY: mh * 0.1,
          maxY: mh * 0.95,
        }

        // Expand the person bbox slightly so region boxes feel less tight.
        const personPadX = mw * 0.03
        const personPadY = mh * 0.02
        const all = expandBox(allRaw, mw, mh, personPadX, personPadY)

        const personH = all.maxY - all.minY
        // Non-overlapping vertical bands. Each region box will fill its band,
        // making regions much taller while guaranteeing no overlap.
        // If the shoes band would be too small, expand it by shrinking the bottom band.
        const topFrac = 0.62
        const minShoesFrac = 0.12
        let bottomEndFrac = 0.92
        if (1 - bottomEndFrac < minShoesFrac) bottomEndFrac = 1 - minShoesFrac

        const topY1 = all.minY + personH * topFrac
        const bottomY0 = topY1
        const bottomY1 = all.minY + personH * bottomEndFrac
        const shoesY0 = bottomY1

        const topBand = { y0: all.minY, y1: topY1 }
        const bottomBand = { y0: bottomY0, y1: bottomY1 }
        const shoesBand = { y0: shoesY0, y1: all.maxY }

        const byId: Record<RegionId, { y0: number; y1: number }> = {
          top: topBand,
          bottom: bottomBand,
          shoes: shoesBand,
        }

        const rawBoxes: Box[] = regions
          .map((r) => {
            const band = byId[r.id]
            // For X extents, use the mask within the band's Y-range.
            // For Y extents, fill the entire band to make regions long and non-overlapping.
            const bb = bboxFromMask(mask, mw, mh, band.y0, band.y1) ?? all

            // Pad primarily in X so boxes feel garment-wide without causing overlaps.
            const padX = mw * 0.06
            const use = expandBox(bb, mw, mh, padX, 0)
            use.minY = clamp(Math.floor(band.y0), 0, mh - 1)
            use.maxY = clamp(Math.ceil(band.y1), 0, mh - 1)

            return {
              id: r.id,
              x: use.minX / mw,
              y: use.minY / mh,
              w: (use.maxX - use.minX) / mw,
              h: (use.maxY - use.minY) / mh,
            }
          })
          .map((b) => ({
            ...b,
            // Small safety expansion in normalized space.
            x: clamp(b.x - 0.005, 0, 0.95),
            y: clamp(b.y - 0.005, 0, 0.95),
            w: clamp(b.w + 0.01, 0.12, 0.98),
            h: clamp(b.h + 0.01, 0.12, 0.98),
          }))

        if (cancelled) return
        // Canvas dims are fixed; we compute the exact draw rect so overlays align.
        const canvasW = 840
        const canvasH = 980
        const draw = containRect(img.naturalWidth, img.naturalHeight, canvasW, canvasH)
        setState({ status: 'ready', boxes: rawBoxes, draw })

        // Draw.
        const canvas = canvasRef.current
        if (!canvas) return
        const ctx = canvas.getContext('2d')
        if (!ctx) return

        const w = canvas.width
        const h = canvas.height
        ctx.clearRect(0, 0, w, h)
        const { dx, dy, dw, dh } = containRect(img.naturalWidth, img.naturalHeight, w, h)
        ctx.drawImage(img, dx, dy, dw, dh)

        // Overlay.
        ctx.save()
        ctx.translate(dx, dy)

        const neon = '#39ff14'
        ctx.lineWidth = 5
        ctx.strokeStyle = neon
        ctx.fillStyle = neon
        ctx.shadowColor = neon
        ctx.shadowBlur = 10

        for (const b of rawBoxes) {
          const x = b.x * dw
          const y = b.y * dh
          const bw = b.w * dw
          const bh = b.h * dh
          ctx.strokeRect(x, y, bw, bh)
        }

        ctx.restore()
      } catch (e) {
        if (cancelled) return
        setState({
          status: 'error',
          message: e instanceof Error ? e.message : 'Failed to run CV.',
        })
      }
    }

    run()
    return () => {
      cancelled = true
    }
  }, [src, regions])

  return (
    <div className={className}>
      <div className="relative overflow-hidden rounded-2xl border border-border bg-muted">
        <canvas
          ref={canvasRef}
          width={840}
          height={980}
          className="h-full w-full"
        />
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/10 via-transparent to-transparent" />

        {state.status === 'ready' ? (
          <div className="absolute inset-0">
            {(() => {
              // Force labels by vertical order (top-most -> Top, etc).
              const ordered = [...state.boxes].sort((a, b) => a.y - b.y)
              const keys: RegionId[] = ['top', 'bottom', 'shoes']
              const labels = orderedLabels ?? (['Top', 'Bottom', 'Shoes'] as const)
              const canvasW = 840
              const canvasH = 980

              return ordered.map((b, idx) => {
                const k = keys[idx] ?? b.id
                const label = labels[idx] ?? regions.find((r) => r.id === k)?.label ?? k
                const hint = regionHints?.[k]

                const leftPct = ((state.draw.dx + b.x * state.draw.dw) / canvasW) * 100
                const topPct = ((state.draw.dy + b.y * state.draw.dh) / canvasH) * 100
                const wPct = ((b.w * state.draw.dw) / canvasW) * 100
                const hPct = ((b.h * state.draw.dh) / canvasH) * 100

                return (
                  <div
                    key={`${k}_${idx}`}
                    className="absolute"
                    style={{ left: `${leftPct}%`, top: `${topPct}%`, width: `${wPct}%`, height: `${hPct}%` }}
                  >
                    <div
                      className={[
                        'group relative h-full w-full rounded-md',
                        'transition-[transform,box-shadow,background-color] duration-200',
                        'hover:bg-black/5 hover:shadow-[0_0_0_2px_rgba(57,255,20,0.9),0_0_24px_rgba(57,255,20,0.25)]',
                      ].join(' ')}
                      onMouseEnter={() => setHovered(k)}
                      onMouseLeave={() => setHovered((cur) => (cur === k ? null : cur))}
                      onClick={() => {
                        if (hint?.href) window.open(hint.href, '_blank', 'noopener,noreferrer')
                      }}
                      role={hint?.href ? 'link' : undefined}
                      tabIndex={hint?.href ? 0 : -1}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && hint?.href) window.open(hint.href, '_blank', 'noopener,noreferrer')
                      }}
                    >
                      <div className="pointer-events-none absolute left-2 top-2 rounded-full bg-black/55 px-2 py-1 text-[11px] font-medium text-white backdrop-blur">
                        {label}
                      </div>

                      {hint && hovered === k ? (
                        <div className="absolute -right-2 top-2 z-10 w-[240px] translate-x-full">
                          <div className="rounded-2xl border border-border bg-background/95 p-3 shadow-xl backdrop-blur">
                            <div className="text-xs font-semibold">{hint.title}</div>
                            <div className="mt-0.5 text-xs text-muted-foreground">
                              {[hint.brand, hint.priceLabel].filter(Boolean).join(' · ') || 'Best match'}
                            </div>
                            {hint.href ? (
                              <a
                                href={hint.href}
                                target="_blank"
                                rel="noreferrer"
                                className="mt-2 inline-flex items-center rounded-full border border-border bg-muted px-3 py-1 text-xs font-medium transition-colors hover:bg-muted/70"
                              >
                                Open product
                              </a>
                            ) : (
                              <div className="mt-2 text-xs text-muted-foreground">No product link available</div>
                            )}
                          </div>
                        </div>
                      ) : null}
                    </div>
                  </div>
                )
              })
            })()}
          </div>
        ) : null}

        {state.status !== 'ready' ? (
          <div className="absolute inset-0 grid place-items-center bg-background/40 backdrop-blur-[2px]">
            <div className="rounded-full border border-border bg-background px-4 py-2 text-xs text-muted-foreground">
              {state.status === 'error'
                ? `CV error: ${state.message}`
                : state.status === 'processing'
                  ? 'Detecting body + regions…'
                  : 'Loading CV model…'}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  )
}

