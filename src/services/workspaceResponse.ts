import type { Dataset, DatasetWorkspace } from '@/types'
import type { UploadPolicy } from '@/types/backend'

// Validate transport data before it enters reactive UI state. Invalid contracts are
// surfaced as errors, never disguised as an offline connection or filled with seeds.
type Check = (value: unknown) => boolean
const text: Check = value => typeof value === 'string'
const number: Check = value => typeof value === 'number' && Number.isFinite(value)
const count: Check = value => number(value) && Number(value) >= 0 && Number.isInteger(value)
const bool: Check = value => typeof value === 'boolean'
const nullable = (check: Check): Check => value => value === null || check(value)
const optional = (check: Check): Check => value => value === undefined || check(value)
const array = (check: Check): Check => value => Array.isArray(value) && value.every(check)
const choice = (...values: string[]): Check => value => typeof value === 'string' && values.includes(value)
const object = (fields: Record<string, Check>): Check => value => typeof value === 'object' && value !== null
  && !Array.isArray(value) && Object.entries(fields).every(([key, check]) => check((value as Record<string, unknown>)[key]))
const date: Check = value => typeof value === 'string' && Number.isFinite(Date.parse(value))
const ruleType = choice('required', 'unique', 'numeric', 'regex', 'range', 'min', 'max', 'allowed', 'date')
const bound: Check = value => value === '' || number(value)
const defaults = { condition: text, minimum: bound, maximum: bound, selectedDate: optional(text), endDate: optional(text) }
const rule = object({ id: text, enabled: bool, column: text, type: ruleType, ...defaults,
  severity: optional(choice('error', 'warning')), dateFormats: optional(array(text)) })
const ruleset = object({ id: text, name: text, description: text, kind: choice('default', 'custom'), rules: array(rule) })
const catalog = object({ defaultRuleType: ruleType, ruleTypes: array(object({ value: ruleType, label: text, defaults: object(defaults) })), dateConditions: array(text) })
const summary: Check = value => object({ kind: choice('top-values'), values: array(object({ value: text, count })) })(value)
  || object({ kind: choice('number-range'), minimum: number, maximum: number })(value)
  || object({ kind: choice('date-range'), minimum: date, maximum: date })(value)
const dataset = object({
  id: text, name: text, source: text, sourceIcon: choice('file'), rowCount: count, columns: array(text),
  version: text, isCurrentVersion: bool, status: choice('needs-review', 'healthy', 'unvalidated', 'running', 'failed'),
  processingStatus: choice('not_started', 'running', 'completed', 'failed'), rulesChangedSinceRun: bool,
  quality: nullable(number), qualityNote: text, lastValidatedAt: nullable(date),
  qualityDimensions: array(object({ id: text, label: text, score: nullable(number), passed: nullable(count), total: nullable(count), description: text })),
  columnProfiles: nullable(array(object({ name: text, observedTypes: array(choice('text', 'integer', 'number', 'date', 'boolean')),
    missingCount: count, warningCount: nullable(count), uniqueCount: count, summary }))),
  validation: nullable(object({ checksRun: count, issues: array(object({ id: text, column: text, rule: text, message: text, affectedRows: count })) })),
  ruleset, filename: optional(text), uploadedAt: optional(date), uploadedBy: optional(text), downloadFilename: optional(text),
  history: optional(array(object({ id: text, occurredAt: date, title: choice('Dataset uploaded', 'Validation ran', 'Ruleset saved', 'Dataset edited', 'Findings ignored'), description: text }))),
  validationPending: optional(bool), reviewChangedSinceRun: optional(bool), dataChangedSinceRun: optional(bool),
  versionId: optional(text), latestRunId: optional(text), processingError: optional(text),
  cellReview: optional(nullable(array(object({ id: text, column: text, ruleId: text, rule: text, kind: choice('violation', 'warning'),
    reason: text, currentValue: nullable(value => text(value) || number(value) || bool(value)),
    cells: array(object({ rowNumber: value => count(value) && Number(value) > 0, identifier: nullable(text) })) })))),
})

function parse<T>(value: unknown, check: Check, name: string): T {
  if (!check(value)) throw new Error(`The backend returned an invalid ${name}. Check the API version and response schema.`)
  return value as T
}
export const parseDataset = (value: unknown) => parse<Dataset>(value, dataset, 'dataset')
export const parseWorkspace = (value: unknown) => parse<DatasetWorkspace>(value, object({ datasets: array(dataset), ruleCatalog: catalog }), 'workspace')
export const parseUploadPolicy = (value: unknown) => parse<UploadPolicy>(value, object({ extensions: array(text), max_upload_bytes: count }), 'upload policy')
