import type { ColumnProfile, DatasetRow, DatasetRuleset } from '@/types'
import { dateValue, isMissing, numericValue } from './datasetValues'

export function profileDataset(rows: readonly DatasetRow[], columns: readonly string[], ruleset: DatasetRuleset): ColumnProfile[] {
  return columns.map(name => {
    const values = rows.map(row => row[name] ?? null).filter(value => !isMissing(value))
    const frequencies = new Map<string, number>()
    const observed = new Set<ColumnProfile['observedTypes'][number]>()
    const numbers: number[] = [], dates: number[] = []
    const formats = ruleset.rules.find(rule => rule.enabled && rule.column === name && rule.type === 'date')?.dateFormats
    for (const value of values) {
      const text = String(value)
      frequencies.set(text, (frequencies.get(text) ?? 0) + 1)
      const number = numericValue(value), date = dateValue(value, formats)
      if (Number.isFinite(number)) { observed.add(Number.isInteger(number) ? 'integer' : 'number'); numbers.push(number) }
      else if (Number.isFinite(date)) { observed.add('date'); dates.push(date) }
      else observed.add('text')
    }
    const categories = [...frequencies].sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0)).slice(0, 5).map(([value, count]) => ({ value, count }))
    numbers.sort((a, b) => a - b); dates.sort((a, b) => a - b)
    const low = numbers[0], high = numbers.at(-1), first = dates[0], last = dates.at(-1)
    const summary: ColumnProfile['summary'] = [...observed].every(type => type === 'integer' || type === 'number') && low !== undefined && high !== undefined
      ? { kind: 'number-range', minimum: low, maximum: high }
      : observed.size === 1 && first !== undefined && last !== undefined
        ? { kind: 'date-range', minimum: new Date(first).toISOString().slice(0, 10), maximum: new Date(last).toISOString().slice(0, 10) }
        : { kind: 'top-values', values: categories }
    return { name, observedTypes: [...observed].sort(), missingCount: rows.length - values.length, warningCount: null, uniqueCount: frequencies.size, summary }
  })
}

