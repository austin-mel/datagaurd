import type { QualityRule, RuleEditorCatalog, RuleType } from '@/types'
import { supportedDateConditions } from '@/types/ruleset'

const ruleTypes = [
  { value: 'required', label: 'Required' },
  { value: 'unique', label: 'Unique' },
  { value: 'numeric', label: 'Numeric' },
  { value: 'regex', label: 'Regex' },
  { value: 'range', label: 'Min / max' },
  { value: 'min', label: 'Minimum' },
  { value: 'max', label: 'Maximum' },
  { value: 'allowed', label: 'Allowed values' },
  { value: 'date', label: 'Date constraint' },
] as const

export const seededRuleCatalog: RuleEditorCatalog = {
  defaultRuleType: 'required',
  ruleTypes: ruleTypes.map(option => ({ ...option, defaults: { condition: ruleCondition(option.value), minimum: 0, maximum: 100, selectedDate: '', endDate: '' } })),
  dateConditions: [...supportedDateConditions],
}

export function ruleCondition(type: RuleType): string {
  switch (type) {
    case 'required': return 'Not empty'
    case 'unique': return 'One occurrence per value'
    case 'numeric': return 'Numeric value'
    case 'date': return 'On or before selected date'
    default: return ''
  }
}

// Default checks apply to the dataset's identifier column.
export function createDefaultRules(identifierColumn: string): QualityRule[] {
  return (['required', 'unique'] as const).map(type => ({
    id: `${identifierColumn}-${type}`,
    enabled: true,
    column: identifierColumn,
    type,
    condition: ruleCondition(type),
    minimum: 0,
    maximum: 100,
  }))
}
