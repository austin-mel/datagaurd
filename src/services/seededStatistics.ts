import { getSeededStatisticalFindings } from '@/data/statisticalFindings'
import type { DatasetRow } from '@/types'
import type { Finding } from '@/types/backend'
import { numericValue } from './datasetValidation'

// Refresh the seeded IQR checks after local edits, using the backend's
// interpolated quartiles and the settings carried by each seeded finding.
// This is a local simulation; it does not call a backend.
export function analyzeSeededStatistics(datasetId: string, rows: readonly DatasetRow[]): Finding[] {
  return getSeededStatisticalFindings(datasetId).flatMap(finding => {
    if (finding.rule_id !== 'STAT_IQR' || finding.column === null) return []
    const { minimum_usable_values: minimum, iqr_multiplier: multiplier } = finding.threshold
    if (typeof minimum !== 'number' || typeof multiplier !== 'number') return []
    const column = finding.column
    const numbers = rows.flatMap((row, index) => {
      const value = numericValue(row[column] ?? null)
      return Number.isFinite(value) ? [{ value, rowNumber: index + 1 }] : []
    })
    if (numbers.length < minimum) return []
    const ordered = numbers.map(item => item.value).sort((a, b) => a - b)
    const quartile = (quarter: number) => {
      const position = (ordered.length - 1) * quarter / 4, index = Math.floor(position)
      const left = ordered[index] ?? 0, right = ordered[Math.min(index + 1, ordered.length - 1)] ?? left
      return left + (right - left) * (position - index)
    }
    const q1 = quartile(1), q3 = quartile(3), iqr = q3 - q1
    const lower = q1 - multiplier * iqr, upper = q3 + multiplier * iqr
    if (!iqr || !Number.isFinite(lower) || !Number.isFinite(upper)) return []
    const members = numbers.filter(item => item.value < lower || item.value > upper).map(item => item.rowNumber)
    if (!members.length) return []
    return [{ ...finding,
      observed_result: { usable_values: numbers.length, q1, q3, iqr, lower_fence: lower, upper_fence: upper, outlier_count: members.length },
      affected_count: members.length, affected_record_numbers: members,
      record_samples: members.slice(0, 20).map(record_number => ({ record_number, value: String(rows[record_number - 1]?.[column] ?? '') })),
    }]
  })
}
