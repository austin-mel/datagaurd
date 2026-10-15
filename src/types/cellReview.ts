import type { DatasetValue } from './dataset'

export interface ReviewedCell {
  /** One-based data row, excluding the file header. */
  rowNumber: number
  identifier: string | null
}

export interface CellReviewGroup {
  id: string
  column: string
  ruleId: string
  rule: string
  kind: 'violation' | 'warning'
  reason: string
  currentValue: DatasetValue
  cells: readonly ReviewedCell[]
}

export type CellReviewAction =
  | { type: 'replace'; value: string | null }
  | { type: 'delete-row' }
  | { type: 'ignore'; reason: string }

export interface CellReviewRequest {
  version: string
  groupId: string
  rowNumber: number
  scope: 'one' | 'all'
  action: CellReviewAction
}
