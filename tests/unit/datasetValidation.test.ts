import { describe, expect, it } from 'vitest'
import { assertValidRuleset, isMissing, numericValue, profileDataset, validateDataset } from '@/services'
import type { DatasetValue, QualityRule } from '@/types'
import { checkedAt, rule, ruleset } from '../fixtures/workspace'

const run = (values: DatasetValue[], overrides: Partial<QualityRule> = {}) =>
  validateDataset(values.map(value => ({ value })), ['value'], ruleset([rule(overrides)]), new Date(checkedAt))

describe('value parsing', () => {
  it.each([null, undefined, '', ' \t\n'])('recognizes missing value %s', value => expect(isMissing(value)).toBe(true))
  it.each([0, false, '0', 'null'])('keeps present value %s', value => expect(isMissing(value)).toBe(false))
  it.each([[' +1.5e2 ', 150], ['.5', 0.5], ['-0', -0], [12, 12]] as const)('parses %s', (value, expected) => expect(numericValue(value)).toBe(expected))
  it.each(['', ' ', '0x10', '1,000', 'Infinity', '12abc', true, null])('rejects nonnumeric %s', value => expect(numericValue(value)).toBeNaN())
})

describe('validation scores and findings', () => {
  it('counts each invalid row once across overlapping rules', () => {
    const result = validateDataset([{ value: null }, { value: -1 }, { value: 2 }, { value: 2 }], ['value'], ruleset([
      rule(), rule({ id: 'UNIQUE', type: 'unique' }), rule({ id: 'MINIMUM', type: 'min', minimum: 0 }),
    ]), new Date(checkedAt))
    expect(result.qualityDimensions.map(d => d.score)).toEqual([75, 0, 25])
    expect(result.quality).toBeCloseTo(100 / 3)
    expect(result.validation?.issues.map(i => i.affectedRows)).toEqual([1, 2, 1])
    expect(result.cellReview?.flatMap(g => g.cells).map(c => c.rowNumber).sort()).toEqual([1, 2, 3, 4])
    expect(result.lastValidatedAt).toBe(checkedAt)
  })
  it('keeps warnings visible without reducing validity', () => {
    const result = run([null, 1], { severity: 'warning' })
    expect(result.qualityDimensions.map(d => d.score)).toEqual([50, 100, null])
    expect(result.status).toBe('needs-review')
  })
  it('ignores only the specified rule finding without inventing completeness', () => {
    const result = validateDataset([{ value: null }], ['value'], ruleset(), new Date(checkedAt), () => true)
    expect(result.validation?.issues).toEqual([])
    expect(result.qualityDimensions.map(d => d.score)).toEqual([0, 100, null])
  })
  it('reports unavailable scores on an empty dataset', () => {
    expect(run([]).quality).toBeNull()
    expect(run([]).qualityDimensions.every(d => d.score === null)).toBe(true)
  })
  it('does not run disabled rules', () => {
    const result = run([null], { enabled: false })
    expect(result.status).toBe('unvalidated')
    expect(result.validation).toEqual({ checksRun: 0, issues: [] })
  })
  it.each([
    [{ type: 'numeric' }, ['1e2', 'bad', null], 1],
    [{ type: 'range', minimum: 1, maximum: 2 }, [0, 1, 2, 3], 2],
    [{ type: 'min', minimum: 1 }, [0, 1, 2], 1],
    [{ type: 'max', maximum: 2 }, [1, 2, 3], 1],
    [{ type: 'allowed', condition: 'A, "B,C"' }, ['A', 'B,C', 'D'], 1],
    [{ type: 'regex', condition: '[A-Z]{2}' }, ['AB', 'abc', 'AB\n'], 2],
  ] as [Partial<QualityRule>, DatasetValue[], number][])('checks %j', (options, values, affected) => {
    expect(run(values, options).validation?.issues[0]?.affectedRows).toBe(affected)
  })
  it.each([
    ['Before selected date', 2], ['On or before selected date', 1],
    ['After selected date', 2], ['On or after selected date', 1], ['Between two selected dates', 1],
  ])('enforces %s boundaries', (condition, count) => {
    const result = run(['2024-02-28', '2024-02-29', '2024-03-01'], { type: 'date', condition, selectedDate: '2024-02-29', endDate: '2024-03-01' })
    expect(result.validation?.issues[0]?.affectedRows).toBe(count)
  })
  it('accepts configured formats and rejects impossible calendar dates', () => {
    const result = run(['29/02/2024', '29/02/2023', '31/04/2024'], { type: 'date', condition: 'Before selected date', selectedDate: '2025-01-01', dateFormats: ['%d/%m/%Y'] })
    expect(result.validation?.issues[0]?.affectedRows).toBe(2)
  })
})

describe('ruleset validation and profiles', () => {
  it.each([
    ruleset([], { name: ' ' }), ruleset([rule(), rule()]), ruleset([rule({ column: 'unknown' })]),
    ruleset([rule({ id: 'DATASET_COLUMNS' })]), ruleset([rule({ type: 'range', minimum: 5, maximum: 1 })]),
    ruleset([rule({ type: 'min', minimum: '' })]), ruleset([rule({ type: 'max', maximum: Infinity })]),
    ruleset([rule({ type: 'date', condition: 'Before selected date', selectedDate: '2023-02-29' })]),
    ruleset([rule({ type: 'date', condition: 'Between two selected dates', selectedDate: '2024-02-02', endDate: '2024-01-01' })]),
    ruleset([rule({ type: 'regex', condition: '(?=x)', enabled: false })]),
  ])('rejects invalid configuration %#', invalid => expect(() => assertValidRuleset(invalid, ['value'])).toThrow())
  it('profiles numeric, date, mixed and missing values', () => {
    const profiles = profileDataset([{ n: 1, d: '2024-01-01', m: 'x', empty: null }, { n: '2.5', d: '2024-03-01', m: 2, empty: '' }], ['n', 'd', 'm', 'empty'], ruleset([]))
    expect(profiles[0]?.summary).toEqual({ kind: 'number-range', minimum: 1, maximum: 2.5 })
    expect(profiles[1]?.summary).toEqual({ kind: 'date-range', minimum: '2024-01-01', maximum: '2024-03-01' })
    expect(profiles[2]?.observedTypes).toEqual(['integer', 'text'])
    expect(profiles[3]).toMatchObject({ missingCount: 2, uniqueCount: 0, summary: { kind: 'top-values', values: [] } })
  })
})
