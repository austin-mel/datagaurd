import { supportedDateConditions } from '@/types/ruleset'
import type { DatasetRuleset, QualityRule } from '@/types'
import type { Dataset, DatasetRow, DatasetValue, QualityDimension, ValidationIssue } from '@/types'

export class RulesetValidationError extends Error {}

type DimensionId = 'completeness' | 'validity' | 'uniqueness'
interface PreparedRule {
  rule: QualityRule
  dimension: DimensionId
  message: string
  passes: (value: DatasetValue) => boolean
}
type ValidationResult = Pick<Dataset, 'validation' | 'quality' | 'qualityDimensions' | 'qualityNote' | 'status' | 'lastValidatedAt'>

function isMissing(value: DatasetValue | undefined): boolean {
  return value === null || value === undefined || (typeof value === 'string' && !value.trim())
}

function numericValue(value: DatasetValue): number {
  return typeof value === 'number' || typeof value === 'string' ? Number(value) : NaN
}

function dateValue(value: DatasetValue): number {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value.trim())) return NaN
  const date = new Date(`${value.trim()}T00:00:00Z`)
  return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value.trim() ? date.getTime() : NaN
}

function validationDay(date: Date): string {
  const parts = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Los_Angeles', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(date)
  const part = (type: string) => parts.find(item => item.type === type)?.value
  return `${part('year')}-${part('month')}-${part('day')}`
}

function prepareRule(rule: QualityRule, today: number): PreparedRule {
  const label = rule.column.replaceAll('_', ' ').replace(/\bid\b/gi, 'ID').replace(/^./, character => character.toUpperCase())
  const fail = (message: string): never => { throw new RulesetValidationError(`${rule.column}: ${message}`) }
  const bound = (value: number | '', name: string): number => {
    if (value === '' || !Number.isFinite(value)) return fail(`enter a finite ${name}.`)
    return value
  }
  const check = (message: string, passes: PreparedRule['passes'], dimension: DimensionId = 'validity'): PreparedRule => ({ rule, message, passes, dimension })

  switch (rule.type) {
    case 'required': return check(`${label} is required.`, value => !isMissing(value), 'completeness')
    // Duplicate frequencies are evaluated across the whole column below.
    case 'unique': return check(`${label} must be unique.`, () => true, 'uniqueness')
    case 'range': {
      const minimum = bound(rule.minimum, 'minimum')
      const maximum = bound(rule.maximum, 'maximum')
      if (minimum > maximum) fail('the minimum must be less than or equal to the maximum.')
      return check(`${label} must be between ${minimum} and ${maximum}.`, value => {
        const number = numericValue(value)
        return Number.isFinite(number) && number >= minimum && number <= maximum
      })
    }
    case 'min': {
      const minimum = bound(rule.minimum, 'minimum')
      return check(`${label} must be at least ${minimum}.`, value => Number.isFinite(numericValue(value)) && numericValue(value) >= minimum)
    }
    case 'max': {
      const maximum = bound(rule.maximum, 'maximum')
      return check(`${label} must be at most ${maximum}.`, value => Number.isFinite(numericValue(value)) && numericValue(value) <= maximum)
    }
    case 'allowed': {
      const allowed = rule.condition.split(',').map(value => value.trim()).filter(Boolean)
      if (!allowed.length) fail('enter at least one allowed value, separated by commas.')
      const values = new Set(allowed)
      return check(`${label} must be one of: ${allowed.join(', ')}.`, value => values.has(String(value).trim()))
    }
    case 'regex': {
      if (!rule.condition.trim()) fail('enter a regular expression.')
      let pattern: RegExp
      try { pattern = new RegExp(rule.condition) } catch { return fail('enter a valid regular expression.') }
      return check(`${label} must match ${rule.condition}.`, value => pattern.test(String(value).trim()))
    }
    case 'date': {
      const condition = rule.condition.trim()
      if (!supportedDateConditions.some(option => option === condition)) fail('select a supported date condition.')
      return check(`${label} must satisfy: ${condition.toLowerCase()}.`, value => {
        const date = dateValue(value)
        if (!Number.isFinite(date)) return false
        switch (condition) {
          case 'On or before today': return date <= today
          case 'On or after today': return date >= today
          case 'Before today': return date < today
          case 'After today': return date > today
          default: return true
        }
      })
    }
    default: return fail('select a supported rule type.')
  }
}

