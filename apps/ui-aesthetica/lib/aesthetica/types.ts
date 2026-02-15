export type RadarAxisId =
  | 'minimal_maximal'
  | 'structured_relaxed'
  | 'neutral_color'
  | 'classic_experimental'
  | 'casual_formal'

export type TasteRadarPoint = {
  id: RadarAxisId
  axis: string
  leftLabel: string
  rightLabel: string
  value: number // 0-100
}

export type ProductMatch = {
  id: string
  title: string
  retailer?: string
  price?: string
  url?: string
  tier: 'closest' | 'alternative' | 'premium'
  score: number // 0-1
}

export type GarmentSegment = {
  id: string
  type: 'top' | 'bottom' | 'outerwear' | 'shoes' | 'accessory'
  summary: string
  matches: ProductMatch[]
}

export type Capture = {
  id: string
  capturedAtISO: string
  locationHint?: string
  summary: string
  aestheticOneLiner: string
  latencySeconds: number
  outfitEmbeddingId: string
  radarDelta: Partial<Record<RadarAxisId, number>> // delta in points (e.g. +4)
  segments: GarmentSegment[]
}

