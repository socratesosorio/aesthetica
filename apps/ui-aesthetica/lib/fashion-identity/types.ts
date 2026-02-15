export type IdentityVector = {
  minimal: number
  structured: number
  neutral: number
  classic: number
  casual: number
  experimental: number
  tailored: number
  street: number
  colorForward: number
  trendDriven: number
  relaxed: number
  maximal: number
}

export type IdentityDemoFlags = {
  wrapped: boolean
  geography: boolean
  drift: boolean
  celebrity: boolean
  dna: boolean
  microTrends: boolean
  noteworthy: boolean
  tasteMatch: boolean
  era: boolean
  forecast: boolean
  essay: boolean
  seasons: boolean
  percentiles: boolean
  futureSelf: boolean
}

export type IdentityTimePoint = {
  key: string
  dateISO: string
  label: string
  index: number
  minimal: number
  maximal: number
  neutral: number
  colorForward: number
  structured: number
  relaxed: number
  classic: number
  trendDriven: number
}

export type DriftAnnotation = {
  key: string
  dateISO: string
  label: string
  axis: 'minimal' | 'neutral' | 'structured' | 'classic'
  delta: number
  message: string
}

export type IdentityRegionMatch = {
  key: string
  city: string
  year: number
  label: string
  similarity: number
  lat: number
  lng: number
}

export type WrappedSummary = {
  periodStartISO: string
  periodEndISO: string
  periodLabel: string
  topAesthetic: {
    label: string
    score: number
  }
  fashionAge: {
    value: number
    rationale: string
  }
  fashionGeography: {
    topMatch: string
    driftMatch: string
  }
  silhouetteBias: {
    relaxed: number
    structured: number
    maximal: number
  }
  palette: string[]
  mostCapturedItem: {
    item: string
    count: number
  }
  unexpectedPhase: string
  summaryText: string
}

export type CelebrityTwin = {
  key: string
  name: string
  era: string
  similarity: number
  palette: string[]
}

export type TasteMatchPerson = {
  key: string
  handle: string
  overlap: number
  vector: IdentityVector
}

export type IdentityPercentileLine = {
  key: string
  label: string
  value: number
  text: string
}

export type IdentitySeasonSegment = {
  key: string
  label: 'Comfort season' | 'Formal ambition season' | 'Experimental season' | 'Identity consolidation season'
  startISO: string
  endISO: string
  weeks: number
  share: number
}

export type NoteworthyStyle = {
  key: string
  createdAtISO: string
  title: string
  prompt: string
  rationale: string
  source: 'capture' | 'recommendation'
  captureId?: string
}

export type FashionIdentityResult = {
  generatedAtISO: string
  lastSignalISO: string
  sourceCounts: {
    styleScores: number
    captures: number
    catalogRecommendations: number
    styleRecommendations: number
  }
  hasAnyDemo: boolean
  demoFlags: IdentityDemoFlags
  vector: IdentityVector
  wrapped: WrappedSummary
  geography: {
    regions: IdentityRegionMatch[]
    headline: string
    driftLine: string
  }
  drift: {
    series: IdentityTimePoint[]
    annotations: DriftAnnotation[]
  }
  celebrityTwin: {
    selected: CelebrityTwin
    top3: CelebrityTwin[]
  }
  dna: {
    radar: Array<{ key: string; label: string; value: number }>
    stabilityPercent: number
    mutationPhase: boolean
  }
  microTrends: {
    insights: string[]
  }
  noteworthy: {
    items: NoteworthyStyle[]
  }
  tasteMatch: {
    topMatch: TasteMatchPerson
    others: TasteMatchPerson[]
    divergenceLine: string
    deltas: Array<{ key: string; label: string; overlap: number; delta: number }>
  }
  era: {
    current: string
    trendingToward: string
  }
  forecast: {
    primary: string
    signals: string[]
    projectedVector6w: IdentityVector
    projectedVector52w: IdentityVector
    slopesPerWeek: {
      minimal: number
      structured: number
      neutral: number
      classic: number
      casual: number
      tailored: number
    }
  }
  monthlyEssay: {
    paragraph: string
  }
  seasons: {
    segments: IdentitySeasonSegment[]
  }
  percentiles: {
    lines: IdentityPercentileLine[]
  }
  futureSelf: {
    year: number
    era: string
    twinName: string
    rationale: string
  }
}
