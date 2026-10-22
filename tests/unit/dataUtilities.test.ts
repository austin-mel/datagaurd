import { describe, expect, it } from 'vitest'
import {
  createDatasetCsv,
  validateUpload,
  displayCellValue,
  groupCellFinding,
  summarizeCellReview,
  exceedsPercentage,
  iqrFences,
  analyzeSeededStatistics,
  countStatisticalWarnings,
  profileDataset,
  hasPendingValidation,
  assertIdentifierRules,
  resolveIdentifier,
} from '@/services'
import {
  cloneRuleset,
  createQualityRule,
  ruleDefaults,
  rulesetSignature,
  formatDate,
  formatNumber,
  formatOpenedAt,
  formatPacificDate,
  formatPacificTime,
  formatScore,
  formatValidatedAt,
} from '@/utils'
import { seededRuleCatalog } from '@/data'
import type { DatasetRow } from '@/types'
import { dataset, group, rule, ruleset } from '../fixtures/workspace'

it('exports ordered CSV with UTF-8 BOM, escaped quotes, line breaks and null cells', async () => {
  const blob = createDatasetCsv(['name', 'value', 'missing'], [{ name: 'café,"quoted"', value: 'a\nb' }, { name: 'zero', value: 0, missing: false }])
  expect(blob.type).toBe('text/csv;charset=utf-8')
  expect([...new Uint8Array(await blob.arrayBuffer()).slice(0, 3)]).toEqual([239, 187, 191])
  expect(await blob.text()).toBe('"name","value","missing"\r\n"café,""quoted""","a\nb",""\r\n"zero","0","false"\r\n')
})

describe('upload policy', () => {
  const policy = { extensions: ['.csv', '.xlsx'], max_upload_bytes: 1024 * 1024 }
  it.each([['data.CSV', 1, null], ['book.xlsx', 1024 * 1024, null], ['data.csv', 0, 'empty'],
    ['data.csv', 1024 * 1024 + 1, 'limit'], ['data.csv.exe', 1, 'Choose'], ['data', 1, 'Choose']] as const)(
    'validates %s (%i bytes)', (name, size, error) => {
      const result = validateUpload({ name, size }, policy)
      if (error) expect(result).toContain(error)
      else expect(result).toBeNull()
    },
  )
})

describe('cell review grouping', () => {
  it('deduplicates membership, skips invalid row numbers and preserves value types', () => {
    const groups = groupCellFinding(group(), [{ id: 'A', value: 1 }, { id: '', value: '1' }, { value: null }], [1, 1, 2, 3, 99], 'id')
    expect(groups.map(g => g.currentValue)).toEqual([1, '1', null])
    expect(groups.flatMap(g => g.cells)).toEqual([{ rowNumber: 1, identifier: 'A' }, { rowNumber: 2, identifier: null }, { rowNumber: 3, identifier: null }])
    expect(new Set(groups.map(g => g.id)).size).toBe(3)
  })
  it('counts overlapping findings once per cell and severity', () => {
    expect(summarizeCellReview([group(), group({ id: 'another' }), group({ kind: 'warning' })])).toEqual({ cells: 1, rows: 1, violations: 1, warnings: 1 })
  })
  it.each([[null, 'NULL (missing)'], ['', 'Empty string'], [false, 'false'], [0, '0']] as const)('displays %s', (value, label) => expect(displayCellValue(value)).toBe(label))
})

describe('statistics', () => {
  it('interpolates quartiles and excludes exact fence boundaries', () => {
    const result = iqrFences([1, 2, 3, 4], 1.5)
    expect(result).toMatchObject({ q1: 1.75, q3: 3.25, iqr: 1.5, lower: -0.5, upper: 5.5, hasSpread: true })
    expect(result.isOutside(5.5)).toBe(false)
    expect(result.isOutside(5.5001)).toBe(true)
    expect(iqrFences([2, 2, 2], 1.5).hasSpread).toBe(false)
  })
  it('compares percentage thresholds strictly without floating point drift', () => {
    expect(exceedsPercentage(1, 10, 10)).toBe(false)
    expect(exceedsPercentage(1, 10, 9.999)).toBe(true)
    expect(exceedsPercentage(1, 0, 10)).toBe(false)
    expect(exceedsPercentage(-1, 10, 0)).toBe(false)
  })
  const analyze = (rows: DatasetRow[], baseline?: DatasetRow[]) => analyzeSeededStatistics(rows, ['value'], ruleset([]), profileDataset(rows, ['value'], ruleset([])), baseline ? { rows: baseline, columns: ['value'], version: 'v1' } : undefined)
  it('finds outliers using complete membership and requires enough samples', () => {
    const rows = Array.from({ length: 24 }, (_, i) => ({ value: i < 20 ? i : 1000 }))
    const findings = analyze(rows)
    expect(findings[0]).toMatchObject({ rule_id: 'STAT_IQR', affected_record_numbers: [21, 22, 23, 24] })
    expect(countStatisticalWarnings('value', [...findings, ...findings])).toBe(4)
    expect(countStatisticalWarnings('other', findings)).toBe(0)
    expect(analyze(rows.slice(0, 10))).toEqual([])
  })
  it('detects missingness, row count, category and schema drift', () => {
    const before = Array.from({ length: 20 }, () => ({ value: 'A' }))
    const changed = Array.from({ length: 30 }, (_, i) => ({ value: i < 5 ? null : 'B' }))
    expect(analyze(changed, before).map(f => f.rule_id)).toEqual(expect.arrayContaining(['STAT_ROW_COUNT', 'STAT_MISSINGNESS', 'STAT_CATEGORY_MIX']))
    expect(analyze([{ value: 1 }], before).map(f => f.rule_id)).toContain('SCHEMA_COLUMNS')
  })
})

