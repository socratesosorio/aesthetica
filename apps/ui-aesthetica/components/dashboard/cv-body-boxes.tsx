'use client'

import * as React from 'react'

type RegionId = 'top' | 'bottom' | 'shoes'

export type RegionLabel = {
  id: RegionId
  label: string
}

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
  img.src = src
  await img.decode()
  return img
}

function drawContain(
  ctx: CanvasRenderingContext2D,
  img: HTMLImageElement,
  w: number,
  h: number,
) {
  const s = Math.min(w / img.naturalWidth, h / img.naturalHeight)
  const dw = img.naturalWidth * s
  const dh = img.naturalHeight * s
  const dx = (w - dw) / 2
  const dy = (h - dh) / 2
  ctx.drawImage(img, dx, dy, dw, dh)
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
  className,
}: {
  src: string
  regions: RegionLabel[]
  className?: string
}) {
  const canvasRef = React.useRef<HTMLCanvasElement | null>(null)
  const [state, setState] = React.useState<
    | { status: 'idle' | 'loading' | 'processing' }
    | { status: 'ready'; boxes: Box[] }
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

        // Ensure a backend is set (webgl when available).
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const tfAny = tf as any
        if (tfAny?.getBackend?.() !== 'webgl') {
          try {
            await tfAny.setBackend?.('webgl')
            await tfAny.ready?.()
          } catch {
            // fall back silently
          }
        }

        const net = await bodyPix.load({
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
        setState({ status: 'ready', boxes: rawBoxes })

        // Draw.
        const canvas = canvasRef.current
        if (!canvas) return
        const ctx = canvas.getContext('2d')
        if (!ctx) return

        const w = canvas.width
        const h = canvas.height
        ctx.clearRect(0, 0, w, h)
        const { dx, dy, dw, dh } = drawContain(ctx, img, w, h)

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

