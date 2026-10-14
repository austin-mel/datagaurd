import { supportedDateConditions } from '../types/ruleset'
import type { DatasetRuleset, QualityRule, Dataset, DatasetRow, DatasetValue, QualityDimension, ValidationIssue, ColumnProfile } from '../types'

export class RulesetValidationError extends Error {}
export const qualityNote = 'Scores count each row once. Completeness: every cell present. Validity: no rule errors. Uniqueness: present, unique values in every enabled unique column. Overall is the mean of available scores.'
type ValidationResult = Pick<Dataset, 'validation' | 'quality' | 'qualityDimensions' | 'qualityNote' | 'status' | 'lastValidatedAt' | 'processingStatus' | 'rulesChangedSinceRun' | 'columnProfiles'>

function isMissing(value: DatasetValue | undefined): boolean {
  return value === null || value === undefined || (typeof value === 'string' && !value.trim())
}
function numericValue(value: DatasetValue): number {
  if (typeof value === 'number') return value
  if (typeof value !== 'string' || !/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(value.trim())) return NaN
  return Number(value)
}
function dateValue(value: DatasetValue, formats: QualityRule['dateFormats'] = ['%Y-%m-%d']): number {
  if (typeof value !== 'string') return NaN
  for (const format of formats) {
    const match = value.trim().match(format === '%Y-%m-%d' ? /^(\d{4})-(\d{2})-(\d{2})$/ : /^(\d{2})\/(\d{2})\/(\d{4})$/)
    if (!match) continue
    const [, a, b, c] = match
    const iso = format === '%Y-%m-%d' ? value.trim() : format === '%m/%d/%Y' ? c + '-' + a + '-' + b : c + '-' + b + '-' + a
    const day = new Date(iso + 'T00:00:00Z')
    if (Number.isFinite(day.getTime()) && day.getUTCFullYear() >= 1 && day.toISOString().slice(0, 10) === iso) return day.getTime()
  }
  return NaN
}
function prepareRule(rule: QualityRule) {
  const fail = (message: string): never => { throw new RulesetValidationError(rule.column + ': ' + message) }
  const bound = (value: number | '', name: string): number => value === '' || !Number.isFinite(value) ? fail('enter a finite ' + name + '.') : value
  switch (rule.type) {
    case 'required': return (value: DatasetValue) => !isMissing(value)
    case 'unique': return () => true
    case 'numeric': return (value: DatasetValue) => Number.isFinite(numericValue(value))
    case 'range':
    case 'min':
    case 'max': {
      const minimum = rule.type === 'max' ? -Infinity : bound(rule.minimum, 'minimum')
      const maximum = rule.type === 'min' ? Infinity : bound(rule.maximum, 'maximum')
      if (minimum > maximum) fail('minimum must be less than or equal to maximum.')
      return (value: DatasetValue) => Number.isFinite(numericValue(value)) && numericValue(value) >= minimum && numericValue(value) <= maximum
    }
    case 'allowed': {
      const values = new Set(rule.condition.split(',').map(value => value.trim()).filter(Boolean))
      if (!values.size) fail('enter at least one allowed value.')
      return (value: DatasetValue) => values.has(String(value))
    }
    case 'regex': {
      if (!rule.condition) fail('enter a regular expression.')
      let pattern: RegExp
      try { pattern = new RegExp('^(?:' + rule.condition + ')$(?![\\s\\S])') } catch { return fail('enter a valid regular expression.') }
      return (value: DatasetValue) => pattern.test(String(value))
    }
    case 'date': {
      if (!supportedDateConditions.some(option => option === rule.condition)) fail('select a supported date condition.')
      const selected = dateValue(rule.selectedDate ?? '')
      const end = dateValue(rule.endDate ?? '')
      if (!Number.isFinite(selected)) fail('select a valid calendar date.')
      if (rule.condition === 'Between two selected dates') {
        if (!Number.isFinite(end)) fail('select a valid end date.')
        if (selected > end) fail('the start date must be on or before the end date.')
      }
      return (value: DatasetValue) => {
        const day = dateValue(value, rule.dateFormats)
        if (!Number.isFinite(day)) return false
        switch (rule.condition) {
          case 'On or before selected date': return day <= selected
          case 'On or after selected date': return day >= selected
          case 'Before selected date': return day < selected
          case 'After selected date': return day > selected
          case 'Between two selected dates': return day >= selected && day <= end
          default: return false
        }
      }
    }
  }
}
export function assertValidRuleset(ruleset: DatasetRuleset, columns: readonly string[]) {
  const ids = new Set<string>()
  for (const rule of ruleset.rules) {
    if (!rule.id.trim() || ids.has(rule.id)) throw new RulesetValidationError('Every rule must have a unique ID.')
    ids.add(rule.id)
    if (!rule.enabled) continue
    if (!columns.includes(rule.column)) throw new RulesetValidationError('Unknown column: ' + rule.column)
    prepareRule(rule)
  }
}

