import type { DatasetRuleset, QualityRule, DatasetValue } from '@/types'
import { supportedDateConditions } from '@/types'
import { normalizeRuleId } from '@/utils'
import { assertIdentifierRules } from './identifiers'
import { compilePortablePattern, parseAllowedValues } from './ruleSyntax'
import { dateValue, isMissing, numericValue } from './datasetValues'

export class RulesetValidationError extends Error {}

export function prepareRule(rule: QualityRule) {
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
      const values = new Set(parseAllowedValues(rule.condition))
      return (value: DatasetValue) => values.has(String(value))
    }
    case 'regex': {
      const pattern = compilePortablePattern(rule.condition)
      return (value: DatasetValue) => pattern.test(String(value))
    }
    case 'date': {
      if (rule.dateFormats && (!rule.dateFormats.length || new Set(rule.dateFormats).size !== rule.dateFormats.length
        || rule.dateFormats.some(format => !['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y'].includes(format)))) fail('select unique, supported date formats.')
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
  if (!ruleset.name.trim()) throw new RulesetValidationError('Enter a ruleset name.')
  try { assertIdentifierRules(ruleset, columns) }
  catch (cause) { throw new RulesetValidationError(cause instanceof Error ? cause.message : 'Invalid identifier checks.') }
  const ids = new Set<string>()
  const normalizedIds = new Set([ruleset.backendConfiguration?.structural_rule_id ?? 'DATASET_COLUMNS'])
  for (const rule of ruleset.rules) {
    if (!rule.id.trim() || ids.has(rule.id)) throw new RulesetValidationError('Every rule must have a unique ID.')
    ids.add(rule.id)
    const normalized = normalizeRuleId(rule.id, ids.size - 1)
    if (normalizedIds.has(normalized)) throw new RulesetValidationError('Rule IDs conflict after normalization.')
    normalizedIds.add(normalized)
    if (!columns.includes(rule.column)) throw new RulesetValidationError('Unknown column: ' + rule.column)
    try { prepareRule(rule) }
    catch (cause) { throw new RulesetValidationError(cause instanceof Error ? cause.message : 'Invalid rule.') }
  }
}

