export const ruleTypes = [
  { value: 'required', label: 'Required' },
  { value: 'unique', label: 'Unique' },
  { value: 'regex', label: 'Regex' },
  { value: 'range', label: 'Min / max' },
  { value: 'min', label: 'Minimum' },
  { value: 'max', label: 'Maximum' },
  { value: 'allowed', label: 'Allowed values' },
  { value: 'date', label: 'Date constraint' },
] as const

export type RuleType = (typeof ruleTypes)[number]['value']

export interface QualityRule {
  id: string
  enabled: boolean
  column: string
  type: RuleType
  condition: string
  minimum: number | ''
  maximum: number | ''
}

export interface DatasetRuleset {
  kind: 'default' | 'custom'
  rules: readonly QualityRule[]
}

export function ruleCondition(type: RuleType): string {
  switch (type) {
    case 'required': return 'Not empty'
    case 'unique': return 'One occurrence per non-empty ID'
    case 'date': return 'On or before today'
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

export function cloneRuleset(ruleset: DatasetRuleset): DatasetRuleset {
  return { kind: ruleset.kind, rules: ruleset.rules.map(rule => ({ ...rule })) }
}
