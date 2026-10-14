import type { DatasetRuleset } from './ruleset'

export type DatasetValue = string | number | boolean | null
export type DatasetRow = Readonly<Record<string, DatasetValue>>

export interface QualityDimension {
  id: string
  label: string
  score: number | null
  passed: number | null
  total: number | null
  description: string
}

export type ProfileSummary =
  | { kind: 'top-values'; values: readonly { value: string; count: number }[] }
  | { kind: 'number-range'; minimum: number; maximum: number; minimumInvalid?: boolean; maximumInvalid?: boolean }
  | { kind: 'date-range'; minimum: string; maximum: string }

export interface ColumnProfile {
  name: string
  observedTypes: readonly ('text' | 'integer' | 'number' | 'date' | 'boolean')[]
  missingCount: number
  uniqueCount: number
  summary: ProfileSummary
}

export interface ValidationIssue {
  id: string
  column: string
  rule: string
  message: string
  affectedRows: number
}

export interface DatasetHistoryEvent {
  id: string
  occurredAt: string
  title: string
  description: string
}

export interface Dataset {
  id: string
  name: string
  source: string
  sourceIcon: 'file'
  filename?: string
  uploadedAt?: string
  uploadedBy?: string
  downloadFilename?: string
  history?: readonly DatasetHistoryEvent[]
  rowCount: number
  version: string
  isCurrentVersion: boolean
  status: 'needs-review' | 'healthy' | 'blocked' | 'unvalidated' | 'running' | 'failed'
  processingStatus: 'not_started' | 'running' | 'completed' | 'failed'
  processingError?: string
  rulesChangedSinceRun: boolean
  versionId?: string
  latestRunId?: string
  quality: number | null
  qualityDimensions: readonly QualityDimension[]
  qualityNote: string
  lastValidatedAt: string | null
  columns: readonly string[]
  columnProfiles: readonly ColumnProfile[] | null
  validation: {
    checksRun: number
    issues: readonly ValidationIssue[]
  } | null
  ruleset: DatasetRuleset
}
