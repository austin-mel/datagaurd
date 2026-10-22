import type { Dataset } from '@/types'
import { validateDataset } from './datasetValidation'
import { countStatisticalWarnings } from './statisticalWarnings'
import { groupCellFinding } from './cellReview'
import { analyzeSeededStatistics, type StatisticalBaseline } from './seededStatistics'
import { resolveIdentifier } from './identifiers'
import { ignoreKey, ruleSignatures, type SessionData } from './seededSession'

export function validateSeededDataset(record: Pick<Dataset, 'id' | 'columns' | 'ruleset'>, data: SessionData, validatedAt: Date, baseline?: StatisticalBaseline) {
  const rows = data.rows.map(row => row.values), signatures = ruleSignatures(record.ruleset)
  const report = validateDataset(rows, record.columns, record.ruleset, validatedAt, (index, rule) => {
    if (!data.ignored.size) return false
    const row = data.rows[index]
    return !!row && data.ignored.has(ignoreKey(row, rule.column, 'violation', rule.id, signatures.get(rule.id)))
  })
  const findings = analyzeSeededStatistics(rows, record.columns, record.ruleset, report.columnProfiles ?? [], baseline).flatMap(finding => {
    if (finding.column === null || !finding.affected_record_numbers.length) return [finding]
    const column = finding.column
    const members = finding.affected_record_numbers.filter(number => {
      const row = data.rows[number - 1]
      return row && !data.ignored.has(ignoreKey(row, column, 'warning', finding.rule_id))
    })
    return members.length ? [{ ...finding, affected_count: members.length, affected_record_numbers: members,
      record_samples: finding.record_samples.filter(sample => members.includes(sample.record_number)) }] : []
  })
  const identifierColumn = resolveIdentifier(record.ruleset, record.columns).column ?? undefined
  report.cellReview = [...(report.cellReview ?? []), ...findings.flatMap(finding => finding.column === null ? [] :
    groupCellFinding({ column: finding.column, ruleId: finding.rule_id, rule: finding.rule_id,
      kind: 'warning', reason: finding.explanation }, rows, finding.affected_record_numbers, identifierColumn))]
  report.columnProfiles = report.columnProfiles?.map(profile => ({
    ...profile, warningCount: countStatisticalWarnings(profile.name, findings),
  })) ?? null
  if (findings.length) report.status = 'needs-review'
  const globalWarnings = findings.filter(finding => !finding.affected_record_numbers.length)
  if (globalWarnings.length) report.qualityNote += ' Dataset warnings: ' + [...new Set(globalWarnings.map(finding => finding.explanation))].join(' ')
  if (data.ignored.size) report.qualityNote += ' Ignored rule findings are excluded from error counts; completeness still reflects actual missing cells.'
  return report
}

