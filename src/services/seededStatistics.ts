import type { ColumnProfile, DatasetRow, DatasetRuleset } from '../types'
import type { Finding } from '../types/backend'
import { isMissing, numericValue, profileDataset } from './datasetValidation'
import { exceedsPercentage, iqrFences } from './decimalStatistics'

export interface StatisticalBaseline {
  rows: readonly DatasetRow[]
  columns: readonly string[]
  version: string
}

// Local simulation of backend statistics. Every column/row is scanned; no fixture declarations select checks.
export function analyzeSeededStatistics(rows: readonly DatasetRow[], columns: readonly string[], ruleset: DatasetRuleset,
  profiles: readonly ColumnProfile[], baseline?: StatisticalBaseline): Finding[] {
  const settings = ruleset.backendConfiguration?.statistics
  const minimum = settings?.statistical_min_samples ?? 20, multiplier = settings?.iqr_multiplier ?? 1.5
  const missingThreshold = settings?.missingness_increase_percentage_points ?? 5
  const rowThreshold = settings?.row_count_change_percentage ?? 20
  const categoryThreshold = settings?.category_share_change_percentage_points ?? 10
  const findings: Finding[] = []
  const previous = new Map((baseline ? profileDataset(baseline.rows, baseline.columns, ruleset) : []).map(profile => [profile.name, profile]))
  const normalizedTypes = (profile: ColumnProfile) => [...new Set(profile.observedTypes.map(type => type === 'integer' ? 'number' : type))].sort()
  const incompatible = profiles.filter(profile => {
    const old = previous.get(profile.name), currentTypes = normalizedTypes(profile)
    return old && currentTypes.length && normalizedTypes(old).length && JSON.stringify(currentTypes) !== JSON.stringify(normalizedTypes(old))
  }).map(profile => profile.name)
  const emit = (rule_id: string, column: string | null, explanation: string, observed_result: Finding['observed_result'],
    threshold: Finding['threshold'], members: number[] = [], category: Finding['category'] = 'statistical') => {
    findings.push({ rule_id, column, explanation, observed_result, threshold, category, severity: 'warning',
      baseline_id: rule_id === 'STAT_IQR' ? null : baseline?.version ?? null,
      affected_count: members.length, affected_record_numbers: members,
      record_samples: members.slice(0, 20).map(record_number => ({ record_number, value: String(column ? rows[record_number - 1]?.[column] ?? '' : '') })),
    })
  }
  if (baseline) {
    const added = columns.filter(name => !baseline.columns.includes(name)).sort()
    const removed = baseline.columns.filter(name => !columns.includes(name)).sort()
    const required = ruleset.backendConfiguration?.required_columns ?? columns
    if (added.length || removed.some(name => !required.includes(name)) || incompatible.length) {
      emit('SCHEMA_COLUMNS', null, 'Dataset columns or observed value types changed.',
        { added_columns: added, removed_columns: removed, incompatible_columns: incompatible.sort().map(column => ({
          column, baseline_types: normalizedTypes(previous.get(column)!), current_types: normalizedTypes(profiles.find(profile => profile.name === column)!),
        })) }, { compatible_types_required: true, required_columns: [...required] }, [], 'schema')
    }
    const oldRows = baseline.rows.length
    if (exceedsPercentage(Math.abs(rows.length - oldRows), oldRows, rowThreshold)) {
      emit('STAT_ROW_COUNT', null, 'The record count changed beyond the configured threshold.',
        { baseline_rows: oldRows, current_rows: rows.length, change_percentage: 100 * Math.abs(rows.length - oldRows) / oldRows },
        { change_percentage: rowThreshold, comparison: 'strictly_greater' })
    }
  }
  for (const column of columns) {
    const profile = profiles.find(item => item.name === column)
    if (!profile) continue
    const numbers = rows.flatMap((row, index) => {
      const value = numericValue(row[column] ?? null)
      return Number.isFinite(value) ? [{ value, rowNumber: index + 1 }] : []
    })
    if (numbers.length >= minimum) {
      const ordered = numbers.map(item => item.value).sort((a, b) => a - b)
      const fences = iqrFences(ordered, multiplier)
      const { q1, q3, iqr, lower, upper } = fences
      if (fences.hasSpread && [iqr, lower, upper].every(Number.isFinite)) {
        const members = numbers.filter(item => fences.isOutside(item.value)).map(item => item.rowNumber)
        if (members.length) emit('STAT_IQR', column, 'Values lie outside the configured interquartile fences; review their validity.',
          { usable_values: numbers.length, q1, q3, iqr, lower_fence: lower, upper_fence: upper, outlier_count: members.length },
          { iqr_multiplier: multiplier, minimum_usable_values: minimum, comparison: 'strictly_outside' }, members)
      }
    }
    const old = previous.get(column)
    if (!baseline || !old || incompatible.includes(column)) continue
    const oldRows = baseline.rows.length, newRows = rows.length
    const missingNumerator = profile.missingCount * oldRows - old.missingCount * newRows
    if (Math.min(oldRows, newRows) >= minimum && exceedsPercentage(missingNumerator, oldRows * newRows, missingThreshold)) {
      emit('STAT_MISSINGNESS', column, 'The missing-value percentage increased beyond the configured threshold.',
        { baseline_missing: old.missingCount, current_missing: profile.missingCount, baseline_rows: oldRows, current_rows: newRows,
          increase_percentage_points: 100 * missingNumerator / (oldRows * newRows) },
        { increase_percentage_points: missingThreshold, minimum_records_per_version: minimum, comparison: 'strictly_greater' })
    }
    const newCount = newRows - profile.missingCount, oldCount = oldRows - old.missingCount
    if (JSON.stringify(normalizedTypes(profile)) !== '["text"]' || JSON.stringify(normalizedTypes(old)) !== '["text"]'
      || Math.min(newCount, oldCount) < minimum) continue
    const frequencies = (data: readonly DatasetRow[]) => {
      const counts = new Map<string, number>()
      for (const row of data) {
        const value = row[column]
        if (!isMissing(value)) counts.set(String(value), (counts.get(String(value)) ?? 0) + 1)
      }
      return counts
    }
    const currentCounts = frequencies(rows), oldCounts = frequencies(baseline.rows)
    let largest: string | undefined, difference = -1
    for (const value of [...new Set([...currentCounts.keys(), ...oldCounts.keys()])].sort()) {
      const delta = Math.abs((currentCounts.get(value) ?? 0) * oldCount - (oldCounts.get(value) ?? 0) * newCount)
      if (delta > difference) { largest = value; difference = delta }
    }
    if (largest !== undefined && exceedsPercentage(difference, newCount * oldCount, categoryThreshold)) {
      emit('STAT_CATEGORY_MIX', column, 'The category distribution changed beyond the configured threshold.',
        { current_nonmissing: newCount, baseline_nonmissing: oldCount, category: largest,
          baseline_count: oldCounts.get(largest) ?? 0, current_count: currentCounts.get(largest) ?? 0,
          maximum_change_percentage_points: 100 * difference / (newCount * oldCount) },
        { share_change_percentage_points: categoryThreshold, minimum_nonmissing_per_version: minimum, comparison: 'strictly_greater' })
    }
  }
  return findings
}
