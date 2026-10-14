import type { DatasetRuleset, QualityRule, RuleEditorCatalog, RuleType } from '@/types'

export function cloneRuleset(ruleset: DatasetRuleset): DatasetRuleset & { rules: QualityRule[] } {
  return { ...ruleset, rules: ruleset.rules.map(rule => ({ ...rule })) }
}

export function ruleDefaults(catalog: RuleEditorCatalog, type: RuleType) {
  const definition = catalog.ruleTypes.find(option => option.value === type)
  if (!definition) throw new Error(`Unsupported rule type: ${type}`)
  return { ...definition.defaults }
}

export function createQualityRule(catalog: RuleEditorCatalog, column: string): QualityRule {
  return {
    id: crypto.randomUUID(), enabled: true, column, type: catalog.defaultRuleType,
    ...ruleDefaults(catalog, catalog.defaultRuleType),
  }
}
