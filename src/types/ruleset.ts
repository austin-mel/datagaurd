import type { RuleSet } from './backend'
export type RuleType = 'required' | 'unique' | 'regex' | 'range' | 'min' | 'max' | 'allowed' | 'date' | 'numeric'

export const supportedDateConditions = ['On or before selected date', 'On or after selected date', 'Before selected date', 'After selected date', 'Between two selected dates'] as const
export type DateCondition = (typeof supportedDateConditions)[number]

export interface QualityRule {
  id: string
  enabled: boolean
  column: string
  type: RuleType
  condition: string
  minimum: number | ''
  maximum: number | ''
  selectedDate?: string
  endDate?: string
  severity?: 'error' | 'warning'
  dateFormats?: readonly ('%Y-%m-%d' | '%m/%d/%Y' | '%d/%m/%Y')[]
  backendRule?: RuleSet['rules'][number]
}

export interface DatasetRuleset {
  id: string
  name: string
  description: string
  kind: 'default' | 'custom'
  rules: readonly QualityRule[]
  backendConfiguration?: RuleSet
}

export interface RuleEditorCatalog {
  defaultRuleType: RuleType
  ruleTypes: readonly {
    value: RuleType
    label: string
    defaults: Pick<QualityRule, 'condition' | 'minimum' | 'maximum' | 'selectedDate' | 'endDate'>
  }[]
  dateConditions: readonly DateCondition[]
}
