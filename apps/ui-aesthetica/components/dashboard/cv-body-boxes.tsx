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

type Pt = { x: number; y: number; score: number }

function avg(a: number, b: number) {
  return (a + b) / 2
}

function inBounds(p: Pt, w: number, h: number) {
  // keypoints slightly outside frame are usually unstable
  return p.x >= 0 && p.x <= w && p.y >= 0 && p.y <= h
}

function getKeypoint(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  keypoints: any[],
  names: string[],
): Pt | null {
  const byName = new Map<string, unknown>()
  for (const kp of keypoints || []) {
    const name = (kp as any)?.name
    if (typeof name === 'string') byName.set(name, kp)
  }
  for (const name of names) {
    const kp = byName.get(name) as any
    const x = kp?.x
    const y = kp?.y
    const score = kp?.score
    if (typeof x === 'number' && typeof y === 'number' && typeof score === 'number') return { x, y, score }
  }
  return null
}

function deriveBoxesFromPose(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  pose: any,
  imgW: number,
  imgH: number,
  scoreMin = 0.22,
): Box[] {
  const kps = pose?.keypoints ?? []

  // MoveNet names (tfjs runtime) are typically snake_case; keep aliases to be safe.
  const ls = getKeypoint(kps, ['left_shoulder', 'leftShoulder'])
  const rs = getKeypoint(kps, ['right_shoulder', 'rightShoulder'])
  const lh = getKeypoint(kps, ['left_hip', 'leftHip'])
  const rh = getKeypoint(kps, ['right_hip', 'rightHip'])
  const lk = getKeypoint(kps, ['left_knee', 'leftKnee'])
  const rk = getKeypoint(kps, ['right_knee', 'rightKnee'])
  const la = getKeypoint(kps, ['left_ankle', 'leftAnkle'])
  const ra = getKeypoint(kps, ['right_ankle', 'rightAnkle'])

  const good = (p: Pt | null) => (p && p.score >= scoreMin ? p : null)
  const gls = good(ls)
  const grs = good(rs)
  const glh = good(lh)
  const grh = good(rh)
  const glk = good(lk)
  const grk = good(rk)
  const gla = good(la)
  const gra = good(ra)

  // STRICT: if we can't confidently see feet, the image is likely cropped.
  // In that case, don't label *any* regions (avoid misleading top/bottom-only boxes).
  if (!gla || !gra) return []
  if (!inBounds(gla, imgW, imgH) || !inBounds(gra, imgW, imgH)) return []

  // Require at least one shoulder + one hip (relaxed) to anchor torso.
  if (!gls && !grs) return []
  if (!glh && !grh) return []

  const shoulderY = gls && grs ? avg(gls.y, grs.y) : (gls?.y ?? grs!.y)
  const hipY = glh && grh ? avg(glh.y, grh.y) : (glh?.y ?? grh!.y)

  const torsoXs = [gls?.x, grs?.x, glh?.x, grh?.x].filter((x): x is number => typeof x === 'number')
  if (torsoXs.length < 2) return []
  const torsoXMin = Math.min(...torsoXs)
  const torsoXMax = Math.max(...torsoXs)

  const hipXs = [glh?.x, grh?.x].filter((x): x is number => typeof x === 'number')
  const hipXMin = hipXs.length ? Math.min(...hipXs) : torsoXMin
  const hipXMax = hipXs.length ? Math.max(...hipXs) : torsoXMax

  // Torso width estimate for padding.
  const torsoW = Math.max(1, Math.max(torsoXMax - torsoXMin, hipXMax - hipXMin))
  const padX = torsoW * 0.35
  const padY = imgH * 0.02

  // TOP region: shoulders -> hips
  const topY0 = clamp(shoulderY - padY, 0, imgH - 1)
  const topY1 = clamp(hipY + padY, 0, imgH - 1)
  const topX0 = clamp(torsoXMin - padX, 0, imgW - 1)
  const topX1 = clamp(torsoXMax + padX, 0, imgW - 1)

  // BOTTOM region: hips -> knees (if knees confident), else extend to mid-thigh estimate.
  let bottomY1 = hipY + (hipY - shoulderY) * 0.9
  let bottomX0 = hipXMin - padX * 0.5
  let bottomX1 = hipXMax + padX * 0.5
  if (glk || grk) {
    const kneeY = glk && grk ? avg(glk.y, grk.y) : (glk?.y ?? grk!.y)
    bottomY1 = kneeY + padY
    const kneeXs = [glk?.x, grk?.x].filter((x): x is number => typeof x === 'number')
    const kneeXMin = kneeXs.length ? Math.min(...kneeXs) : hipXMin
    const kneeXMax = kneeXs.length ? Math.max(...kneeXs) : hipXMax
    bottomX0 = Math.min(bottomX0, kneeXMin - padX * 0.35)
    bottomX1 = Math.max(bottomX1, kneeXMax + padX * 0.35)
  }
  const bottomY0 = clamp(hipY - padY, 0, imgH - 1)
  bottomY1 = clamp(bottomY1, 0, imgH - 1)
  bottomX0 = clamp(bottomX0, 0, imgW - 1)
  bottomX1 = clamp(bottomX1, 0, imgW - 1)

  // SHOES region: ankles -> image bottom (if ankles confident). If not, skip shoes.
  let shoes: Box | null = null
  if (gla && gra) {
    const ankleY = avg(gla.y, gra.y)
    const ankleXMin = Math.min(gla.x, gra.x)
    const ankleXMax = Math.max(gla.x, gra.x)
    const shoesPadX = torsoW * 0.45
    const shoesY0 = clamp(ankleY - imgH * 0.04, 0, imgH - 1)
    const shoesY1 = clamp(imgH - 1, 0, imgH - 1)
    const shoesX0 = clamp(ankleXMin - shoesPadX, 0, imgW - 1)
    const shoesX1 = clamp(ankleXMax + shoesPadX, 0, imgW - 1)
    shoes = {
      id: 'shoes',
      x: shoesX0 / imgW,
      y: shoesY0 / imgH,
      w: Math.max(0.12, (shoesX1 - shoesX0) / imgW),
      h: Math.max(0.12, (shoesY1 - shoesY0) / imgH),
    }
  }

  const top: Box = {
    id: 'top',
    x: topX0 / imgW,
    y: topY0 / imgH,
    w: Math.max(0.12, (topX1 - topX0) / imgW),
    h: Math.max(0.12, (topY1 - topY0) / imgH),
  }
  const bottom: Box = {
    id: 'bottom',
    x: bottomX0 / imgW,
    y: bottomY0 / imgH,
    w: Math.max(0.12, (bottomX1 - bottomX0) / imgW),
    h: Math.max(0.12, (bottomY1 - bottomY0) / imgH),
  }

  // Keep consistent ordering.
  const out = [top, bottom, shoes].filter(Boolean) as Box[]
  if (out.length < 3) return []
  return out.map((b) => ({
    ...b,
    x: clamp(b.x, 0, 0.95),
    y: clamp(b.y, 0, 0.95),
    w: clamp(b.w, 0.12, 0.98),
    h: clamp(b.h, 0.12, 0.98),
  }))
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

function countMaskPixels(mask: Uint8Array, mw: number, mh: number, y0: number, y1: number) {
  const yy0 = clamp(Math.floor(y0), 0, mh - 1)
  const yy1 = clamp(Math.ceil(y1), 0, mh)
  let count = 0
  for (let y = yy0; y < yy1; y++) {
    const row = y * mw
    for (let x = 0; x < mw; x++) if (mask[row + x] > 0) count++
  }
  return { count, yy0, yy1 }
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
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let detector: any | null = null

    async function run() {
      try {
        setState({ status: 'loading' })

        const [poseDetection, bodyPix, tf, img] = await Promise.all([
          // IMPORTANT: import the CJS entrypoint directly to avoid Turbopack choking
          // on the package's ESM bundle (which pulls in MediaPipe exports).
          import('@tensorflow-models/pose-detection/dist/index.js'),
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

        // 1) Try pose landmarks (MoveNet) first for accuracy.
        try {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const poseAny =
            (poseDetection as any)?.createDetector
              ? (poseDetection as any)
              : (poseDetection as any)?.default?.createDetector
                ? (poseDetection as any).default
                : (poseDetection as any)?.default ?? poseDetection
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const movenetAny = (poseAny as any)?.movenet

          detector = await poseAny.createDetector(poseAny.SupportedModels.MoveNet, {
            modelType: movenetAny?.modelType?.SINGLEPOSE_THUNDER ?? movenetAny?.modelType?.SINGLEPOSE_LIGHTNING,
          })

          if (cancelled) return
          setState({ status: 'processing' })

          // Estimate pose on the full-res image for better landmarks.
          const poses = await detector.estimatePoses(img, { maxPoses: 1, flipHorizontal: false })
          const pose = poses?.[0]

          const poseBoxes = pose ? deriveBoxesFromPose(pose, img.naturalWidth, img.naturalHeight) : []
          // If pose is not confident (or missing), fall back to BodyPix.
          if (!poseBoxes || poseBoxes.length < 2) throw new Error('Pose not confident')

          if (cancelled) return

          const canvasW = 840
          const canvasH = 980
          const draw = containRect(img.naturalWidth, img.naturalHeight, canvasW, canvasH)
          setState({ status: 'ready', boxes: poseBoxes, draw })

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

          for (const b of poseBoxes) {
            const x = b.x * dw
            const y = b.y * dh
            const bw = b.w * dw
            const bh = b.h * dh
            ctx.strokeRect(x, y, bw, bh)
          }

          ctx.restore()
          return
        } catch {
          // Fall back to BodyPix (older heuristic) if pose model fails to load/run.
        }

        // 2) Fallback: BodyPix segmentation + heuristics.
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

        // Confidence gate: if segmentation looks bad, don't draw boxes.
        // This avoids "confidently wrong" boxes when the model fails.
        const full = countMaskPixels(mask, mw, mh, 0, mh)
        const fullRatio = full.count / Math.max(1, mw * mh)

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

        const personArea = (all.maxX - all.minX) * (all.maxY - all.minY)
        const personAreaRatio = personArea / Math.max(1, mw * mh)
        const segmentationConfident =
          Number.isFinite(fullRatio) &&
          Number.isFinite(personAreaRatio) &&
          fullRatio >= 0.03 &&
          fullRatio <= 0.85 &&
          personAreaRatio >= 0.05 &&
          personAreaRatio <= 0.95

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

        const boxesCandidate: Array<Box | null> = regions.map((r) => {
            const band = byId[r.id]
            const bandCount = countMaskPixels(mask, mw, mh, band.y0, band.y1)
            const bandArea = Math.max(1, (bandCount.yy1 - bandCount.yy0) * mw)
            const bandRatio = bandCount.count / bandArea

            // If there's basically no person pixels in a band, treat it as "not sure".
            // e.g. shoes might be out of frame.
            if (bandRatio < 0.015) return null

            // For X extents, use the mask within the band's Y-range.
            // For Y extents, fill the entire band to make regions long and non-overlapping.
            const bb = bboxFromMask(mask, mw, mh, band.y0, band.y1)
            if (!bb) return null

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

        const rawBoxes: Box[] = boxesCandidate
          .filter((b): b is Box => Boolean(b))
          .map((b) => ({
            ...b,
            // Small safety expansion in normalized space.
            x: clamp(b.x - 0.005, 0, 0.95),
            y: clamp(b.y - 0.005, 0, 0.95),
            w: clamp(b.w + 0.01, 0.12, 0.98),
            h: clamp(b.h + 0.01, 0.12, 0.98),
          }))

        // If segmentation isn't confident, or we don't have ALL regions, show zero boxes.
        // This matches the product requirement: if we're not sure, don't label anything.
        const finalBoxes = segmentationConfident && rawBoxes.length >= 3 ? rawBoxes : []

        if (cancelled) return
        // Canvas dims are fixed; we compute the exact draw rect so overlays align.
        const canvasW = 840
        const canvasH = 980
        const draw = containRect(img.naturalWidth, img.naturalHeight, canvasW, canvasH)
        setState({ status: 'ready', boxes: finalBoxes, draw })

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

        for (const b of finalBoxes) {
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
      try {
        detector?.dispose?.()
      } catch {
        // ignore
      }
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
              // Render by region id to avoid mislabeling when a region is missing.
              const order: Record<RegionId, number> = { top: 0, bottom: 1, shoes: 2 }
              const ordered = [...state.boxes].sort((a, b) => (order[a.id] ?? 99) - (order[b.id] ?? 99))
              const labels = orderedLabels ?? (['Top', 'Bottom', 'Shoes'] as const)
              const canvasW = 840
              const canvasH = 980

              return ordered.map((b, idx) => {
                const k = b.id
                const label = labels[order[k] ?? idx] ?? regions.find((r) => r.id === k)?.label ?? k
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

