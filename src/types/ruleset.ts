export type RuleType = 'required' | 'unique' | 'regex' | 'range' | 'min' | 'max' | 'allowed' | 'date'

export const supportedDateConditions = ['On or before today', 'On or after today', 'Before today', 'After today', 'Valid date'] as const
export type DateCondition = (typeof supportedDateConditions)[number]

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
  id: string
  name: string
  description: string
  kind: 'default' | 'custom'
  rules: readonly QualityRule[]
}

export interface RuleEditorCatalog {
  defaultRuleType: RuleType
  ruleTypes: readonly {
    value: RuleType
    label: string
    defaults: Pick<QualityRule, 'condition' | 'minimum' | 'maximum'>
  }[]
  dateConditions: readonly DateCondition[]
}
