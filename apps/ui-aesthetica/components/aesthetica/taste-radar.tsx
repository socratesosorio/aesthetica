'use client'

import * as React from 'react'
import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
} from 'recharts'

import type { TasteRadarPoint } from '@/lib/aesthetica/types'
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from '@/components/ui/chart'

function scoreBand(value: number) {
  if (value <= 20) return 'strong'
  if (value <= 40) return 'lean'
  if (value < 60) return 'balanced'
  if (value < 80) return 'lean'
  return 'strong'
}

function interpretation(point: TasteRadarPoint, raw: unknown): React.ReactNode {
  const v = typeof raw === 'number' ? raw : Number(raw)
  const value = Number.isFinite(v) ? Math.max(0, Math.min(100, v)) : 50
  const band = scoreBand(value)
  const towardRight = value >= 60
  const towardLeft = value <= 40

  const left = point.leftLabel || 'Left'
  const right = point.rightLabel || 'Right'
  const axis = point.axis || 'Axis'

  const side =
    band === 'balanced'
      ? 'balanced'
      : towardRight
        ? 'right'
        : towardLeft
          ? 'left'
          : 'balanced'

  const where =
    side === 'balanced'
      ? `You’re fairly balanced between ${left.toLowerCase()} and ${right.toLowerCase()}.`
      : side === 'right'
        ? `${band === 'strong' ? 'Strongly' : 'Leaning'} ${right.toLowerCase()}.`
        : `${band === 'strong' ? 'Strongly' : 'Leaning'} ${left.toLowerCase()}.`

  const range =
    side === 'balanced'
      ? '41–59'
      : side === 'left'
        ? band === 'strong'
          ? '0–20'
          : '21–40'
        : band === 'strong'
          ? '80–100'
          : '60–79'

  const common = {
    title: `How to read this`,
    ranges:
      'Score bands: 0–20 strong-left · 21–40 lean-left · 41–59 balanced · 60–79 lean-right · 80–100 strong-right.',
  } as const

  const copyById: Record<TasteRadarPoint['id'], { what: string; examples: string; tryNext: string }> = {
    minimal_maximal: {
      what:
        'This axis captures how “quiet” vs “expressive” your styling tends to be. Minimal leans toward clean shapes, fewer details, and restrained statement pieces; maximal leans toward bolder silhouettes, textures, prints, and visible styling decisions.',
      examples:
        'Minimal signals: monochrome outfits, simple knits/tees, sleek leather, subtle hardware, clean sneakers/loafers. Maximal signals: layered outfits, contrast stitching, loud graphics, mixed prints, statement accessories, exaggerated proportions.',
      tryNext:
        side === 'left'
          ? 'If you want to experiment without feeling loud, try one expressive element at a time (a patterned scarf, a statement shoe, or a textured jacket) while keeping the rest simple.'
          : 'If you want to feel more pared-back, keep silhouette bold but reduce “surface noise” (fewer logos/prints), and anchor with one neutral base color.',
    },
    structured_relaxed: {
      what:
        'This axis measures silhouette discipline. Structured leans toward tailoring, crisp seams, sharp shoulders, and defined lines. Relaxed leans toward drape, softness, ease, and movement.',
      examples:
        'Structured signals: blazers, crisp trousers, sharp collars, denim with shape, boots with structure. Relaxed signals: wide-leg pants, soft knits, loose shirting, slouchy outerwear, minimal constriction.',
      tryNext:
        side === 'left'
          ? 'To soften without losing structure, add one relaxed piece (a slouchy knit or wide-leg trouser) paired with a structured anchor (a blazer or crisp shoe).'
          : 'To sharpen without feeling stiff, try one tailored item (a blazer, a structured coat, or pleated trouser) with the rest kept relaxed.',
    },
    neutral_color: {
      what:
        'This axis reflects color palette preference. Neutral leans toward black/white/gray/beige and low-saturation tones; color-forward leans toward higher saturation, bolder accents, or more frequent color contrast.',
      examples:
        'Neutral signals: tonal outfits, charcoal + cream, black leather, muted blues/olives, low-contrast layering. Color-forward signals: bright outerwear, saturated tops, loud accents, frequent complementary contrasts.',
      tryNext:
        side === 'left'
          ? 'To add color without breaking your vibe, use controlled accents: one saturated item (bag/shoe/hat) or a single “hero” top, with everything else neutral.'
          : 'To make color feel more elegant, lower saturation (dusty tones), use tonal layering, and keep materials premium (wool, leather, crisp cotton).',
    },
    classic_experimental: {
      what:
        'This axis captures your relationship to trend and novelty. Classic leans toward timeless silhouettes and familiar staples; experimental leans toward unusual cuts, newer proportions, niche brands, or “fashion moves” that stand out.',
      examples:
        'Classic signals: trench coats, straight denim, simple tees, loafers, clean suiting. Experimental signals: asymmetric pieces, unexpected volume, statement cuts, unusual color blocking, avant textures.',
      tryNext:
        side === 'left'
          ? 'To go slightly more experimental, keep the same base staples but swap one dimension: silhouette (wider), texture (sheen/knit), or detail (zip/hardware).'
          : 'To keep experimentation wearable, anchor with one classic base layer (straight pant, simple tee, clean shoe) and let one experimental piece do the talking.',
    },
    casual_formal: {
      what:
        'This axis reflects how polished your default outfits read. Casual leans toward comfort, sport references, and everyday ease. Formal leans toward refinement, crispness, and “put-together” signals (even in simple outfits).',
      examples:
        'Casual signals: tees, hoodies, sneakers, relaxed denim, minimal fuss. Formal signals: tailored trousers, structured outerwear, leather shoes, crisp shirting, fewer sporty references.',
      tryNext:
        side === 'left'
          ? 'To look more polished without losing comfort, upgrade one element: swap sneakers for loafers, add a structured coat, or use a crisp trouser with a soft top.'
          : 'To make formal feel effortless, loosen one element: a relaxed trouser with a sharp shoe, or a tee under tailored outerwear—keep proportions intentional.',
    },
  }

  const block = copyById[point.id]

  return (
    <div className="grid gap-2">
      <div className="text-foreground text-xs font-medium">{where}</div>
      <div className="text-muted-foreground text-xs">
        You’re in the <span className="font-medium text-foreground">{range}</span> range on{' '}
        <span className="font-medium text-foreground">{axis}</span>.
      </div>

      <div className="text-muted-foreground text-xs leading-relaxed">
        <span className="font-medium text-foreground">What this measures:</span> {block.what}
      </div>

      <div className="text-muted-foreground text-xs leading-relaxed">
        <span className="font-medium text-foreground">Typical signals:</span> {block.examples}
      </div>

      <div className="text-muted-foreground text-xs leading-relaxed">
        <span className="font-medium text-foreground">Try next:</span> {block.tryNext}
      </div>

      <div className="pt-1 text-[11px] text-muted-foreground">
        <span className="font-medium text-foreground">{common.title}:</span> {common.ranges}
      </div>
    </div>
  )
}

