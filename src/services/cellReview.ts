import type { CellReviewGroup, DatasetRow, DatasetValue, ReviewedCell } from '@/types'

export function displayCellValue(value: DatasetValue): string {
  return value === null ? 'NULL (missing)' : value === '' ? 'Empty string' : String(value)
}

export function groupCellFinding(
  finding: Pick<CellReviewGroup, 'column' | 'ruleId' | 'rule' | 'kind' | 'reason'>,
  rows: readonly DatasetRow[], recordNumbers: Iterable<number>, identifierColumn?: string,
): CellReviewGroup[] {
  const groups = new Map<DatasetValue, Omit<CellReviewGroup, 'cells'> & { cells: ReviewedCell[] }>()
  for (const rowNumber of new Set(recordNumbers)) {
    const row = rows[rowNumber - 1]
    if (!row) continue
    const currentValue = row[finding.column] ?? null
    let group = groups.get(currentValue)
    if (!group) {
      group = { ...finding, id: JSON.stringify([finding.kind, finding.ruleId, finding.column, currentValue]), currentValue, cells: [] }
      groups.set(currentValue, group)
    }
    const identifier = identifierColumn ? row[identifierColumn] : null
    group.cells.push({ rowNumber, identifier: identifier == null || identifier === '' ? null : String(identifier) })
  }
  return [...groups.values()]
}

export function summarizeCellReview(groups: readonly CellReviewGroup[]) {
  const cells = new Set<string>(), rows = new Set<number>()
  const violations = new Set<string>(), warnings = new Set<string>()
  for (const group of groups) for (const cell of group.cells) {
    const key = JSON.stringify([group.column, cell.rowNumber])
    cells.add(key)
    rows.add(cell.rowNumber)
    const bucket = group.kind === 'warning' ? warnings : violations
    bucket.add(key)
  }
  return { cells: cells.size, rows: rows.size, violations: violations.size, warnings: warnings.size }
}
