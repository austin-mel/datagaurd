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
  type: 'text' | 'integer' | 'number' | 'date' | 'boolean'
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
  sourceIcon: 'file' | 'cloud'
  filename?: string
  uploadedAt?: string
  uploadedBy?: string
  downloadFilename?: string
  history?: readonly DatasetHistoryEvent[]
  rowCount: number
  version: string
  isCurrentVersion: boolean
  status: 'needs-review' | 'healthy' | 'blocked' | 'unvalidated'
  quality: number | null
  qualityDimensions: readonly QualityDimension[]
  qualityNote: string
  lastValidatedAt: string
  columns: readonly string[]
  columnProfiles: readonly ColumnProfile[]
  validation: {
    checksRun: number
    issues: readonly ValidationIssue[]
  }
  ruleset: DatasetRuleset
}