describe('identifier resolution and rule helpers', () => {
  const auto = ruleset([], { backendConfiguration: { schema_version: 1, name: 'auto', identifier_policy: 'auto', structural_rule_id: 'COLUMNS', required_columns: [], rules: [] } })
  it.each([['PrimaryKey', 'id'], ['recordId'], ['customer-id']])('normalizes and prioritizes headers %j', (...headers) => {
    expect(resolveIdentifier(auto, headers).column).toBe(headers[0])
  })
  it('refuses ambiguous identifiers', () => {
    expect(resolveIdentifier(auto, ['id', 'uuid']).column).toBeNull()
    expect(resolveIdentifier(auto, ['name']).reason).toContain('No recognized')
    expect(resolveIdentifier(ruleset([rule({ type: 'unique' })]), ['value']).column).toBe('value')
  })
  it('protects automatic identifier checks', () => {
    expect(() => assertIdentifierRules(auto, ['id'])).toThrow(/Retain/)
    const valid = { ...auto, rules: [rule({ id: 'GENERIC_ID_REQUIRED', column: 'id' }), rule({ id: 'GENERIC_ID_UNIQUE', column: 'id', type: 'unique' })] }
    expect(() => assertIdentifierRules(valid, ['id'])).not.toThrow()
  })
  it('clones editable rule objects and supplies fresh IDs', () => {
    const source = ruleset()
    cloneRuleset(source).rules[0]!.enabled = false
    expect(source.rules[0]?.enabled).toBe(true)
    expect(createQualityRule(seededRuleCatalog, 'id').id).not.toBe(createQualityRule(seededRuleCatalog, 'id').id)
    expect(() => ruleDefaults({ ...seededRuleCatalog, ruleTypes: [] }, 'date')).toThrow(/Unsupported/)
  })
  it('ignores editor metadata and order while detecting semantic changes', () => {
    const original = ruleset([rule(), rule({ id: 'OTHER', type: 'min' })])
    expect(rulesetSignature({ ...original, name: 'Renamed', rules: [...original.rules].reverse() })).toBe(rulesetSignature(original))
    expect(rulesetSignature(ruleset([rule({ severity: 'warning' })]))).not.toBe(rulesetSignature(ruleset()))
  })
})

describe('validation eligibility', () => {
  it.each(['validationPending', 'rulesChangedSinceRun', 'reviewChangedSinceRun', 'dataChangedSinceRun'] as const)('runs when %s', flag => expect(hasPendingValidation(dataset({ [flag]: true }))).toBe(true))
  it('prevents concurrent runs and allows failed attempts', () => {
    expect(hasPendingValidation(dataset())).toBe(false)
    expect(hasPendingValidation(dataset({ processingStatus: 'running', validationPending: true }))).toBe(false)
    expect(hasPendingValidation(dataset({ processingStatus: 'failed' }))).toBe(true)
  })
})

describe('formatters', () => {
  it('formats numbers, missing scores and invalid dates', () => {
    expect(formatNumber(123456)).toBe('123,456')
    expect(formatScore(12.34)).toBe('12.3')
    expect(formatScore(null)).toBe('Not available')
    expect(formatValidatedAt(null)).toBe('Not available')
    expect(formatValidatedAt('invalid')).toBe('Not yet validated')
    for (const format of [formatDate, formatPacificDate, formatPacificTime]) expect(format('invalid')).toBe('—')
  })
  it('uses Pacific time for events and UTC for date-only values', () => {
    expect(formatDate('2026-01-15')).toBe('Jan 15, 2026')
    expect(formatPacificDate('2026-01-15T01:00:00Z')).toBe('Jan 14, 2026')
    expect(formatPacificTime('2026-01-15T01:00:00Z')).toBe('17:00')
    expect(formatValidatedAt('2026-07-15T12:00:00Z')).toBe('Jul 15, 2026 · 05:00')
  })
  it.each([[0, 'Opened just now'], [1, 'Opened 1 min ago'], [60, 'Opened 1 hour ago'], [120, 'Opened 2 hours ago'], [1440, 'Opened yesterday'], [2880, 'Opened 2 days ago'], [-1, 'Opened just now']] as const)('formats %i minutes ago', (minutes, label) => expect(formatOpenedAt(0, minutes * 60000)).toBe(label))
})
