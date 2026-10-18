import type { CellReviewGroup, Dataset, DatasetRuleset, DatasetWorkspace, QualityRule } from '../../src/types'
import { seededRuleCatalog } from '../../src/data/qualityRules'

export const datasetId = '11111111-1111-4111-8111-111111111111'
export const checkedAt = '2026-01-15T12:00:00.000Z'
export function rule(overrides: Partial<QualityRule> = {}): QualityRule {
  return { id: 'VALUE_REQUIRED', column: 'value', type: 'required', enabled: true,
    condition: 'Not empty', minimum: 0, maximum: 100, ...overrides }
}
export function ruleset(rules: readonly QualityRule[] = [rule()], overrides: Partial<DatasetRuleset> = {}): DatasetRuleset {
  return { id: 'test-rules', name: 'Test rules', description: 'Fixture checks', kind: 'custom', rules, ...overrides }
}
export function group(overrides: Partial<CellReviewGroup> = {}): CellReviewGroup {
  return { id: 'missing-value', column: 'value', ruleId: 'VALUE_REQUIRED', rule: 'required',
    kind: 'violation', reason: 'value must not be empty.', currentValue: null,
    cells: [{ rowNumber: 2, identifier: 'B' }], ...overrides }
}
export function dataset(overrides: Partial<Dataset> = {}): Dataset {
  return {
    id: datasetId, name: 'Test inventory', source: 'CSV upload', sourceIcon: 'file', filename: 'inventory.csv',
    rowCount: 2, columns: ['id', 'value'], version: 'v1', isCurrentVersion: true,
    status: 'needs-review', processingStatus: 'completed', rulesChangedSinceRun: false, validationPending: false,
    quality: 50, qualityNote: 'One missing value.', lastValidatedAt: checkedAt,
    qualityDimensions: [{ id: 'completeness', label: 'Completeness', score: 50, passed: 1, total: 2, description: 'rows with no missing cells' }],
    columnProfiles: [{ name: 'value', observedTypes: ['integer'], missingCount: 1, warningCount: 0, uniqueCount: 1,
      summary: { kind: 'number-range', minimum: 10, maximum: 10 } }],
    validation: { checksRun: 1, issues: [{ id: 'VALUE_REQUIRED', column: 'value', rule: 'required', message: 'value must not be empty.', affectedRows: 1 }] },
    ruleset: ruleset(), cellReview: [group()],
    history: [{ id: 'uploaded', occurredAt: checkedAt, title: 'Dataset uploaded', description: 'inventory.csv' }],
    ...overrides,
  }
}
export function workspace(datasets: Dataset[] = [dataset()]): DatasetWorkspace {
  return { datasets, ruleCatalog: structuredClone(seededRuleCatalog) }
}
