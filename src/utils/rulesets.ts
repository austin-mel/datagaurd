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

// Compare saved checks with the version's applied checks, ignoring editor-only metadata.
export function rulesetSignature(ruleset: DatasetRuleset): string {
  return JSON.stringify({ kind: ruleset.kind, rules: ruleset.rules.map(rule => ({
    id: rule.id, enabled: rule.enabled, column: rule.column, type: rule.type, severity: rule.severity ?? 'error',
    condition: ['regex', 'allowed', 'date'].includes(rule.type) ? rule.condition : undefined,
    minimum: ['range', 'min'].includes(rule.type) ? rule.minimum : undefined,
    maximum: ['range', 'max'].includes(rule.type) ? rule.maximum : undefined,
    selectedDate: rule.type === 'date' ? rule.selectedDate ?? '' : undefined,
    endDate: rule.type === 'date' && rule.condition === 'Between two selected dates' ? rule.endDate ?? '' : undefined,
    dateFormats: rule.type === 'date' ? rule.dateFormats ?? ['%Y-%m-%d'] : undefined,
  })).sort((a, b) => a.id.localeCompare(b.id)) })
}

export function normalizeRuleId(id: string, index: number) {
  return /^[A-Z][A-Z0-9_]+$/.test(id) ? id : 'UI_' + index + '_' + id.replace(/[^A-Za-z0-9_]/g, '_').toUpperCase()
}
