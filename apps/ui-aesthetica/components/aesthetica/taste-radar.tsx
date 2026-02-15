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
              formatter={(value) => (
                <div className="flex w-full items-center justify-between gap-6">
                  <span className="text-muted-foreground">Score</span>
                  <span className="font-mono font-medium tabular-nums">
                    {Number(value).toFixed(0)}
                  </span>
                </div>
              )}
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

