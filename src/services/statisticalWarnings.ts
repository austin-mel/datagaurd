import type { Finding } from '@/types/backend'

export function countStatisticalWarnings(column: string, findings: readonly Finding[]): number {
  const records = new Set<number>()
  for (const finding of findings) {
    if (finding.category !== 'statistical' || finding.column !== column) continue
    // Use complete record membership, never the capped sample or a sum that
    // could count a cell twice when multiple statistical checks flag it.
    for (const record of finding.affected_record_numbers) records.add(record)
  }
  return records.size
}
