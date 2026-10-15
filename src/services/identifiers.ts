import type { DatasetRuleset, QualityRule } from '../types'

export function resolveIdentifier(ruleset: DatasetRuleset, headers: readonly string[]): { column: string | null; reason: string | null } {
  const configuration = ruleset.backendConfiguration
  if (configuration?.identifier_column) return { column: configuration.identifier_column, reason: null }
  if (configuration?.identifier_policy !== 'auto') {
    const columns = new Set(ruleset.rules.filter(rule => rule.enabled && rule.type === 'unique').map(rule => rule.column))
    return columns.size === 1 ? { column: [...columns][0] ?? null, reason: null }
      : { column: null, reason: 'No unambiguous identifier column is configured.' }
  }
  const normalized = headers.map(header => ({ header, name: header.trim().replace(/([a-z0-9])([A-Z])/g, '$1_$2').replace(/[\s-]+/g, '_').toLowerCase() }))
  const groups = [['pk', 'primary_key', 'primarykey', 'primary_id'], ['id', 'uuid', 'guid'], ['record_id', 'row_id', 'unique_id']]
  const candidates = groups.map(group => normalized.filter(item => group.includes(item.name)))
  candidates.push(normalized.filter(item => /_(?:id|uuid|guid|pk)$/.test(item.name)))
  for (const group of candidates) {
    if (group.length === 1) return { column: group[0]?.header ?? null, reason: null }
    if (group.length) return { column: null, reason: 'Multiple possible primary keys: ' + group.map(item => item.header).join(', ') + '. Set identifier_column explicitly.' }
  }
  return { column: null, reason: 'No recognized primary key or ID column. Set identifier_column explicitly.' }
}

export function isAutomaticIdentifierRule(ruleset: DatasetRuleset, rule: QualityRule): boolean {
  return ruleset.backendConfiguration?.identifier_policy === 'auto' && ['GENERIC_ID_REQUIRED', 'GENERIC_ID_UNIQUE'].includes(rule.id)
}

export function assertIdentifierRules(ruleset: DatasetRuleset, headers: readonly string[]): void {
  if (ruleset.backendConfiguration?.identifier_policy !== 'auto') return
  const { column } = resolveIdentifier(ruleset, headers)
  for (const [id, type] of [['GENERIC_ID_REQUIRED', 'required'], ['GENERIC_ID_UNIQUE', 'unique']] as const) {
    const rule = ruleset.rules.find(item => item.id === id)
    if (column ? !rule || !rule.enabled || rule.type !== type || rule.column !== column || (rule.severity ?? 'error') !== 'error' : !!rule) {
      throw new Error('Retain the automatic required and unique checks for the resolved identifier.')
    }
  }
}
