import type { Finding } from '@/types/backend'

// Simulated output from backend services/statistics.py using the seeded rows.
// Defaults: 20 usable values, interpolated quartiles, and fences at 1.5 × IQR.
// Comparative checks have no cell members; only explicit affected records count.
const seededStatisticalFindings: Readonly<Record<string, readonly Finding[]>> = {
  facilities: [{
    rule_id: 'STAT_IQR', column: 'inspection_score', category: 'statistical',
    severity: 'warning', baseline_id: null,
    explanation: 'Values lie outside the configured interquartile fences; review their validity.',
    observed_result: {
      usable_values: 20, q1: 84.75, q3: 92.25, iqr: 7.5,
      lower_fence: 73.5, upper_fence: 103.5, outlier_count: 3,
    },
    threshold: { iqr_multiplier: 1.5, minimum_usable_values: 20, comparison: 'strictly_outside' },
    affected_count: 3, affected_record_numbers: [18, 19, 20],
    record_samples: [
      { record_number: 18, value: '-8' },
      { record_number: 19, value: '108' },
      { record_number: 20, value: '105' },
    ],
  }],
  // Text columns have no numeric outliers; no comparative findings are seeded.
  customers: [],
}

export function getSeededStatisticalFindings(datasetId: string): readonly Finding[] {
  const findings = seededStatisticalFindings[datasetId]
  if (!findings) throw new Error(`No seeded statistical findings for dataset ${datasetId}`)
  return structuredClone(findings)
}
