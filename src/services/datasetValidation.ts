import type { Dataset, DatasetRow, DatasetRuleset, QualityRule, QualityDimension, ValidationIssue } from '@/types'
import { groupCellFinding } from './cellReview'
import { resolveIdentifier } from './identifiers'
import { assertValidRuleset, prepareRule } from './rulesetValidation'
import { isMissing } from './datasetValues'
import { profileDataset } from './datasetProfiling'

const qualityNote = 'Scores count each row once. Completeness: every cell present. Validity: no rule errors. Uniqueness: present, unique values in every enabled unique column. Overall is the mean of available scores.'
type ValidationResult = Pick<Dataset, 'validation' | 'quality' | 'qualityDimensions' | 'qualityNote' | 'status' | 'lastValidatedAt' | 'processingStatus' | 'rulesChangedSinceRun' | 'validationPending' | 'columnProfiles' | 'cellReview'>

export function validateDataset(input: Iterable<DatasetRow>, columns: readonly string[], ruleset: DatasetRuleset, validatedAt: Date,
  isIgnored: (rowIndex: number, rule: QualityRule) => boolean = () => false,
): ValidationResult {
  assertValidRuleset(ruleset, columns)
  const rows = [...input]
  const checks = ruleset.rules.filter(rule => rule.enabled).map(rule => ({
    rule, passes: prepareRule(rule), affected: new Set<number>(), frequencies: new Map<string, number>(),
  }))
  for (const check of checks) {
    if (check.rule.type === 'unique') for (const row of rows) {
      const value = row[check.rule.column] ?? null
      if (!isMissing(value)) check.frequencies.set(String(value), (check.frequencies.get(String(value)) ?? 0) + 1)
    }
  }
  const invalid = new Set<number>(), nonunique = new Set<number>()
  let complete = 0
  rows.forEach((row, index) => {
    if (columns.every(column => !isMissing(row[column]))) complete++
    for (const check of checks) {
      if (isIgnored(index, check.rule)) continue
      const value = row[check.rule.column] ?? null
      const missing = isMissing(value)
      if (check.rule.type === 'unique' && (missing || check.frequencies.get(String(value)) !== 1)) nonunique.add(index)
      if (check.rule.type !== 'required' && missing) continue
      if (check.rule.type === 'unique' ? check.frequencies.get(String(value)) !== 1 : !check.passes(value)) {
        check.affected.add(index)
        if (check.rule.severity !== 'warning') invalid.add(index)
      }
    }
  })
  const issues: ValidationIssue[] = checks.filter(check => check.affected.size).map(check => ({
    id: check.rule.id, column: check.rule.column, rule: check.rule.type,
    message: check.rule.column + ' failed ' + check.rule.type + (check.rule.condition ? ': ' + check.rule.condition : '')
      + (check.rule.type === 'date' ? ' (' + check.rule.selectedDate
        + (check.rule.condition === 'Between two selected dates' ? ' – ' + check.rule.endDate : '') + ')' : '') + '.',
    affectedRows: check.affected.size,
  }))
  const dimension = (id: string, label: string, passed: number, description: string, available = true): QualityDimension => ({
    id, label, score: available && rows.length ? 100 * passed / rows.length : null,
    passed: available ? passed : null, total: available ? rows.length : null,
    description: available ? description : 'No enabled uniqueness rules',
  })
  const qualityDimensions = [
    dimension('completeness', 'Completeness', complete, 'rows with no missing cells'),
    dimension('validity', 'Validity', rows.length - invalid.size, 'rows without rule errors'),
    dimension('uniqueness', 'Uniqueness', rows.length - nonunique.size, 'rows unique in all tagged columns', checks.some(check => check.rule.type === 'unique')),
  ]
  const scores = qualityDimensions.flatMap(item => item.score === null ? [] : [item.score])
  const identifierColumn = resolveIdentifier(ruleset, columns).column ?? undefined
  const cellReview = checks.flatMap(check => {
    const issue = issues.find(item => item.id === check.rule.id)
    return issue ? groupCellFinding({ column: issue.column, ruleId: issue.id, rule: issue.rule,
      kind: 'violation', reason: issue.message }, rows, [...check.affected].map(index => index + 1), identifierColumn) : []
  })
  return {
    cellReview,
    validation: { checksRun: checks.length, issues },
    quality: scores.length ? scores.reduce((sum, score) => sum + score, 0) / scores.length : null,
    qualityDimensions, qualityNote,
    status: !checks.length ? 'unvalidated' : issues.length ? 'needs-review' : 'healthy',
    processingStatus: 'completed', rulesChangedSinceRun: false, validationPending: false,
    lastValidatedAt: validatedAt.toISOString(), columnProfiles: profileDataset(rows, columns, ruleset),
  }
}

