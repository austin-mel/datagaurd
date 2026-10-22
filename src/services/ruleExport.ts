import type { RuleSet, DatasetRuleset } from '@/types'
import { assertValidRuleset, RulesetValidationError } from './rulesetValidation'
import { normalizeRuleId } from '@/utils'
import { isAutomaticIdentifierRule } from './identifiers'
import { parseAllowedValues } from './ruleSyntax'

// Convert sample editor rules for scripts/export-demo-manifest.mjs.
export function rulesToBackend(ruleset: DatasetRuleset, columns: readonly string[]): RuleSet {
  if (ruleset.kind !== 'custom') throw new RulesetValidationError('Create a custom ruleset before saving changes.')
  assertValidRuleset(ruleset, columns)
  const ids = new Map(ruleset.rules.map((rule, index) => [rule.id,
    normalizeRuleId(rule.id, index)]))
  const structuralId = ruleset.backendConfiguration?.structural_rule_id ?? 'DATASET_COLUMNS'
  const used = new Set([structuralId, ...ids.values()])
  const result: RuleSet['rules'] = []
  for (const rule of ruleset.rules) {
    if (isAutomaticIdentifierRule(ruleset, rule)) continue
    const id = ids.get(rule.id)
    if (!id) throw new RulesetValidationError('Rule ID is missing.')
    const common = { id, column: rule.column, enabled: rule.enabled, severity: rule.severity ?? 'error',
      explanation: rule.column + ' must satisfy ' + rule.type + '.' }
    const prerequisite = () => {
      let parserId = id + '_PARSE'
      while (used.has(parserId)) parserId += '_P'
      used.add(parserId)
      result.push({ ...common, id: parserId, kind: 'numeric', generated_for: id })
      return parserId
    }
    switch (rule.type) {
      case 'required': case 'unique': case 'numeric': result.push({ ...common, kind: rule.type }); break
      case 'regex': result.push({ ...common, kind: 'pattern', pattern: rule.condition, explanation: rule.column + ' must match ' + rule.condition + '.' }); break
      case 'allowed': {
        const values = parseAllowedValues(rule.condition)
        result.push({ ...common, kind: 'allowed_values', values, explanation: rule.column + ' must be one of: ' + values.join(', ') + '.' }); break
      }
      case 'min': result.push({ ...common, kind: 'min', minimum: Number(rule.minimum), prerequisite: prerequisite(),
        explanation: rule.column + ' must satisfy min: ' + rule.minimum + '.' }); break
      case 'max': result.push({ ...common, kind: 'max', maximum: Number(rule.maximum), prerequisite: prerequisite(),
        explanation: rule.column + ' must satisfy max: ' + rule.maximum + '.' }); break
      case 'range': result.push({ ...common, kind: 'range', minimum: Number(rule.minimum), maximum: Number(rule.maximum), prerequisite: prerequisite(),
        explanation: rule.column + ' must satisfy range: ' + rule.minimum + ' through ' + rule.maximum + '.' }); break
      case 'date': {
        const formats = [...(rule.dateFormats ?? ['%Y-%m-%d'])]
        const explanation = rule.column + ' must satisfy ' + rule.condition + ': ' + rule.selectedDate
          + (rule.condition === 'Between two selected dates' ? ' through ' + rule.endDate + ' (inclusive).' : '.')
        if (rule.condition === 'Between two selected dates') result.push({ ...common, explanation, kind: 'between_dates', formats, start_date: rule.selectedDate ?? '', end_date: rule.endDate ?? '' })
        else {
          const kind = rule.condition === 'On or before selected date' ? 'on_or_before_date' : rule.condition === 'Before selected date' ? 'before_date'
            : rule.condition === 'After selected date' ? 'after_date' : 'on_or_after_date'
          result.push({ ...common, explanation, kind, formats, date: rule.selectedDate ?? '' })
        }
        break
      }
    }
  }
  const policy = ruleset.backendConfiguration?.identifier_policy ?? 'configured'
  return {
    ...ruleset.backendConfiguration, schema_version: 1, name: ruleset.name,
    structural_rule_id: structuralId, identifier_policy: policy,
    required_columns: [...new Set([...(ruleset.backendConfiguration?.required_columns ?? (policy === 'auto' ? [] : columns)),
      ...ruleset.rules.filter(rule => !isAutomaticIdentifierRule(ruleset, rule)).map(rule => rule.column)])],
    rules: result,
  }
}