export function TasteRadar({
  data,
  className,
}: {
  data: TasteRadarPoint[]
  className?: string
}) {
  return (
    <ChartContainer
      config={{
        taste: { label: 'Taste', color: 'hsl(var(--foreground))' },
      }}
      className={className ?? 'aspect-auto h-[360px] w-full'}
    >
      <RadarChart data={data} outerRadius="78%">
        <ChartTooltip
          cursor={false}
          content={
            <ChartTooltipContent
              formatter={(value, _name, _item, _index, payload) => {
                const point = payload as unknown as TasteRadarPoint
                return (
                  <div className="grid gap-2 max-w-[380px]">
                    <div className="flex w-full items-center justify-between gap-6">
                      <span className="text-muted-foreground">Score</span>
                      <span className="font-mono font-medium tabular-nums">
                        {Number(value).toFixed(0)}
                      </span>
                    </div>
                    <div className="whitespace-normal">{interpretation(point, value)}</div>
                  </div>
                )
              }}
              labelFormatter={(label) => label}
            />
          }
        />
        <PolarGrid stroke="hsl(var(--border))" strokeOpacity={0.35} />
        <PolarAngleAxis dataKey="axis" tickLine={false} axisLine={false} />
        <PolarRadiusAxis
          angle={90}
          domain={[0, 100]}
          tickCount={6}
          tickLine={false}
          axisLine={false}
        />
        <Radar
          dataKey="value"
          name="Taste"
          stroke="var(--color-taste)"
          fill="var(--color-taste)"
          fillOpacity={0.1}
          strokeWidth={2.5}
        />
      </RadarChart>
    </ChartContainer>
  )
}