export function assertValidRuleset(ruleset: DatasetRuleset, columns: readonly string[]) {
  const ids = new Set<string>()
  for (const rule of ruleset.rules) {
    if (!rule.id.trim() || ids.has(rule.id)) throw new RulesetValidationError('Every rule must have a unique ID.')
    ids.add(rule.id)
    if (!rule.enabled) continue
    if (!columns.includes(rule.column)) throw new RulesetValidationError(`Unknown column: ${rule.column}`)
    prepareRule(rule, 0)
  }
}

export function validateDataset(rows: Iterable<DatasetRow>, columns: readonly string[], ruleset: DatasetRuleset, validatedAt: Date): ValidationResult {
  assertValidRuleset(ruleset, columns)
  const today = dateValue(validationDay(validatedAt))
  const checks = ruleset.rules.filter(rule => rule.enabled).map(rule => ({
    ...prepareRule(rule, today), total: 0, failed: 0, frequencies: new Map<DatasetValue, number>(),
  }))
  if (checks.length) {
    for (const row of rows) {
      for (const check of checks) {
        const value = row[check.rule.column] ?? null
        // Missing values belong to required checks, not format or uniqueness checks.
        if (check.rule.type !== 'required' && isMissing(value)) continue
        check.total++
        if (check.rule.type === 'unique') {
          const key = typeof value === 'string' ? value.trim() : value
          check.frequencies.set(key, (check.frequencies.get(key) ?? 0) + 1)
        } else if (!check.passes(value)) check.failed++
      }
    }
  }

  const issues: ValidationIssue[] = []
  const dimensions: Record<DimensionId, { label: string; checks: number; total: number; failed: number }> = {
    completeness: { label: 'Completeness', checks: 0, total: 0, failed: 0 },
    validity: { label: 'Validity', checks: 0, total: 0, failed: 0 },
    uniqueness: { label: 'Uniqueness', checks: 0, total: 0, failed: 0 },
  }
  for (const check of checks) {
    if (check.rule.type === 'unique') {
      for (const count of check.frequencies.values()) if (count > 1) check.failed += count
    }
    const dimension = dimensions[check.dimension]
    dimension.checks++
    dimension.total += check.total
    dimension.failed += check.failed
    if (check.failed) issues.push({
      id: check.rule.id, column: check.rule.column, rule: check.rule.type === 'allowed' ? 'allowed values' : check.rule.type,
      message: check.message, affectedRows: check.failed,
    })
  }

  const roundScore = (score: number) => Math.round(score * 10) / 10
  const scores: number[] = []
  const qualityDimensions: QualityDimension[] = Object.entries(dimensions).map(([id, dimension]) => {
    const score = dimension.total ? (dimension.total - dimension.failed) / dimension.total * 100 : null
    if (score !== null) scores.push(score)
    return {
      id, label: dimension.label, score: score === null ? null : roundScore(score),
      passed: dimension.total ? dimension.total - dimension.failed : null, total: dimension.total || null,
      description: !dimension.checks ? `No ${id} checks configured`
        : !dimension.total ? 'No values to evaluate'
          : id === 'completeness' ? 'required values present' : id === 'uniqueness' ? 'non-empty values occur once' : 'value checks passed',
    }
  })
  return {
    validation: { checksRun: checks.length, issues },
    quality: scores.length ? roundScore(scores.reduce((sum, score) => sum + score, 0) / scores.length) : null,
    qualityDimensions,
    qualityNote: 'Overall is the mean of the available, unrounded dimension scores for the saved ruleset. Required checks evaluate missing values; other checks evaluate non-empty values.',
    status: !checks.length ? 'unvalidated' : issues.length ? 'needs-review' : 'healthy',
    lastValidatedAt: validatedAt.toISOString(),
  }
}
