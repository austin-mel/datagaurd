import type { DatasetValue, QualityRule } from '@/types'

export function isMissing(value: DatasetValue | undefined): boolean {
  return value === null || value === undefined || (typeof value === 'string' && !value.trim())
}
export function numericValue(value: DatasetValue): number {
  if (typeof value === 'number') return value
  if (typeof value !== 'string' || !/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(value.trim())) return NaN
  return Number(value)
}
export function dateValue(value: DatasetValue, formats: QualityRule['dateFormats'] = ['%Y-%m-%d']): number {
  if (typeof value !== 'string') return NaN
  for (const format of formats) {
    const match = value.trim().match(format === '%Y-%m-%d' ? /^(\d{4})-(\d{2})-(\d{2})$/ : /^(\d{2})\/(\d{2})\/(\d{4})$/)
    if (!match) continue
    const [, a, b, c] = match
    const iso = format === '%Y-%m-%d' ? value.trim() : format === '%m/%d/%Y' ? c + '-' + a + '-' + b : c + '-' + b + '-' + a
    const day = new Date(iso + 'T00:00:00Z')
    if (Number.isFinite(day.getTime()) && day.getUTCFullYear() >= 1 && day.toISOString().slice(0, 10) === iso) return day.getTime()
  }
  return NaN
}