export function validateDataset(input: Iterable<DatasetRow>, columns: readonly string[], ruleset: DatasetRuleset, validatedAt: Date): ValidationResult {
  assertValidRuleset(ruleset, columns)
  const rows = [...input]
  const checks = ruleset.rules.filter(rule => rule.enabled).map(rule => ({
    rule, passes: prepareRule(rule), affected: new Set<number>(), frequencies: new Map<DatasetValue, number>(),
  }))
  for (const check of checks) {
    if (check.rule.type === 'unique') for (const row of rows) {
      const value = row[check.rule.column] ?? null
      if (!isMissing(value)) check.frequencies.set(value, (check.frequencies.get(value) ?? 0) + 1)
    }
  }
  const invalid = new Set<number>(), nonunique = new Set<number>()
  let complete = 0
  rows.forEach((row, index) => {
    if (columns.every(column => !isMissing(row[column]))) complete++
    for (const check of checks) {
      const value = row[check.rule.column] ?? null
      const missing = isMissing(value)
      if (check.rule.type === 'unique' && (missing || check.frequencies.get(value) !== 1)) nonunique.add(index)
      if (check.rule.type !== 'required' && missing) continue
      if (check.rule.type === 'unique' ? check.frequencies.get(value) !== 1 : !check.passes(value)) {
        check.affected.add(index)
        if (check.rule.severity !== 'warning') invalid.add(index)
      }
    }
  })
  const issues: ValidationIssue[] = checks.filter(check => check.affected.size).map(check => ({
    id: check.rule.id, column: check.rule.column, rule: check.rule.type,
    message: check.rule.column + ' failed ' + check.rule.type + (check.rule.condition ? ': ' + check.rule.condition : '')
      + (check.rule.type === 'date' ? ' (' + check.rule.selectedDate
        + (check.rule.condition === 'Between two selected dates' ? ' – ' + check.rule.endDate : '') + ')' : '') + '.',
    affectedRows: check.affected.size,
  }))
  const dimension = (id: string, label: string, passed: number, description: string, available = true): QualityDimension => ({
    id, label, score: available && rows.length ? 100 * passed / rows.length : null,
    passed: available ? passed : null, total: available ? rows.length : null,
    description: available ? description : 'No enabled uniqueness rules',
  })
  const qualityDimensions = [
    dimension('completeness', 'Completeness', complete, 'rows with no missing cells'),
    dimension('validity', 'Validity', rows.length - invalid.size, 'rows without rule errors'),
    dimension('uniqueness', 'Uniqueness', rows.length - nonunique.size, 'rows unique in all tagged columns', checks.some(check => check.rule.type === 'unique')),
  ]
  const scores = qualityDimensions.flatMap(item => item.score === null ? [] : [item.score])
  return {
    validation: { checksRun: checks.length, issues },
    quality: scores.length ? scores.reduce((sum, score) => sum + score, 0) / scores.length : null,
    qualityDimensions, qualityNote,
    status: !checks.length ? 'unvalidated' : issues.length ? 'needs-review' : 'healthy',
    processingStatus: 'completed', rulesChangedSinceRun: false,
    lastValidatedAt: validatedAt.toISOString(), columnProfiles: profileDataset(rows, columns, ruleset),
  }
}

export function profileDataset(rows: readonly DatasetRow[], columns: readonly string[], ruleset: DatasetRuleset): ColumnProfile[] {
  return columns.map(name => {
    const values = rows.map(row => row[name] ?? null).filter(value => !isMissing(value))
    const frequencies = new Map<string, number>()
    const observed = new Set<ColumnProfile['observedTypes'][number]>()
    const numbers: number[] = [], dates: number[] = []
    const formats = ruleset.rules.find(rule => rule.enabled && rule.column === name && rule.type === 'date')?.dateFormats
    for (const value of values) {
      const text = String(value)
      frequencies.set(text, (frequencies.get(text) ?? 0) + 1)
      const number = numericValue(value), date = dateValue(value, formats)
      if (Number.isFinite(number)) { observed.add(Number.isInteger(number) ? 'integer' : 'number'); numbers.push(number) }
      else if (Number.isFinite(date)) { observed.add('date'); dates.push(date) }
      else observed.add('text')
    }
    const categories = [...frequencies].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, 5).map(([value, count]) => ({ value, count }))
    numbers.sort((a, b) => a - b); dates.sort((a, b) => a - b)
    const low = numbers[0], high = numbers.at(-1), first = dates[0], last = dates.at(-1)
    const summary: ColumnProfile['summary'] = observed.size === 1 && low !== undefined && high !== undefined
      ? { kind: 'number-range', minimum: low, maximum: high }
      : observed.size === 1 && first !== undefined && last !== undefined
        ? { kind: 'date-range', minimum: new Date(first).toISOString().slice(0, 10), maximum: new Date(last).toISOString().slice(0, 10) }
        : { kind: 'top-values', values: categories }
    return { name, observedTypes: [...observed].sort(), missingCount: rows.length - values.length, uniqueCount: frequencies.size, summary }
  })
}

