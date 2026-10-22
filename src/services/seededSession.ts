import type { CellReviewGroup, Dataset, DatasetHistoryEvent, DatasetRow, DatasetRuleset } from '@/types'
import { rulesetSignature } from '@/utils'

export type SourceRow = { id: number; values: DatasetRow }
export type SessionData = { rows: readonly SourceRow[]; ignored: ReadonlySet<string> }

// Default/custom is editor metadata, not a change to validation or ignore semantics.
export function validationSignature(ruleset: DatasetRuleset) {
  return rulesetSignature({ ...ruleset, kind: 'custom' })
}
export function ruleSignatures(ruleset: DatasetRuleset) {
  return new Map(ruleset.rules.map(rule => [rule.id, validationSignature({ ...ruleset, rules: [rule] })]))
}
export function ignoreKey(row: SourceRow, column: string, kind: CellReviewGroup['kind'], ruleId: string, signature?: string) {
  return JSON.stringify([row.id, column, kind, ruleId, row.values[column] ?? null, signature ?? null])
}

export function nextVersion(record: Dataset) { return 'v' + (Number(record.version.replace(/^v/, '')) + 1) }
export function downloadFilename(record: Dataset, version: string) {
  return (record.filename ?? record.name).replace(/\.[^.]+$/, '') + '_' + version + '.csv'
}
export function historyEvent(title: DatasetHistoryEvent['title'], description: string): DatasetHistoryEvent {
  return { id: crypto.randomUUID(), occurredAt: new Date().toISOString(), title, description }
}

