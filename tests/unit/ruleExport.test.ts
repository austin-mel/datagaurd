import { expect, it } from 'vitest'
import { rulesToBackend } from '@/services'
import { createDefaultRules } from '@/data'
import { rule, ruleset } from '../fixtures/workspace'

it('exports every editor rule type for backend seeding', () => {
  const source = ruleset([
    rule(), rule({ id: 'UNIQUE', type: 'unique' }), rule({ id: 'NUMERIC', type: 'numeric' }),
    rule({ id: 'REGEX', type: 'regex', condition: '[A-Z]+' }), rule({ id: 'ALLOWED', type: 'allowed', condition: 'A, "B,C"' }),
    rule({ id: 'RANGE', type: 'range', minimum: 1, maximum: 5 }), rule({ id: 'MINIMUM', type: 'min', minimum: 2 }), rule({ id: 'MAXIMUM', type: 'max', maximum: 10 }),
    ...['On or before selected date', 'Before selected date', 'After selected date', 'On or after selected date', 'Between two selected dates'].map((condition, i) => rule({ id: `DATE_${i}`, type: 'date', condition, selectedDate: '2024-01-01', endDate: '2025-01-01' })),
  ])
  const configuration = rulesToBackend(source, ['value'])
  expect(configuration.rules).toMatchObject([
    { id: 'VALUE_REQUIRED', kind: 'required' }, { id: 'UNIQUE', kind: 'unique' }, { id: 'NUMERIC', kind: 'numeric' },
    { id: 'REGEX', kind: 'pattern', pattern: '[A-Z]+' }, { id: 'ALLOWED', kind: 'allowed_values', values: ['A', 'B,C'] },
    { id: 'RANGE_PARSE', kind: 'numeric', generated_for: 'RANGE' },
    { id: 'RANGE', kind: 'range', minimum: 1, maximum: 5, prerequisite: 'RANGE_PARSE' },
    { id: 'MINIMUM_PARSE', kind: 'numeric', generated_for: 'MINIMUM' },
    { id: 'MINIMUM', kind: 'min', minimum: 2, prerequisite: 'MINIMUM_PARSE' },
    { id: 'MAXIMUM_PARSE', kind: 'numeric', generated_for: 'MAXIMUM' },
    { id: 'MAXIMUM', kind: 'max', maximum: 10, prerequisite: 'MAXIMUM_PARSE' },
    { id: 'DATE_0', kind: 'on_or_before_date', date: '2024-01-01', formats: ['%Y-%m-%d'] },
    { id: 'DATE_1', kind: 'before_date', date: '2024-01-01' },
    { id: 'DATE_2', kind: 'after_date', date: '2024-01-01' },
    { id: 'DATE_3', kind: 'on_or_after_date', date: '2024-01-01' },
    { id: 'DATE_4', kind: 'between_dates', start_date: '2024-01-01', end_date: '2025-01-01' },
  ])
})

it('normalizes UI IDs and avoids prerequisite collisions', () => {
  const result = rulesToBackend(ruleset([rule({ id: 'lower-case' }), rule({ id: 'MIN', type: 'min' }), rule({ id: 'MIN_PARSE' })]), ['value'])
  expect(result.rules.map(r => r.id)).toEqual(['UI_0_LOWER_CASE', 'MIN_PARSE_P', 'MIN', 'MIN_PARSE'])
  expect(result.required_columns).toEqual(['value'])
})

it('protects default rulesets from writes', () => {
  expect(() => rulesToBackend(ruleset([], { kind: 'default' }), [])).toThrow(/custom/)
})

it('retains automatic identifier policy without persisting generated UI checks', () => {
  const automaticRules = createDefaultRules('id').map(check => ({
    ...check, id: check.type === 'required' ? 'GENERIC_ID_REQUIRED' : 'GENERIC_ID_UNIQUE',
  }))
  const editor = ruleset([rule(), ...automaticRules], {
    backendConfiguration: { schema_version: 1, name: 'Automatic checks', structural_rule_id: 'COLUMNS',
      identifier_policy: 'auto', required_columns: ['value'], rules: [] },
  })
  const configuration = rulesToBackend(editor, ['id', 'value'])
  expect(configuration.identifier_policy).toBe('auto')
  expect(configuration.rules.map(r => r.id)).toEqual(['VALUE_REQUIRED'])
  expect(configuration.required_columns).toEqual(['value'])
})
